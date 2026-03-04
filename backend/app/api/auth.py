from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    get_current_user,
)

router = APIRouter()


@router.post(
    "/register",
    response_model=schemas.UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(user_data: schemas.UserCreate, db: Session = Depends(get_db)):
    """用户注册"""
    # 检查用户名是否已存在
    db_user = (
        db.query(models.User)
        .filter(models.User.username == user_data.username)
        .first()
    )
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已存在",
        )

    # 检查邮箱是否已存在
    db_user = (
        db.query(models.User).filter(models.User.email == user_data.email).first()
    )
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邮箱已被注册",
        )

    # 创建新用户
    hashed_password = get_password_hash(user_data.password)
    db_user = models.User(
        username=user_data.username,
        email=user_data.email,
        password_hash=hashed_password,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return db_user


@router.post("/login", response_model=schemas.Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """用户登录"""
    # 查找用户
    user = (
        db.query(models.User)
        .filter(models.User.username == form_data.username)
        .first()
    )

    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 创建访问令牌
    access_token_expires = timedelta(minutes=30 * 24 * 60)  # 30天
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=schemas.UserResponse)
async def get_current_user_info(
    current_user: models.User = Depends(get_current_user),
):
    """获取当前用户信息"""
    return current_user


@router.put("/profile", response_model=schemas.UserResponse)
async def update_profile(
    update_data: schemas.UserUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新当前用户的基本信息（用户名 / 邮箱 / 密码）"""
    # 如果更新邮箱，检查是否被其他用户占用
    if update_data.email and update_data.email != current_user.email:
        exists = (
            db.query(models.User)
            .filter(
                models.User.email == update_data.email,
                models.User.id != current_user.id,
            )
            .first()
        )
        if exists:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="邮箱已被其他账号使用",
            )

    # 如果更新用户名，检查是否被其他用户占用
    if update_data.username and update_data.username != current_user.username:
        exists = (
            db.query(models.User)
            .filter(
                models.User.username == update_data.username,
                models.User.id != current_user.id,
            )
            .first()
        )
        if exists:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户名已被其他账号使用",
            )

    if update_data.username is not None:
        current_user.username = update_data.username
    if update_data.email is not None:
        current_user.email = update_data.email
    if update_data.password:
        current_user.password_hash = get_password_hash(update_data.password)

    db.add(current_user)
    db.commit()
    db.refresh(current_user)

    return current_user

