from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime
from .common import BaseResponse

# 상품 등록 관련 스키마
class ProductRegistrationRequest(BaseModel):
    """상품 등록 요청"""
    product_name: str
    description: str
    category: Optional[str] = None

class ProductCompletionRequest(BaseModel):
    """상품 등록 완료 요청"""
    product_id: str
    hs_code: str
    seller_id: str

# HS코드 추천 관련 스키마
class HSRecommendationResponse(BaseModel):
    """HS코드 추천 응답"""
    recommended_codes: List[Dict[str, Any]]
    confidence: float
    reasoning: str

# AI 분석 결과 관련 스키마
class AnalysisResult(BaseModel):
    """AI 분석 결과"""
    product_id: str
    hs_code: str
    tariff_analysis: Dict[str, Any]
    requirements_analysis: Dict[str, Any]
    precedents_analysis: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

class AnalysisStatusResponse(BaseModel):
    """분석 상태 응답"""
    product_id: str
    status: str  # "pending", "processing", "completed", "failed"
    progress: int  # 0-100
    estimated_completion: Optional[datetime] = None

# 챗봇 관련 스키마
class ChatRequest(BaseModel):
    """챗봇 요청"""
    message: str
    product_id: Optional[str] = None
    user_id: Optional[str] = None

class ChatResponse(BaseModel):
    """챗봇 응답"""
    answer: str
    sources: List[Dict[str, str]]
    confidence: float
    analysis_type: str  # "tariff", "requirements", "precedents", "general"
