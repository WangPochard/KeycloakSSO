from sqlalchemy import Column, String, Boolean, Integer, DateTime, Text
from sqlalchemy.sql import func
from app.database import Base

class User(Base):
    """使用者表"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    keycloak_uuid = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, index=True)
    email = Column(String(255), unique=True, index=True)
    password_hash = Column(String(255))
    first_name = Column(String(100))
    last_name = Column(String(100))
    department = Column(String(100))
    employee_id = Column(String(50))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self):
        return f"<User {self.username}>"


class SubSystem(Base):
    """子系統表"""
    __tablename__ = "subsystems"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    code = Column(String(50), unique=True, nullable=False, index=True)
    description = Column(Text)
    url = Column(String(500), nullable=False)
    icon = Column(String(500))  # 圖示 URL
    keycloak_client_id = Column(String(100), nullable=False)
    keycloak_client_secret = Column(String(500))  # 加密儲存
    is_active = Column(Boolean, default=True)
    order = Column(Integer, default=0)  # 排序
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self):
        return f"<SubSystem {self.name}>"