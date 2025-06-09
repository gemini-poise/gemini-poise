from fastapi import APIRouter

from .endpoints import users, api_keys, config, token_bucket

api_router = APIRouter()

api_router.include_router(users.router, prefix="/v1")
api_router.include_router(api_keys.router, prefix="/v1")
api_router.include_router(config.router, prefix="/v1")
api_router.include_router(token_bucket.router, prefix="/v1/token-bucket", tags=["token-bucket"])
