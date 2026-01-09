from app.logger import setup_logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base
from app.routers import auth, users, subsystems

# 建立資料表
Base.metadata.create_all(bind=engine)

app = FastAPI(title="主系統 SSO")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 註冊路由
app.include_router(auth.router, prefix="/api/auth", tags=["認證"])
app.include_router(users.router, prefix="/api/users", tags=["使用者"])
app.include_router(subsystems.router, prefix="/api/subsystems", tags=["子系統"])

@app.get("/")
def root():
    return {"message": "主系統 SSO API"}