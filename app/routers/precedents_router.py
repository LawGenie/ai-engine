"""
판례 분석 라우터 (통합 레이어)

Original Implementation:
- Location: precedents-analysis/
- Files: main.py, cbp_scraper.py, ai_analyzer.py, vector_precedents_search.py, faiss_precedents_db.py
- Author: hwangseojin223
- Purpose: CBP 판례 데이터 수집, FAISS 벡터 검색, AI 기반 판례 분석

Integration Work:
- Date: 2025-10-12
- Purpose: 메인 AI Engine에 판례 분석 기능 통합
- Changes: FastAPI 라우터로 변환, lifespan 초기화, 단일 서버 통합

Note: 
원본 코드는 precedents-analysis/ 디렉토리에 보존되어 있으며,
이 파일은 해당 모듈들을 import하여 FastAPI 엔드포인트로 제공하는 통합 레이어입니다.
원작자(hwangseojin223)의 기여 이력은 precedents-analysis/ 디렉토리의 Git 이력에서 확인 가능합니다.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
import logging
import sys
from pathlib import Path

# precedents-analysis 디렉토리를 Python path에 추가
project_root = Path(__file__).resolve().parents[2]
precedents_path = project_root / "precedents-analysis"
if str(precedents_path) not in sys.path:
    sys.path.insert(0, str(precedents_path))

# precedents-analysis 모듈 import (팀원 원본 코드)
try:
    from cbp_scraper import CBPDataCollector
    from ai_analyzer import PrecedentsAnalyzer
    from vector_precedents_search import VectorPrecedentsSearch
    print("✅ precedents-analysis 모듈 import 성공")
except ImportError as e:
    print(f"❌ precedents-analysis 모듈 import 실패: {e}")
    CBPDataCollector = None
    PrecedentsAnalyzer = None
    VectorPrecedentsSearch = None

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/precedents",
    tags=["precedents"],
    responses={404: {"description": "Not found"}},
)

# 요청 모델
class ProductAnalysisRequest(BaseModel):
    product_id: str
    product_name: str
    description: str
    hs_code: str
    origin_country: str = "US"
    price: float = 0.0
    fob_price: float = 0.0

# 판례 상세 정보 모델
class PrecedentDetail(BaseModel):
    case_id: str
    title: str
    description: str
    status: str
    link: str
    source: str
    hs_code: str

# 응답 모델
class PrecedentsAnalysisResponse(BaseModel):
    success_cases: List[str]
    failure_cases: List[str]
    review_cases: List[str]
    actionable_insights: List[str]
    risk_factors: List[str]
    recommended_action: str
    confidence_score: float
    is_valid: bool
    precedents_data: List[PrecedentDetail]

# 전역 인스턴스 (lifespan에서 초기화)
analyzer = None
cbp_collector = None
vector_search = None
analysis_cache = {}

def initialize_precedents_services():
    """판례 분석 서비스 초기화"""
    global analyzer, cbp_collector, vector_search
    
    if CBPDataCollector is None or PrecedentsAnalyzer is None or VectorPrecedentsSearch is None:
        logger.warning("⚠️ precedents-analysis 모듈을 import할 수 없습니다. 판례 분석 기능이 비활성화됩니다.")
        return False
    
    try:
        logger.info("🚀 판례 분석 서비스 초기화 중...")
        
        # 인스턴스 생성
        analyzer = PrecedentsAnalyzer()
        cbp_collector = CBPDataCollector()
        vector_search = VectorPrecedentsSearch()
        
        # 상호 연결 설정
        vector_search.set_cbp_collector(cbp_collector)
        cbp_collector.set_vector_search(vector_search)
        
        logger.info("✅ 판례 분석 서비스 초기화 완료")
        return True
        
    except Exception as e:
        logger.error(f"❌ 판례 분석 서비스 초기화 실패: {e}")
        return False

@router.get("/health")
async def precedents_health_check():
    """판례 분석 서비스 헬스체크"""
    is_ready = analyzer is not None and cbp_collector is not None and vector_search is not None
    
    return {
        "status": "healthy" if is_ready else "unavailable",
        "service": "precedents-analysis",
        "version": "1.0.0",
        "cache_size": len(analysis_cache),
        "ready": is_ready
    }

@router.post("/analyze", response_model=PrecedentsAnalysisResponse)
async def analyze_precedents(request: ProductAnalysisRequest):
    """
    상품 정보를 받아서 판례 분석을 수행합니다.
    CBP 데이터 수집 + 벡터 검색 + AI 분석
    """
    # 서비스가 초기화되지 않았으면 에러
    if analyzer is None or cbp_collector is None or vector_search is None:
        raise HTTPException(
            status_code=503, 
            detail="Precedents analysis service is not available. Please check server logs."
        )
    
    try:
        logger.info(f"🚀 판례 분석 시작: {request.product_id} - {request.product_name}")
        
        # 1. CBP에서 실제 판례 데이터 수집 (캐싱 적용)
        logger.info(f"📋 CBP 데이터 수집 시작: HS코드 {request.hs_code}")
        cbp_data = await cbp_collector.get_precedents_by_hs_code(request.hs_code)
        logger.info(f"✅ CBP 데이터 수집 완료: {len(cbp_data)}개 사례")
        
        # 2. 벡터 검색으로 유사 판례 추가 수집
        logger.info("🔍 벡터 기반 유사 판례 검색 시작")
        similar_precedents = await vector_search.find_similar_precedents(
            product_description=request.description,
            product_name=request.product_name,
            top_k=5
        )
        logger.info(f"✅ 유사 판례 검색 완료: {len(similar_precedents)}개")
        
        # 3. 기존 CBP 데이터 + 유사 판례 결합
        combined_data = cbp_data + similar_precedents
        logger.info(f"📊 총 판례 데이터: {len(combined_data)}개 (CBP: {len(cbp_data)}, 유사: {len(similar_precedents)})")
        
        # 4. AI 분석 수행 (캐싱 적용)
        cache_key = f"{request.hs_code}_{request.product_name}_{len(combined_data)}"
        
        if cache_key in analysis_cache:
            logger.info("✅ 캐시에서 AI 분석 결과 반환")
            analysis_result = analysis_cache[cache_key]
        else:
            logger.info("🤖 AI 분석 시작")
            analysis_result = await analyzer.analyze_precedents(request.model_dump(), combined_data)
            analysis_cache[cache_key] = analysis_result
            logger.info("✅ AI 분석 완료 및 캐싱")
        
        # 5. 결과 포맷팅
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
        
        # 7. 결과 반환
        return PrecedentsAnalysisResponse(
            success_cases=success_cases,
            failure_cases=failure_cases,
            review_cases=review_cases,
            actionable_insights=analysis_result.get("actionable_insights", []),
            risk_factors=analysis_result.get("risk_factors", []),
            recommended_action=analysis_result.get("recommended_action", ""),
            confidence_score=analysis_result.get("confidence_score", 0.0),
            is_valid=analysis_result.get("is_valid", False),
            precedents_data=precedents_data
        )
        
    except Exception as e:
        logger.error(f"❌ 판례 분석 실패: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@router.get("/test-cbp/{hs_code}")
async def test_cbp_data(hs_code: str):
    """CBP 데이터 수집 테스트 엔드포인트"""
    if cbp_collector is None:
        raise HTTPException(status_code=503, detail="CBP collector not available")
    
    try:
        logger.info(f"🧪 CBP 테스트 시작: HS코드 {hs_code}")
        cbp_data = await cbp_collector.get_precedents_by_hs_code(hs_code)
        
        return {
            "hs_code": hs_code,
            "data_count": len(cbp_data),
            "sample_data": cbp_data[:3] if cbp_data else [],
            "status": "success"
        }
        
    except Exception as e:
        logger.error(f"❌ CBP 테스트 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"CBP test failed: {str(e)}")

@router.get("/cache-stats")
async def get_cache_stats():
    """캐시 및 벡터 검색 통계 조회"""
    if cbp_collector is None or vector_search is None:
        raise HTTPException(status_code=503, detail="Services not available")
    
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
        logger.error(f"❌ 통계 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Stats retrieval failed: {str(e)}")

