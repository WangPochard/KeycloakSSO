from passlib.context import CryptContext
from logging import getLogger
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models import SessionToken

logger = getLogger(__name__)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    驗證密碼
    Args:
        plain_password: 使用者輸入的明文密碼
        hashed_password: 資料庫中儲存的 hash 密碼
    """
    logger.info(f"驗證密碼: 明文={plain_password}, Hash={hashed_password}")
    result = pwd_context.verify(plain_password, hashed_password)
    logger.info(f"驗證結果: {result}")
    return result

def cleanup_expired_sessions(db: Session):
    db.query(SessionToken).filter(
        SessionToken.expires_at < datetime.now(timezone.utc)
    ).delete()
    db.commit()