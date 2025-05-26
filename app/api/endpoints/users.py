from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from ... import crud, schemas
from ...core.security import (
    verify_password,
    create_access_token,
    delete_token,
    user_dependency,
    db_dependency,
    redis_dependency,
    oauth2_scheme,
)

router = APIRouter(tags=["Authentication"])


@router.post("/login", response_model=schemas.Token)
async def login_for_access_token(
    login_data: schemas.LoginRequest, db: db_dependency, redis: redis_dependency
):
    """
    用户登录接口，使用用户名和密码获取 Token。
    """
    user = crud.users.get_user_by_username(db, username=login_data.username)
    if not user or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = await create_access_token(user_id=user.id, redis_client=redis)

    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/users/me/", response_model=schemas.User)
async def read_users_me(
    current_user: user_dependency,  # 使用认证依赖，自动验证 Token 并注入当前用户
):
    """
    获取当前登录用户的信息。需要有效的 Token。
    """
    # current_user 依赖已经验证了 Token 并从数据库加载了用户对象
    return current_user


@router.post("/logout")
async def logout(
    current_user: user_dependency,
    token: Annotated[str, Depends(oauth2_scheme)],
    redis: redis_dependency,
):
    """
    用户登出，使当前 Token 失效。
    """
    deleted_count = await delete_token(token, redis)
    if deleted_count == 0:
        print(f"Warning: Token {token} not found in Redis during logout.")
    return {"message": f"{current_user}Successfully logged out"}


@router.post("/users/", response_model=schemas.User)
async def create_user(user: schemas.UserCreate, db: db_dependency):
    db_user = crud.users.get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    return crud.users.create_user(db=db, user=user)
