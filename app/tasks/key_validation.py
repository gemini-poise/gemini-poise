import logging
from typing import List, Dict, Type, TypeVar

import httpx
from sqlalchemy.orm import Session

from ..api.endpoints.proxies.base_proxy import update_key_status_based_on_response
from ..crud import api_keys as crud_api_keys
from ..crud import config as crud_config
from ..core.database import SessionLocal

logger = logging.getLogger(__name__)

T = TypeVar("T")


def _get_config_value_with_default(
    db: Session, key: str, default_value: T, value_type: Type[T]
) -> T:
    """
    Helper function to retrieve a configuration value from the database,
    convert it to the specified type, and handle invalid values with a default.
    """
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


def validate_api_key_task():
    """
    Scheduled task: Checks the validity of API Keys in the database.
    Uses the update_key_status_based_on_response helper function for status updates.
    """
    logger.info("Starting API Key validation task...")
    db = SessionLocal()
    task_httpx_client = None
    try:
        max_failed_count = _get_config_value_with_default(
            db, "key_validation_max_failed_count", 3, int
        )
        timeout_seconds = _get_config_value_with_default(
            db, "key_validation_timeout_seconds", 10.0, float
        )

        logger.info(
            f"Task config: Max Failed Count = {max_failed_count}, Timeout = {timeout_seconds}s."
        )

        task_httpx_client = httpx.Client(timeout=timeout_seconds)

        all_keys = db.query(crud_api_keys.models.ApiKey).filter(
            crud_api_keys.models.ApiKey.status != "error"
        ).all()

        if not all_keys:
            logger.info("No non-error API keys found in database to validate.")
            return

        config = crud_config.get_config_by_key(db, "target_api_url")
        if not config or not config.value:
            logger.warning(
                "Target AI API URL is not configured, skipping key validation."
            )
            return

        target_url = config.value.rstrip("/")
        model_name = (
            crud_config.get_config_value(db, "key_validation_model_name")
            or "gemini-1.5-flash"
        )
        validation_endpoint = (
            f"{target_url}/models/{model_name}:streamGenerateContent?alt=sse"
        )

        validated_count = 0
        invalidated_count = 0
        for key in all_keys:
            # if key.status == "exhausted":
            #     logger.info(f"Skipping validation for exhausted key ID {key.id}.")
            #     continue

            try:
                headers = {
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
                    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) CherryStudio/1.3.9 Chrome/134.0.6998.205 Electron/35.2.2 Safari/537.36",
                    "x-goog-api-client": "google-genai-sdk/0.13.0 gl-node/web",
                    "x-goog-api-key": key.key_value,
                }
                json_data = {
                    "contents": [{"parts": [{"text": "hi"}], "role": "user"}],
                    "generationConfig": {
                        "maxOutputTokens": 1,
                        "thinkingConfig": {
                            "includeThoughts": False,
                            "thinkingBudget": 0,
                        },
                    },
                }

                response = task_httpx_client.post(
                    validation_endpoint, headers=headers, json=json_data
                )
                is_valid = response.status_code == 200 and "text" in response.text
                
                if response.status_code == 429:
                    update_key_status_based_on_response(db, key, False, max_failed_count, status_override="exhausted")
                else:
                    update_key_status_based_on_response(db, key, is_valid, max_failed_count)

                if is_valid:
                    validated_count += 1
                else:
                    invalidated_count += 1

            except httpx.RequestError as exc:
                logger.error(
                    f"Error validating API Key ID {key.id} ({key.key_value[:8]}...): {exc}",
                    exc_info=True,
                )
                update_key_status_based_on_response(db, key, False, max_failed_count, status_override="error")
                invalidated_count += 1
            except Exception as e:
                logger.error(
                    f"Unexpected error during validation for API Key ID {key.id} ({key.key_value[:8]}...): {e}",
                    exc_info=True,
                )
                update_key_status_based_on_response(db, key, False, max_failed_count, status_override="error")
                invalidated_count += 1

        logger.info(
            f"API Key validation task finished. Validated: {validated_count}, Invalidated: {invalidated_count}."
        )

    except Exception as e:
        logger.error(
            f"Error during API Key validation task execution: {e}", exc_info=True
        )
        db.rollback()
    finally:
        db.close()
        if task_httpx_client:
            task_httpx_client.close()
            logger.info("Task httpx client closed.")


def check_keys_validity(db: Session, key_ids: List[int]) -> List[Dict]:
    """
    Checks the validity of a list of API Keys by their IDs.
    Returns a list of dictionaries, each containing key_value, status, and message.
    """
    logger.info(f"Starting bulk API Key validation for {len(key_ids)} keys...")
    results = []
    task_httpx_client = None

    try:

        timeout_seconds = _get_config_value_with_default(
            db, "key_validation_timeout_seconds", 10.0, float
        )

        task_httpx_client = httpx.Client(timeout=timeout_seconds)

        config = crud_config.get_config_by_key(db, "target_api_url")
        if not config or not config.value:
            logger.warning(
                "Target AI API URL is not configured, skipping key validation."
            )
            for key_id in key_ids:
                api_key_obj = crud_api_keys.get_api_key(db, key_id)
                key_value = api_key_obj.key_value if api_key_obj else f"ID:{key_id}"
                results.append(
                    {
                        "key_value": key_value,
                        "status": "error",
                        "message": "Target API URL not configured.",
                    }
                )
            return results

        target_url = config.value.rstrip("/")
        model_name = (
            crud_config.get_config_value(db, "key_validation_model_name")
            or "gemini-1.5-flash"
        )
        validation_endpoint = (
            f"{target_url}/models/{model_name}:streamGenerateContent?alt=sse"
        )

        for key_id in key_ids:
            api_key_obj = crud_api_keys.get_api_key(db, key_id)
            if not api_key_obj:
                results.append(
                    {
                        "key_value": f"ID:{key_id}",
                        "status": "error",
                        "message": "Key not found in DB.",
                    }
                )
                continue

            try:
                headers = {
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
                    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) CherryStudio/1.3.9 Chrome/134.0.6998.205 Electron/35.2.2 Safari/537.36",
                    "x-goog-api-client": "google-genai-sdk/0.13.0 gl-node/web",
                    "x-goog-api-key": api_key_obj.key_value,
                }
                json_data = {
                    "contents": [{"parts": [{"text": "hi"}], "role": "user"}],
                    "generationConfig": {
                        "maxOutputTokens": 1,
                        "thinkingConfig": {
                            "includeThoughts": False,
                            "thinkingBudget": 0,
                        },
                    },
                }

                response = task_httpx_client.post(
                    validation_endpoint, headers=headers, json=json_data
                )
                is_valid = response.status_code == 200 and "text" in response.text

                if response.status_code == 429:
                    status_str = "exhausted"
                    message_str = f"Validation failed: {response.status_code} - Too Many Requests"
                else:
                    status_str = "valid" if is_valid else "error"
                    message_str = (
                        "Key is valid."
                        if is_valid
                        else f"Validation failed: {response.status_code} - {response.text}"
                    )

                results.append(
                    {
                        "key_value": api_key_obj.key_value,
                        "status": status_str,
                        "message": message_str,
                    }
                )

            except httpx.RequestError as exc:
                logger.error(
                    f"Error validating API Key ID {api_key_obj.id} ({api_key_obj.key_value[:8]}...): {exc}"
                )
                results.append(
                    {
                        "key_value": api_key_obj.key_value,
                        "status": "error",
                        "message": f"Network error: {exc}",
                    }
                )
            except Exception as e:
                logger.error(
                    f"Unexpected error during validation for API Key ID {api_key_obj.id} ({api_key_obj.key_value[:8]}...): {e}"
                )
                results.append(
                    {
                        "key_value": api_key_obj.key_value,
                        "status": "error",
                        "message": f"Unexpected error: {e}",
                    }
                )
    except Exception as e:
        logger.error(
            f"Error during bulk API Key validation task setup: {e}", exc_info=True
        )
        # If an error occurs during setup, ensure all requested keys are marked with an error
        for key_id in key_ids:
            # Avoid adding duplicates if some results were already processed
            if not any(
                r.get("key_value") == crud_api_keys.get_api_key(db, key_id).key_value
                for r in results
            ):
                api_key_obj = crud_api_keys.get_api_key(db, key_id)
                key_value = api_key_obj.key_value if api_key_obj else f"ID:{key_id}"
                results.append(
                    {
                        "key_value": key_value,
                        "status": "error",
                        "message": f"Setup error: {e}",
                    }
                )
    finally:
        if task_httpx_client:
            task_httpx_client.close()
            logger.info("Bulk validation httpx client closed.")

    logger.info(f"Bulk API Key validation finished. Processed {len(results)} keys.")
    return results
