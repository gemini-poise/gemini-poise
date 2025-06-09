import json
import logging

from fastapi import APIRouter, Request, HTTPException

from .base_proxy import base_proxy_request
from .... import crud
from ....core.config import settings
from ....core.security import db_dependency

logger = logging.getLogger(__name__)

router = APIRouter(prefix=settings.GEMINI_PURE_PROXY_PREFIX, tags=["Gemini Pure Proxy"])


@router.api_route(
    "/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"]
)
async def gemini_pure_proxy_request(path: str, request: Request, db: db_dependency):
    if not request.url.path.startswith(settings.GEMINI_PURE_PROXY_PREFIX):
        logger.warning(
            f"Gemini pure proxy received request with unexpected path: {request.url.path}"
        )
        raise HTTPException(status_code=404, detail="Not Found")

    logger.info(
        f"Received Gemini pure proxy request: path='{path}', query_params='{request.query_params}'"
    )

    target_config = crud.config.get_config_by_key(db, "target_api_url")
    if not target_config or not target_config.value:
        raise HTTPException(
            status_code=503,
            detail="Target Gemini API URL is not configured. Please add 'target_api_url' to the config table.",
        )

    target_url = target_config.value.rstrip("/")
    logger.info(f"Target Gemini API URL configured: {target_url}")
    full_target_url = f"{target_url}/{path}"

    stream = False

    if request.query_params.get("alt") == "sse":
        stream = True
        logger.info("Streaming requested via 'alt=sse' query parameter.")
    else:
        try:
            body = await request.body()
            if body:
                request_data = json.loads(body)
                if "stream" in request_data and isinstance(
                    request_data["stream"], bool
                ):
                    stream = request_data["stream"]
                    logger.info(f"Streaming set to {stream} via request body.")
                elif "stream" in request_data:
                    logger.warning(
                        f"Received non-boolean 'stream' parameter in body: {request_data['stream']}. Ignoring."
                    )

        except json.JSONDecodeError:
            logger.warning(
                "Request body is not JSON, cannot check for 'stream' parameter."
            )
            pass
        except Exception as e:
            logger.error(
                f"An error occurred while processing request body for stream parameter: {e}",
                exc_info=True,
            )
            pass

    internal_api_key = request.headers.get("x-goog-api-key")

    if not internal_api_key:
        internal_api_key = request.query_params.get("key")
        if internal_api_key:
            logger.info("Internal API key found in query parameters.")
        else:
            logger.warning(
                "Internal API key not found in x-goog-api-key header or query parameters."
            )

    api_token_config = crud.config.get_config_by_key(db, "api_token")
    if not api_token_config or not api_token_config.value:
        raise HTTPException(
            status_code=503, detail="Internal API token is not configured."
        )

    expected_internal_api_token = api_token_config.value

    if not internal_api_key or internal_api_key != expected_internal_api_token:
        raise HTTPException(
            status_code=401, detail="Invalid or missing internal API key."
        )

    target_api_key_obj = crud.api_keys.get_active_api_key_with_token_bucket(db)
    if not target_api_key_obj:
        raise HTTPException(
            status_code=503, detail="No active target API keys available."
        )

    query_params_to_send = dict(request.query_params)

    if "key" in query_params_to_send:
        del query_params_to_send["key"]

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

    success = 200 <= response.status_code < 300
    if response.status_code == 429:
        crud.api_keys.update_api_key_usage(db, target_api_key_obj.id, False, status_override="exhausted")
    else:
        crud.api_keys.update_api_key_usage(db, target_api_key_obj.id, success)
    db.commit()

    return response
