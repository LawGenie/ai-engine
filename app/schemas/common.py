from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

class BaseResponse(BaseModel):
    """공통 응답 스키마"""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None

class ErrorResponse(BaseModel):
    """에러 응답 스키마"""
    success: bool = False
    error: str
    detail: Optional[str] = None

class HealthResponse(BaseModel):
    """헬스체크 응답 스키마"""
    status: str
    timestamp: datetime
    services: Dict[str, str]
