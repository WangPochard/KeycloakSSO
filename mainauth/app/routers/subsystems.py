from fastapi import Header, APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from httpx import request
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import AuthorizationCode, SubSystem, User, SessionToken
from app.auth.keycloak import get_user_info, exchange_token_for_subsystem
from app.schemas import SubSystemCreate, SubSystemInDB
from typing import List
from datetime import datetime, timedelta, timezone
import secrets
from logging import getLogger

security = HTTPBearer()
router = APIRouter()
logger = getLogger(__name__)
# 加上這行測試
logger.info("========== subsystems.py 載入了 ==========")

@router.get("/")
async def get_subsystems(db: Session = Depends(get_db)):
    """取得子系統列表"""
    try:
        # 取得所有啟用的子系統
        subsystems = db.query(SubSystem).filter(SubSystem.is_active == True).all()
        return subsystems
        
    except Exception as e:
        logger.error(f"無效的認證 token: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.post("/", response_model=SubSystemInDB)
def create_subsystem(subsystem: SubSystemCreate, db: Session = Depends(get_db)):
    """建立新的子系統"""
    
    # 檢查 code 是否已存在
    existing = db.query(SubSystem).filter(SubSystem.code == subsystem.code).first()
    if existing:
        raise HTTPException(status_code=400, detail="子系統代碼已存在")
    
    # 建立新的子系統
    new_subsystem = SubSystem(
        name=subsystem.name,
        code=subsystem.code,
        description=subsystem.description,
        url=subsystem.url,
        icon=subsystem.icon,
        keycloak_client_id=subsystem.keycloak_client_id,
        is_active=subsystem.is_active,
        order=subsystem.order
    )
    
    db.add(new_subsystem)
    db.commit()
    db.refresh(new_subsystem)
    
    return new_subsystem


@router.get("/{subsystem_id}", response_model=SubSystemInDB)
def get_subsystem(subsystem_id: int, db: Session = Depends(get_db)):
    """取得單一子系統"""
    subsystem = db.query(SubSystem).filter(SubSystem.id == subsystem_id).first()
    if not subsystem:
        raise HTTPException(status_code=404, detail="子系統不存在")
    return subsystem

@router.put("/{subsystem_id}", response_model=SubSystemInDB)
def update_subsystem(subsystem_id: int, subsystem_update: SubSystemCreate, db: Session = Depends(get_db)):
    """更新子系統"""
    subsystem = db.query(SubSystem).filter(SubSystem.id == subsystem_id).first()
    if not subsystem:
        raise HTTPException(status_code=404, detail="子系統不存在")
    
    # 更新欄位
    for key, value in subsystem_update.dict(exclude_unset=True).items():
        setattr(subsystem, key, value)
    
    db.commit()
    db.refresh(subsystem)
    
    return subsystem


@router.delete("/{subsystem_id}")
def delete_subsystem(subsystem_id: int, db: Session = Depends(get_db)):
    """刪除子系統（軟刪除，設為不啟用）"""
    subsystem = db.query(SubSystem).filter(SubSystem.id == subsystem_id).first()
    if not subsystem:
        raise HTTPException(status_code=404, detail="子系統不存在")
    
    # 軟刪除
    subsystem.is_active = False
    db.commit()
    
    return {"message": "子系統已停用"}