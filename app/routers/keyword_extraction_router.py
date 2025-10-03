"""
키워드 추출 라우터
상품명과 설명에서 핵심 키워드를 추출하는 API
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from workflows.tools import RequirementsTools

router = APIRouter(prefix="/keywords", tags=["keywords"])

class KeywordExtractionRequest(BaseModel):
    product_name: str
    product_description: Optional[str] = ""

class KeywordExtractionResponse(BaseModel):
    keywords: List[str]
    product_name: str
    product_description: str
    extracted_count: int

# 도구 인스턴스
tools = RequirementsTools()

@router.post("/extract", response_model=KeywordExtractionResponse)
async def extract_keywords(request: KeywordExtractionRequest):
    """
    상품명과 설명에서 핵심 키워드 추출
    
    Args:
        request: 키워드 추출 요청 정보
        
    Returns:
        KeywordExtractionResponse: 추출된 키워드 목록
    """
    try:
        print(f"🔑 키워드 추출 요청 - 상품: {request.product_name}")
        
        # 키워드 추출 실행
        keywords = tools._extract_keywords_from_product(
            product_name=request.product_name,
            product_description=request.product_description or ""
        )
        
        print(f"✅ 키워드 추출 완료 - 추출된 키워드: {keywords[:5]}")
        
        return KeywordExtractionResponse(
            keywords=keywords,
            product_name=request.product_name,
            product_description=request.product_description or "",
            extracted_count=len(keywords)
        )
        
    except Exception as e:
        print(f"❌ 키워드 추출 실패: {e}")
        raise HTTPException(status_code=500, detail=f"키워드 추출 중 오류 발생: {str(e)}")

@router.get("/health")
async def health_check():
    """키워드 추출 서비스 상태 확인"""
    return {
        "status": "healthy",
        "service": "keyword_extraction",
        "description": "상품명과 설명에서 핵심 키워드를 추출하는 서비스"
    }
