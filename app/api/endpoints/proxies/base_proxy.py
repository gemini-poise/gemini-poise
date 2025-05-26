import logging
from typing import Optional, Dict

import httpx
from fastapi import Request, HTTPException, status
from fastapi.responses import StreamingResponse, Response
from sqlalchemy.orm import Session

from .... import crud

logger = logging.getLogger(__name__)

httpx_client = httpx.AsyncClient(timeout=60.0)


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
        max_failed_count: int
):
    """
    更新状态
    """
    original_key_status = api_key.status
    original_failed_count = api_key.failed_count

    if is_successful:
        if api_key.failed_count > 0 or api_key.status != "active":
            api_key.failed_count = 0
            api_key.status = "active"
            db.add(api_key)
            logger.info(f"API Key ID {api_key.id} ({api_key.key_value[:8]}...) is now active and failed count reset.")
    else:
        api_key.failed_count += 1
        logger.warning(
            f"API Key ID {api_key.id} ({api_key.key_value[:8]}...) failed, failed count: {api_key.failed_count}.")

        if api_key.failed_count >= max_failed_count and api_key.status == "active":
            api_key.status = "inactive"
            db.add(api_key)
            logger.warning(
                f"API Key ID {api_key.id} ({api_key.key_value[:8]}...) set to inactive due to exceeding max failed count ({max_failed_count}).")

    if api_key.status != original_key_status or api_key.failed_count != original_failed_count:
        db.commit()
    else:
        db.rollback()


async def base_proxy_request(
        request: Request,
        db: Session,
        full_target_url: str,
        api_key_fetch_func=None,
        api_key_header_name: str = "x-goog-api-key",
        stream: bool = False,
        params: dict = None,
        skip_token_validation: bool = False,
        target_api_key: str = None,
        headers: Optional[Dict] = None
):
    """
    """
    if not skip_token_validation:
        validate_api_token(request, db)

    key_value = None
    selected_key = None
    max_failed_count = 3
    if api_key_header_name:
        if target_api_key:
            key_value = target_api_key
            selected_key = type('ApiKey', (object,),
                                {'id': 'direct', 'key_value': key_value, 'failed_count': 0, 'status': 'active'})()
        elif api_key_fetch_func:
            selected_key = api_key_fetch_func(db)
            if selected_key is None:
                raise HTTPException(status_code=503, detail="No active API keys available.")
            key_value = selected_key.key_value
        else:
            raise ValueError(
                "Either api_key_fetch_func or target_api_key must be provided if api_key_header_name is not empty.")

        if key_value is None:
            raise HTTPException(status_code=503, detail="API key not available.")

        selected_key_id = getattr(selected_key, 'id', 'N/A')

        max_failed_count_str = crud.config.get_config_value(db, "key_validation_max_failed_count")
        if max_failed_count_str:
            try:
                max_failed_count = int(max_failed_count_str)
                if max_failed_count < 0:
                    logger.warning(f"Invalid max failed count '{max_failed_count_str}' from config, using default 3.")
                    max_failed_count = 3
            except ValueError:
                logger.warning(
                    f"Invalid max failed count format '{max_failed_count_str}' from config, using default 3.")
                max_failed_count = 3

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

            response_headers = dict(proxy_response.headers)
            response_headers.pop("content-encoding", None)
            response_headers.pop("content-length", None)

            return Response(
                content=proxy_response.content,
                status_code=proxy_response.status_code,
                headers=response_headers
            )


    except httpx.RequestError as exc:
        logger.error(f"An error occurred while requesting {exc.request.url!r}: {exc}", exc_info=True)
        if api_key_header_name and selected_key:
            max_failed_count_str = crud.config.get_config_value(db, "key_validation_max_failed_count")
            max_failed_count = 3
            if max_failed_count_str:
                try:
                    max_failed_count = int(max_failed_count_str)
                    if max_failed_count < 0:
                        max_failed_count = 3
                except ValueError:
                    max_failed_count = 3
            update_key_status_based_on_response(db, selected_key, False, max_failed_count)

        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Proxy request failed: {exc}")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)
        if api_key_header_name and selected_key:
            max_failed_count_str = crud.config.get_config_value(db, "key_validation_max_failed_count")
            max_failed_count = 3
            if max_failed_count_str:
                try:
                    max_failed_count = int(max_failed_count_str)
                    if max_failed_count < 0:
                        max_failed_count = 3
                except ValueError:
                    max_failed_count = 3
            update_key_status_based_on_response(db, selected_key, False, max_failed_count)

        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"An unexpected error occurred: {e}")
