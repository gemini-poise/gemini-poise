import logging
import asyncio
import uuid
import json
from datetime import datetime, timezone
from typing import List, Dict, Type, TypeVar, Optional, Tuple
from enum import Enum
import concurrent.futures
from dataclasses import dataclass

import httpx
from sqlalchemy.orm import Session

from ..api.endpoints.proxies.base_proxy import update_key_status_based_on_response
from ..crud import api_keys as crud_api_keys
from ..crud import config as crud_config
from ..models import models
from ..core.database import SessionLocal

logger = logging.getLogger(__name__)

T = TypeVar("T")

# 常量定义
class ValidationConfig:
    """验证配置常量"""
    MAX_CONCURRENT_WORKERS = 10
    DEFAULT_CONCURRENT_WORKERS = 1
    DEFAULT_TIMEOUT = 30.0  # 增加到30秒匹配前端
    DEFAULT_MAX_FAILED_COUNT = 3
    DEFAULT_MODEL_NAME = "gemini-1.5-flash"
    
    # Redis任务存储配置
    BULK_CHECK_TASK_PREFIX = "bulk_check_task:"
    BULK_CHECK_TASK_TTL = 3600  # 1小时过期（运行中的任务）
    BULK_CHECK_COMPLETED_TASK_TTL = 60  # 1分钟过期（已完成的任务）


class ValidationStatus(Enum):
    """验证状态枚举"""
    VALID = "valid"
    EXHAUSTED = "exhausted"
    ERROR = "error"
    TIMEOUT_ABORT = "timeout_abort"
    NETWORK_ERROR = "network_error"


@dataclass
class ValidationResult:
    """验证结果数据类"""
    key: models.ApiKey
    is_valid: bool
    status: ValidationStatus
    message: str = ""
    
    @property
    def status_str(self) -> str:
        """返回状态字符串"""
        if self.status == ValidationStatus.TIMEOUT_ABORT:
            return "timeout"
        return self.status.value
        
    @property
    def display_message(self) -> str:
        """返回国际化消息键"""
        if self.status == ValidationStatus.VALID:
            return "apiKeys.validation.keyIsValid"
        elif self.status == ValidationStatus.EXHAUSTED:
            return "apiKeys.validation.tooManyRequests"
        elif self.status == ValidationStatus.TIMEOUT_ABORT:
            return "apiKeys.validation.timeoutTemporary"
        else:
            return f"Validation failed: {self.message}"


# HTTP 超时配置
class HttpTimeoutConfig:
    """HTTP 超时配置"""
    CONNECT = 10.0
    READ = 30.0  # 使用配置值
    WRITE = 15.0
    POOL = 5.0

# 验证请求的固定头部和数据
class RequestConfig:
    """请求配置类"""
    HEADERS = {
        "accept": "*/*",
        "accept-language": "zh-CN",
        "content-type": "application/json",
        "priority": "u=1, i",
        "sec-ch-ua": '"Not:A-Brand";v="24", "Chromium";v="134"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "cross-site",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.6998.205 Safari/537.36",
        "x-goog-api-client": "google-genai-sdk/0.13.0 gl-node/web",
    }

    JSON_DATA = {
        "contents": [{"parts": [{"text": "hi"}], "role": "user"}],
        "generationConfig": {
            "maxOutputTokens": 1,
            "thinkingConfig": {
                "includeThoughts": False,
                "thinkingBudget": 0,
            },
        },
    }


class RedisTaskManager:
    """Redis 任务管理器"""
    
    @staticmethod
    def _get_redis_client():
        """获取Redis客户端"""
        from ..crud.api_keys_cache import get_redis_client
        return get_redis_client()

    @classmethod
    def create_bulk_check_task(cls, key_ids: List[int]) -> str:
        """创建批量检测任务，返回任务ID"""
        task_id = str(uuid.uuid4())
        
        try:
            redis_client = cls._get_redis_client()
            
            task_data = {
                "task_id": task_id,
                "key_ids": key_ids,
                "status": "pending",
                "progress": 0,
                "total_keys": len(key_ids),
                "completed_keys": 0,
                "results": [],
                "created_at": datetime.now(timezone.utc).isoformat(),
                "started_at": None,
                "finished_at": None,
                "error": None
            }
            
            redis_key = f"{ValidationConfig.BULK_CHECK_TASK_PREFIX}{task_id}"
            redis_client.setex(redis_key, ValidationConfig.BULK_CHECK_TASK_TTL, json.dumps(task_data))
            
            logger.info(f"Created bulk check task {task_id} for {len(key_ids)} keys")
            return task_id
            
        except Exception as e:
            logger.error(f"Failed to create bulk check task: {e}")
            raise

    @classmethod
    def get_bulk_check_task_status(cls, task_id: str) -> Optional[Dict]:
        """获取批量检测任务状态"""
        try:
            redis_client = cls._get_redis_client()
            redis_key = f"{ValidationConfig.BULK_CHECK_TASK_PREFIX}{task_id}"
            
            task_data = redis_client.get(redis_key)
            if not task_data:
                return None
                
            return json.loads(task_data)
            
        except Exception as e:
            logger.error(f"Failed to get bulk check task status: {e}")
            return None

    @classmethod
    def update_bulk_check_task(cls, task_id: str, **updates):
        """更新批量检测任务状态"""
        try:
            redis_client = cls._get_redis_client()
            redis_key = f"{ValidationConfig.BULK_CHECK_TASK_PREFIX}{task_id}"
            
            task_data = redis_client.get(redis_key)
            if not task_data:
                logger.warning(f"Task {task_id} not found for update")
                return
                
            task_dict = json.loads(task_data)
            task_dict.update(updates)
            
            # 更新进度百分比
            if "completed_keys" in updates:
                total_keys = task_dict.get("total_keys", 1)
                completed = task_dict.get("completed_keys", 0)
                task_dict["progress"] = round((completed / total_keys) * 100, 2)
            
            # 如果任务完成或失败，使用较短的TTL
            task_status = task_dict.get("status", "pending")
            ttl = (ValidationConfig.BULK_CHECK_COMPLETED_TASK_TTL 
                   if task_status in ["completed", "failed"] 
                   else ValidationConfig.BULK_CHECK_TASK_TTL)
            
            redis_client.setex(redis_key, ttl, json.dumps(task_dict))
            
            if task_status in ["completed", "failed"]:
                logger.info(f"Task {task_id} {task_status}, TTL set to {ttl} seconds")
            
        except Exception as e:
            logger.error(f"Failed to update bulk check task {task_id}: {e}")

    @classmethod
    def delete_bulk_check_task(cls, task_id: str) -> bool:
        """删除批量检测任务数据"""
        try:
            redis_client = cls._get_redis_client()
            redis_key = f"{ValidationConfig.BULK_CHECK_TASK_PREFIX}{task_id}"
            
            result = redis_client.delete(redis_key)
            logger.info(f"Deleted bulk check task {task_id} from Redis")
            return result > 0
            
        except Exception as e:
            logger.error(f"Failed to delete bulk check task {task_id}: {e}")
            return False


# 向后兼容性保持原函数名
def _get_redis_client():
    return RedisTaskManager._get_redis_client()

def create_bulk_check_task(key_ids: List[int]) -> str:
    return RedisTaskManager.create_bulk_check_task(key_ids)

def get_bulk_check_task_status(task_id: str) -> Optional[Dict]:
    return RedisTaskManager.get_bulk_check_task_status(task_id)

def update_bulk_check_task(task_id: str, **updates):
    return RedisTaskManager.update_bulk_check_task(task_id, **updates)

def delete_bulk_check_task(task_id: str) -> bool:
    return RedisTaskManager.delete_bulk_check_task(task_id)


def execute_bulk_check_task_sync(task_id: str):
    """
    同步执行批量检测任务（用于 BackgroundTasks）
    """
    try:
        # 获取任务信息
        task_data = get_bulk_check_task_status(task_id)
        if not task_data:
            logger.error(f"Task {task_id} not found")
            return
            
        # 更新任务状态为运行中
        update_bulk_check_task(
            task_id,
            status="running",
            started_at=datetime.now(timezone.utc).isoformat()
        )
        
        key_ids = task_data["key_ids"]
        results = []
        
        # 创建新的数据库会话
        db = SessionLocal()
        try:
            logger.info(f"Starting bulk check task {task_id} for {len(key_ids)} keys")
            
            # 调用原有的检测函数
            results = check_keys_validity(db, key_ids, task_id=task_id)
            
            # 更新任务状态为完成
            update_bulk_check_task(
                task_id,
                status="completed",
                results=results,
                completed_keys=len(key_ids),
                finished_at=datetime.now(timezone.utc).isoformat()
            )
            
            logger.info(f"Completed bulk check task {task_id}")
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error executing bulk check task {task_id}: {e}")
        update_bulk_check_task(
            task_id,
            status="failed",
            error=str(e),
            finished_at=datetime.now(timezone.utc).isoformat()
        )


async def execute_bulk_check_task_async(task_id: str):
    """
    异步执行批量检测任务
    """
    try:
        # 获取任务信息
        task_data = get_bulk_check_task_status(task_id)
        if not task_data:
            logger.error(f"Task {task_id} not found")
            return
            
        # 更新任务状态为运行中
        update_bulk_check_task(
            task_id,
            status="running",
            started_at=datetime.now(timezone.utc).isoformat()
        )
        
        key_ids = task_data["key_ids"]
        results = []
        
        # 创建新的数据库会话
        db = SessionLocal()
        try:
            logger.info(f"Starting bulk check task {task_id} for {len(key_ids)} keys")
            
            # 调用原有的检测函数
            results = check_keys_validity(db, key_ids, task_id=task_id)
            
            # 更新任务状态为完成
            update_bulk_check_task(
                task_id,
                status="completed",
                results=results,
                completed_keys=len(key_ids),
                finished_at=datetime.now(timezone.utc).isoformat()
            )
            
            logger.info(f"Completed bulk check task {task_id}")
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error executing bulk check task {task_id}: {e}")
        update_bulk_check_task(
            task_id,
            status="failed",
            error=str(e),
            finished_at=datetime.now(timezone.utc).isoformat()
        )


def _get_config_value_with_default(
    db: Session, key: str, default_value: T, value_type: Type[T]
) -> T:
    """获取配置值，如果无效则返回默认值"""
    config_str = crud_config.get_config_value(db, key)
    if config_str:
        try:
            converted_value = value_type(config_str)
            if (value_type is int and converted_value < 0) or (
                value_type is float and converted_value <= 0
            ):
                logger.warning(
                    f"Invalid {key.replace('_', ' ')} '{config_str}' from config, using default {default_value}."
                )
                return default_value
            return converted_value
        except ValueError:
            logger.warning(
                f"Invalid {key.replace('_', ' ')} format '{config_str}' from config, using default {default_value}."
            )
            return default_value
    return default_value


def _get_validation_config(db: Session) -> Tuple[str, int, float, int]:
    """获取验证相关的配置"""
    config = crud_config.get_config_by_key(db, "target_api_url")
    if not config or not config.value:
        raise ValueError("Target AI API URL is not configured")
    
    target_url = config.value.rstrip("/")
    model_name = crud_config.get_config_value(db, "key_validation_model_name") or ValidationConfig.DEFAULT_MODEL_NAME
    validation_endpoint = f"{target_url}/models/{model_name}:streamGenerateContent?alt=sse"
    
    max_failed_count = _get_config_value_with_default(
        db, "key_validation_max_failed_count", ValidationConfig.DEFAULT_MAX_FAILED_COUNT, int
    )
    timeout_seconds = _get_config_value_with_default(
        db, "key_validation_timeout_seconds", ValidationConfig.DEFAULT_TIMEOUT, float
    )
    
    # 获取并发数量配置，默认为1，最大限制为10
    concurrent_count = _get_config_value_with_default(
        db, "key_validation_concurrent_count", ValidationConfig.DEFAULT_CONCURRENT_WORKERS, int
    )
    if concurrent_count < 1:
        concurrent_count = ValidationConfig.DEFAULT_CONCURRENT_WORKERS
        logger.warning("Invalid concurrent count (< 1), using default 1.")
    elif concurrent_count > ValidationConfig.MAX_CONCURRENT_WORKERS:
        concurrent_count = ValidationConfig.MAX_CONCURRENT_WORKERS
        logger.warning(f"Concurrent count exceeds maximum limit ({ValidationConfig.MAX_CONCURRENT_WORKERS}), using maximum {ValidationConfig.MAX_CONCURRENT_WORKERS}.")
    
    return validation_endpoint, max_failed_count, timeout_seconds, concurrent_count


class KeyValidator:
    """密钥验证器类"""
    
    @staticmethod
    def _create_http_client(timeout_seconds: float) -> httpx.Client:
        """创建优化的HTTP客户端"""
        timeout_config = httpx.Timeout(
            connect=HttpTimeoutConfig.CONNECT,
            read=timeout_seconds,
            write=HttpTimeoutConfig.WRITE,
            pool=HttpTimeoutConfig.POOL
        )
        
        return httpx.Client(timeout=timeout_config)
    
    @staticmethod
    def _validate_single_key(
        key: models.ApiKey,
        validation_endpoint: str,
        timeout_seconds: float,
    ) -> ValidationResult:
        """验证单个API密钥"""
        try:
            headers = RequestConfig.HEADERS.copy()
            headers["x-goog-api-key"] = key.key_value
            
            with KeyValidator._create_http_client(timeout_seconds) as client:
                response = client.post(validation_endpoint, headers=headers, json=RequestConfig.JSON_DATA)
                is_valid = response.status_code == 200 and "text" in response.text
                
                if response.status_code == 429:
                    return ValidationResult(key, False, ValidationStatus.EXHAUSTED)
                elif is_valid:
                    return ValidationResult(key, True, ValidationStatus.VALID)
                else:
                    return ValidationResult(key, False, ValidationStatus.ERROR, f"HTTP_{response.status_code}")

        except httpx.RequestError as exc:
            # 特殊处理 AbortError
            error_msg = str(exc)
            if "AbortError" in error_msg or "signal is aborted" in error_msg:
                logger.warning(f"Key validation aborted for API Key ID {key.id} ({key.key_value[:8]}...): {exc}")
                return ValidationResult(key, False, ValidationStatus.TIMEOUT_ABORT, str(exc))
            else:
                logger.error(f"Error validating API Key ID {key.id} ({key.key_value[:8]}...): {exc}")
                return ValidationResult(key, False, ValidationStatus.NETWORK_ERROR, str(exc))
        except Exception as e:
            logger.error(f"Unexpected error during validation for API Key ID {key.id} ({key.key_value[:8]}...): {e}")
            return ValidationResult(key, False, ValidationStatus.ERROR, str(e))
    
    @staticmethod
    def _update_key_status_from_result(result: ValidationResult, max_failed_count: int):
        """根据验证结果更新密钥状态"""
        with SessionLocal() as thread_db:
            thread_key = crud_api_keys.get_api_key(thread_db, result.key.id)
            if not thread_key:
                return
                
            if result.status == ValidationStatus.EXHAUSTED:
                update_key_status_based_on_response(
                    thread_db, thread_key, False, max_failed_count, 
                    status_override="exhausted", count_usage=False
                )
            elif result.status == ValidationStatus.VALID:
                update_key_status_based_on_response(
                    thread_db, thread_key, True, max_failed_count, count_usage=False
                )
            elif result.status == ValidationStatus.TIMEOUT_ABORT:
                # AbortError 不应该计入失败次数，只记录为临时错误
                logger.info(f"API Key ID {result.key.id} validation aborted due to timeout, not counting as failure")
                # 不更新失败计数，保持原状态
                pass
            else:
                update_key_status_based_on_response(
                    thread_db, thread_key, False, max_failed_count, 
                    status_override="error", count_usage=False
                )
            
            thread_db.commit()


# 向后兼容性函数
def _validate_single_key(
    key: models.ApiKey,
    validation_endpoint: str,
    timeout_seconds: float,
) -> Tuple[models.ApiKey, bool, str]:
    """向后兼容的验证函数"""
    result = KeyValidator._validate_single_key(key, validation_endpoint, timeout_seconds)
    # 转换新的结果格式为旧格式
    if result.status == ValidationStatus.EXHAUSTED:
        return result.key, False, "exhausted"
    elif result.status == ValidationStatus.VALID:
        return result.key, True, "valid"
    elif result.status == ValidationStatus.TIMEOUT_ABORT:
        return result.key, False, "timeout_abort"
    else:
        return result.key, False, result.message


def _update_key_status_in_thread(key_id: int, status_info: str, max_failed_count: int):
    """向后兼容的状态更新函数"""
    with SessionLocal() as thread_db:
        thread_key = crud_api_keys.get_api_key(thread_db, key_id)
        if not thread_key:
            return
        
        # 创建模拟的ValidationResult来使用新的更新逻辑
        if status_info == "exhausted":
            status = ValidationStatus.EXHAUSTED
        elif status_info == "valid":
            status = ValidationStatus.VALID
        elif status_info == "timeout_abort":
            status = ValidationStatus.TIMEOUT_ABORT
        else:
            status = ValidationStatus.ERROR
            
        result = ValidationResult(thread_key, status == ValidationStatus.VALID, status, status_info)
        KeyValidator._update_key_status_from_result(result, max_failed_count)


def _perform_concurrent_validation(
    keys_to_validate: List[models.ApiKey],
    validation_endpoint: str,
    max_failed_count: int,
    timeout_seconds: float,
    concurrent_count: int,
    task_name: str = "validation"
) -> Tuple[int, int]:
    """执行并发验证，返回(成功数量, 失败数量)"""
    validated_count = 0
    invalidated_count = 0
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent_count) as executor:
        future_to_key = {
            executor.submit(KeyValidator._validate_single_key, key, validation_endpoint, timeout_seconds): key 
            for key in keys_to_validate
        }
        
        for future in concurrent.futures.as_completed(future_to_key):
            try:
                result = future.result()
                logger.info(f"validating API Key ID {result.key.id} ({result.key.key_value[:8]}...) "
                           f"is valid : {result.is_valid}, status: {result.status}")
                KeyValidator._update_key_status_from_result(result, max_failed_count)
                
                if result.is_valid:
                    validated_count += 1
                else:
                    invalidated_count += 1
                    
            except Exception as exc:
                logger.error(f"Error processing {task_name} result: {exc}")
                invalidated_count += 1
    
    return validated_count, invalidated_count


def _perform_key_validation(db: Session, status_filter: Optional[str] = None):
    """执行密钥验证的核心逻辑"""
    try:
        # 查询要验证的密钥
        query = db.query(models.ApiKey)
        if status_filter:
            query = query.filter(models.ApiKey.status == status_filter)
        else:
            query = query.filter(models.ApiKey.status != "error")

        keys_to_validate = query.all()
        if not keys_to_validate:
            logger.info(f"No API keys with status '{status_filter or 'non-error'}' found in database to validate.")
            return

        # 获取验证配置
        validation_endpoint, max_failed_count, timeout_seconds, concurrent_count = _get_validation_config(db)
        
        # 在开始时就打印并发数量
        logger.info(f"Starting '{status_filter or 'non-error'}' key validation with concurrent count: {concurrent_count}")
        
        # 执行并发验证
        validated_count, invalidated_count = _perform_concurrent_validation(
            keys_to_validate, validation_endpoint, max_failed_count, 
            timeout_seconds, concurrent_count, f"{status_filter or 'non-error'} key validation"
        )

        logger.info(
            f"API Key validation for status '{status_filter or 'non-error'}' finished. "
            f"Validated: {validated_count}, Invalidated: {invalidated_count}. "
            f"Concurrent workers: {concurrent_count}."
        )

    except ValueError as ve:
        logger.warning(f"Configuration error: {ve}")
    except Exception as e:
        logger.error(f"Error during API Key validation task execution for status '{status_filter or 'non-error'}': {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()


def _execute_validation_task(status_filter: str):
    """执行验证任务的通用模板"""
    logger.info(f"Starting '{status_filter}' API Key validation task...")
    db = SessionLocal()
    try:
        _perform_key_validation(db, status_filter)
        # 记录密钥存活统计数据
        crud_api_keys.record_key_survival_statistics(db)
    finally:
        db.close()


def validate_active_api_keys_task():
    """定时任务：检查活跃密钥有效性"""
    _execute_validation_task("active")


def validate_exhausted_api_keys_task():
    """定时任务：检查已耗尽密钥有效性"""
    _execute_validation_task("exhausted")


def validate_error_api_keys_task():
    """定时任务：检查错误密钥有效性"""
    _execute_validation_task("error")


def check_keys_validity(db: Session, key_ids: List[int], task_id: Optional[str] = None) -> List[Dict]:
    """批量检查密钥有效性"""
    logger.info(f"Starting bulk API Key validation for {len(key_ids)} keys...")
    results = []

    try:
        # 获取验证配置
        validation_endpoint, max_failed_count, timeout_seconds, concurrent_count = _get_validation_config(db)
        logger.info(f"Starting bulk validation with concurrent count: {concurrent_count}")
        
        # 获取所有key对象
        keys_to_validate = []
        for key_id in key_ids:
            api_key_obj = crud_api_keys.get_api_key(db, key_id)
            if api_key_obj:
                keys_to_validate.append(api_key_obj)
            else:
                results.append({
                    "key_value": f"ID:{key_id}",
                    "status": "error",
                    "message": "Key not found in DB.",
                })

        if not keys_to_validate:
            return results

        # 执行并发验证
        completed_count = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent_count) as executor:
            future_to_key = {
                executor.submit(KeyValidator._validate_single_key, key, validation_endpoint, timeout_seconds): key 
                for key in keys_to_validate
            }
            
            for future in concurrent.futures.as_completed(future_to_key):
                try:
                    result = future.result()
                    
                    # 更新数据库状态（批量检查也不统计使用次数）
                    KeyValidator._update_key_status_from_result(result, max_failed_count)
                    
                    # 准备返回结果
                    results.append({
                        "key_id": result.key.id,
                        "key_value": result.key.key_value,
                        "status": result.status_str,
                        "message": result.display_message,
                    })
                    
                    # 更新任务进度（如果提供了task_id）
                    if task_id:
                        completed_count += 1
                        update_bulk_check_task(task_id, completed_keys=completed_count)
                    
                except Exception as exc:
                    logger.error(f"Error processing bulk validation result: {exc}")
                    original_key = future_to_key[future]
                    results.append({
                        "key_id": original_key.id,
                        "key_value": original_key.key_value,
                        "status": "error",
                        "message": f"Processing error: {exc}",
                    })
                    
                    # 更新任务进度（如果提供了task_id）
                    if task_id:
                        completed_count += 1
                        update_bulk_check_task(task_id, completed_keys=completed_count)

        logger.info(f"Bulk API Key validation finished. Processed {len(results)} keys with {concurrent_count} concurrent workers.")

    except ValueError as ve:
        # 配置错误时为所有key返回错误结果
        for key_id in key_ids:
            if not any(r.get("key_value", "").endswith(str(key_id)) for r in results):
                api_key_obj = crud_api_keys.get_api_key(db, key_id)
                key_value = api_key_obj.key_value if api_key_obj else f"ID:{key_id}"
                results.append({
                    "key_value": key_value,
                    "status": "error",
                    "message": str(ve),
                })
    except Exception as e:
        logger.error(f"Error during bulk API Key validation task setup: {e}", exc_info=True)
        # 确保所有key都有error结果
        for key_id in key_ids:
            if not any(r.get("key_value", "").endswith(str(key_id)) for r in results):
                api_key_obj = crud_api_keys.get_api_key(db, key_id)
                key_value = api_key_obj.key_value if api_key_obj else f"ID:{key_id}"
                results.append({
                    "key_value": key_value,
                    "status": "error",
                    "message": f"Setup error: {e}",
                })

    return results
