from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import *
from app.auth.keycloak import *
from app.config import settings
from app.schemas import *
import secrets
from logging import getLogger
from datetime import datetime, timedelta, timezone
from app.utils import verify_password

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

# @router.post("/login")
# async def login_with_password(login_data: LoginRequest, db: Session = Depends(get_db)):
#     """使用帳號密碼直接登入 Keycloak"""
#     try:
#         user = db.query(User).filter(User.username == login_data.username).first()
#         password = login_data.password

#         # 驗證密碼
#         if not user or not verify_password(password, user.password_hash):
#             raise HTTPException(
#                 status_code=status.HTTP_401_UNAUTHORIZED,
#                 detail="帳號或密碼錯誤"
#             )

#         if not user.is_active:
#             raise HTTPException(
#                 status_code=status.HTTP_403_FORBIDDEN,
#                 detail="帳號已被停用"
#             )

#         session = db.query(SessionToken).filter(SessionToken.user_id == user.id).first()
#         if session:
#             if session.expires_at < datetime.now(timezone.utc) :
#                 logger.warning(f"Session 已過期，刪除 session")
#                 new_session_token = await refresh_access_token(session.refresh_token)
#                 session.access_token = new_session_token["access_token"]
#                 session.refresh_token = new_session_token["refresh_token"]
#                 expires_in_seconds = new_session_token.get("expires_in", 300)
#                 expires_at = datetime.now(timezone.utc)  + timedelta(seconds=expires_in_seconds)
#                 session.expires_at = expires_at

#                 db.commit()
#                 # db.refresh(session)
#                 return {
#                     "session_token": session.access_token,
#                     "user": {
#                         "id": user.id,
#                         "keycloak_uuid": user.keycloak_uuid,
#                         "username": user.username,
#                         "email": user.email,
#                     }
#                 }
#             else:
#                 logger.info(f"Session 有效，回傳 session token")
#                 return {
#                     "session_token": session.access_token,
#                     "user": {
#                         "id": user.id,
#                         "keycloak_uuid": user.keycloak_uuid,
#                         "username": user.username,
#                         "email": user.email,
#                     }
#                 }
#         # 沒有session紀錄、或session已過期，創建新的session

#         session_token = await direct_login(user.username, password)

#         expires_in_seconds = session_token.get("expires_in", 300)
#         expires_at = datetime.now(timezone.utc)  + timedelta(seconds=expires_in_seconds)

#         session = SessionToken(
#             user_id=user.id,
#             access_token=session_token["access_token"],
#             refresh_token=session_token["refresh_token"],
#             expires_at=expires_at
#         )

#         db.add(session)
#         db.commit()
#         # db.refresh(session)
#         logger.info(f"使用者 {user.username} 登入成功")

#         # 返回 token 和使用者資訊
#         return {
#             "session_token": session.access_token,
#             "user": {
#                 "id": user.id,
#                 "keycloak_uuid": user.keycloak_uuid,
#                 "username": user.username,
#                 "email": user.email,
#                 "first_name": user.first_name,
#                 "last_name": user.last_name,
#             }
#         }
        
#     except HTTPException as e:
#         logger.warning(f"HTTPException: {e.status_code} - {e.detail}")
#         raise 
#     except Exception as e:
#         logger.error(f"登入失敗: {str(e)}")
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail="登入處理失敗"
#         )

@router.post("/login")
async def login_with_password(login_data: LoginRequest, db: Session = Depends(get_db)):
    try:
        user = db.query(User).filter(User.username == login_data.username).first()

        if not user or not verify_password(login_data.password, user.password_hash):
            raise HTTPException(status_code=401, detail="帳號或密碼錯誤")

        if not user.is_active:
            raise HTTPException(status_code=403, detail="帳號已被停用")

        # ✅ 每次登入都創建新的 session,不要查詢舊的!
        session_token = await direct_login(user.username, login_data.password)
        expires_in_seconds = session_token.get("expires_in", 300)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)

        session = SessionToken(
            user_id=user.id,
            access_token=session_token["access_token"],
            refresh_token=session_token["refresh_token"],
            expires_at=expires_at
        )

        db.add(session)
        db.commit()
        db.refresh(session)
        
        logger.info(f"使用者 {user.username} 登入成功")

        return {
            "session_token": session.access_token,
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
            }
        }
        
    except HTTPException as e:
        raise 
    except Exception as e:
        logger.error(f"登入失敗: {str(e)}")
        raise HTTPException(status_code=500, detail="登入處理失敗")

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

@router.get("/code/{subsystem_id}/{user_id}")
async def get_subsystem_code(subsystem_id: int, user_id: int, db: Session = Depends(get_db)):
    try:
        # 1. 查詢該使用者最新且未過期的 session
        now = datetime.now(timezone.utc)
        session = db.query(SessionToken).filter(
            SessionToken.user_id == user_id,
            SessionToken.expires_at > now  # ⭐ 只查詢未過期的
        ).order_by(SessionToken.created_at.desc()).first()  # ⭐ 取最新的
        
        if not session:
            logger.error(f"找不到有效的 session，user_id: {user_id}")
            raise HTTPException(status_code=401, detail="Session 已過期或不存在，請重新登入")
        
        logger.info(f"✅ 找到有效 session: {session.access_token[:10]}...")
        logger.info(f"   Session expires_at: {session.expires_at}")
        
        # 2. 驗證子系統和使用者
        subsystem = db.query(SubSystem).filter(SubSystem.id == subsystem_id).first()
        if not subsystem:
            raise HTTPException(status_code=404, detail="子系統不存在")
        
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="使用者不存在")
        
        # 3. 刪除該使用者對該子系統的所有舊 authorization_code
        deleted_count = db.query(AuthorizationCode).filter(
            AuthorizationCode.user_id == user.id,
            AuthorizationCode.subsystem_id == subsystem.id
        ).delete()
        
        if deleted_count > 0:
            logger.info(f"刪除了 {deleted_count} 個舊的授權碼")
        
        db.commit()
        
        # 4. 創建新的 authorization_code（使用最新的 session token）
        expires_at = now + timedelta(minutes=10)

        sso_result = await exchange_token_for_subsystem(session.access_token, subsystem.keycloak_client_id)
        
        auth_code = AuthorizationCode(
            code=session.access_token,
            user_id=user.id,
            subsystem_id=subsystem.id,
            sso_token=sso_result["sso_token"],
            keycloak_uuid=user.keycloak_uuid,
            expires_at=expires_at,
            is_used=True,
            created_at=now
        )
        
        db.add(auth_code)
        db.commit()
        db.refresh(auth_code)
        
        logger.info(f"✅ 新增授權碼成功")
        logger.info(f"   User: {user.id}, Subsystem: {subsystem.id}")
        logger.info(f"   Expires at: {expires_at}")
        
        return {
            "token": sso_result["sso_token"],  # 返回最新的 token
            "subsystem_url": subsystem.url
        }
        
    except HTTPException as e:
        raise
    except Exception as e:
        logger.error(f"取得授權碼失敗: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="取得授權碼失敗")

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
        logger.error(f"Internal Server Error")
        raise e
    except Exception as e:
        logger.error(f"Token 驗證失敗: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token 無效或已過期"
        )