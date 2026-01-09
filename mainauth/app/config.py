from pydantic_settings import BaseSettings
from urllib.parse import quote_plus

class Settings(BaseSettings):
    # Database
    DB_USER: str
    DB_PASSWORD: str
    DB_HOST: str
    DB_PORT: str
    DB_NAME: str
    
    # Keycloak
    KEYCLOAK_URL: str
    KEYCLOAK_REALM: str
    KEYCLOAK_CLIENT_ID: str
    KEYCLOAK_CLIENT_SECRET: str = "CuxacZm7gM4D4SYxhafhgvyqilKl4tyQ"
    KEYCLOAK_ADMIN_USERNAME: str 
    KEYCLOAK_ADMIN_PASSWORD: str 
    
    # App
    SECRET_KEY: str = ""
    MAIN_SYSTEM_URL: str
    
    class Config:
        env_file = ".env"
    
    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql://{self.DB_USER}:{quote_plus(self.DB_PASSWORD)}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @property
    def KEYCLOAK_ADMIN_PWD(self) -> str:
        return quote_plus(self.KEYCLOAK_ADMIN_PASSWORD)

settings = Settings()