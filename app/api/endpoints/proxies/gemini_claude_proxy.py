"""
Claude 到 Gemini 代理服务模块

该模块提供了将 Claude 格式的 API 请求转换为 Gemini 格式，
并将 Gemini 的响应转换回 Claude 格式的代理服务。

支持的功能：
- Claude Messages API (/v1/messages)
"""

import json
import logging
from typing import Tuple, Dict, Any, Optional, List

import httpx
from starlette import status
from fastapi import APIRouter, Request, HTTPException, Response
from fastapi.responses import StreamingResponse

from .base_proxy import update_key_status_based_on_response, record_api_call_log, httpx_client
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

router = APIRouter(
    prefix="/claude",
    tags=["Claude to Gemini Proxy"]
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
        key_obj = crud.api_keys.get_active_api_key_with_token_bucket(db)
        if not key_obj:
            raise ProxyError(503, "没有可用的活跃目标 API 密钥。")
        return key_obj
    
    @staticmethod
    def update_key_usage(db, api_key, success: bool, status_override: str = None) -> None:
        """更新密钥使用状态"""
        try:
            max_failed_count = ConfigManager.get_max_failed_count(db)
            update_key_status_based_on_response(db, api_key, success, max_failed_count, status_override)
            record_api_call_log(db, api_key.id)
        except Exception as e:
            logger.error(f"更新密钥使用状态失败: {e}")


class ClaudeRequestTransformer:
    """Claude 请求转换器"""
    
    @staticmethod
    def _process_claude_content_item(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """处理 Claude 内容项目"""
        if item.get("type") == "text":
            return {"text": item.get("text", "")}
        elif item.get("type") == "image":
            source = item.get("source", {})
            if source.get("type") == "base64":
                media_type = source.get("media_type", "image/jpeg")
                data = source.get("data", "")
                return {"inline_data": {"mime_type": media_type, "data": data}}
        return None
    
    @staticmethod
    def _convert_claude_messages_to_contents(messages: List[Dict[str, Any]], system: str = None) -> List[Dict[str, Any]]:
        """将 Claude 消息格式转换为 Gemini contents 格式"""
        contents = []
        
        if system:
            if isinstance(system, list):
                for sys_item in system:
                    if isinstance(sys_item, dict) and sys_item.get("type") == "text":
                        contents.append({"role": "user", "parts": [{"text": sys_item.get("text", "")}]})
            else:
                contents.append({"role": "user", "parts": [{"text": str(system)}]})
        
        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")
            
            gemini_role = "user" if role == "user" else "model"
            
            if isinstance(content, list):
                parts = []
                for item in content:
                    if isinstance(item, dict):
                        part = ClaudeRequestTransformer._process_claude_content_item(item)
                        if part:
                            parts.append(part)
                    else:
                        parts.append({"text": str(item)})
                if parts:
                    contents.append({"role": gemini_role, "parts": parts})
            else:
                contents.append({"role": gemini_role, "parts": [{"text": str(content)}]})
        
        return contents
    
    @staticmethod
    def _build_claude_generation_config(claude_request: Dict[str, Any]) -> Dict[str, Any]:
        """构建 Claude 生成配置"""
        config = {
            "temperature": claude_request.get("temperature", DEFAULT_TEMPERATURE),
            "topP": claude_request.get("top_p", DEFAULT_TOP_P),
            "topK": claude_request.get("top_k", DEFAULT_TOP_K),
            "stopSequences": claude_request.get("stop_sequences", []),
        }
        
        max_tokens = claude_request.get("max_tokens")
        if max_tokens is not None:
            config["maxOutputTokens"] = max_tokens
        
        return config
    
    @staticmethod
    def transform_claude_to_gemini_request(
        request: Request, body: bytes
    ) -> Tuple[str, Dict[str, Any], bool]:
        """
        将 Claude 格式的请求转换为 Gemini 格式
        
        参数:
            request: FastAPI 请求对象
            body: 请求体字节数据
        
        返回:
            tuple: (Gemini 路径, Gemini 请求体字典, 是否流式响应)
        """
        try:
            if not body:
                raise ProxyError(400, "请求体不能为空")
            
            claude_request = json.loads(body)
            stream = claude_request.get("stream", False)
            
            model = claude_request.get("model", "gemini-pro")
            logger.info(f"原始请求模型: {model}")
            
            # 将 Claude 模型名称映射到 Gemini 模型名称
            claude_to_gemini_model_mapping = {
                "claude-3-5-sonnet-20241022": "gemini-1.5-pro",
                "claude-3-5-sonnet-20240620": "gemini-1.5-pro",
                "claude-3-5-haiku-20241022": "gemini-1.5-flash",
                "claude-3-opus-20240229": "gemini-1.5-pro",
                "claude-3-sonnet-20240229": "gemini-1.5-pro",
                "claude-3-haiku-20240307": "gemini-1.5-flash",
                "claude-sonnet-4-20250514": "gemini-2.5-flash",
                "claude-instant-1.2": "gemini-1.5-flash",
            }
            
            if model.startswith("claude-"):
                gemini_model = claude_to_gemini_model_mapping.get(model, "gemini-1.5-pro")
                logger.info(f"映射 Claude 模型 '{model}' 到 Gemini 模型 '{gemini_model}'")
            else:
                gemini_model = model
                logger.info(f"使用原始模型名称: {gemini_model}")
            
            if "preview" in gemini_model.lower():
                logger.info(f"请求使用预览版模型: {gemini_model}，如果认证失败可能需要更换为标准模型")
            
            messages = claude_request.get("messages", [])
            system = claude_request.get("system")
            contents = ClaudeRequestTransformer._convert_claude_messages_to_contents(messages, system)
            
            gemini_request = {
                "contents": contents,
                "generationConfig": ClaudeRequestTransformer._build_claude_generation_config(claude_request),
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
            logger.error(f"转换 Claude 请求到 Gemini 请求时出错: {e}", exc_info=True)
            raise ProxyError(500, f"Error transforming request: {str(e)}", e)


class ClaudeResponseTransformer:
    """Claude 响应转换器"""
    
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
    def _get_claude_stop_reason(gemini_reason: str) -> str:
        """转换结束原因为 Claude 格式"""
        mapping = {
            "STOP": "end_turn",
            "MAX_TOKENS": "max_tokens",
        }
        return mapping.get(gemini_reason, "end_turn")
    
    @staticmethod
    def _generate_claude_response_id() -> str:
        """生成 Claude 格式的响应 ID"""
        import uuid
        return f"msg_{uuid.uuid4().hex[:24]}"
    
    @staticmethod
    async def transform_gemini_to_claude_streaming(stream):
        """将 Gemini 流式响应转换为 Claude 流式响应格式"""
        try:
            message_id = ClaudeResponseTransformer._generate_claude_response_id()
            
            start_event = {
                "type": "message_start",
                "message": {
                    "id": message_id,
                    "type": "message",
                    "role": "assistant",
                    "content": [],
                    "model": "gemini-pro",
                    "stop_reason": None,
                    "stop_sequence": None,
                    "usage": {"input_tokens": 0, "output_tokens": 0}
                }
            }
            yield f"event: message_start\ndata: {json.dumps(start_event)}\n\n"
            
            content_start_event = {
                "type": "content_block_start",
                "index": 0,
                "content_block": {"type": "text", "text": ""}
            }
            yield f"event: content_block_start\ndata: {json.dumps(content_start_event)}\n\n"
            
            async for chunk in stream:
                if not chunk.strip():
                    continue
                
                try:
                    chunk_text = chunk.decode("utf-8")
                    if chunk_text.startswith("data: "):
                        chunk_text = chunk_text[6:]
                    
                    gemini_chunk = json.loads(chunk_text)
                    candidate = gemini_chunk.get("candidates", [{}])[0]
                    
                    content_text = ClaudeResponseTransformer._extract_content_text(candidate)
                    
                    if content_text:
                        delta_event = {
                            "type": "content_block_delta",
                            "index": 0,
                            "delta": {"type": "text_delta", "text": content_text}
                        }
                        yield f"event: content_block_delta\ndata: {json.dumps(delta_event)}\n\n"
                    
                    if candidate.get("finishReason"):
                        stop_reason = ClaudeResponseTransformer._get_claude_stop_reason(
                            candidate["finishReason"]
                        )
                        
                        content_stop_event = {
                            "type": "content_block_stop",
                            "index": 0
                        }
                        yield f"event: content_block_stop\ndata: {json.dumps(content_stop_event)}\n\n"
                        
                        usage_metadata = gemini_chunk.get("usageMetadata", {})
                        message_stop_event = {
                            "type": "message_stop",
                            "message": {
                                "id": message_id,
                                "type": "message",
                                "role": "assistant",
                                "content": [{"type": "text", "text": content_text}],
                                "model": gemini_chunk.get("model", "gemini-pro"),
                                "stop_reason": stop_reason,
                                "stop_sequence": None,
                                "usage": {
                                    "input_tokens": usage_metadata.get("promptTokenCount", 0),
                                    "output_tokens": usage_metadata.get("candidatesTokenCount", 0)
                                }
                            }
                        }
                        yield f"event: message_stop\ndata: {json.dumps(message_stop_event)}\n\n"
                        break
                
                except json.JSONDecodeError:
                    continue
                except Exception as e:
                    logger.error(f"处理 Claude 流式响应块时出错: {e}")
                    continue
        
        except Exception as e:
            import httpx
            if isinstance(e, (httpx.ReadError, httpx.RemoteProtocolError, httpx.NetworkError)):
                logger.warning(f"网络连接问题导致流式响应中断: {type(e).__name__}: {e}")
            else:
                logger.error(f"转换 Gemini 到 Claude 流式响应时出错: {e}", exc_info=True)
            
            try:
                error_event = {
                    "type": "error",
                    "error": {
                        "type": "api_error",
                        "message": "Stream processing error"
                    }
                }
                yield f"event: error\ndata: {json.dumps(error_event)}\n\n"
            except Exception as cleanup_error:
                logger.error(f"清理 Claude 流式响应时出错: {cleanup_error}")
    
    @staticmethod
    def transform_gemini_to_claude_response(response_content: bytes) -> Dict[str, Any]:
        """将 Gemini 响应转换为 Claude 响应格式"""
        try:
            gemini_response = json.loads(response_content)
            
            response_text = ""
            stop_reason = "end_turn"
            
            if gemini_response.get("candidates"):
                candidate = gemini_response["candidates"][0]
                response_text = ClaudeResponseTransformer._extract_content_text(candidate)
                
                if candidate.get("finishReason"):
                    stop_reason = ClaudeResponseTransformer._get_claude_stop_reason(
                        candidate["finishReason"]
                    )
            
            usage_metadata = gemini_response.get("usageMetadata", {})
            input_tokens = usage_metadata.get("promptTokenCount", 0)
            output_tokens = usage_metadata.get("candidatesTokenCount", 0)
            
            claude_response = {
                "id": ClaudeResponseTransformer._generate_claude_response_id(),
                "type": "message",
                "role": "assistant",
                "content": [{"type": "text", "text": response_text}],
                "model": gemini_response.get("model", "gemini-pro"),
                "stop_reason": stop_reason,
                "stop_sequence": None,
                "usage": {
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens
                }
            }
            
            return claude_response
        
        except json.JSONDecodeError:
            logger.error("Gemini 响应不是有效的 JSON 格式")
            raise ProxyError(500, "Invalid JSON in Gemini response")
        except Exception as e:
            logger.error(f"转换 Gemini 响应到 Claude 格式时出错: {e}", exc_info=True)
            raise ProxyError(500, f"Error transforming response: {str(e)}", e)


class ClaudeStreamAdapter:
    """适配 Gemini 流式响应到 Claude 流式响应格式的适配器"""

    def __init__(self, stream):
        self.stream = stream

    async def aiter_bytes(self):
        async for chunk in ClaudeResponseTransformer.transform_gemini_to_claude_streaming(self.stream):
            yield chunk.encode("utf-8")


class ProxyHandler:
    """代理请求处理器"""
    
    def __init__(self, db):
        self.db = db
        self.config_manager = ConfigManager()
        self.auth_validator = AuthValidator()
        self.key_manager = KeyManager()
    
    async def _safely_read_response_content(self, response) -> bytes:
        """安全地读取响应内容"""
        try:
            if hasattr(response, 'aread'):
                return await response.aread()
            else:
                return response.content
        except Exception as e:
            logger.warning(f"无法读取响应内容: {e}")
            return b'{"error": {"message": "Failed to read response content"}}'
    
    async def _setup_authentication(self, request: Request) -> Tuple[str, Any]:
        """设置认证并返回目标 URL 和 API 密钥对象"""
        target_url = self.config_manager.get_target_url(self.db)
        internal_token = self.config_manager.get_internal_api_token(self.db)
        
        self.auth_validator.validate_internal_api_key(request, internal_token)
        
        api_key_obj = self.key_manager.get_active_api_key(self.db)
        
        return target_url, api_key_obj


@router.api_route("/v1/messages", methods=["POST"])
async def claude_messages(request: Request, db: db_dependency):
    """Claude Messages API 端点，将请求转换为 Gemini 格式并返回转换后的响应"""
    handler = ProxyHandler(db)
    
    try:
        logger.info("收到 Claude Messages 请求")
        # logger.info(f"请求方法: {request.method}")
        # logger.info(f"请求URL: {request.url}")
        # logger.info(f"请求头: {dict(request.headers)}")
        
        # 检查是否有 beta=true 参数
        beta_param = request.query_params.get("beta")
        if beta_param != "true":
            logger.warning(f"Claude Messages 请求缺少 beta=true 参数: {beta_param}")
        
        target_url, api_key_obj = await handler._setup_authentication(request)
        logger.info(f"目标 Gemini API URL: {target_url}")
        
        body = await request.body()
        # logger.info(f"收到的请求体: {body}")
        # logger.info(f"请求体长度: {len(body)} 字节")
        
        # 尝试解析并打印 JSON 内容
        try:
            if body:
                parsed_body = json.loads(body)
                # logger.info(f"解析后的请求体: {json.dumps(parsed_body, indent=2, ensure_ascii=False)}")
            else:
                logger.warning("请求体为空")
        except json.JSONDecodeError as e:
            logger.error(f"请求体不是有效的 JSON: {e}")
            # logger.info(f"原始请求体内容: {body.decode('utf-8', errors='replace')}")
        
        gemini_path, gemini_request_body, stream = ClaudeRequestTransformer.transform_claude_to_gemini_request(
            request, body
        )
        
        if not gemini_path:
            raise ProxyError(400, "无法解析请求体")
        
        full_target_url = f"{target_url}/{gemini_path}"
        # logger.info(f"转换后的 Gemini 目标 URL: {full_target_url}")
        # logger.info(f"Target API Key being sent: {api_key_obj.key_value[:8]}...")
        # logger.info(f"发送给 Gemini 的请求体: {json.dumps(gemini_request_body, indent=2, ensure_ascii=False)}")
        
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
                handler.key_manager.update_key_usage(db, api_key_obj, False, "exhausted")
            else:
                handler.key_manager.update_key_usage(db, api_key_obj, success)

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
                    handler.key_manager.update_key_usage(db, api_key_obj, False, "exhausted")
                else:
                    handler.key_manager.update_key_usage(db, api_key_obj, success)

            if not (200 <= proxy_response.status_code < 300):
                logger.error(f"最终代理请求失败，状态码: {proxy_response.status_code}")

                error_content = await handler._safely_read_response_content(proxy_response)
                # logger.error(f"Gemini API 错误响应: {error_content.decode('utf-8', errors='replace')}")

                if stream and proxy_response_context:
                    await proxy_response_context.__aexit__(None, None, None)
                elif proxy_response:
                    await proxy_response.aclose()

                try:
                    error_data = json.loads(error_content)
                    claude_error = {
                        "type": "error",
                        "error": {
                            "type": "api_error",
                            "message": error_data.get("error", {}).get("message", "Request failed")
                        }
                    }
                    error_content = json.dumps(claude_error).encode()
                except:
                    claude_error = {
                        "type": "error",
                        "error": {
                            "type": "api_error",
                            "message": "Request failed"
                        }
                    }
                    error_content = json.dumps(claude_error).encode()

                return Response(
                    content=error_content,
                    status_code=proxy_response.status_code,
                    media_type="application/json"
                )

            if stream:
                logger.info("返回 Claude 流式响应")
                response_headers = dict(proxy_response.headers)
                response_headers.pop("content-length", None)
                response_headers.pop("content-encoding", None)
                response_headers["content-type"] = "text/event-stream"
                
                return StreamingResponse(
                    content=ClaudeStreamAdapter(proxy_response.aiter_bytes()).aiter_bytes(),
                    status_code=proxy_response.status_code,
                    headers=response_headers,
                    background=lambda: proxy_response_context.__aexit__(None, None, None),
                )
            else:
                logger.info("返回 Claude 非流式响应")
                response_content = await handler._safely_read_response_content(proxy_response)
                
                claude_response = ClaudeResponseTransformer.transform_gemini_to_claude_response(
                    response_content
                )
                return Response(
                    content=json.dumps(claude_response).encode(),
                    status_code=proxy_response.status_code,
                    media_type="application/json",
                )

        except httpx.RequestError as exc:
            logger.error(f"请求错误: {exc}", exc_info=True)
            if 'api_key_obj' in locals():
                handler.key_manager.update_key_usage(db, api_key_obj, False, "error")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Proxy request failed: {exc}",
            )
        except Exception as e:
            logger.error(f"处理请求时发生未预期错误: {e}", exc_info=True)
            if 'api_key_obj' in locals():
                handler.key_manager.update_key_usage(db, api_key_obj, False, "error")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An unexpected error occurred: {e}",
            )

    except ProxyError as e:
        if 'api_key_obj' in locals():
            handler.key_manager.update_key_usage(db, api_key_obj, False, "error")
        raise HTTPException(status_code=e.status_code, detail=e.detail)

    except Exception as e:
        if 'api_key_obj' in locals():
            handler.key_manager.update_key_usage(db, api_key_obj, False, "error")
        logger.error(f"Claude Messages 请求处理时发生未预期错误: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {e}",
        )