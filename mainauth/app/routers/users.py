from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models import User
from app.schemas import *
from app.auth.keycloak import hash_password, create_keycloak_user
from logging import getLogger

logger = getLogger(__name__)

router = APIRouter()

@router.get("/")
def get_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """取得使用者列表"""
    users = db.query(User).offset(skip).limit(limit).all()
    return users

@router.get("/{user_id}")
def get_user(user_id: int, db: Session = Depends(get_db)):
    """取得單一使用者"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="使用者不存在")
    return user

@router.post("/create")
async def create_local_user(payload: LocalUserCreate, db: Session = Depends(get_db)):
    """創建使用者（同時創建在本地 DB 和 Keycloak）"""
    
    # 1. 檢查本地 DB 是否已存在
    user = db.query(User).filter(User.username == payload.username).first()
    if user:
        raise HTTPException(status_code=400, detail="使用者已存在")
    
    try:
        # 2. 在 Keycloak 創建使用者，取得 UUID
        keycloak_uuid = await create_keycloak_user(
            username=payload.username,
            password=payload.password,
            email=payload.email,
            first_name=payload.first_name,
            last_name=payload.last_name
        )
        logger.info(f"Keycloak 使用者創建成功，UUID: {keycloak_uuid}")
        
        # 3. 在本地 DB 創建使用者
        user = User(
            keycloak_uuid=keycloak_uuid,
            username=payload.username,
            email=payload.email,
            first_name=payload.first_name,
            last_name=payload.last_name,
            password_hash=hash_password(payload.password),  # 雖然有 Keycloak，但也可以保存本地 hash 作為備援
            is_active=True
        )
        
        db.add(user)
        db.commit()
        db.refresh(user)

        logger.info(f"本地 DB 使用者創建成功，ID: {user.id}")
        
        return {
            "message": "使用者創建成功",
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "keycloak_uuid": user.keycloak_uuid
            }
        }
        
    except HTTPException as e:
        # 如果 Keycloak 創建失敗，不要創建本地使用者
        logger.error(f"HTTPException: {e.detail}")
        db.rollback()
        raise e
    except Exception as e:
        logger.error(f"未預期的錯誤: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        db.rollback()
        raise HTTPException(status_code=500, detail=f"創建使用者失敗: {str(e)}")