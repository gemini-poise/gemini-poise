import asyncio
import json
import logging
import random
from typing import Optional, Dict, Any, Tuple

from fastapi import APIRouter, Request, HTTPException

from .base_proxy import (
  base_proxy_request,
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

# 重试配置
INITIAL_RETRY_DELAY = 0.1  # 初始重试延迟（秒）
MAX_RETRY_DELAY = 1.0  # 最大重试延迟（秒）
RETRY_BACKOFF_FACTOR = 1.5  # 指数退避因子


def _get_cached_configs(db: db_dependency) -> Tuple[Optional[str], Optional[str], Optional[int]]:
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
      retry_count_config = crud.config.get_config_by_key(db, "proxy_retry_max_count")

      _config_cache = {
        "target_api_url": target_config.value if target_config else None,
        "api_token": api_token_config.value if api_token_config else None,
        "proxy_retry_max_count": int(retry_count_config.value) if retry_count_config and retry_count_config.value else 3
      }
      _cache_timestamp = current_time
      logger.debug("Configuration cache refreshed")
    except Exception as e:
      logger.error(f"Failed to refresh configuration cache: {e}")
      # 如果缓存刷新失败，保持原有缓存或返回默认值
      if not _config_cache:
        return None, None, 3

  return (
    _config_cache.get("target_api_url"),
    _config_cache.get("api_token"),
    _config_cache.get("proxy_retry_max_count", 3)
  )


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


def _is_retryable_error(exception: Exception) -> bool:
  """判断异常是否可以重试"""
  if isinstance(exception, HTTPException):
    # 4xx和5xx错误都可以重试（除了400参数错误，因为换key无法解决参数问题）
    return exception.status_code >= 400 and exception.status_code != 400

  if isinstance(exception, ProxyError):
    # 基于ProxyError的状态码判断，4xx和5xx都可以重试（除了400）
    return exception.status_code >= 400 and exception.status_code != 400

  # 网络相关错误通常可以重试
  error_types = (
    ConnectionError,
    TimeoutError,
    OSError,  # 包括网络相关的OSError
  )

  return isinstance(exception, error_types)


async def _calculate_retry_delay(attempt: int) -> float:
  """计算重试延迟时间，使用指数退避和抖动"""
  base_delay = min(
    INITIAL_RETRY_DELAY * (RETRY_BACKOFF_FACTOR ** attempt),
    MAX_RETRY_DELAY
  )

  # 添加随机抖动，避免所有重试同时发生
  jitter = random.uniform(0.1, 0.3) * base_delay
  delay = base_delay + jitter

  logger.debug(f"Retry attempt {attempt + 1}, delay: {delay:.2f}s")
  return delay


def _get_api_key_from_request(request: Request) -> Optional[str]:
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


async def _execute_proxy_request_with_retry(
  request: Request,
  db: db_dependency,
  full_target_url: str,
  stream: bool,
  query_params_to_send: Dict[str, Any],
  max_retries: int = 3
) -> Any:
  """执行带重试的代理请求，每次重试使用新的API密钥"""
  last_exception = None
  # 总尝试次数 = 1次原始请求 + max_retries次重试
  total_attempts = max_retries + 1

  # Log retry configuration at start
  logger.info(f"Starting proxy request execution, max retries: {max_retries}, total attempts: {total_attempts}")

  for attempt in range(total_attempts):
    try:
      # Determine if this is a retry
      if attempt == 0:
        logger.info(f"Executing initial request (attempt {attempt + 1}/{total_attempts})")
      else:
        logger.info(f"Executing retry request (retry {attempt}/{max_retries}, total attempt {attempt + 1}/{total_attempts})")

      logger.debug(f"Proxy request attempt {attempt + 1}/{total_attempts}")

      # 每次尝试都获取新的API密钥
      current_api_key_obj = KeyManager.get_active_api_key(db)
      if current_api_key_obj:
        logger.debug(f"Using API key for attempt {attempt + 1}: {current_api_key_obj.key_name if hasattr(current_api_key_obj, 'key_name') else 'unnamed'}")

      response = await base_proxy_request(
        request=request,
        db=db,
        full_target_url=full_target_url,
        stream=stream,
        skip_token_validation=True,
        params=query_params_to_send,
        api_key_header_name="x-goog-api-key",
        selected_key_obj=current_api_key_obj,
      )

      # 请求成功，返回响应
      if attempt == 0:
        logger.info(f"✅ Proxy request succeeded (initial request successful, no retries needed)")
      else:
        logger.info(f"✅ Proxy request retry succeeded (succeeded after {attempt} retries, total {attempt + 1} attempts)")

      return response

    except Exception as e:
      last_exception = e

      # Determine if this is a retry failure
      if attempt == 0:
        logger.warning(f"❌ Initial request failed (attempt {attempt + 1}/{total_attempts}): {str(e)}")
      else:
        logger.warning(f"❌ Retry request failed (retry {attempt}/{max_retries}, total attempt {attempt + 1}/{total_attempts}): {str(e)}")

      # 判断是否可以重试
      if not _is_retryable_error(e):
        logger.info(f"🚫 Error is not retryable, throwing exception directly: {type(e).__name__}")
        raise e

      # 如果这是最后一次尝试，不再重试
      if attempt == total_attempts - 1:
        logger.error(f"💥 All attempts failed (initial request + {max_retries} retries = {total_attempts} total attempts all failed)")
        break

      # 计算延迟时间并等待
      delay = await _calculate_retry_delay(attempt)
      logger.info(f"⏳ Preparing retry {attempt + 1}/{max_retries}, will retry with new API key after {delay:.2f} seconds...")
      await asyncio.sleep(delay)

  # 所有重试都失败，抛出最后一个异常
  logger.error(f"🔥 Retry mechanism completed, all {total_attempts} attempts failed, throwing last exception")
  if last_exception:
    raise last_exception


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
    # 2. 获取缓存的配置
    target_api_url, api_token, retry_count = _get_cached_configs(db)

    if not target_api_url:
      raise HTTPException(status_code=503, detail="目标 Gemini API URL 未配置，请在配置表中添加 'target_api_url'。")
    if not api_token:
      raise HTTPException(status_code=503, detail="内部 API 令牌未配置。")

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

    # 6. 准备查询参数（移除内部key）
    query_params_to_send = dict(request.query_params)
    query_params_to_send.pop("key", None)

    # 7. 调用带重试的基础代理，使用缓存的重试次数
    # API密钥将在重试函数内部动态获取
    response = await _execute_proxy_request_with_retry(
      request=request,
      db=db,
      full_target_url=full_target_url,
      stream=stream,
      query_params_to_send=query_params_to_send,
      max_retries=retry_count
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
