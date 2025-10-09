from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    """애플리케이션 설정 (환경변수 우선)"""
    
    # OpenAI 설정
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    graph_model: str = "gpt-4o-mini"
    
    # FastAPI 설정
    fastapi_host: str = "0.0.0.0"
    fastapi_port: int = 8000
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()