import json
import logging
from typing import Optional, Dict, Any, Tuple

from fastapi import APIRouter, Request, HTTPException

from .base_proxy import (
  base_proxy_request,
  ConfigManager,
  KeyManager,
  ProxyError
)
from .... import crud
from ....core.config import settings
from ....core.security import db_dependency

logger = logging.getLogger(__name__)

router = APIRouter(prefix=settings.GEMINI_PURE_PROXY_PREFIX, tags=["Gemini Pure Proxy"])

# 配置缓存，避免重复查询数据库
_config_cache: Dict[str, Any] = {}
_cache_timestamp = 0
CACHE_TTL = 300  # 5分钟缓存过期时间


def _get_cached_configs(db: db_dependency) -> Tuple[Optional[str], Optional[str]]:
  """获取缓存的配置，减少数据库查询"""
  global _config_cache, _cache_timestamp
  import time

  current_time = time.time()

  # 检查缓存是否过期
  if current_time - _cache_timestamp > CACHE_TTL:
    try:
      # 批量查询配置
      target_config = crud.config.get_config_by_key(db, "target_api_url")
      api_token_config = crud.config.get_config_by_key(db, "api_token")

      _config_cache = {
        "target_api_url": target_config.value if target_config else None,
        "api_token": api_token_config.value if api_token_config else None
      }
      _cache_timestamp = current_time
      logger.debug("Configuration cache refreshed")
    except Exception as e:
      logger.error(f"Failed to refresh configuration cache: {e}")
      # 如果缓存刷新失败，保持原有缓存或返回None
      if not _config_cache:
        return None, None

  return _config_cache.get("target_api_url"), _config_cache.get("api_token")


def _extract_stream_parameter(body: bytes) -> Tuple[bool, Optional[Dict[str, Any]]]:
  """安全地解析请求体中的stream参数"""
  if not body:
    return False, None

  try:
    request_data = json.loads(body)
    if not isinstance(request_data, dict):
      logger.warning("Request body is not a JSON object")
      return False, request_data

    stream_value = request_data.get("stream")
    if stream_value is None:
      return False, request_data

    if isinstance(stream_value, bool):
      logger.debug(f"Stream parameter found in request body: {stream_value}")
      return stream_value, request_data
    else:
      logger.warning(f"Invalid stream parameter type: {type(stream_value)}, expected bool")
      return False, request_data

  except json.JSONDecodeError as e:
    logger.warning(f"Failed to decode JSON request body: {e}")
    return False, None
  except Exception as e:
    logger.error(f"Unexpected error parsing request body: {e}", exc_info=True)
    return False, None


def _get_api_key_from_request(request: Request) -> Optional[str]:
  """从请求中提取API密钥，支持多种方式"""
  # 优先从header获取
  api_key = request.headers.get("x-goog-api-key")
  if api_key:
    logger.debug("API key found in x-goog-api-key header")
    return api_key

  # 从查询参数获取
  api_key = request.query_params.get("key")
  if api_key:
    logger.debug("API key found in query parameters")
    return api_key

  logger.warning("API key not found in headers or query parameters")
  return None


@router.api_route(
  "/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"]
)
async def gemini_pure_proxy_request(path: str, request: Request, db: db_dependency):
  """
  Gemini纯代理请求处理

  优化要点：
  1. 配置缓存减少数据库查询
  2. 统一的错误处理
  3. 请求体一次性读取避免重复
  4. 更健壮的参数解析
  """
  # 1. 验证请求路径
  if not request.url.path.startswith(settings.GEMINI_PURE_PROXY_PREFIX):
    logger.warning(f"Invalid request path: {request.url.path}")
    raise HTTPException(status_code=404, detail="Not Found")

  logger.info(f"Processing Gemini proxy request: path='{path}', method='{request.method}'")

  try:
    # 2. 获取配置使用ConfigManager
    target_api_url = ConfigManager.get_target_url(db)
    api_token = ConfigManager.get_internal_api_token(db)

    # 3. 构建目标URL
    target_url = target_api_url.rstrip("/")
    full_target_url = f"{target_url}/{path}"
    logger.debug(f"Target URL: {full_target_url}")

    # 4. 确定是否为流式请求
    stream = False
    cached_body = None

    # 检查查询参数中的alt=sse
    if request.query_params.get("alt") == "sse":
      stream = True
      logger.debug("Streaming enabled via 'alt=sse' query parameter")
    else:
      # 读取请求体一次，避免重复读取
      body = await request.body()
      if body:
        stream, cached_body = _extract_stream_parameter(body)

    # 5. 验证内部API密钥
    internal_api_key = _get_api_key_from_request(request)

    if not internal_api_key or internal_api_key != api_token:
      logger.warning("Invalid or missing internal API key")
      raise HTTPException(
        status_code=401,
        detail="Invalid or missing internal API key."
      )

    # 6. 获取目标API密钥使用KeyManager
    target_api_key_obj = KeyManager.get_active_api_key(db)

    # 7. 准备查询参数（移除内部key）
    query_params_to_send = dict(request.query_params)
    query_params_to_send.pop("key", None)

    # 8. 调用基础代理
    response = await base_proxy_request(
      request=request,
      db=db,
      full_target_url=full_target_url,
      stream=stream,
      skip_token_validation=True,
      params=query_params_to_send,
      api_key_header_name="x-goog-api-key",
      selected_key_obj=target_api_key_obj,
    )

    return response

  except ProxyError as pe:
    # 处理ProxyError，转换为HTTPException
    raise HTTPException(status_code=pe.status_code, detail=pe.detail)
  except HTTPException:
    # 重新抛出HTTP异常，保持原有状态码
    raise
  except Exception as e:
    logger.error(f"Unexpected error in gemini_pure_proxy_request: {e}", exc_info=True)
    raise HTTPException(
      status_code=500,
      detail="Internal server error occurred while processing the request."
    )
