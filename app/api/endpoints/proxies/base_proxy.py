import logging
from typing import Optional, Dict

import httpx
from fastapi import Request, HTTPException, status
from fastapi.responses import StreamingResponse, Response
from sqlalchemy.orm import Session

from datetime import datetime, timezone

from .... import crud
from ....models.models import ApiCallLog

logger = logging.getLogger(__name__)

# 优化的 httpx 客户端配置，使用连接池和超时配置
httpx_client = httpx.AsyncClient(
    timeout=httpx.Timeout(
        connect=10.0,    # 连接超时
        read=60.0,       # 读取超时
        write=30.0,      # 写入超时
        pool=5.0         # 连接池超时
    ),
    limits=httpx.Limits(
        max_keepalive_connections=20,  # 最大保持连接数
        max_connections=100,           # 最大连接数
        keepalive_expiry=30.0         # 连接保持时间
    ),
    follow_redirects=True,
    http2=True  # 启用 HTTP/2 支持
)


def get_max_failed_count(db: Session) -> int:
    """获取最大失败次数配置"""
    max_failed_count_str = crud.config.get_config_value(db, "key_validation_max_failed_count")
    max_failed_count = 3  # 默认值
    if max_failed_count_str:
        try:
            max_failed_count = int(max_failed_count_str)
            if max_failed_count < 0:
                logger.warning(f"Invalid max failed count '{max_failed_count_str}' from config, using default 3.")
                max_failed_count = 3
        except ValueError:
            logger.warning(f"Invalid max failed count format '{max_failed_count_str}' from config, using default 3.")
    return max_failed_count


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
    更新状态
    """
    original_key_status = api_key.status
    original_failed_count = api_key.failed_count
    original_usage_count = api_key.usage_count

    if count_usage:
        api_key.usage_count += 1

    if status_override:
        api_key.status = status_override
        if status_override == "exhausted" or status_override == "error":
            api_key.failed_count += 1
        db.add(api_key)
        logger.info(f"API Key ID {api_key.id} ({api_key.key_value[:8]}...) status overridden to '{status_override}', usage count: {api_key.usage_count}.")
    elif is_successful:
        if api_key.failed_count > 0 or api_key.status != "active":
            api_key.failed_count = 0
            api_key.status = "active"
            db.add(api_key)
            logger.info(f"API Key ID {api_key.id} ({api_key.key_value[:8]}...) is now active and failed count reset, usage count: {api_key.usage_count}.")
    else:
        api_key.failed_count += 1
        logger.warning(
            f"API Key ID {api_key.id} ({api_key.key_value[:8]}...) failed, failed count: {api_key.failed_count}, usage count: {api_key.usage_count}.")

        if api_key.failed_count >= max_failed_count and api_key.status == "active":
            api_key.status = "error"
            db.add(api_key)
            logger.warning(
                f"API Key ID {api_key.id} ({api_key.key_value[:8]}...) set to error due to exceeding max failed count ({max_failed_count}), usage count: {api_key.usage_count}.")

    if api_key.status != original_key_status or api_key.failed_count != original_failed_count or api_key.usage_count != original_usage_count:
        db.commit()
    else:
        db.rollback()


def record_api_call_log(db: Session, api_key_id: int):
    """
    记录 API 调用日志，按分钟统计。
    """
    now = datetime.now(timezone.utc)
    timestamp_minute = now.replace(second=0, microsecond=0)

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
    """
    if not skip_token_validation:
        validate_api_token(request, db)

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
            raise ValueError(
                "Either api_key_fetch_func, target_api_key, or selected_key_obj must be provided if api_key_header_name is not empty.")

        if key_value is None:
            raise HTTPException(status_code=503, detail="API key not available.")

    max_failed_count = get_max_failed_count(db) if selected_key else 3

    if headers is None:
        final_headers = dict(request.headers)
        final_headers.pop("host", None)
        final_headers.pop("connection", None)
        final_headers.pop("keep-alive", None)
        final_headers.pop("proxy-authenticate", None)
        final_headers.pop("proxy-authorization", None)
        final_headers.pop("te", None)
        final_headers.pop("transfer-encoding", None)
        final_headers.pop("upgrade", None)
        final_headers.pop("Authorization", None)
    else:
        final_headers = headers

    if api_key_header_name and key_value:
        final_headers[api_key_header_name] = key_value if api_key_header_name == "x-goog-api-key" else f"Bearer {key_value}"

    body = await request.body()
    body_to_send = body

    try:
        query_params_to_send = params if params is not None else dict(request.query_params)
        if stream:
            proxy_response_context = httpx_client.stream(
                method=request.method,
                url=full_target_url,
                headers=final_headers,
                params=query_params_to_send,
                content=body_to_send
            )
            proxy_response = await proxy_response_context.__aenter__()
            if api_key_header_name and selected_key:
                try:
                    initial_status = proxy_response.status_code
                    is_successful = initial_status >= 200 and initial_status < 300
                    update_key_status_based_on_response(db, selected_key, is_successful, max_failed_count)
                    record_api_call_log(db, selected_key.id)
                except Exception:
                    logger.warning("Could not get initial status code for streaming response to update key status.")
                    pass

            response_headers = dict(proxy_response.headers)
            response_headers.pop("content-encoding", None)
            response_headers.pop("content-length", None)

            return StreamingResponse(
                content=proxy_response.aiter_bytes(),
                status_code=proxy_response.status_code,
                headers=response_headers,
                background=lambda: proxy_response_context.__aexit__(None, None, None)
            )
        else:
            query_params_to_send = params if params is not None else dict(request.query_params)
            proxy_response = await httpx_client.request(
                method=request.method,
                url=full_target_url,
                headers=final_headers,
                params=query_params_to_send,
                content=body_to_send
            )

            if api_key_header_name and selected_key:
                is_successful = proxy_response.status_code >= 200 and proxy_response.status_code < 300
                update_key_status_based_on_response(db, selected_key, is_successful, max_failed_count)
                record_api_call_log(db, selected_key.id)

            response_headers = dict(proxy_response.headers)
            response_headers.pop("content-encoding", None)
            response_headers.pop("content-length", None)

            return Response(
                content=proxy_response.content,
                status_code=proxy_response.status_code,
                headers=response_headers
            )


    except httpx.RequestError as exc:
        handle_proxy_error(db, selected_key, exc, "error")
    except Exception as e:
        handle_proxy_error(db, selected_key, e, "error")

