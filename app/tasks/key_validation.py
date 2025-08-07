import logging
from typing import List, Dict, Type, TypeVar, Optional, Tuple
import concurrent.futures

import httpx
from sqlalchemy.orm import Session

from ..api.endpoints.proxies.base_proxy import update_key_status_based_on_response
from ..crud import api_keys as crud_api_keys
from ..crud import config as crud_config
from ..core.database import SessionLocal

logger = logging.getLogger(__name__)

T = TypeVar("T")

# 常量定义
MAX_CONCURRENT_WORKERS = 10
DEFAULT_CONCURRENT_WORKERS = 1
DEFAULT_TIMEOUT = 10.0
DEFAULT_MAX_FAILED_COUNT = 3
DEFAULT_MODEL_NAME = "gemini-1.5-flash"

# 验证请求的固定头部和数据
VALIDATION_HEADERS = {
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

VALIDATION_JSON_DATA = {
    "contents": [{"parts": [{"text": "hi"}], "role": "user"}],
    "generationConfig": {
        "maxOutputTokens": 1,
        "thinkingConfig": {
            "includeThoughts": False,
            "thinkingBudget": 0,
        },
    },
}


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
    model_name = crud_config.get_config_value(db, "key_validation_model_name") or DEFAULT_MODEL_NAME
    validation_endpoint = f"{target_url}/models/{model_name}:streamGenerateContent?alt=sse"
    
    max_failed_count = _get_config_value_with_default(db, "key_validation_max_failed_count", DEFAULT_MAX_FAILED_COUNT, int)
    timeout_seconds = _get_config_value_with_default(db, "key_validation_timeout_seconds", DEFAULT_TIMEOUT, float)
    
    # 获取并发数量配置，默认为1，最大限制为10
    concurrent_count = _get_config_value_with_default(db, "key_validation_concurrent_count", DEFAULT_CONCURRENT_WORKERS, int)
    if concurrent_count < 1:
        concurrent_count = DEFAULT_CONCURRENT_WORKERS
        logger.warning("Invalid concurrent count (< 1), using default 1.")
    elif concurrent_count > MAX_CONCURRENT_WORKERS:
        concurrent_count = MAX_CONCURRENT_WORKERS
        logger.warning(f"Concurrent count exceeds maximum limit ({MAX_CONCURRENT_WORKERS}), using maximum {MAX_CONCURRENT_WORKERS}.")
    
    return validation_endpoint, max_failed_count, timeout_seconds, concurrent_count


def _validate_single_key(
    key: crud_api_keys.models.ApiKey,
    validation_endpoint: str,
    timeout_seconds: float,
) -> Tuple[crud_api_keys.models.ApiKey, bool, str]:
    """验证单个API密钥"""
    try:
        headers = VALIDATION_HEADERS.copy()
        headers["x-goog-api-key"] = key.key_value
        
        with httpx.Client(timeout=timeout_seconds) as client:
            response = client.post(validation_endpoint, headers=headers, json=VALIDATION_JSON_DATA)
            is_valid = response.status_code == 200 and "text" in response.text
            
            if response.status_code == 429:
                return key, False, "exhausted"
            elif is_valid:
                return key, True, "valid"
            else:
                return key, False, f"error_{response.status_code}"

    except httpx.RequestError as exc:
        logger.error(f"Error validating API Key ID {key.id} ({key.key_value[:8]}...): {exc}")
        return key, False, f"network_error: {exc}"
    except Exception as e:
        logger.error(f"Unexpected error during validation for API Key ID {key.id} ({key.key_value[:8]}...): {e}")
        return key, False, f"unexpected_error: {e}"


def _update_key_status_in_thread(key_id: int, status_info: str, max_failed_count: int):
    """在独立线程中更新密钥状态"""
    with SessionLocal() as thread_db:
        thread_key = crud_api_keys.get_api_key(thread_db, key_id)
        if not thread_key:
            return
            
        if status_info == "exhausted":
            update_key_status_based_on_response(thread_db, thread_key, False, max_failed_count, status_override="exhausted")
        elif status_info == "valid":
            update_key_status_based_on_response(thread_db, thread_key, True, max_failed_count)
        else:
            update_key_status_based_on_response(thread_db, thread_key, False, max_failed_count, status_override="error")
        
        thread_db.commit()


def _perform_concurrent_validation(
    keys_to_validate: List[crud_api_keys.models.ApiKey],
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
            executor.submit(_validate_single_key, key, validation_endpoint, timeout_seconds): key 
            for key in keys_to_validate
        }
        
        for future in concurrent.futures.as_completed(future_to_key):
            try:
                key, is_valid, status_info = future.result()
                _update_key_status_in_thread(key.id, status_info, max_failed_count)
                
                if is_valid:
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
        query = db.query(crud_api_keys.models.ApiKey)
        if status_filter:
            query = query.filter(crud_api_keys.models.ApiKey.status == status_filter)
        else:
            query = query.filter(crud_api_keys.models.ApiKey.status != "error")

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


def check_keys_validity(db: Session, key_ids: List[int]) -> List[Dict]:
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
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent_count) as executor:
            future_to_key = {
                executor.submit(_validate_single_key, key, validation_endpoint, timeout_seconds): key 
                for key in keys_to_validate
            }
            
            for future in concurrent.futures.as_completed(future_to_key):
                try:
                    key, is_valid, status_info = future.result()
                    
                    # 更新数据库状态
                    _update_key_status_in_thread(key.id, status_info, max_failed_count)
                    
                    # 准备返回结果
                    if status_info == "exhausted":
                        status_str, message_str = "exhausted", "Validation failed: 429 - Too Many Requests"
                    elif status_info == "valid":
                        status_str, message_str = "valid", "Key is valid."
                    else:
                        status_str, message_str = "error", f"Validation failed: {status_info}"
                    
                    results.append({
                        "key_value": key.key_value,
                        "status": status_str,
                        "message": message_str,
                    })
                    
                except Exception as exc:
                    logger.error(f"Error processing bulk validation result: {exc}")
                    original_key = future_to_key[future]
                    results.append({
                        "key_value": original_key.key_value,
                        "status": "error",
                        "message": f"Processing error: {exc}",
                    })

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
