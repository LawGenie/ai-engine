from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any
import json
import logging
from cbp_scraper import CBPDataCollector
from ai_analyzer import PrecedentsAnalyzer
from vector_precedents_search import VectorPrecedentsSearch

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Precedents Analysis AI Engine", version="1.0.0")

# CORS 설정 추가
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 요청 모델
class ProductAnalysisRequest(BaseModel):
    product_id: str
    product_name: str
    description: str
    hs_code: str
    origin_country: str
    price: float
    fob_price: float

# 판례 상세 정보 모델
class PrecedentDetail(BaseModel):
    case_id: str
    title: str
    description: str
    status: str
    link: str
    source: str
    hs_code: str

# 판례 분석 전용 모델들만 유지

# 응답 모델
class PrecedentsAnalysisResponse(BaseModel):
    success_cases: List[str]
    failure_cases: List[str]
    review_cases: List[str]  # 검토 필요 사례 추가
    actionable_insights: List[str]
    risk_factors: List[str]
    recommended_action: str
    confidence_score: float
    is_valid: bool
    precedents_data: List[PrecedentDetail]  # 판례 원본 데이터 추가

# 🚀 AI 분석기, CBP 데이터 수집기, 벡터 검색기 초기화
analyzer = PrecedentsAnalyzer()
cbp_collector = CBPDataCollector()
vector_search = VectorPrecedentsSearch()

# 🚀 상호 연결 설정
vector_search.set_cbp_collector(cbp_collector)
cbp_collector.set_vector_search(vector_search)

# AI 분석 결과 캐싱을 위한 딕셔너리
analysis_cache = {}

@app.get("/health")
async def health_check():
    """헬스체크 엔드포인트"""
    return {
        "status": "healthy",
        "service": "precedents-analysis-ai-engine",
        "version": "1.0.0"
    }

# 판례 분석 전용 엔드포인트만 유지

@app.post("/analyze-precedents", response_model=PrecedentsAnalysisResponse)
async def analyze_precedents(request: ProductAnalysisRequest):
    """
    상품 정보를 받아서 판례 분석을 수행합니다. (캐싱 + 벡터 검색 적용)
    """
    try:
        logger.info(f"🚀 판례 분석 시작: {request.product_id} - {request.product_name}")
        
        # 🚀 1. CBP에서 실제 판례 데이터 수집 (캐싱 적용)
        logger.info(f"CBP 데이터 수집 시작: HS코드 {request.hs_code}")
        cbp_data = await cbp_collector.get_precedents_by_hs_code(request.hs_code)
        logger.info(f"CBP 데이터 수집 완료: {len(cbp_data)}개 사례 발견")
        
        # 🚀 2. 벡터 검색으로 유사 판례 추가 수집
        logger.info("벡터 기반 유사 판례 검색 시작")
        similar_precedents = await vector_search.find_similar_precedents(
            product_description=request.description,
            product_name=request.product_name,
            top_k=5
        )
        logger.info(f"유사 판례 검색 완료: {len(similar_precedents)}개 추가 사례")
        
        # 🚀 3. 기존 CBP 데이터 + 유사 판례 결합
        combined_data = cbp_data + similar_precedents
        logger.info(f"총 판례 데이터: {len(combined_data)}개 (CBP: {len(cbp_data)}, 유사: {len(similar_precedents)})")
        
        # 🚀 4. AI 분석 수행 (캐싱 적용)
        cache_key = f"{request.hs_code}_{request.product_name}_{len(combined_data)}"
        
        if cache_key in analysis_cache:
            logger.info("✅ 캐시에서 AI 분석 결과 반환")
            analysis_result = analysis_cache[cache_key]
        else:
            logger.info("AI 분석 시작")
            analysis_result = await analyzer.analyze_precedents(request.model_dump(), combined_data)
            analysis_cache[cache_key] = analysis_result  # 결과 캐싱
            logger.info("AI 분석 완료 및 캐싱")
        
        # 5. 딕셔너리를 문자열로 변환
        success_cases = []
        failure_cases = []
        review_cases = []
        
        for case in analysis_result.get("success_cases", []):
            if isinstance(case, dict):
                success_cases.append(case.get("text", str(case)))
            else:
                success_cases.append(str(case))
        
        for case in analysis_result.get("failure_cases", []):
            if isinstance(case, dict):
                failure_cases.append(case.get("text", str(case)))
            else:
                failure_cases.append(str(case))
        
        for case in analysis_result.get("review_cases", []):
            if isinstance(case, dict):
                review_cases.append(case.get("text", str(case)))
            else:
                review_cases.append(str(case))
        
        # 6. 판례 원본 데이터 포맷팅
        precedents_data = []
        for precedent in combined_data:
            precedents_data.append(PrecedentDetail(
                case_id=precedent.get("case_id", "N/A"),
                title=precedent.get("title", "N/A"),
                description=precedent.get("description", "N/A"),
                status=precedent.get("status", "UNKNOWN"),
                link=precedent.get("link", ""),
                source=precedent.get("source", "unknown"),
                hs_code=precedent.get("hs_code", request.hs_code)
            ))
        
        # 7. 결과 반환 (판례 원본 데이터 포함)
        return PrecedentsAnalysisResponse(
            success_cases=success_cases,
            failure_cases=failure_cases,
            review_cases=review_cases,  # 검토 필요 사례 추가
            actionable_insights=analysis_result.get("actionable_insights", []),
            risk_factors=analysis_result.get("risk_factors", []),
            recommended_action=analysis_result.get("recommended_action", ""),
            confidence_score=analysis_result.get("confidence_score", 0.0),
            is_valid=analysis_result.get("is_valid", False),
            precedents_data=precedents_data  # 판례 원본 데이터 추가!
        )
        
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

@app.get("/cache-stats")
async def get_cache_stats():
    """
    캐시 및 벡터 검색 통계 조회
    """
    try:
        cache_stats = cbp_collector.get_cache_stats()
        search_stats = vector_search.get_search_stats()
        
        return {
            "cbp_cache_stats": cache_stats,
            "search_stats": search_stats,
            "ai_analysis_cache_size": len(analysis_cache),
            "ai_analysis_cache_keys": list(analysis_cache.keys()),
            "status": "success"
        }
        
    except Exception as e:
        logger.error(f"통계 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Stats retrieval failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
