import httpx
from fastapi import HTTPException
from app.config import settings
from passlib.context import CryptContext
from logging import getLogger
from datetime import datetime, timezone

logger = getLogger(__name__)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def create_keycloak_user(username: str, password: str, email: str = None, 
                               first_name: str = None, last_name: str = None):
    """在 Keycloak 創建使用者"""
    
    # 1. 先取得 admin token
    admin_token = await get_admin_token()
    
    # 2. 創建使用者
    users_url = f"{settings.KEYCLOAK_URL}/admin/realms/{settings.KEYCLOAK_REALM}/users"
    
    headers = {
        "Authorization": f"Bearer {admin_token}",
        "Content-Type": "application/json"
    }
    
    user_data = {
        "username": username,
        "enabled": True,
        "email": email,
        "firstName": first_name,
        "lastName": last_name,
        "credentials": [{
            "type": "password",
            "value": password,
            "temporary": False
        }]
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(users_url, json=user_data, headers=headers)
        
        if response.status_code == 409:
            raise HTTPException(status_code=400, detail="Keycloak 中使用者已存在")
        
        if response.status_code != 201:
            raise HTTPException(
                status_code=response.status_code, 
                detail=f"無法在 Keycloak 創建使用者: {response.text}"
            )
        
        # 3. 從 Location header 取得使用者 ID
        location = response.headers.get("Location")
        user_id = location.split("/")[-1]
        
        return user_id


async def get_admin_token():
    """
    取得 Keycloak admin token
    
    Grant Type是 OAuth2 的授權類型
        authorization_code - 使用者登入，重導向拿 code
        password - 直接用帳號密碼換 token（不安全）
        ** client_credentials - 服務對服務，用 client ID + secret 換 token（我們現在用的）
        refresh_token - 用 refresh token 換新的 access token
    """
    token_url = f"{settings.KEYCLOAK_URL}/realms/djangoSSO/protocol/openid-connect/token"
    
    
    data = {
        "grant_type": "client_credentials", # 用 client ID + secret 換 token
        "client_id": settings.KEYCLOAK_CLIENT_ID,
        "client_secret": settings.KEYCLOAK_CLIENT_SECRET,
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(token_url, data=data)

        logger.info("admin token..")
        logger.info(f"Status Code: {response.status_code}")
        logger.info(f"Response: {response.text}")
        
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="無法取得 Keycloak admin token")
        
        return response.json()["access_token"]


async def exchange_code_for_token(code: str, redirect_uri: str):
    """用 code 換 token"""
    token_url = f"{settings.KEYCLOAK_URL}/realms/{settings.KEYCLOAK_REALM}/protocol/openid-connect/token"
    
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": settings.KEYCLOAK_CLIENT_ID,
        "client_secret": settings.KEYCLOAK_CLIENT_SECRET,
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(token_url, data=data)
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail="無法取得 token")
        return response.json()


async def get_user_info(access_token: str):
    """用 token 取得使用者資訊"""
    userinfo_url = f"{settings.KEYCLOAK_URL}/realms/{settings.KEYCLOAK_REALM}/protocol/openid-connect/userinfo"
    
    logger.info(f"=== 驗證 Token ===")
    logger.info(f"Token 長度: {len(access_token)}")
    logger.info(f"Token 前50字元: {access_token[:50]}")
    logger.info(f"Token 後50字元: {access_token[-50:]}")
    logger.info(f"Userinfo URL: {userinfo_url}")

    headers = {"Authorization": f"Bearer {access_token}"}
    
    # 加上這些 log！
    logger.info(f"Request Headers: {headers}")

    async with httpx.AsyncClient() as client:
        response = await client.get(userinfo_url, headers=headers)
        
        logger.info(f"Keycloak 回應狀態碼: {response.status_code}")
        logger.info(f"Keycloak 回應內容: {response.text}")
        
        if response.status_code != 200:
            logger.error(f"Token 驗證失敗，狀態碼: {response.status_code}")
            logger.error(f"錯誤訊息: {response.text}")
            raise HTTPException(status_code=401, detail="無效的 token")
        return response.json()


def hash_password(password: str) -> str:
    return pwd_context.hash(password)

async def direct_login(username: str, password: str):
    """使用帳號密碼向 Keycloak 取得 token（Resource Owner Password Credentials）"""
    token_url = f"{settings.KEYCLOAK_URL}/realms/{settings.KEYCLOAK_REALM}/protocol/openid-connect/token"
    
    data = {
        "grant_type": "password",
        "client_id": settings.KEYCLOAK_CLIENT_ID,
        "client_secret": settings.KEYCLOAK_CLIENT_SECRET,
        "username": username,
        "password": password,
        "scope": "openid profile email"
    }
    
    logger.info("=== 向 Keycloak 請求新 Token ===")
    logger.info(f"Token URL: {token_url}")
    logger.info(f"Username: {username}")
    
    async with httpx.AsyncClient() as client:
        response = await client.post(token_url, data=data)

        logger.info(f"Keycloak Login Status: {response.status_code}")
        logger.info(f"Keycloak Login Response: {response.text}")
        
        if response.status_code != 200:
            raise HTTPException(status_code=401, detail="帳號或密碼錯誤")
        
        token_data = response.json()
        
        # 診斷：解析並檢查 token 時間
        import base64
        import json
        import time
        
        access_token = token_data["access_token"]
        parts = access_token.split('.')
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + '==').decode('utf-8'))
        
        current_time = time.time()
        
        logger.info("=== Keycloak 回傳的 Token 資訊 ===")
        logger.info(f"Token 發行時間 (iat): {datetime.fromtimestamp(payload['iat'], tz=timezone.utc)}")
        logger.info(f"Token 過期時間 (exp): {datetime.fromtimestamp(payload['exp'], tz=timezone.utc)}")
        logger.info(f"當前時間: {datetime.fromtimestamp(current_time, tz=timezone.utc)}")
        logger.info(f"Token 有效期: {(payload['exp'] - payload['iat'])/60} 分鐘")
        
        if current_time > payload['exp']:
            logger.error(f"Keycloak 回傳的 Token 已經過期！")
        else:
            logger.info(f"Token 有效，還有 {(payload['exp'] - current_time)/60:.1f} 分鐘")
        
        return token_data

async def refresh_access_token(refresh_token: str):
    """使用 refresh token 取得新的 access token"""
    token_url = f"{settings.KEYCLOAK_URL}/realms/{settings.KEYCLOAK_REALM}/protocol/openid-connect/token"
    
    data = {
        "grant_type": "refresh_token",
        "client_id": settings.KEYCLOAK_CLIENT_ID,
        "client_secret": settings.KEYCLOAK_CLIENT_SECRET,
        "refresh_token": refresh_token
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(token_url, data=data)
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=401,
                detail="Refresh token 無效"
            )
        
        return response.json()

# async def exchange_token_for_subsystem(user_access_token: str, target_client_id: str, target_client_secret: str):
#     """
#     使用 Token Exchange 為特定子系統取得專屬 token
#     """
#     token_url = f"{settings.KEYCLOAK_URL}/realms/{settings.KEYCLOAK_REALM}/protocol/openid-connect/token"
    
#     data = {
#         "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
#         "client_id": target_client_id,
#         "client_secret": target_client_secret,
#         "subject_token": user_access_token,
#         "subject_token_type": "urn:ietf:params:oauth:token-type:access_token",
#         "requested_token_type": "urn:ietf:params:oauth:token-type:access_token"
#     }

#     logger.info(f"發送 Token Exchange 請求到: {token_url}")
#     logger.info(f"Client ID: {target_client_id}")
    
#     async with httpx.AsyncClient() as client:
#         response = await client.post(
#             token_url,
#             data=data,
#             headers={"Content-Type": "application/x-www-form-urlencoded"}
#         )
    
#     if response.status_code != 200:
#         logger.error(f"Token Exchange 失敗: {response.text}")
#         raise HTTPException(status_code=500, detail="Token 交換失敗")
        
#     result = response.json()
#     return result["access_token"]

async def exchange_token_for_subsystem(user_access_token: str, target_client_id: str):
    """
    使用 Keycloak Token Exchange
    將「主系統的 user access token」
    換成「子系統專用的 access token」
    """

    token_url = (
        f"{settings.KEYCLOAK_URL}/realms/"
        f"{settings.KEYCLOAK_REALM}/protocol/openid-connect/token"
    )

    data = {
        # Token Exchange 固定值
        "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",

        # 誰來換（主系統 client）
        "client_id": settings.KEYCLOAK_CLIENT_ID,
        "client_secret": settings.KEYCLOAK_CLIENT_SECRET,

        # 要拿誰的 token 來換（account）
        "subject_token": user_access_token,
        "subject_token_type": "urn:ietf:params:oauth:token-type:access_token",

        # 要換成誰的 token（子系統）
        "audience": target_client_id,
    }

    logger.info("=== Token Exchange ===")
    logger.info(f"Target client: {target_client_id}")

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            token_url,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    logger.info(f"Keycloak status: {response.status_code}")
    logger.info(f"Keycloak response: {response.text}")

    if response.status_code != 200:
        raise HTTPException(
            status_code=401,
            detail=f"Token Exchange 失敗: {response.text}",
        )

    result = response.json()

    return {
        "sso_token": result["access_token"],
        "expires_in": result["expires_in"],
        "token_type": result["token_type"],
    }

async def logout_user(access_token: str):
    """登出使用者（撤銷 token）"""
    logout_url = f"{settings.KEYCLOAK_URL}/realms/{settings.KEYCLOAK_REALM}/protocol/openid-connect/logout"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    data = {
        "client_id": settings.KEYCLOAK_CLIENT_ID,
        "client_secret": settings.KEYCLOAK_CLIENT_SECRET
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(logout_url, headers=headers, data=data)
        
        if response.status_code not in [200, 204]:
            raise HTTPException(
                status_code=400,
                detail="登出失敗"
            )