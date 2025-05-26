import json
import logging
import time
import httpx
from starlette import status

from fastapi import APIRouter, Request, HTTPException, Response
from fastapi.responses import StreamingResponse

from .base_proxy import update_key_status_based_on_response
from .... import crud
from ....core.config import settings
from ....core.security import db_dependency

logger = logging.getLogger(__name__)

httpx_client = httpx.AsyncClient(timeout=60.0)

router = APIRouter(prefix=settings.OPENAI_PROXY_PREFIX, tags=["OpenAI to Gemini Proxy"])


async def transform_openai_to_gemini_request(
    request: Request, body: bytes
) -> tuple[str, dict, bool]:
    """
    将 OpenAI 格式的请求转换为 Gemini 格式

    参数:
        request: FastAPI 请求对象
        body: 请求体字节数据

    返回:
        tuple: (Gemini 路径, Gemini 请求体字典, 是否流式响应)
    """
    try:
        if not body:
            return "", {}, False

        openai_request = json.loads(body)
        stream = openai_request.get("stream", False)

        model = openai_request.get("model", "gemini-pro")
        if "preview" in model.lower():
            logger.info(
                f"请求使用预览版模型: {model}，如果认证失败可能需要更换为标准模型"
            )

        gemini_model = model
        if "thinkingConfig" in openai_request:
            if not gemini_model.endswith("-thinking"):
                gemini_model = f"{gemini_model}-thinking"

        messages = openai_request.get("messages", [])
        contents = []

        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")

            if role == "system":
                contents.append({"role": "user", "parts": [{"text": content}]})
                contents.append(
                    {
                        "role": "model",
                        "parts": [{"text": "我理解了。我会按照您的指示进行回答。"}],
                    }
                )
                continue

            gemini_role = "user" if role == "user" else "model"

            if isinstance(content, list):
                parts = []
                for item in content:
                    if item.get("type") == "text":
                        parts.append({"text": item.get("text", "")})
                    elif item.get("type") == "image_url":
                        image_url = item.get("image_url", {}).get("url", "")
                        if image_url.startswith("data:image/"):
                            parts.append(
                                {
                                    "inline_data": {
                                        "mime_type": image_url.split(";")[0].replace(
                                            "data:", ""
                                        ),
                                        "data": image_url.split("base64,")[1],
                                    }
                                }
                            )
                contents.append({"role": gemini_role, "parts": parts})
            else:
                contents.append({"role": gemini_role, "parts": [{"text": content}]})

        gemini_request = {
            "contents": contents,
            "generationConfig": {
                "temperature": openai_request.get("temperature", 0.7),
                "topP": openai_request.get("top_p", 0.95),
                "topK": openai_request.get("top_k", 40),
                "maxOutputTokens": openai_request.get(
                    "max_tokens", None
                ),
                "stopSequences": openai_request.get("stop", []),
            },
        }

        gemini_request["generationConfig"]["thinkingConfig"] = openai_request.get(
            "thinkingConfig", {"includeThoughts": False, "thinkingBudget": 0}
        )

        if stream:
            gemini_path = f"models/{gemini_model}:streamGenerateContent"
        else:
            gemini_path = f"models/{gemini_model}:generateContent"
        return gemini_path, gemini_request, stream

    except json.JSONDecodeError:
        logger.warning("请求体不是有效的 JSON 格式")
        raise HTTPException(status_code=400, detail="Invalid JSON in request body")
    except Exception as e:
        logger.error(f"转换 OpenAI 请求到 Gemini 请求时出错: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Error transforming request: {str(e)}"
        )


async def transform_gemini_to_openai_streaming(stream):
    """
    将 Gemini 流式响应转换为 OpenAI 流式响应格式
    """
    try:
        async for chunk in stream:
            if not chunk.strip():
                continue

            try:
                gemini_chunk = json.loads(chunk.decode("utf-8").replace("data: ", ""))
                candidate = gemini_chunk.get("candidates", [{}])[0]
                finish_reason = None
                if candidate.get("finishReason"):
                    if candidate["finishReason"] == "STOP":
                        finish_reason = "stop"
                    elif candidate["finishReason"] == "MAX_TOKENS":
                        finish_reason = "length"
                    else:
                        finish_reason = "stop"

                content_text = ""
                if candidate.get("content", {}).get("parts"):
                    for part in candidate["content"]["parts"]:
                        if part.get("text"):
                            content_text += part["text"]

                openai_response = {
                    "id": gemini_chunk.get(
                        "name", "chatcmpl-" + str(hash(json.dumps(gemini_chunk)))
                    ),
                    "object": "chat.completion.chunk",
                    "created": int(
                        time.time()
                    ),
                    "model": gemini_chunk.get("model", "gemini-pro"),
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"content": content_text},
                            "finish_reason": finish_reason,
                        }
                    ],
                }
                if not content_text and finish_reason:
                    openai_response["choices"][0]["delta"] = {}
                    openai_response["choices"][0]["finish_reason"] = finish_reason
                elif finish_reason:
                    openai_response["choices"][0]["finish_reason"] = finish_reason

                yield f"data: {json.dumps(openai_response)}\n\n"

                if finish_reason:
                    yield "data: [DONE]\n\n"

            except json.JSONDecodeError:
                continue
            except Exception as e:
                logger.error(f"处理流式响应块时出错: {e}")
                continue

    except Exception as e:
        logger.error(f"转换 Gemini 流式响应时出错: {e}", exc_info=True)
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
        yield "data: [DONE]\n\n"


async def transform_gemini_to_openai_response(response_content: bytes) -> dict:
    """
    将 Gemini 响应转换为 OpenAI 响应格式
    """
    try:
        gemini_response = json.loads(response_content)

        response_text = ""

        if gemini_response.get("candidates"):
            candidate = gemini_response["candidates"][0]
            if candidate.get("content", {}).get("parts"):
                for part in candidate["content"]["parts"]:
                    if part.get("text"):
                        response_text += part["text"]

        finish_reason = "stop"
        if gemini_response.get("candidates", [{}])[0].get("finishReason"):
            reason = gemini_response["candidates"][0]["finishReason"]
            if reason == "MAX_TOKENS":
                finish_reason = "length"

        openai_response = {
            "id": gemini_response.get(
                "name", "chatcmpl-" + str(hash(json.dumps(gemini_response)))
            ),
            "object": "chat.completion",
            "created": int(gemini_response.get("createTime", 0)),
            "model": "gpt-3.5-turbo",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": response_text},
                    "finish_reason": finish_reason,
                }
            ],
            "usage": {
                "prompt_tokens": gemini_response.get("usageMetadata", {}).get(
                    "promptTokenCount", 0
                ),
                "completion_tokens": gemini_response.get("usageMetadata", {}).get(
                    "candidatesTokenCount", 0
                ),
                "total_tokens": (
                    gemini_response.get("usageMetadata", {}).get("promptTokenCount", 0)
                    + gemini_response.get("usageMetadata", {}).get(
                        "candidatesTokenCount", 0
                    )
                ),
            },
        }

        return openai_response

    except json.JSONDecodeError:
        logger.error("Gemini 响应不是有效的 JSON 格式")
        raise HTTPException(status_code=500, detail="Invalid JSON in Gemini response")
    except Exception as e:
        logger.error(f"转换 Gemini 响应到 OpenAI 格式时出错: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Error transforming response: {str(e)}"
        )


class StreamAdapter:
    """
    适配 Gemini 流式响应到 OpenAI 流式响应格式的适配器
    """

    def __init__(self, stream):
        self.stream = stream

    async def aiter_bytes(self):
        async for chunk in transform_gemini_to_openai_streaming(self.stream):
            yield chunk.encode("utf-8")


@router.api_route("/chat/completions", methods=["POST"])
async def openai_chat_completions(request: Request, db: db_dependency):
    """
    OpenAI 聊天补全 API 端点，将请求转换为 Gemini 格式并返回转换后的响应
    """
    if not request.url.path.startswith(
        settings.OPENAI_PROXY_PREFIX + "/chat/completions"
    ):
        logger.warning(f"OpenAI 代理收到意外路径的请求: {request.url.path}")
        raise HTTPException(status_code=404, detail="Not Found")

    logger.info(f"收到 OpenAI 聊天补全请求")

    target_config = crud.config.get_config_by_key(db, "target_api_url")
    if not target_config or not target_config.value:
        raise HTTPException(
            status_code=503,
            detail="目标 Gemini API URL 未配置，请在配置表中添加 'target_api_url'。",
        )

    target_url = target_config.value.rstrip("/")
    logger.info(f"目标 Gemini API URL: {target_url}")

    body = await request.body()
    gemini_path, gemini_request_body, stream = await transform_openai_to_gemini_request(
        request, body
    )

    if not gemini_path:
        raise HTTPException(status_code=400, detail="无法解析请求体")

    full_target_url = f"{target_url}/{gemini_path}"
    logger.info(f"转换后的 Gemini 目标 URL: {full_target_url}")

    api_token_config = crud.config.get_config_by_key(db, "api_token")
    if not api_token_config or not api_token_config.value:
        raise HTTPException(status_code=503, detail="内部 API 令牌未配置。")

    expected_internal_api_token = api_token_config.value

    auth_header = request.headers.get("Authorization", "")
    internal_api_key = ""

    if auth_header.startswith("Bearer "):
        internal_api_key = auth_header.replace("Bearer ", "")

    if not internal_api_key or internal_api_key != expected_internal_api_token:
        raise HTTPException(status_code=401, detail="无效或缺失的内部 API 密钥。")

    target_api_key_obj = crud.api_keys.get_random_active_api_key_from_db(db)
    if not target_api_key_obj:
        raise HTTPException(status_code=503, detail="没有可用的活跃目标 API 密钥。")
    target_api_key = target_api_key_obj.key_value

    query_params_to_send = {}
    if stream:
        query_params_to_send["alt"] = "sse"

    logger.info(f"Target API Key being sent: {target_api_key[:8]}...")
    clean_headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": target_api_key,
    }

    proxy_response = None
    proxy_response_context = None

    try:
        if stream:
            proxy_response_context = httpx_client.stream(
                method=request.method,
                url=full_target_url,
                headers=clean_headers,
                params=query_params_to_send,
                json=gemini_request_body,
            )
            proxy_response = await proxy_response_context.__aenter__()
        else:
            proxy_response = await httpx_client.request(
                method=request.method,
                url=full_target_url,
                headers=clean_headers,
                params=query_params_to_send,
                json=gemini_request_body,
            )

        is_successful = (
            proxy_response.status_code >= 200 and proxy_response.status_code < 300
        )
        max_failed_count_str = crud.config.get_config_value(
            db, "key_validation_max_failed_count"
        )
        max_failed_count = 3
        if max_failed_count_str:
            try:
                max_failed_count = int(max_failed_count_str)
                if max_failed_count < 0:
                    max_failed_count = 3
            except ValueError:
                max_failed_count = 3
        crud.api_keys.update_api_key_usage(db, target_api_key_obj.id, is_successful)
        db.commit()

        if proxy_response.status_code == 401 and "preview" in gemini_path:
            logger.warning(f"预览版模型 {gemini_path} 认证失败 (401)，尝试使用标准模型")

            if stream and proxy_response_context:
                await proxy_response_context.__aexit__(None, None, None)
            elif proxy_response:
                await proxy_response.aclose()

            standard_model = "gemini-1.5-flash"
            new_gemini_path = f"models/{standard_model}:generateContent"
            new_full_target_url = f"{target_url}/{new_gemini_path}"

            logger.info(f"回退到标准模型，新的目标 URL: {new_full_target_url}")

            fallback_query_params_to_send = {} 
            try:
                proxy_response = await httpx_client.request(
                    method=request.method,
                    url=new_full_target_url,
                    headers=clean_headers,
                    params=fallback_query_params_to_send,
                    json=gemini_request_body,
                )

                is_successful = (
                    proxy_response.status_code >= 200
                    and proxy_response.status_code < 300
                )
                max_failed_count_str = crud.config.get_config_value(
                    db, "key_validation_max_failed_count"
                )
                max_failed_count = 3
                if max_failed_count_str:
                    try:
                        max_failed_count = int(max_failed_count_str)
                        if max_failed_count < 0:
                            max_failed_count = 3
                    except ValueError:
                        max_failed_count = 3
                crud.api_keys.update_api_key_usage(db, target_api_key_obj.id, is_successful)
                db.commit()

                if not (200 <= proxy_response.status_code < 300):
                    logger.error(
                        f"Proxy fallback request failed with status code: {proxy_response.status_code}"
                    )

            except httpx.RequestError as exc:
                logger.error(
                    f"An error occurred during fallback request to {exc.request.url!r}: {exc}",
                    exc_info=True,
                )
            except Exception as e:
                logger.error(
                    f"An unexpected error occurred during fallback: {e}", exc_info=True
                )

        if not (200 <= proxy_response.status_code < 300):
            logger.error(
                f"Final proxy request failed with status code: {proxy_response.status_code}"
            )
            error_body = None
            try:
                if hasattr(proxy_response, "read"):
                    error_body = await proxy_response.read()
                elif hasattr(
                    proxy_response, "aclose"
                ): 
                    if stream and proxy_response_context:
                        await proxy_response_context.__aexit__(None, None, None)
                    else:
                        await proxy_response.aclose()
                else:
                    error_body = proxy_response.content

                return Response(
                    content=error_body if error_body is not None else b"",
                    status_code=proxy_response.status_code,
                    headers=proxy_response.headers,
                    media_type=proxy_response.headers.get(
                        "content-type", "application/json"
                    ),
                )
            except Exception as e:
                logger.error(f"Could not process error response body: {e}")
                raise HTTPException(
                    status_code=proxy_response.status_code,
                    detail="Proxy request failed and could not read error body.",
                )

        if stream:
            logger.info("返回流式响应")
            return StreamingResponse(
                content=StreamAdapter(proxy_response.aiter_bytes()).aiter_bytes(),
                status_code=proxy_response.status_code,
                headers=proxy_response.headers,
                background=lambda: proxy_response_context.__aexit__(None, None, None),
            )
        else:
            logger.info("返回非流式响应")
            openai_response = await transform_gemini_to_openai_response(
                proxy_response.content
            )
            return Response(
                content=json.dumps(openai_response).encode(),
                status_code=proxy_response.status_code,
                headers=proxy_response.headers,
                media_type="application/json",
            )

    except httpx.RequestError as exc:
        logger.error(
            f"An error occurred while making proxy request to {exc.request.url!r}: {exc}",
            exc_info=True,
        )
        if target_api_key_obj:
            crud.api_keys.update_api_key_usage(db, target_api_key_obj.id, False)
            db.commit()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Proxy request failed: {exc}",
        )
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)
        if target_api_key_obj:
            crud.api_keys.update_api_key_usage(db, target_api_key_obj.id, False)
            db.commit()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {e}",
        )


@router.api_route("/images/generations", methods=["POST"])
async def openai_image_generations(request: Request, db: db_dependency):
    """
    OpenAI 图像生成 API 端点，将请求转换为 Gemini Imagen 格式并返回转换后的响应
    """
    if not request.url.path.startswith(
        settings.OPENAI_PROXY_PREFIX + "/images/generations"
    ):
        logger.warning(f"OpenAI 图像生成代理收到意外路径的请求: {request.url.path}")
        raise HTTPException(status_code=404, detail="Not Found")

    logger.info(f"收到 OpenAI 图像生成请求")

    target_config = crud.config.get_config_by_key(db, "target_api_url")
    if not target_config or not target_config.value:
        raise HTTPException(
            status_code=503,
            detail="目标 Gemini API URL 未配置，请在配置表中添加 'target_api_url'。",
        )

    target_url = target_config.value.rstrip("/")
    logger.info(f"目标 Gemini API URL: {target_url}")

    body = await request.body()
    try:
        openai_request = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="无效的 JSON 请求体")

    api_token_config = crud.config.get_config_by_key(db, "api_token")
    if not api_token_config or not api_token_config.value:
        raise HTTPException(status_code=503, detail="内部 API 令牌未配置。")

    expected_internal_api_token = api_token_config.value

    auth_header = request.headers.get("Authorization", "")
    internal_api_key = ""

    if auth_header.startswith("Bearer "):
        internal_api_key = auth_header.replace("Bearer ", "")

    if not internal_api_key or internal_api_key != expected_internal_api_token:
        raise HTTPException(status_code=401, detail="无效或缺失的内部 API 密钥。")

    target_api_key_obj = crud.api_keys.get_random_active_api_key_from_db(db)
    if not target_api_key_obj:
        raise HTTPException(status_code=503, detail="没有可用的活跃目标 API 密钥。")
    target_api_key = target_api_key_obj.key_value

    prompt = openai_request.get("prompt", "")
    if not prompt:
        raise HTTPException(status_code=400, detail="缺少必需的 'prompt' 参数")

    n = min(openai_request.get("n", 1), 4)
    size = openai_request.get("size", "1024x1024")

    width, height = 1024, 1024
    if size == "256x256":
        width, height = 256, 256
    elif size == "512x512":
        width, height = 512, 512
    elif size == "1024x1024":
        width, height = 1024, 1024
    elif "x" in size:
        try:
            width_str, height_str = size.split("x")
            width, height = int(width_str), int(height_str)
        except (ValueError, TypeError):
            width, height = 1024, 1024

    imagen_request = {
        "prompt": {"text": prompt},
        "sampleCount": n,
        "sampleImageSize": {"width": width, "height": height},
    }

    full_target_url = f"{target_url}/v1beta/models/imagegeneration:generateImage"
    logger.info(f"Imagen 目标 URL: {full_target_url}")

    headers = {"Content-Type": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            headers["x-goog-api-key"] = target_api_key
            response = await client.post(
                full_target_url, json=imagen_request, headers=headers
            )

            success = 200 <= response.status_code < 300
            crud.api_keys.update_api_key_usage(db, target_api_key_obj.id, success)
            db.commit()

            if not success:
                error_detail = "图像生成请求失败"
                try:
                    error_json = response.json()
                    if "error" in error_json:
                        error_detail = error_json["error"].get("message", error_detail)
                except Exception:
                    pass
                raise HTTPException(
                    status_code=response.status_code, detail=error_detail
                )

            imagen_response = response.json()

            image_data = []
            for i in range(min(n, len(imagen_response.get("images", [])))):
                image = imagen_response["images"][i]
                image_data.append(
                    {
                        "url": image.get("publicImageUrl", ""),
                        "b64_json": image.get("base64", ""),
                    }
                )

            openai_response = {
                "created": int(imagen_response.get("createTime", 0))
                or int(time.time()),
                "data": image_data,
            }

            return Response(
                content=json.dumps(openai_response),
                status_code=200,
                media_type="application/json",
            )

    except httpx.RequestError as e:
        logger.error(f"Imagen 请求错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"图像生成请求失败: {str(e)}")
    except Exception as e:
        logger.error(f"处理图像生成请求时出现错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"处理图像生成请求时出错: {str(e)}")


@router.get("/models")
async def list_models(request: Request, db: db_dependency):
    """
    OpenAI 模型列表 API 端点
    从 Gemini API 获取支持的模型列表并返回
    """
    logger.info("收到获取模型列表请求")

    target_config = crud.config.get_config_by_key(db, "target_api_url")
    if not target_config or not target_config.value:
        raise HTTPException(
            status_code=503,
            detail="目标 Gemini API URL 未配置，请在配置表中添加 'target_api_url'。",
        )
    target_url = target_config.value.rstrip("/")

    api_token_config = crud.config.get_config_by_key(db, "api_token")
    if not api_token_config or not api_token_config.value:
        raise HTTPException(status_code=503, detail="内部 API 令牌未配置。")
    expected_internal_api_token = api_token_config.value

    auth_header = request.headers.get("Authorization", "")
    internal_api_key = ""

    if auth_header.startswith("Bearer "):
        internal_api_key = auth_header.replace("Bearer ", "")

    if not internal_api_key or internal_api_key != expected_internal_api_token:
        raise HTTPException(status_code=401, detail="无效或缺失的内部 API 密钥。")
    
    target_api_key_obj = crud.api_keys.get_random_active_api_key_from_db(db)
    if not target_api_key_obj:
        raise HTTPException(status_code=503, detail="没有可用的活跃目标 API 密钥。")
    target_api_key = target_api_key_obj.key_value

    full_target_url = f"{target_url}/models"
    logger.info(f"获取 Gemini 模型列表的 URL: {full_target_url}")

    headers = {"Content-Type": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(
                f"{full_target_url}?key={target_api_key}", headers=headers
            )
            response.raise_for_status()

            gemini_models_response = response.json()

            openai_models = []
            for model in gemini_models_response.get("models", []):
                model_id = model.get("name", "").split("/")[-1]
                if model_id:
                    openai_models.append(
                        {
                            "id": model_id,
                            "object": "model",
                            "created": int(time.time()),
                            "owned_by": "google",
                            "permission": [],
                            "root": model_id,
                            "parent": None,
                        }
                    )

            crud.api_keys.update_api_key_usage(db, target_api_key_obj.id, True)
            db.commit()
            
            return Response(
                content=json.dumps({"object": "list", "data": openai_models}),
                status_code=200,
                media_type="application/json",
            )

    except httpx.RequestError as e:
        logger.error(f"从 Gemini 获取模型列表失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"无法从 Gemini 获取模型列表: {str(e)}"
        )
    except httpx.HTTPStatusError as e:
        if target_api_key_obj:
            crud.api_keys.update_api_key_usage(db, target_api_key_obj.id, False)
            db.commit()
        logger.error(
            f"从 Gemini 获取模型列表时收到错误状态码: {e.response.status_code} - {e.response.text}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"从 Gemini 获取模型列表失败: {e.response.text}",
        )
    except Exception as e:
        if target_api_key_obj:
            crud.api_keys.update_api_key_usage(db, target_api_key_obj.id, False)
            db.commit()
        logger.error(f"处理获取模型列表请求时出错: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"处理获取模型列表请求时出错: {str(e)}"
        )


@router.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
    include_in_schema=False,
)
async def openai_proxy_request_fallback(path: str, request: Request):
    """
    处理未实现的 OpenAI API 端点
    """
    return Response(
        content=json.dumps(
            {
                "error": {
                    "message": f"未实现的 OpenAI API 端点: {path}",
                    "type": "not_implemented",
                    "code": "not_implemented",
                }
            }
        ),
        status_code=501,
        media_type="application/json",
    )
