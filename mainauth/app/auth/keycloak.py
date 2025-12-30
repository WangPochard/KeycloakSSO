import httpx
from fastapi import HTTPException
from app.config import settings
from passlib.context import CryptContext
from logging import getLogger

logger = getLogger(__name__)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

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
    
    headers = {"Authorization": f"Bearer {access_token}"}
    
    async with httpx.AsyncClient() as client:
        response = await client.get(userinfo_url, headers=headers)
        if response.status_code != 200:
            raise HTTPException(status_code=401, detail="無效的 token")
        return response.json()

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
    
    headers = {"Authorization": f"Bearer {access_token}"}
    
    async with httpx.AsyncClient() as client:
        response = await client.get(userinfo_url, headers=headers)
        if response.status_code != 200:
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
    
    async with httpx.AsyncClient() as client:
        response = await client.post(token_url, data=data)

        logger.info("direct login..")
        logger.info(f"Keycloak Login Status: {response.status_code}")
        logger.info(f"Keycloak Login Response: {response.text}")
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=401,
                detail="帳號或密碼錯誤"
            )
        
        return response.json()

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