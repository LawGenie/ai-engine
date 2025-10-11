"""
HS 코드 분석 전용 FastAPI 서버
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import logging
from hs_code_analyzer import HsCodeAnalyzer
from workflows.workflow import run_analysis_workflow

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="HS Code Analysis Service",
    description="제품 정보를 바탕으로 미국 HS 코드를 추천하는 AI 서비스",
    version="1.0.0"
)

# HS 코드 분석기 인스턴스
hs_analyzer = HsCodeAnalyzer()

# Pydantic 모델들
class HsCodeAnalysisRequest(BaseModel):
    product_name: str
    product_description: str
    origin_country: Optional[str] = None

class HsCodeSuggestion(BaseModel):
    hsCode: str
    description: str
    confidenceScore: float
    reasoning: str
    usTariffRate: float

class HsCodeAnalysisResponse(BaseModel):
    suggestions: list[HsCodeSuggestion]
    analysisSessionId: str
    timestamp: str
    startTime: str
    endTime: str
    processingTimeMs: float
    isValid: bool

@app.get("/")
async def root():
    return {
        "message": "HS Code Analysis Service",
        "version": "1.0.0",
        "status": "running"
    }

@app.get("/health")
async def health_check():
    """
    서비스 상태 확인
    """
    return {
        "status": "healthy", 
        "service": "hs-code-analysis",
        "version": "1.0.0"
    }

@app.post("/api/hs-code/analyze", response_model=HsCodeAnalysisResponse)
async def analyze_hs_code(request: HsCodeAnalysisRequest):
    """
    제품 정보를 바탕으로 HS 코드 3개를 추천합니다.
    
    Args:
        request: 제품 정보 (제품명, 설명, 원산지)
        
    Returns:
        HsCodeAnalysisResponse: HS 코드 추천 결과
    """
    try:
        logger.info(f"HS 코드 분석 요청 - 제품명: {request.product_name}")
        
        result = await hs_analyzer.analyze_hs_code(
            product_name=request.product_name,
            product_description=request.product_description,
            origin_country=request.origin_country
        )
        
        return HsCodeAnalysisResponse(**result)
        
    except Exception as e:
        logger.error(f"HS 코드 분석 API 오류: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"HS 코드 분석 중 오류가 발생했습니다: {str(e)}"
        )

@app.post("/api/hs-code/analyze-graph", response_model=HsCodeAnalysisResponse)
async def analyze_hs_code_graph(request: HsCodeAnalysisRequest):
    """
    LangGraph + FAISS 유사도 검색 기반으로 HS 코드 3개를 추천합니다.
    """
    try:
        logger.info(f"[Graph] HS 코드 분석 요청 - 제품명: {request.product_name}")
        graph_result = run_analysis_workflow(
            product_name=request.product_name,
            description=request.product_description or ""
        )
        # graph_result: { suggestions: [...], analysisSessionId: ... }
        return HsCodeAnalysisResponse(**graph_result)
    except Exception as e:
        logger.error(f"[Graph] HS 코드 분석 API 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Graph 분석 오류: {str(e)}")

@app.get("/api/hs-code/status")
async def get_service_status():
    """
    서비스 상태 및 설정 정보를 반환합니다.
    """
    return {
        "service": "hs-code-analysis",
        "model": hs_analyzer.model,
        "status": "active",
        "endpoints": [
            "GET /",
            "GET /health", 
            "GET /api/hs-code/status",
            "POST /api/hs-code/analyze"
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app", 
        host="127.0.0.1", 
        port=8001,  # HS 코드 분석 전용 포트
        reload=True
    )
