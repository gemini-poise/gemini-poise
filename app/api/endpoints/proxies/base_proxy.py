import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Optional, Dict

import httpx
from fastapi import Request, HTTPException, status
from fastapi.responses import StreamingResponse, Response
from sqlalchemy.orm import Session

from .... import crud
from ....models.models import ApiCallLog

logger = logging.getLogger(__name__)

# 线程池用于异步处理缓存失效等非关键操作
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="proxy_bg_")

# 公共常量
DEFAULT_TIMEOUT = 60.0
DEFAULT_MAX_FAILED_COUNT = 3
DEFAULT_TEMPERATURE = 0.7
DEFAULT_TOP_P = 0.95
DEFAULT_TOP_K = 40
FALLBACK_MODEL = "gemini-1.5-flash"
CHUNK_SIZE = 8192


class ProxyError(Exception):
  """代理处理异常基类"""

  def __init__(self, status_code: int, detail: str, original_error: Optional[Exception] = None):
    self.status_code = status_code
    self.detail = detail
    self.original_error = original_error
    super().__init__(detail)


class ConfigManager:
  """配置管理器 - 统一处理各种配置获取"""

  @staticmethod
  def get_target_url(db) -> str:
    """获取目标 API URL"""
    config = crud.config.get_config_by_key(db, "target_api_url")
    if not config or not config.value:
      raise ProxyError(503, "目标 Gemini API URL 未配置，请在配置表中添加 'target_api_url'。")
    return config.value.rstrip("/")

  @staticmethod
  def get_internal_api_token(db) -> str:
    """获取内部 API 令牌"""
    config = crud.config.get_config_by_key(db, "api_token")
    if not config or not config.value:
      raise ProxyError(503, "内部 API 令牌未配置。")
    return config.value

  @staticmethod
  def get_max_failed_count(db) -> int:
    """获取最大失败次数配置"""
    config_str = crud.config.get_config_value(db, "key_validation_max_failed_count")
    if not config_str:
      return DEFAULT_MAX_FAILED_COUNT
    try:
      count = int(config_str)
      return count if count >= 0 else DEFAULT_MAX_FAILED_COUNT
    except ValueError:
      logger.warning(f"Invalid max failed count format '{config_str}', using default {DEFAULT_MAX_FAILED_COUNT}")
      return DEFAULT_MAX_FAILED_COUNT


class AuthValidator:
  """认证验证器 - 统一处理各种认证验证"""

  @staticmethod
  def validate_internal_api_key(request: Request, expected_token: str) -> None:
    """验证内部 API 密钥"""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
      raise ProxyError(401, "无效或缺失的内部 API 密钥。")

    api_key = auth_header.replace("Bearer ", "")
    if not api_key or api_key != expected_token:
      raise ProxyError(401, "无效或缺失的内部 API 密钥。")


class KeyManager:
  """API 密钥管理器 - 统一处理API密钥相关操作"""

  @staticmethod
  def get_active_api_key(db):
    """获取活跃的API密钥"""
    try:
      api_key = crud.api_keys.get_active_api_key_with_token_bucket(db)
      if not api_key:
        raise ProxyError(503, "没有可用的活跃目标 API 密钥。")
      return api_key
    except Exception as e:
      logger.error(f"获取活跃API密钥失败: {e}")
      raise ProxyError(503, "获取API密钥配置失败。")

  @staticmethod
  def update_key_usage(db, api_key, success: bool, status_override: str = None) -> None:
    """更新密钥使用状态"""
    try:
      max_failed_count = ConfigManager.get_max_failed_count(db)
      update_key_status_based_on_response(db, api_key, success, max_failed_count, status_override)
      record_api_call_log(db, api_key.id)
    except Exception as e:
      logger.error(f"更新密钥使用状态失败: {e}")


def _clean_response_headers(headers: Dict) -> Dict:
  """清理响应头，移除不需要的header"""
  cleaned_headers = dict(headers)
  # 移除可能导致问题的header
  headers_to_remove = [
    "content-encoding",
    "content-length",
    "transfer-encoding",
    "connection",
    "keep-alive"
  ]

  for header in headers_to_remove:
    cleaned_headers.pop(header, None)

  return cleaned_headers


def _async_invalidate_cache():
  """异步执行缓存失效操作"""
  try:
    from ....crud.api_keys import invalidate_active_api_keys_cache
    invalidate_active_api_keys_cache()
    logger.debug("🔄 [CACHE] Cache invalidated successfully")
  except Exception as e:
    logger.warning(f"⚠️ [CACHE] Failed to invalidate cache: {e}")


# 优化的 httpx 客户端配置，使用连接池和超时配置
httpx_client = httpx.AsyncClient(
  timeout=httpx.Timeout(
    connect=10.0,  # 连接超时
    read=60.0,  # 读取超时
    write=30.0,  # 写入超时
    pool=5.0  # 连接池超时
  ),
  limits=httpx.Limits(
    max_keepalive_connections=20,  # 最大保持连接数
    max_connections=100,  # 最大连接数
    keepalive_expiry=30.0  # 连接保持时间
  ),
  follow_redirects=True,
  http2=True  # 启用 HTTP/2 支持
)


def get_max_failed_count(db: Session) -> int:
  """获取最大失败次数配置 - 保持向后兼容"""
  return ConfigManager.get_max_failed_count(db)


def handle_proxy_error(db: Session, selected_key, error: Exception, error_type: str = "error"):
  """统一处理代理错误"""
  if selected_key:
    max_failed_count = get_max_failed_count(db)
    update_key_status_based_on_response(db, selected_key, False, max_failed_count, status_override=error_type)

  if isinstance(error, httpx.RequestError):
    logger.error(f"An error occurred while requesting {error.request.url!r}: {error}", exc_info=True)
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Proxy request failed: {error}")
  else:
    logger.error(f"An unexpected error occurred: {error}", exc_info=True)
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"An unexpected error occurred: {error}")


def validate_api_token(request: Request, db: Session):
  """
  """
  api_token_config = crud.config.get_config_by_key(db, "api_token")
  if not api_token_config or not api_token_config.value:
    raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="API token is not configured.")

  expected_api_token = api_token_config.value

  auth_header = request.headers.get("Authorization")
  if not auth_header:
    logger.warning("Authorization header missing during API token validation.")
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authorization header missing.")

  try:
    scheme, token = auth_header.split()
    if scheme.lower() != "bearer":
      logger.warning(f"Invalid authentication scheme '{scheme}' during API token validation.")
      raise ValueError("Invalid authentication scheme")
    if token != expected_api_token:
      logger.warning("Invalid API token during validation.")
      raise ValueError("Invalid API token")
  except ValueError:
    logger.warning("Invalid API token format during validation.")
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API token or format.")


def update_key_status_based_on_response(
  db: Session,
  api_key,
  is_successful: bool,
  max_failed_count: int,
  status_override: Optional[str] = None,
  count_usage: bool = True
):
  """
  更新API密钥状态

  优化要点：
  1. 减少不必要的数据库操作
  2. 异步处理缓存失效
  3. 更好的事务管理
  """
  if not api_key:
    logger.warning("API key is None, skipping status update")
    return

  # 保存原始状态以判断是否需要更新
  original_status = api_key.status
  original_failed_count = api_key.failed_count
  original_usage_count = api_key.usage_count

  needs_db_update = False
  status_changed = False

  # 更新使用计数和最后使用时间
  if count_usage:
    api_key.usage_count += 1
    api_key.last_used_at = datetime.now(timezone.utc)
    needs_db_update = True

  # 处理状态覆盖
  if status_override:
    if api_key.status != status_override:
      api_key.status = status_override
      status_changed = True
      needs_db_update = True

    if status_override in ("exhausted", "error"):
      api_key.failed_count += 1
      needs_db_update = True

    logger.info(f"API Key ID {api_key.id} ({api_key.key_value[:8]}...) "
                f"status overridden to '{status_override}', usage: {api_key.usage_count}")

  # 处理成功请求
  elif is_successful:
    if api_key.failed_count > 0:
      api_key.failed_count = 0
      needs_db_update = True

    if api_key.status != "active":
      api_key.status = "active"
      status_changed = True
      needs_db_update = True

    if needs_db_update:
      logger.info(f"API Key ID {api_key.id} ({api_key.key_value[:8]}...) "
                  f"restored to active, usage: {api_key.usage_count}")

  # 处理失败请求
  else:
    api_key.failed_count += 1
    needs_db_update = True

    logger.warning(f"API Key ID {api_key.id} ({api_key.key_value[:8]}...) "
                   f"failed, count: {api_key.failed_count}, usage: {api_key.usage_count}")

    # 检查是否需要标记为错误状态
    if api_key.failed_count >= max_failed_count and api_key.status == "active":
      api_key.status = "error"
      status_changed = True
      logger.warning(f"API Key ID {api_key.id} ({api_key.key_value[:8]}...) "
                     f"marked as error after {max_failed_count} failures")

  # 只有在需要时才进行数据库操作
  if needs_db_update:
    try:
      db.add(api_key)
      db.commit()

      # 异步处理缓存失效，不阻塞主请求
      if status_changed:
        loop = asyncio.get_event_loop()
        loop.run_in_executor(_executor, _async_invalidate_cache)
        logger.debug(f"🔄 [CACHE] Scheduled async cache invalidation for key {api_key.id}")

    except Exception as e:
      logger.error(f"Failed to update API key status: {e}")
      db.rollback()
      raise
  else:
    # 没有变更时回滚事务
    db.rollback()


def record_api_call_log(db: Session, api_key_id: int):
  """
  记录 API 调用日志，按分钟统计

  优化要点：
  1. 更好的错误处理
  2. 减少数据库查询
  """
  try:
    now = datetime.now(timezone.utc)
    timestamp_minute = now.replace(second=0, microsecond=0)

    # 使用 UPSERT 模式减少查询
    log_entry = db.query(ApiCallLog).filter(
      ApiCallLog.api_key_id == api_key_id,
      ApiCallLog.timestamp == timestamp_minute
    ).first()

    if log_entry:
      log_entry.call_count += 1
    else:
      log_entry = ApiCallLog(
        api_key_id=api_key_id,
        timestamp=timestamp_minute,
        call_count=1
      )
      db.add(log_entry)

    db.commit()
    logger.debug(f"API call logged for key {api_key_id} at {timestamp_minute}")

  except Exception as e:
    logger.error(f"Failed to record API call log: {e}")
    db.rollback()
    # 不抛出异常，避免影响主请求流程


async def base_proxy_request(
  request: Request,
  db: Session,
  full_target_url: str,
  api_key_fetch_func=None,
  api_key_header_name: str = "x-goog-api-key",
  stream: bool = False,
  params: dict = None,
  skip_token_validation: bool = False,
  selected_key_obj=None,
  headers: Optional[Dict] = None
):
  """
  基础代理请求处理

  优化要点：
  1. 消除重复代码
  2. 更好的错误处理
  3. 统一的响应头处理
  """
  # 1. 验证API令牌（如果需要）
  if not skip_token_validation:
    validate_api_token(request, db)

  # 2. 获取API密钥
  key_value = None
  selected_key = None

  if api_key_header_name:
    if selected_key_obj:
      selected_key = selected_key_obj
      key_value = selected_key.key_value
    elif api_key_fetch_func:
      selected_key = api_key_fetch_func(db)
      if selected_key is None:
        raise HTTPException(status_code=503, detail="No active API keys available.")
      key_value = selected_key.key_value
    else:
      raise ValueError("Either api_key_fetch_func or selected_key_obj must be provided if api_key_header_name is not empty.")

    if key_value is None:
      raise HTTPException(status_code=503, detail="API key not available.")

  # 3. 获取配置
  max_failed_count = get_max_failed_count(db) if selected_key else 3

  # 4. 准备请求头
  if headers is None:
    final_headers = dict(request.headers)
    # 移除代理相关的header
    proxy_headers = [
      "host", "connection", "keep-alive", "proxy-authenticate",
      "proxy-authorization", "te", "transfer-encoding", "upgrade", "Authorization"
    ]
    for header in proxy_headers:
      final_headers.pop(header, None)
  else:
    final_headers = headers

  # 设置API密钥header
  if api_key_header_name and key_value:
    if api_key_header_name == "x-goog-api-key":
      final_headers[api_key_header_name] = key_value
    else:
      final_headers[api_key_header_name] = f"Bearer {key_value}"

  # 5. 准备请求参数
  query_params_to_send = params if params is not None else dict(request.query_params)
  body = await request.body()

  try:
    # 6. 发送请求
    if stream:
      return await _handle_streaming_request(
        request, full_target_url, final_headers, query_params_to_send,
        body, selected_key, max_failed_count, db
      )
    else:
      return await _handle_regular_request(
        request, full_target_url, final_headers, query_params_to_send,
        body, selected_key, max_failed_count, db
      )

  except httpx.RequestError as exc:
    handle_proxy_error(db, selected_key, exc, "error")
  except Exception as e:
    handle_proxy_error(db, selected_key, e, "error")


async def _handle_streaming_request(
  request: Request, full_target_url: str, headers: Dict, params: Dict,
  body: bytes, selected_key, max_failed_count: int, db: Session
) -> StreamingResponse:
  """处理流式请求"""
  proxy_response_context = httpx_client.stream(
    method=request.method,
    url=full_target_url,
    headers=headers,
    params=params,
    content=body
  )

  proxy_response = await proxy_response_context.__aenter__()

  # 更新API密钥状态
  if selected_key:
    try:
      initial_status = proxy_response.status_code
      is_successful = 200 <= initial_status < 300
      update_key_status_based_on_response(db, selected_key, is_successful, max_failed_count)
      record_api_call_log(db, selected_key.id)
    except Exception as e:
      logger.warning(f"Could not update key status for streaming response: {e}")

  # 清理响应头
  response_headers = _clean_response_headers(proxy_response.headers)

  return StreamingResponse(
    content=proxy_response.aiter_bytes(),
    status_code=proxy_response.status_code,
    headers=response_headers,
    background=lambda: proxy_response_context.__aexit__(None, None, None)
  )


async def _handle_regular_request(
  request: Request, full_target_url: str, headers: Dict, params: Dict,
  body: bytes, selected_key, max_failed_count: int, db: Session
) -> Response:
  """处理常规请求"""
  proxy_response = await httpx_client.request(
    method=request.method,
    url=full_target_url,
    headers=headers,
    params=params,
    content=body
  )

  # 更新API密钥状态
  if selected_key:
    is_successful = 200 <= proxy_response.status_code < 300
    update_key_status_based_on_response(db, selected_key, is_successful, max_failed_count)
    record_api_call_log(db, selected_key.id)

  # 清理响应头
  response_headers = _clean_response_headers(proxy_response.headers)

  return Response(
    content=proxy_response.content,
    status_code=proxy_response.status_code,
    headers=response_headers
  )
