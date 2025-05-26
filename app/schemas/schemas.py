from datetime import datetime
from typing import Optional, List, Generic, TypeVar

from pydantic import BaseModel, Field


# 定义分页请求 Schema
class PaginationParams(BaseModel):
    page: int = Field(
        1, ge=1, description="Page number (starting from 1)"
    )  # 页码，默认为 1，最小为 1
    page_size: int = Field(
        50, ge=1, le=100, description="Items per page (max 100)"
    )  # 每页数量，默认为 50，最小为 1，最大为 100


# 定义分页响应 Schema (通用)
T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    total: int  # 总数
    items: List[T]  # 当前页的数据列表


# --- User Schemas ---
class UserBase(BaseModel):
    username: str


class UserCreate(UserBase):
    password: str


class User(UserBase):
    id: int
    is_active: bool

    class Config:
        from_attributes = True


# --- API Key Schemas ---
class ApiKeyBase(BaseModel):
    key_value: str
    status: str = "active"
    description: Optional[str] = None


class ApiKeyCreate(ApiKeyBase):
    pass


class ApiKeyUpdate(BaseModel):
    key_value: Optional[str] = None
    status: Optional[str] = None
    description: Optional[str] = None


class ApiKey(ApiKeyBase):
    id: int
    created_at: datetime
    last_used_at: Optional[datetime]
    usage_count: int
    failed_count: int

    class Config:
        from_attributes = True


# 定义 Schema 用于批量添加 API Key 的请求体
class ApiKeyBulkAddRequest(BaseModel):
    keys_string: str  # 包含逗号或换行符分隔的 Key 字符串


# 定义 Schema 用于直接接收 Key 列表的请求体
class ApiKeyAddListRequest(BaseModel):
    keys: List[str]


# 定义 Schema 用于批量添加 API Key 的响应体
class ApiKeyBulkAddResponse(BaseModel):
    total_processed: int  # 总共处理的 Key 数量
    total_added: int  # 新插入的 Key 数量
    # existing_keys: List[str] = []
    # added_keys: List[str] = []


# 定义 Schema 用于批量检测 API Key 的请求体
class ApiKeyBulkCheckRequest(BaseModel):
    key_ids: List[int]  # 包含要检测的 Key ID 列表


# 定义 Schema 用于单个 Key 的检测结果
class ApiKeyCheckResult(BaseModel):
    key_value: str
    status: str  # 例如: "valid", "invalid", "error"
    message: Optional[str] = None


# 定义 Schema 用于批量检测 API Key 的响应体
class ApiKeyBulkCheckResponse(BaseModel):
    results: List[ApiKeyCheckResult]


# 定义分页请求 Schema (添加筛选参数)
class ApiKeyPaginationParams(BaseModel):
    page: int = Field(1, ge=1, description="Page number (starting from 1)")
    page_size: int = Field(50, ge=1, le=100, description="Items per page (max 100)")
    # 添加筛选参数
    search_key: Optional[str] = Field(None, description="Search by key value")
    min_failed_count: Optional[int] = Field(
        None, ge=0, description="Filter by minimum failed count"
    )
    status: Optional[str] = Field(
        None, description="Filter by status (active, inactive, exhausted)"
    )


# 定义 API Key 分页响应 Schema
class PaginatedApiKeyResponse(PaginatedResponse[ApiKey]):
    pass


# --- API Call Statistics Schemas ---
class ApiCallStatistics(BaseModel):
    calls_last_1_minute: int = Field(
        0, description="Number of API calls in the last 1 minute"
    )
    calls_last_1_hour: int = Field(
        0, description="Number of API calls in the last 1 hour"
    )
    calls_last_24_hours: int = Field(
        0, description="Number of API calls in the last 24 hours"
    )
    monthly_usage: int = Field(0, description="Total usage count for the current month")


# --- Token Schemas ---
class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None  # 或者 user_id: Optional[int] = None


# --- Login Request Schema ---
class LoginRequest(BaseModel):
    username: str
    password: str


# --- Config Schemas ---


# 定义 Schema 用于返回单个配置项 (包含所有字段)
class ConfigItem(BaseModel):
    id: int
    key: str
    value: str
    updated_at: datetime
    updated_by_user_id: int

    # 可以选择包含更新人的用户名
    # updated_by_username: Optional[str] = None

    class Config:
        from_attributes = True  # 兼容 SQLAlchemy 模型


# 定义 Schema 用于创建单个配置项的请求体
class ConfigCreateRequest(BaseModel):
    key: str
    value: str


# 定义 Schema 用于更新单个配置项的请求体
class ConfigUpdateRequest(BaseModel):
    value: str


# 定义 Schema 用于批量保存配置项的请求体
class ConfigBulkSaveRequestItem(BaseModel):
    key: str
    value: str


# 定义 Schema 用于批量保存配置项的请求体
class ConfigBulkSaveRequest(BaseModel):
    items: List[ConfigBulkSaveRequestItem]


# 定义 Schema 用于返回配置项列表 (可选，直接使用 List[ConfigItem] 也可以)
# class ConfigListResponse(BaseModel):
#     items: List[ConfigItem]
#     total: int # 如果需要分页信息
