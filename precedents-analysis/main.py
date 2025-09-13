from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
import json
import logging
from cbp_scraper import CBPDataCollector
from ai_analyzer import PrecedentsAnalyzer

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Precedents Analysis AI Engine", version="1.0.0")

# 요청 모델
class ProductAnalysisRequest(BaseModel):
    product_id: str
    product_name: str
    description: str
    hs_code: str
    origin_country: str
    price: float
    fob_price: float

# 응답 모델
class PrecedentsAnalysisResponse(BaseModel):
    success_cases: List[str]
    failure_cases: List[str]
    actionable_insights: List[str]
    risk_factors: List[str]
    recommended_action: str
    confidence_score: float
    is_valid: bool

# AI 분석기와 CBP 데이터 수집기 초기화
analyzer = PrecedentsAnalyzer()
cbp_collector = CBPDataCollector()

@app.get("/health")
async def health_check():
    """헬스체크 엔드포인트"""
    return {
        "status": "healthy",
        "service": "precedents-analysis-ai-engine",
        "version": "1.0.0"
    }

@app.post("/analyze-precedents", response_model=PrecedentsAnalysisResponse)
async def analyze_precedents(request: ProductAnalysisRequest):
    """
    상품 정보를 받아서 판례 분석을 수행합니다.
    """
    try:
        logger.info(f"판례 분석 시작: {request.product_id} - {request.product_name}")
        
        # 1. CBP에서 실제 판례 데이터 수집
        logger.info(f"CBP 데이터 수집 시작: HS코드 {request.hs_code}")
        cbp_data = await cbp_collector.get_precedents_by_hs_code(request.hs_code)
        logger.info(f"CBP 데이터 수집 완료: {len(cbp_data)}개 사례 발견")
        
        # 2. AI 분석 수행
        logger.info("AI 분석 시작")
        analysis_result = await analyzer.analyze_precedents(request.dict(), cbp_data)
        logger.info("AI 분석 완료")
        
        # 3. 결과 반환
        return PrecedentsAnalysisResponse(**analysis_result)
        
    except Exception as e:
        logger.error(f"판례 분석 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@app.get("/test-cbp/{hs_code}")
async def test_cbp_data(hs_code: str):
    """
    CBP 데이터 수집 테스트 엔드포인트
    """
    try:
        logger.info(f"CBP 테스트 시작: HS코드 {hs_code}")
        cbp_data = await cbp_collector.get_precedents_by_hs_code(hs_code)
        
        return {
            "hs_code": hs_code,
            "data_count": len(cbp_data),
            "sample_data": cbp_data[:3] if cbp_data else [],
            "status": "success"
        }
        
    except Exception as e:
        logger.error(f"CBP 테스트 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"CBP test failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
