from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

# ============ User Schemas ============

class UserBase(BaseModel):
    username: str
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    department: Optional[str] = None
    employee_id: Optional[str] = None

class UserCreate(UserBase):
    keycloak_uuid: str

class LocalUserCreate(BaseModel):
    username: str
    password: str
    email: str
    first_name: str
    last_name: str

class UserUpdate(BaseModel):
    department: Optional[str] = None
    employee_id: Optional[str] = None
    is_active: Optional[bool] = None

class UserInDB(UserBase):
    id: int
    keycloak_uuid: str
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


# ============ SubSystem Schemas ============

class SubSystemBase(BaseModel):
    name: str
    code: str
    description: Optional[str] = None
    url: str
    icon: Optional[str] = None
    keycloak_client_id: str
    is_active: bool = True
    order: int = 0

class SubSystemCreate(SubSystemBase):
    keycloak_client_secret: Optional[str] = None

class SubSystemUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    icon: Optional[str] = None
    is_active: Optional[bool] = None
    order: Optional[int] = None

class SubSystemInDB(SubSystemBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


# ============ Auth Schemas ============

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    username: Optional[str] = None
    keycloak_uuid: Optional[str] = None

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    user: UserInDB

class ServiceVerifyRequest(BaseModel):
    """
    access_token: 由主系統帶去子系統的一次性隨機碼
    service_name: 子系統名稱
    """
    access_token: str
    service_name: str

class TokenVerifyRequest(BaseModel):
    token: str