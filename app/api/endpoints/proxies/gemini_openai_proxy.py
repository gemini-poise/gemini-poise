"""
OpenAI 到 Gemini 代理服务模块

该模块提供了将 OpenAI 格式的 API 请求转换为 Gemini 格式，
并将 Gemini 的响应转换回 OpenAI 格式的代理服务。

支持的功能：
- 聊天补全 (/chat/completions)
- 图像生成 (/images/generations)
- 图像编辑 (/images/edits)
- 模型列表 (/models)
"""

import json
import logging
import time
from typing import Tuple, Dict, Any, Optional, List

import httpx
from starlette import status
from fastapi import APIRouter, Request, HTTPException, Response
from fastapi.responses import StreamingResponse

from .base_proxy import update_key_status_based_on_response, record_api_call_log
from .... import crud
from ....core.config import settings
from ....core.security import db_dependency

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 60.0
DEFAULT_MAX_FAILED_COUNT = 3
DEFAULT_TEMPERATURE = 0.7
DEFAULT_TOP_P = 0.95
DEFAULT_TOP_K = 40
FALLBACK_MODEL = "gemini-1.5-flash"
CHUNK_SIZE = 8192

GEMINI_TO_OPENAI_FINISH_REASON = {
    "STOP": "stop",
    "MAX_TOKENS": "length",
}

router = APIRouter(
    prefix=settings.OPENAI_PROXY_PREFIX,
    tags=["OpenAI to Gemini Proxy"]
)


class ProxyError(Exception):
    """代理处理异常基类"""
    def __init__(self, status_code: int, detail: str, original_error: Optional[Exception] = None):
        self.status_code = status_code
        self.detail = detail
        self.original_error = original_error
        super().__init__(detail)


class ConfigManager:
    """配置管理器"""
    
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
            return DEFAULT_MAX_FAILED_COUNT


class AuthValidator:
    """认证验证器"""
    
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
    """API 密钥管理器"""
    
    @staticmethod
    def get_active_api_key(db):
        """获取活跃的 API 密钥"""
        key_obj = crud.api_keys.get_random_active_api_key_from_db(db)
        if not key_obj:
            raise ProxyError(503, "没有可用的活跃目标 API 密钥。")
        return key_obj
    
    @staticmethod
    def update_key_usage(db, api_key, success: bool) -> None:
        """更新密钥使用状态"""
        try:
            max_failed_count = ConfigManager.get_max_failed_count(db)
            update_key_status_based_on_response(db, api_key, success, max_failed_count)
        except Exception as e:
            logger.error(f"更新密钥使用状态失败: {e}")


httpx_client = httpx.AsyncClient(timeout=DEFAULT_TIMEOUT)


class RequestTransformer:
    """请求转换器"""
    
    @staticmethod
    def _process_system_message(content: str) -> List[Dict[str, Any]]:
        """处理系统消息"""
        return [
            {"role": "user", "parts": [{"text": content}]},
            {"role": "model", "parts": [{"text": "我理解了。我会按照您的指示进行回答。"}]}
        ]
    
    @staticmethod
    def _process_content_item(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """处理内容项目"""
        if item.get("type") == "text":
            return {"text": item.get("text", "")}
        elif item.get("type") == "image_url":
            image_url = item.get("image_url", {}).get("url", "")
            if image_url.startswith("data:image/"):
                try:
                    mime_type = image_url.split(";")[0].replace("data:", "")
                    data = image_url.split("base64,")[1]
                    return {"inline_data": {"mime_type": mime_type, "data": data}}
                except (IndexError, ValueError) as e:
                    logger.warning(f"无法解析图像数据: {e}")
                    return None
        return None
    
    @staticmethod
    def _convert_messages_to_contents(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """将 OpenAI 消息格式转换为 Gemini contents 格式"""
        contents = []
        
        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")
            
            if role == "system":
                contents.extend(RequestTransformer._process_system_message(content))
                continue
            
            gemini_role = "user" if role == "user" else "model"
            
            if isinstance(content, list):
                parts = []
                for item in content:
                    part = RequestTransformer._process_content_item(item)
                    if part:
                        parts.append(part)
                if parts:
                    contents.append({"role": gemini_role, "parts": parts})
            else:
                contents.append({"role": gemini_role, "parts": [{"text": str(content)}]})
        
        return contents
    
    @staticmethod
    def _build_generation_config(openai_request: Dict[str, Any]) -> Dict[str, Any]:
        """构建生成配置"""
        config = {
            "temperature": openai_request.get("temperature", DEFAULT_TEMPERATURE),
            "topP": openai_request.get("top_p", DEFAULT_TOP_P),
            "topK": openai_request.get("top_k", DEFAULT_TOP_K),
            "stopSequences": openai_request.get("stop", []),
        }
        
        max_tokens = openai_request.get("max_tokens")
        if max_tokens is not None:
            config["maxOutputTokens"] = max_tokens
        
        config["thinkingConfig"] = openai_request.get(
            "thinkingConfig", {"includeThoughts": False, "thinkingBudget": 0}
        )
        
        return config
    
    @staticmethod
    def transform_openai_to_gemini_request(
        request: Request, body: bytes
    ) -> Tuple[str, Dict[str, Any], bool]:
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
                raise ProxyError(400, "请求体不能为空")
            
            openai_request = json.loads(body)
            stream = openai_request.get("stream", False)
            
            model = openai_request.get("model", "gemini-pro")
            if "preview" in model.lower():
                logger.info(f"请求使用预览版模型: {model}，如果认证失败可能需要更换为标准模型")
            
            gemini_model = model
            if "thinkingConfig" in openai_request and not gemini_model.endswith("-thinking"):
                gemini_model = f"{gemini_model}-thinking"
            
            messages = openai_request.get("messages", [])
            contents = RequestTransformer._convert_messages_to_contents(messages)
            
            gemini_request = {
                "contents": contents,
                "generationConfig": RequestTransformer._build_generation_config(openai_request),
            }
            
            action = "streamGenerateContent" if stream else "generateContent"
            gemini_path = f"models/{gemini_model}:{action}"
            
            return gemini_path, gemini_request, stream
            
        except json.JSONDecodeError:
            logger.warning("请求体不是有效的 JSON 格式")
            raise ProxyError(400, "Invalid JSON in request body")
        except ProxyError:
            raise
        except Exception as e:
            logger.error(f"转换 OpenAI 请求到 Gemini 请求时出错: {e}", exc_info=True)
            raise ProxyError(500, f"Error transforming request: {str(e)}", e)


class ResponseTransformer:
    """响应转换器"""
    
    @staticmethod
    def _extract_content_text(candidate: Dict[str, Any]) -> str:
        """从候选响应中提取文本内容"""
        content_text = ""
        if candidate.get("content", {}).get("parts"):
            for part in candidate["content"]["parts"]:
                if part.get("text"):
                    content_text += part["text"]
        return content_text
    
    @staticmethod
    def _get_finish_reason(gemini_reason: str) -> str:
        """转换结束原因"""
        return GEMINI_TO_OPENAI_FINISH_REASON.get(gemini_reason, "stop")
    
    @staticmethod
    def _generate_response_id(base_data: Dict[str, Any]) -> str:
        """生成响应 ID"""
        if "name" in base_data:
            return base_data["name"]
        return "chatcmpl-" + str(abs(hash(json.dumps(base_data, sort_keys=True))))
    
    @staticmethod
    async def transform_gemini_to_openai_streaming(stream):
        """将 Gemini 流式响应转换为 OpenAI 流式响应格式"""
        try:
            async for chunk in stream:
                if not chunk.strip():
                    continue
                
                try:
                    chunk_text = chunk.decode("utf-8")
                    if chunk_text.startswith("data: "):
                        chunk_text = chunk_text[6:]
                    
                    gemini_chunk = json.loads(chunk_text)
                    candidate = gemini_chunk.get("candidates", [{}])[0]
                    
                    finish_reason = None
                    if candidate.get("finishReason"):
                        finish_reason = ResponseTransformer._get_finish_reason(
                            candidate["finishReason"]
                        )
                    
                    content_text = ResponseTransformer._extract_content_text(candidate)
                    
                    openai_response = {
                        "id": ResponseTransformer._generate_response_id(gemini_chunk),
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": gemini_chunk.get("model", "gemini-pro"),
                        "choices": [{
                            "index": 0,
                            "delta": {"content": content_text} if content_text else {},
                            "finish_reason": finish_reason,
                        }],
                    }
                    
                    yield f"data: {json.dumps(openai_response)}\n\n"
                    
                    if finish_reason:
                        yield "data: [DONE]\n\n"
                        break
                
                except json.JSONDecodeError:
                    continue
                except Exception as e:
                    logger.error(f"处理流式响应块时出错: {e}")
                    continue
        
        except Exception as e:
            import httpx
            if isinstance(e, (httpx.ReadError, httpx.RemoteProtocolError, httpx.NetworkError)):
                logger.warning(f"网络连接问题导致流式响应中断: {type(e).__name__}: {e}")
            else:
                logger.error(f"转换 Gemini 流式响应时出错: {e}", exc_info=True)
            
            try:
                error_response = {
                    "id": f"chatcmpl-{int(time.time())}",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": "gemini-pro",
                    "choices": [{
                        "index": 0,
                        "delta": {},
                        "finish_reason": "stop",
                    }],
                }
                yield f"data: {json.dumps(error_response)}\n\n"
                yield "data: [DONE]\n\n"
            except Exception as cleanup_error:
                logger.error(f"清理流式响应时出错: {cleanup_error}")
    
    @staticmethod
    def transform_gemini_to_openai_response(response_content: bytes) -> Dict[str, Any]:
        """将 Gemini 响应转换为 OpenAI 响应格式"""
        try:
            gemini_response = json.loads(response_content)
            
            response_text = ""
            finish_reason = "stop"
            
            if gemini_response.get("candidates"):
                candidate = gemini_response["candidates"][0]
                response_text = ResponseTransformer._extract_content_text(candidate)
                
                if candidate.get("finishReason"):
                    finish_reason = ResponseTransformer._get_finish_reason(
                        candidate["finishReason"]
                    )
            
            usage_metadata = gemini_response.get("usageMetadata", {})
            prompt_tokens = usage_metadata.get("promptTokenCount", 0)
            completion_tokens = usage_metadata.get("candidatesTokenCount", 0)
            
            openai_response = {
                "id": ResponseTransformer._generate_response_id(gemini_response),
                "object": "chat.completion",
                "created": int(gemini_response.get("createTime", time.time())),
                "model": gemini_response.get("model", "gemini-pro"),
                "choices": [{
                    "index": 0,
                    "message": {"role": "assistant", "content": response_text},
                    "finish_reason": finish_reason,
                }],
                "usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens,
                },
            }
            
            return openai_response
        
        except json.JSONDecodeError:
            logger.error("Gemini 响应不是有效的 JSON 格式")
            raise ProxyError(500, "Invalid JSON in Gemini response")
        except Exception as e:
            logger.error(f"转换 Gemini 响应到 OpenAI 格式时出错: {e}", exc_info=True)
            raise ProxyError(500, f"Error transforming response: {str(e)}", e)


class StreamAdapter:
    """适配 Gemini 流式响应到 OpenAI 流式响应格式的适配器"""

    def __init__(self, stream):
        self.stream = stream

    async def aiter_bytes(self):
        async for chunk in ResponseTransformer.transform_gemini_to_openai_streaming(self.stream):
            yield chunk.encode("utf-8")


class ProxyHandler:
    """代理请求处理器"""
    
    def __init__(self, db):
        self.db = db
        self.config_manager = ConfigManager()
        self.auth_validator = AuthValidator()
        self.key_manager = KeyManager()
        self.request_transformer = RequestTransformer()
        self.response_transformer = ResponseTransformer()
    
    async def _validate_request_path(self, request: Request, expected_suffix: str) -> None:
        """验证请求路径"""
        expected_path = settings.OPENAI_PROXY_PREFIX + expected_suffix
        if not request.url.path.startswith(expected_path):
            logger.warning(f"代理收到意外路径的请求: {request.url.path}")
            raise ProxyError(404, "Not Found")
    
    async def _setup_authentication(self, request: Request) -> Tuple[str, Any]:
        """设置认证并返回目标 URL 和 API 密钥对象"""
        target_url = self.config_manager.get_target_url(self.db)
        internal_token = self.config_manager.get_internal_api_token(self.db)
        
        self.auth_validator.validate_internal_api_key(request, internal_token)
        
        api_key_obj = self.key_manager.get_active_api_key(self.db)
        
        return target_url, api_key_obj
    
    async def _make_request(
        self,
        client: httpx.AsyncClient,
        method: str,
        url: str,
        headers: Dict[str, str],
        params: Dict[str, str] = None,
        json_data: Dict[str, Any] = None,
        stream: bool = False
    ):
        """发起 HTTP 请求"""
        try:
            if stream:
                return client.stream(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params or {},
                    json=json_data
                )
            else:
                return await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params or {},
                    json=json_data
                )
        except httpx.RequestError as e:
            logger.error(f"请求 {url} 时发生错误: {e}", exc_info=True)
            raise ProxyError(500, f"Proxy request failed: {e}", e)
    
    async def _handle_preview_model_fallback(
        self,
        client: httpx.AsyncClient,
        target_url: str,
        headers: Dict[str, str],
        gemini_request_body: Dict[str, Any],
        api_key_obj: Any,
        gemini_path: str
    ):
        """处理预览模型的回退逻辑"""
        logger.warning(f"预览版模型 {gemini_path} 认证失败 (401)，尝试使用标准模型")
        
        new_gemini_path = f"models/{FALLBACK_MODEL}:generateContent"
        new_full_target_url = f"{target_url}/{new_gemini_path}"
        
        logger.info(f"回退到标准模型，新的目标 URL: {new_full_target_url}")
        
        response = await self._make_request(
            client=client,
            method="POST",
            url=new_full_target_url,
            headers=headers,
            json_data=gemini_request_body
        )
        
        success = 200 <= response.status_code < 300
        self.key_manager.update_key_usage(self.db, api_key_obj, success)
        
        return response
    
    async def _handle_error_response(self, response) -> Response:
        """处理错误响应"""
        try:
            if hasattr(response, "aread"):
                error_body = await response.aread()
            elif hasattr(response, "content"):
                error_body = response.content
            else:
                error_body = b""
            
            return Response(
                content=error_body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.headers.get("content-type", "application/json"),
            )
        except Exception as e:
            logger.error(f"处理错误响应时出错: {e}")
            raise ProxyError(response.status_code, "Proxy request failed and could not read error body.")


@router.api_route("/chat/completions", methods=["POST"])
async def openai_chat_completions(request: Request, db: db_dependency):
    """OpenAI 聊天补全 API 端点，将请求转换为 Gemini 格式并返回转换后的响应"""
    handler = ProxyHandler(db)
    
    try:
        logger.info("收到 OpenAI 聊天补全请求")
        
        target_url, api_key_obj = await handler._setup_authentication(request)
        logger.info(f"目标 Gemini API URL: {target_url}")
        
        body = await request.body()
        gemini_path, gemini_request_body, stream = handler.request_transformer.transform_openai_to_gemini_request(
            request, body
        )
        
        if not gemini_path:
            raise ProxyError(400, "无法解析请求体")
        
        full_target_url = f"{target_url}/{gemini_path}"
        logger.info(f"转换后的 Gemini 目标 URL: {full_target_url}")
        logger.info(f"Target API Key being sent: {api_key_obj.key_value[:8]}...")
        
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": api_key_obj.key_value,
        }
        
        params = {"alt": "sse"} if stream else {}
        
        proxy_response = None
        proxy_response_context = None
        
        try:
            if stream:
                proxy_response_context = httpx_client.stream(
                    method=request.method,
                    url=full_target_url,
                    headers=headers,
                    params=params,
                    json=gemini_request_body,
                )
                proxy_response = await proxy_response_context.__aenter__()
            else:
                proxy_response = await httpx_client.request(
                    method=request.method,
                    url=full_target_url,
                    headers=headers,
                    params=params,
                    json=gemini_request_body,
                )
            
            success = 200 <= proxy_response.status_code < 300
            if proxy_response.status_code == 429:
                handler.key_manager.update_key_usage(db, api_key_obj, False, status_override="exhausted")
            else:
                handler.key_manager.update_key_usage(db, api_key_obj, success)
            record_api_call_log(db, api_key_obj.id)

            if proxy_response.status_code == 401 and "preview" in gemini_path:
                logger.warning(f"预览版模型 {gemini_path} 认证失败 (401)，尝试使用标准模型")

                if stream and proxy_response_context:
                    await proxy_response_context.__aexit__(None, None, None)
                elif proxy_response:
                    await proxy_response.aclose()

                new_gemini_path = f"models/{FALLBACK_MODEL}:generateContent"
                new_full_target_url = f"{target_url}/{new_gemini_path}"

                logger.info(f"回退到标准模型，新的目标 URL: {new_full_target_url}")

                proxy_response = await httpx_client.request(
                    method=request.method,
                    url=new_full_target_url,
                    headers=headers,
                    json=gemini_request_body,
                )

                success = 200 <= proxy_response.status_code < 300
                if proxy_response.status_code == 429:
                    handler.key_manager.update_key_usage(db, api_key_obj, False, status_override="exhausted")
                else:
                    handler.key_manager.update_key_usage(db, api_key_obj, success)
                record_api_call_log(db, api_key_obj.id)

            if not (200 <= proxy_response.status_code < 300):
                logger.error(f"最终代理请求失败，状态码: {proxy_response.status_code}")

                if stream and proxy_response_context:
                    await proxy_response_context.__aexit__(None, None, None)
                elif proxy_response:
                    await proxy_response.aclose()

                return Response(
                    content=proxy_response.content,
                    status_code=proxy_response.status_code,
                    headers=dict(proxy_response.headers),
                    media_type=proxy_response.headers.get("content-type", "application/json"),
                )

            if stream:
                logger.info("返回流式响应")
                return StreamingResponse(
                    content=StreamAdapter(proxy_response.aiter_bytes()).aiter_bytes(),
                    status_code=proxy_response.status_code,
                    headers=dict(proxy_response.headers),
                    background=lambda: proxy_response_context.__aexit__(None, None, None),
                )
            else:
                logger.info("返回非流式响应")
                openai_response = handler.response_transformer.transform_gemini_to_openai_response(
                    proxy_response.content
                )
                return Response(
                    content=json.dumps(openai_response).encode(),
                    status_code=proxy_response.status_code,
                    headers=dict(proxy_response.headers),
                    media_type="application/json",
                )

        except httpx.RequestError as exc:
            logger.error(f"请求错误: {exc}", exc_info=True)
            if 'api_key_obj' in locals():
                handler.key_manager.update_key_usage(db, api_key_obj, False, status_override="error")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Proxy request failed: {exc}",
            )
        except Exception as e:
            logger.error(f"处理请求时发生未预期错误: {e}", exc_info=True)
            if 'api_key_obj' in locals():
                handler.key_manager.update_key_usage(db, api_key_obj, False, status_override="error")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An unexpected error occurred: {e}",
            )

    except ProxyError as e:
        if 'api_key_obj' in locals():
            handler.key_manager.update_key_usage(db, api_key_obj, False, status_override="error")
        raise HTTPException(status_code=e.status_code, detail=e.detail)

    except Exception as e:
        if 'api_key_obj' in locals():
            handler.key_manager.update_key_usage(db, api_key_obj, False, status_override="error")
        logger.error(f"聊天补全请求处理时发生未预期错误: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {e}",
        )


class ImageRequestTransformer:
    """图像请求转换器"""
    
    @staticmethod
    def parse_size(size_str: str) -> Tuple[int, int]:
        """解析图像尺寸字符串"""
        size_mapping = {
            "256x256": (256, 256),
            "512x512": (512, 512),
            "1024x1024": (1024, 1024),
        }
        
        if size_str in size_mapping:
            return size_mapping[size_str]
        
        if "x" in size_str:
            try:
                width_str, height_str = size_str.split("x")
                width, height = int(width_str), int(height_str)
                return width, height
            except (ValueError, TypeError):
                pass
        
        return 1024, 1024
    
    @staticmethod
    def transform_openai_to_gemini_image_request(openai_request: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
        """将 OpenAI 图像生成请求转换为 Gemini 聊天格式"""
        prompt = openai_request.get("prompt", "")
        if not prompt:
            raise ProxyError(400, "缺少必需的 'prompt' 参数")
        
        model = openai_request.get("model", "gemini-2.0-flash-exp-image-generation")
        
        gemini_request = {
            "contents": [
                {
                    "parts": [{"text": prompt}],
                    "role": "user"
                }
            ],
            "safetySettings": [
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "OFF"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "OFF"},
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "OFF"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "OFF"},
                {"category": "HARM_CATEGORY_CIVIC_INTEGRITY", "threshold": "BLOCK_NONE"}
            ],
            "generationConfig": {
                "temperature": openai_request.get("temperature", 0.7),
                "responseMimeType": "text/plain",
                "responseModalities": ["TEXT", "IMAGE"]
            }
        }
        
        return gemini_request, model
    
    @staticmethod
    def transform_imagen_to_openai_response(imagen_response: Dict[str, Any], n: int) -> Dict[str, Any]:
        """将 Imagen 响应转换为 OpenAI 格式"""
        image_data = []
        images = imagen_response.get("images", [])
        
        for i in range(min(n, len(images))):
            image = images[i]
            image_data.append({
                "url": image.get("publicImageUrl", ""),
                "b64_json": image.get("base64", ""),
            })
        
        return {
            "created": int(imagen_response.get("createTime", 0)) or int(time.time()),
            "data": image_data,
        }


@router.api_route("/images/generations", methods=["POST"])
async def openai_image_generations(request: Request, db: db_dependency):
    """OpenAI 图像生成 API 端点，将请求转换为 Gemini Imagen 格式并返回转换后的响应"""
    handler = ProxyHandler(db)
    
    try:
        logger.info("收到 OpenAI 图像生成请求")
        
        target_url, api_key_obj = await handler._setup_authentication(request)
        logger.info(f"目标 Gemini API URL: {target_url}")
        
        body = await request.body()
        try:
            openai_request = json.loads(body)
        except json.JSONDecodeError:
            raise ProxyError(400, "无效的 JSON 请求体")
        
        gemini_request, model = ImageRequestTransformer.transform_openai_to_gemini_image_request(openai_request)
        n = openai_request.get("n", 1)
        
        full_target_url = f"{target_url}/models/{model}:streamGenerateContent"
        logger.info(f"Gemini 图像生成目标 URL: {full_target_url}")
        
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": api_key_obj.key_value,
        }
        
        params = {"alt": "sse"}
        
        response = await httpx_client.request(
            method="POST",
            url=full_target_url,
            headers=headers,
            params=params,
            json=gemini_request
        )
        
        success = 200 <= response.status_code < 300
        if response.status_code == 429:
            handler.key_manager.update_key_usage(db, api_key_obj, False, status_override="exhausted")
        else:
            handler.key_manager.update_key_usage(db, api_key_obj, success)
        record_api_call_log(db, api_key_obj.id)
        
        if not success:
            error_detail = "图像生成请求失败"
            try:
                error_text = response.text
                error_detail = f"图像生成请求失败: {error_text}"
            except Exception:
                pass
            if response.status_code == 429:
                raise ProxyError(response.status_code, "Too Many Requests")
            else:
                raise ProxyError(response.status_code, error_detail)
        
        try:
            response_text = response.text
            images_data = []
            
            for line in response_text.split('\n'):
                if line.startswith('data: ') and line != 'data: [DONE]':
                    try:
                        chunk_data = json.loads(line[6:])
                        candidates = chunk_data.get('candidates', [])
                        for candidate in candidates:
                            content = candidate.get('content', {})
                            parts = content.get('parts', [])
                            for part in parts:
                                if 'inlineData' in part:
                                    inline_data = part['inlineData']
                                    images_data.append({
                                        "url": "",
                                        "b64_json": inline_data.get('data', '')
                                    })
                    except json.JSONDecodeError:
                        continue
            
            if not images_data:
                images_data = [{"url": "", "b64_json": ""}]
            
            openai_response = {
                "created": int(time.time()),
                "data": images_data[:n]
            }
            
            return Response(
                content=json.dumps(openai_response),
                status_code=200,
                media_type="application/json",
            )
            
        except Exception as e:
            logger.error(f"解析图像生成响应时出错: {e}")
            raise ProxyError(500, f"解析图像生成响应失败: {str(e)}")
    
    except ProxyError as e:
        if 'api_key_obj' in locals():
            handler.key_manager.update_key_usage(db, api_key_obj, False)
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    
    except Exception as e:
        if 'api_key_obj' in locals():
            handler.key_manager.update_key_usage(db, api_key_obj, False)
        logger.error(f"处理图像生成请求时出现错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"处理图像生成请求时出错: {str(e)}")

class ImageEditRequestTransformer:
    """图像编辑请求转换器"""
    
    @staticmethod
    def transform_openai_to_gemini_image_edit_request(openai_request: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
        """
        将 OpenAI 图像编辑请求转换为 Gemini Imagen 格式
        
        OpenAI 图像编辑 API 参数:
        - image: 要编辑的图像文件 (PNG 格式，最大 4MB)
        - mask: 掩码图像文件 (PNG 格式，最大 4MB，可选)
        - prompt: 描述编辑内容的文本 (最大 1000 字符)
        - n: 生成图像数量 (1-10，默认 1)
        - size: 图像尺寸 ("256x256", "512x512", "1024x1024"，默认 "1024x1024")
        - response_format: 响应格式 ("url" 或 "b64_json"，默认 "url")
        - user: 用户标识符 (可选)
        """
        
        prompt = openai_request.get("prompt", "")
        if not prompt:
            raise ProxyError(400, "prompt 参数是必需的")
        
        image_data = openai_request.get("image")
        if not image_data:
            raise ProxyError(400, "image 参数是必需的")
        
        mask_data = openai_request.get("mask")

        size = openai_request.get("size", "1024x1024")
        try:
            width, height = ImageRequestTransformer.parse_size(size)
        except ValueError as e:
            raise ProxyError(400, f"无效的尺寸格式: {e}")
        
        enhanced_prompt = f"根据以下描述编辑或改进图像: {prompt}"
        
        if mask_data:
            enhanced_prompt += " (仅编辑掩码指定的区域)"
        
        if image_data:
            enhanced_prompt = f"基于提供的图像，{prompt}。保持原图的整体风格和构图，只改进指定的部分。"
        
        contents = [
            {
                "role": "user",
                "parts": [
                    {"text": enhanced_prompt}
                ]
            }
        ]
        
        if image_data:
            if image_data.startswith('data:image/'):
                try:
                    mime_type = image_data.split(';')[0].replace('data:', '')
                    data = image_data.split('base64,')[1]
                    contents[0]["parts"].append({
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": data
                        }
                    })
                except (IndexError, ValueError):
                    raise ProxyError(400, "无效的图像数据格式")
            else:
                contents[0]["parts"].append({
                    "inline_data": {
                        "mime_type": "image/png",
                        "data": image_data
                    }
                })
        
        gemini_request = {
            "contents": contents,
            "generationConfig": {
                "temperature": 0.8,
                "topP": 0.95,
                "topK": 40,
                "maxOutputTokens": 4096
            }
        }
        
        model = openai_request.get("model", "gemini-2.0-flash-exp-image-generation")
        
        if "image" not in model.lower() and "vision" not in model.lower():
            model = "gemini-2.0-flash-exp-image-generation"
        
        return gemini_request, model


@router.api_route("/images/edits", methods=["POST"])
async def openai_image_edits(request: Request, db: db_dependency):
    """OpenAI 图像编辑 API 端点，将请求转换为 Gemini 格式并返回转换后的响应"""
    handler = ProxyHandler(db)
    
    try:
        logger.info("收到 OpenAI 图像编辑请求")
        
        target_url, api_key_obj = await handler._setup_authentication(request)
        logger.info(f"目标 Gemini API URL: {target_url}")
        
        content_type = request.headers.get("content-type", "")
        
        if "multipart/form-data" in content_type:
            import base64
            
            form_data = await request.form()
            
            openai_request = {}
            
            if "prompt" in form_data:
                openai_request["prompt"] = form_data["prompt"]
            if "model" in form_data:
                openai_request["model"] = form_data["model"]
            if "n" in form_data:
                try:
                    openai_request["n"] = int(form_data["n"])
                except ValueError:
                    openai_request["n"] = 1
            if "size" in form_data:
                openai_request["size"] = form_data["size"]
            if "response_format" in form_data:
                openai_request["response_format"] = form_data["response_format"]
            
            image_field_names = ["image", "image[]"]
            for field_name in image_field_names:
                if field_name in form_data:
                    image_file = form_data[field_name]
                    if hasattr(image_file, 'read'):
                        image_data = await image_file.read()
                        image_base64 = base64.b64encode(image_data).decode('utf-8')
                        openai_request["image"] = image_base64
                    else:
                        openai_request["image"] = str(image_file)
                    break
            
            mask_field_names = ["mask", "mask[]"]
            for field_name in mask_field_names:
                if field_name in form_data:
                    mask_file = form_data[field_name]
                    if hasattr(mask_file, 'read'):
                        mask_data = await mask_file.read()
                        mask_base64 = base64.b64encode(mask_data).decode('utf-8')
                        openai_request["mask"] = mask_base64
                    else:
                        openai_request["mask"] = str(mask_file)
                    break
        else:
            body = await request.body()
            try:
                openai_request = json.loads(body)
            except json.JSONDecodeError:
                raise ProxyError(400, "请求体不是有效的 JSON 格式")
        
        try:
            gemini_request, model = ImageEditRequestTransformer.transform_openai_to_gemini_image_edit_request(openai_request)
            n = openai_request.get("n", 1)
            
            full_target_url = f"{target_url}/models/{model}:generateContent"
            logger.info(f"Gemini 图像编辑目标 URL: {full_target_url}")
            
            headers = {
                "Content-Type": "application/json",
                "x-goog-api-key": api_key_obj.key_value,
            }
            
            response = await httpx_client.request(
                method="POST",
                url=full_target_url,
                headers=headers,
                json=gemini_request
            )
            
            success = 200 <= response.status_code < 300
            if response.status_code == 429:
                handler.key_manager.update_key_usage(db, api_key_obj, False, status_override="exhausted")
            else:
                handler.key_manager.update_key_usage(db, api_key_obj, success)
            record_api_call_log(db, api_key_obj.id)
            
            if not success:
                error_detail = "图像编辑请求失败"
                try:
                    error_text = response.text
                    error_detail = f"图像编辑请求失败: {error_text}"
                except Exception:
                    pass
                if response.status_code == 429:
                    raise ProxyError(response.status_code, "Too Many Requests")
                else:
                    raise ProxyError(response.status_code, error_detail)
            
            try:
                gemini_response = response.json()
                
                response_text = ""
                if gemini_response.get("candidates"):
                    candidate = gemini_response["candidates"][0]
                    if candidate.get("content", {}).get("parts"):
                        for part in candidate["content"]["parts"]:
                            if part.get("text"):
                                response_text += part["text"]
                
                openai_response = {
                    "created": int(time.time()),
                    "data": [{
                        "url": "",
                        "b64_json": "",
                        "description": response_text or "图像编辑请求已处理"
                    } for _ in range(n)]
                }
                
                return Response(
                    content=json.dumps(openai_response),
                    status_code=200,
                    media_type="application/json",
                )
                
            except Exception as e:
                logger.error(f"解析图像编辑响应时出错: {e}")
                raise ProxyError(500, f"解析图像编辑响应失败: {str(e)}")
        
        except ProxyError:
            raise
        except Exception as e:
            logger.error(f"图像编辑请求处理失败: {e}", exc_info=True)
            
            try:
                handler.key_manager.update_key_usage(db, api_key_obj, False)
            except Exception as update_error:
                logger.error(f"更新密钥使用状态失败: {update_error}")
            
            raise ProxyError(500, f"图像编辑处理失败: {str(e)}", e)
    
    except ProxyError as e:
        if 'api_key_obj' in locals():
            handler.key_manager.update_key_usage(db, api_key_obj, False)
        logger.error(f"代理错误: {e.detail}")
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        if 'api_key_obj' in locals():
            handler.key_manager.update_key_usage(db, api_key_obj, False)
        logger.error(f"未预期的错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="内部服务器错误")

class ModelListTransformer:
    """模型列表转换器"""
    
    @staticmethod
    def transform_gemini_models_to_openai_format(gemini_models: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """将 Gemini 模型列表转换为 OpenAI 格式"""
        openai_models = []
        current_time = int(time.time())
        
        for model in gemini_models:
            model_name = model.get("name", "")
            model_id = model_name.split("/")[-1] if model_name else ""
            
            if model_id:
                openai_models.append({
                    "id": model_id,
                    "object": "model",
                    "created": current_time,
                    "owned_by": "google",
                    "permission": [],
                    "root": model_id,
                    "parent": None,
                })
        
        return openai_models


@router.get("/models")
async def list_models(request: Request, db: db_dependency):
    """OpenAI 模型列表 API 端点，从 Gemini API 获取支持的模型列表并返回"""
    handler = ProxyHandler(db)
    
    try:
        logger.info("收到获取模型列表请求")
        
        target_url, api_key_obj = await handler._setup_authentication(request)
        
        full_target_url = f"{target_url}/models"
        logger.info(f"获取 Gemini 模型列表的 URL: {full_target_url}")
        
        try:
            response = await httpx_client.get(
                f"{full_target_url}?key={api_key_obj.key_value}",
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            
            if response.status_code == 429:
                handler.key_manager.update_key_usage(db, api_key_obj, False, status_override="exhausted")
            else:
                handler.key_manager.update_key_usage(db, api_key_obj, True)
            record_api_call_log(db, api_key_obj.id)
            
            gemini_models_response = response.json()
            gemini_models = gemini_models_response.get("models", [])
            openai_models = ModelListTransformer.transform_gemini_models_to_openai_format(gemini_models)
            
            return Response(
                content=json.dumps({"object": "list", "data": openai_models}),
                status_code=200,
                media_type="application/json",
            )
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                handler.key_manager.update_key_usage(db, api_key_obj, False, status_override="exhausted")
                raise ProxyError(e.response.status_code, "Too Many Requests")
            else:
                handler.key_manager.update_key_usage(db, api_key_obj, False, status_override="error")
                logger.error(
                    f"从 Gemini 获取模型列表时收到错误状态码: {e.response.status_code} - {e.response.text}",
                    exc_info=True,
                )
                raise ProxyError(
                    e.response.status_code,
                    f"从 Gemini 获取模型列表失败: {e.response.text}"
                )
        
        except httpx.RequestError as e:
            handler.key_manager.update_key_usage(db, api_key_obj, False, status_override="error")
            logger.error(f"从 Gemini 获取模型列表失败: {e}", exc_info=True)
            raise ProxyError(500, f"无法从 Gemini 获取模型列表: {str(e)}")
    
    except ProxyError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    
    except Exception as e:
        if 'api_key_obj' in locals():
            handler.key_manager.update_key_usage(db, api_key_obj, False)
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
    """处理未实现的 OpenAI API 端点"""
    logger.warning(f"收到未实现的 OpenAI API 端点请求: {path}")
    
    error_response = {
        "error": {
            "message": f"未实现的 OpenAI API 端点: {path}",
            "type": "not_implemented",
            "code": "not_implemented",
        }
    }
    
    return Response(
        content=json.dumps(error_response),
        status_code=501,
        media_type="application/json",
    )
