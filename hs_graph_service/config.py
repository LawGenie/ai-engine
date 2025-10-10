from pydantic_settings import BaseSettings
from pathlib import Path
import os

class Settings(BaseSettings):
    openai_api_key: str
    graph_model: str = "gpt-4o-mini"
    vector_index_path: str = "../tax_via_hs/index_store"
    fastapi_host: str = "0.0.0.0"
    fastapi_port: int = 8000
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()