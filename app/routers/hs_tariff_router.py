"""
HS Code & Tariff 분석 라우터 (통합 레이어)

Original Implementation:
- Location: hs_graph_service_jh_v2/
- Files: main.py, workflow.py, llm_service.py, vector_service.py, models.py, config.py
- Author: Rosy
- Purpose: LangGraph 기반 HS Code 분석 및 관세율 계산

Integration Work:
- Date: 2025-10-12
- Purpose: 메인 AI Engine에 HS Code/Tariff 분석 기능 통합
- Changes: FastAPI 라우터로 변환, lifespan 초기화, 단일 서버 통합

Note: 
원본 코드는 hs_graph_service_jh_v2/ 디렉토리에 보존되어 있으며,
이 파일은 해당 모듈들을 import하여 FastAPI 엔드포인트로 제공하는 통합 레이어입니다.
원작자(Rosy)의 기여 이력은 hs_graph_service_jh_v2/ 디렉토리의 Git 이력에서 확인 가능합니다.
"""
from fastapi import APIRouter, HTTPException
from typing import List, Optional
from pydantic import BaseModel, Field
import logging
import sys
from pathlib import Path
import asyncio
import time
import uuid

# hs_graph_service_jh_v2 디렉토리를 Python path에 추가
project_root = Path(__file__).resolve().parents[2]
hs_graph_path = project_root / "hs_graph_service_jh_v2"
if str(hs_graph_path) not in sys.path:
    sys.path.insert(0, str(hs_graph_path))

# hs_graph_service_jh_v2 모듈 import (팀원 원본 코드)
try:
    from models import HsCodeAnalysisRequest, HsCodeAnalysisResponse, HsCodeSuggestion
    from workflow import run_hs_analysis_workflow
    from config import settings
    print("✅ hs_graph_service_jh_v2 모듈 import 성공")
except ImportError as e:
    print(f"❌ hs_graph_service_jh_v2 모듈 import 실패: {e}")
    HsCodeAnalysisRequest = None
    HsCodeAnalysisResponse = None
    run_hs_analysis_workflow = None
    settings = None

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/hs-tariff",
    tags=["hs-tariff"],
    responses={404: {"description": "Not found"}},
)

# Backend API 호환용 별도 라우터 (prefix 없음)
api_router = APIRouter(
    tags=["hs-code-api"],
    responses={404: {"description": "Not found"}},
)

# 상수
ANALYSIS_TIMEOUT = 180.0  # 분석 타임아웃 (초) - LLM + 판례 검색 고려

# 전역 인스턴스 상태
hs_service_ready = False

def initialize_hs_tariff_service():
    """HS Code & Tariff 분석 서비스 초기화"""
    global hs_service_ready
    
    if HsCodeAnalysisRequest is None or run_hs_analysis_workflow is None:
        logger.warning("⚠️ hs_graph_service_jh_v2 모듈을 import할 수 없습니다. HS/Tariff 분석 기능이 비활성화됩니다.")
        return False
    
    try:
        logger.info("🚀 HS Code & Tariff 분석 서비스 초기화 중...")
        
        # 서비스 준비 상태 확인
        # (workflow.py에서 벡터 DB 등이 자동 초기화됨)
        hs_service_ready = True
        
        logger.info("✅ HS Code & Tariff 분석 서비스 초기화 완료")
        return True
        
    except Exception as e:
        logger.error(f"❌ HS Code & Tariff 분석 서비스 초기화 실패: {e}")
        return False

@router.get("/health")
async def hs_tariff_health_check():
    """HS Code & Tariff 분석 서비스 헬스체크"""
    return {
        "status": "healthy" if hs_service_ready else "unavailable",
        "service": "hs-tariff-analysis",
        "version": "1.0.0",
        "ready": hs_service_ready
    }

@router.post("/analyze", response_model=HsCodeAnalysisResponse if HsCodeAnalysisResponse else dict)
async def analyze_hs_code(request: HsCodeAnalysisRequest if HsCodeAnalysisRequest else dict):
    """
    HS 코드 분석 API
    
    LangGraph 기반 워크플로우:
    1. 제품 정보 추출
    2. 벡터 검색으로 유사 HS 코드 찾기
    3. LLM으로 최적 HS 코드 추천
    4. 관세율 계산 및 근거 제공
    """
    # 서비스가 초기화되지 않았으면 에러
    if not hs_service_ready or run_hs_analysis_workflow is None:
        raise HTTPException(
            status_code=503, 
            detail="HS Code & Tariff analysis service is not available. Please check server logs."
        )
    
    try:
        logger.info(f"🚀 HS 코드 분석 시작: {request.product_name}")
        
        # LangGraph 워크플로우 실행 (hwangseojin223 원본 코드)
        result = await asyncio.wait_for(
            run_hs_analysis_workflow(
                product_name=request.product_name,
                product_description=request.product_description,
                origin_country=request.origin_country or "KOR"
            ),
            timeout=ANALYSIS_TIMEOUT
        )
        
        logger.info(f"✅ HS 코드 분석 완료: {len(result.suggestions) if hasattr(result, 'suggestions') else 0}개 추천")
        return result
        
    except asyncio.TimeoutError:
        logger.error(f"⏰ 분석 타임아웃 ({ANALYSIS_TIMEOUT}초)")
        raise HTTPException(
            status_code=408, 
            detail=f"분석 시간이 초과되었습니다 ({ANALYSIS_TIMEOUT}초). 제품 설명을 더 간단하게 입력해주세요."
        )
    except ValueError as e:
        logger.error(f"❌ 유효성 검증 오류: {str(e)}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"❌ HS 코드 분석 실패: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"분석 중 오류가 발생했습니다: {str(e)}")

@router.get("/test")
async def test_hs_service():
    """HS Code 서비스 테스트 엔드포인트"""
    if not hs_service_ready:
        raise HTTPException(status_code=503, detail="HS service not available")
    
    return {
        "status": "OK",
        "message": "HS Code & Tariff service is ready",
        "service_ready": hs_service_ready
    }

# ==================== Backend API 호환 엔드포인트 ====================

class BackendHsCodeRequest(BaseModel):
    """Backend API에서 사용하는 HS 코드 분석 요청 (analysisSessionId 포함)"""
    productName: str
    productDescription: str
    analysisSessionId: Optional[str] = None

class BackendHsCodeSuggestion(BaseModel):
    """Backend API 응답 형식의 HS 코드 추천"""
    hsCode: str
    description: str
    confidenceScore: float
    reasoning: str
    tariffReasoning: Optional[str] = None
    usTariffRate: float
    baseTariffRate: Optional[float] = None
    reciprocalTariffRate: Optional[float] = None
    usitcUrl: str
    hierarchicalDescription: Optional[dict] = None

class BackendHsCodeResponse(BaseModel):
    """Backend API 응답 형식 (processingTime 포함)"""
    analysisSessionId: str
    suggestions: List[BackendHsCodeSuggestion]
    processingTime: Optional[str] = None

@api_router.post("/api/hs-code/analyze-graph", response_model=BackendHsCodeResponse)
async def analyze_hs_code_for_backend(request: BackendHsCodeRequest):
    """
    Backend API 호환 HS 코드 분석 엔드포인트
    
    이 엔드포인트는 Java Backend API가 호출하는 형식에 맞춰져 있습니다.
    내부적으로 hs_graph_service_jh_v2의 workflow를 실행합니다.
    """
    # 서비스가 초기화되지 않았으면 에러
    if not hs_service_ready or run_hs_analysis_workflow is None:
        raise HTTPException(
            status_code=503, 
            detail="HS Code & Tariff analysis service is not available. Please check server logs."
        )
    
    try:
        start_time = time.time()
        
        # 세션 ID 생성 (없으면 새로 생성)
        session_id = request.analysisSessionId or str(uuid.uuid4())
        
        logger.info(f"🚀 [Backend API] HS 코드 분석 시작: {request.productName}, 세션ID: {session_id}")
        
        # LangGraph 워크플로우 실행
        result = await asyncio.wait_for(
            run_hs_analysis_workflow(
                product_name=request.productName,
                product_description=request.productDescription,
                origin_country="KOR"
            ),
            timeout=ANALYSIS_TIMEOUT
        )
        
        # 처리 시간 계산
        processing_time_seconds = time.time() - start_time
        processing_time = f"{processing_time_seconds:.2f}s"
        
        # Backend 응답 형식으로 변환
        backend_suggestions = []
        if hasattr(result, 'suggestions') and result.suggestions:
            for suggestion in result.suggestions:
                # hierarchicalDescription을 dict로 변환
                hierarchical_desc = getattr(suggestion, 'hierarchical_description', None)
                if hierarchical_desc and hasattr(hierarchical_desc, 'model_dump'):
                    # Pydantic v2
                    hierarchical_desc = hierarchical_desc.model_dump(by_alias=True)
                elif hierarchical_desc and hasattr(hierarchical_desc, 'dict'):
                    # Pydantic v1
                    hierarchical_desc = hierarchical_desc.dict(by_alias=True)
                
                backend_suggestions.append(BackendHsCodeSuggestion(
                    hsCode=suggestion.hs_code,
                    description=suggestion.description,
                    confidenceScore=suggestion.confidence_score,
                    reasoning=suggestion.reasoning,
                    tariffReasoning=getattr(suggestion, 'tariff_reasoning', None),
                    usTariffRate=suggestion.us_tariff_rate,
                    baseTariffRate=getattr(suggestion, 'base_tariff_rate', None),
                    reciprocalTariffRate=getattr(suggestion, 'reciprocal_tariff_rate', None),
                    usitcUrl=suggestion.usitc_url,
                    hierarchicalDescription=hierarchical_desc
                ))
        
        response = BackendHsCodeResponse(
            analysisSessionId=session_id,
            suggestions=backend_suggestions,
            processingTime=processing_time
        )
        
        logger.info(f"✅ [Backend API] HS 코드 분석 완료: {len(backend_suggestions)}개 추천, 처리시간: {processing_time}")
        return response
        
    except asyncio.TimeoutError:
        logger.error(f"⏰ [Backend API] 분석 타임아웃 ({ANALYSIS_TIMEOUT}초)")
        raise HTTPException(
            status_code=408, 
            detail=f"분석 시간이 초과되었습니다 ({ANALYSIS_TIMEOUT}초). 제품 설명을 더 간단하게 입력해주세요."
        )
    except ValueError as e:
        logger.error(f"❌ [Backend API] 유효성 검증 오류: {str(e)}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"❌ [Backend API] HS 코드 분석 실패: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"분석 중 오류가 발생했습니다: {str(e)}")

