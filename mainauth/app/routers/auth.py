from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.auth.keycloak import *
from app.config import settings
from app.schemas import *
import secrets
from logging import getLogger

logger = getLogger(__name__)

router = APIRouter()

@router.get("/login")
def login(subsystem_code: str = None):
    """導向 Keycloak 登入"""
    state = secrets.token_urlsafe(32)
    
    redirect_uri = f"{settings.MAIN_SYSTEM_URL}/auth/callback"
    
    auth_url = (
        f"{settings.KEYCLOAK_URL}/realms/{settings.KEYCLOAK_REALM}"
        f"/protocol/openid-connect/auth"
        f"?client_id={settings.KEYCLOAK_CLIENT_ID}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code"
        f"&scope=openid profile email"
        f"&state={state}"
    )
    
    return RedirectResponse(auth_url)

@router.post("/login")
async def login_with_password(
    login_data: LoginRequest,
    db: Session = Depends(get_db)
):
    """使用帳號密碼直接登入 Keycloak"""
    try:
        # 1. 向 Keycloak 驗證帳號密碼，取得 token
        tokens = await direct_login(login_data.username, login_data.password)
        access_token = tokens["access_token"]
        refresh_token = tokens.get("refresh_token")
        
        # 2. 用 token 取得使用者資訊
        user_info = await get_user_info(access_token)
        
        # 3. 在本地資料庫建立或更新使用者
        keycloak_uuid = user_info["sub"]
        user = db.query(User).filter(User.keycloak_uuid == keycloak_uuid).first()
        
        if not user:
            # 第一次登入，建立使用者記錄
            user = User(
                keycloak_uuid=keycloak_uuid,
                username=user_info.get("preferred_username"),
                email=user_info.get("email"),
                first_name=user_info.get("given_name"),
                last_name=user_info.get("family_name"),
                is_active=True
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        
        # 4. 返回 token 和使用者資訊
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "Bearer",
            "user": {
                "id": user.id,
                "keycloak_uuid": user.keycloak_uuid,
                "username": user.username,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
            }
        }
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"❌ 登入失敗: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="帳號或密碼錯誤"
        )

@router.get("/callback")
async def callback(code: str, state: str, db: Session = Depends(get_db)):
    """Keycloak 回調"""
    
    # 換 token
    redirect_uri = f"{settings.MAIN_SYSTEM_URL}/auth/callback"
    tokens = await exchange_code_for_token(code, redirect_uri)
    access_token = tokens["access_token"]
    
    # 取得使用者資訊
    user_info = await get_user_info(access_token)
    
    # 建立或更新使用者
    keycloak_uuid = user_info["sub"]
    user = db.query(User).filter(User.keycloak_uuid == keycloak_uuid).first()
    
    if not user:
        user = User(
            keycloak_uuid=keycloak_uuid,
            username=user_info.get("preferred_username"),
            email=user_info.get("email"),
            first_name=user_info.get("given_name"),
            last_name=user_info.get("family_name"),
        )
        db.add(user)
        db.commit()
    
    # 返回 token（或建立 session）
    return {
        "access_token": access_token,
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
        }
    }

@router.post("/verify")
async def verify_token(request: TokenVerifyRequest, db: Session = Depends(get_db)):
    """驗證 token 並回傳使用者資訊（給子系統呼叫）"""
    try:
        logger.info(f"收到驗證請求，token : {request.token[:10]}...")
        
        # 向 Keycloak 驗證 token
        user_info = await get_user_info(request.token)
        logger.info(f"Keycloak 驗證成功: {user_info.get('preferred_username')}")
        
        # 從本地資料庫取得使用者完整資訊
        keycloak_uuid = user_info["sub"]
        user = db.query(User).filter(User.keycloak_uuid == keycloak_uuid).first()
        
        if not user:
            logger.error(f"本地資料庫找不到使用者: {keycloak_uuid}")
            raise HTTPException(status_code=404, detail="使用者不存在於本地資料庫")
        
        if not user.is_active:
            logger.error(f"使用者已停用: {user.username}")
            raise HTTPException(status_code=403, detail="使用者已停用")
        
        logger.info(f"驗證完成，回傳使用者資訊: {user.username}")
        
        # 回傳使用者資訊
        return {
            "valid": True,
            "user": {
                "id": user.id,
                "keycloak_uuid": user.keycloak_uuid,
                "username": user.username,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "department": user.department,
                "employee_id": user.employee_id,
                "is_active": user.is_active
            }
        }
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"❌ Token 驗證失敗: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token 無效或已過期: {str(e)}"
        )