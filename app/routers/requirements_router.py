"""
요구사항 분석 라우터

주요 엔드포인트:
- POST /requirements/analyze: 메인 요구사항 분석 (HS코드 + 상품명)
- POST /requirements/refresh/{hs_code}: 캐시 무효화 및 재분석
- GET /requirements/cache/status/{hs_code}: 캐시 상태 조회
- GET /requirements/statistics: 분석 통계
- POST /requirements/generate-agency-mapping: AI 기반 HS코드 → 기관 매핑
- POST /requirements/batch-generate-agency-mappings: 배치 기관 매핑
- POST /requirements/extract-keywords: 제품명 → 키워드 추출

주의: 이 라우터는 unified_workflow를 사용하여 실제 분석을 수행합니다.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, Any, Optional
from datetime import datetime
import asyncio

from workflows.requirements_workflow import RequirementsWorkflow
from app.services.requirements.hs_code_agency_ai_mapper import get_hs_code_mapper
from app.services.requirements.keyword_extractor import OpenAiKeywordExtractor, HfKeywordExtractor, KeywordExtractor

router = APIRouter(prefix="/requirements", tags=["requirements"])

class RequirementsRequest(BaseModel):
    hs_code: str
    product_name: str
    product_description: Optional[str] = ""
    force_refresh: Optional[bool] = False
    is_new_product: Optional[bool] = False

class RequirementsResponse(BaseModel):
    hs_code: str
    product_name: str
    recommended_agencies: Optional[list] = None
    search_results: Optional[Dict[str, Any]] = None
    llm_summary: Optional[Dict[str, Any]] = None
    processing_time_ms: int
    timestamp: str
    status: str

# 워크플로우 인스턴스
requirements_workflow = RequirementsWorkflow()

@router.post("/analyze", response_model=RequirementsResponse)
async def analyze_requirements(request: RequirementsRequest):
    """
    요구사항 분석
    
    Args:
        request: 분석 요청 정보
        
    Returns:
        RequirementsResponse: 분석 결과
    """
    try:
        print(f"🔍 요구사항 분석 요청 - HS코드: {request.hs_code}, 상품: {request.product_name}")
        
        # 워크플로우 실행
        result = await requirements_workflow.analyze_requirements(
            hs_code=request.hs_code,
            product_name=request.product_name,
            product_description=request.product_description or "",
            force_refresh=request.force_refresh,
            is_new_product=request.is_new_product
        )
        
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        
        print(f"✅ 요구사항 분석 완료 - HS코드: {request.hs_code}")
        
        return RequirementsResponse(**result)
        
    except Exception as e:
        print(f"❌ 요구사항 분석 실패: {e}")
        raise HTTPException(status_code=500, detail=f"분석 중 오류 발생: {str(e)}")

@router.get("/health")
async def health_check():
    """요구사항 분석 서비스 상태 확인"""
    return {
        "status": "healthy",
        "service": "requirements",
        "components": {
            "agency_mapping": "active",
            "search": "active", 
            "llm_summary": "active"
        }
    }

@router.post("/refresh/{hs_code}")
async def refresh_requirements_analysis(
    hs_code: str,
    product_name: str,
    product_description: str = "",
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """요구사항 분석 수동 갱신"""
    try:
        print(f"🔄 요구사항 분석 수동 갱신 요청 - HS코드: {hs_code}")
        
        # 캐시 무효화
        from app.services.requirements.requirements_cache_service import RequirementsCacheService
        cache_service = RequirementsCacheService()
        await cache_service.invalidate_cache(hs_code, product_name)
        
        # 강제 재분석 실행 (requirements_workflow 사용)
        result = await requirements_workflow.analyze_requirements(
            hs_code=hs_code,
            product_name=product_name,
            product_description=product_description,
            force_refresh=True,
            is_new_product=False
        )
        
        return {
            "status": "success",
            "message": "요구사항 분석이 성공적으로 갱신되었습니다",
            "result": result,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        print(f"❌ 수동 갱신 실패: {e}")
        return {
            "status": "error",
            "message": f"요구사항 분석 갱신 실패: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }

@router.get("/cache/status/{hs_code}")
async def get_cache_status(hs_code: str, product_name: str):
    """캐시 상태 확인"""
    try:
        from app.services.requirements.requirements_cache_service import RequirementsCacheService
        cache_service = RequirementsCacheService()
        
        is_valid = await cache_service.is_cache_valid(hs_code, product_name)
        cached_result = await cache_service.get_cached_analysis(hs_code, product_name)
        
        return {
            "status": "success",
            "hs_code": hs_code,
            "product_name": product_name,
            "cache_valid": is_valid,
            "has_cached_data": cached_result is not None,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"캐시 상태 확인 실패: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }

@router.get("/statistics")
async def get_statistics():
    """
    향상된 요구사항 분석 통계 조회
    
    Returns:
        - agency_mapping_stats: HS코드 기관 매핑 통계
        - search_stats: 검색 서비스 통계
        - summary_stats: LLM 요약 통계
        - cache_stats: 캐시 통계 (DB + 메모리)
    """
    try:
        # 각 서비스별 통계 수집
        # 주의: requirements_workflow를 통해 서비스에 접근
        stats = {
            "agency_mapping_stats": await requirements_workflow.agency_mapping_service.get_agency_statistics(),
            "search_stats": await requirements_workflow.search_service.get_search_statistics(),
            "summary_stats": await requirements_workflow.llm_summary_service.get_summary_statistics()
        }
        
        # 캐시 통계 추가
        from app.services.requirements.requirements_cache_service import RequirementsCacheService
        cache_service = RequirementsCacheService()
        cache_stats = await cache_service.get_cache_statistics()
        memory_stats = cache_service.get_memory_cache_stats()
        
        stats["cache_stats"] = {
            "database": cache_stats,
            "memory": memory_stats
        }
        
        return {
            "status": "success",
            "statistics": stats,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


# ===== HS 코드 → 기관 매핑 AI 생성 =====

class HsCodeMappingRequest(BaseModel):
    hs_code: str
    product_name: Optional[str] = ""
    product_category: Optional[str] = ""

class HsCodeMappingResponse(BaseModel):
    hs_code: str
    product_category: str
    primary_agencies: list
    secondary_agencies: list
    search_keywords: list
    key_requirements: list
    confidence_score: float
    reasoning: str
    hs_code_description: Optional[str] = ""
    tokens_used: Optional[int] = 0
    cost: Optional[float] = 0.0
    model: Optional[str] = ""


@router.post("/generate-agency-mapping", response_model=HsCodeMappingResponse)
async def generate_agency_mapping(request: HsCodeMappingRequest):
    """
    AI를 사용하여 HS 코드 → 기관 매핑 생성
    
    이 매핑은 백엔드 DB에 저장되어 재사용됩니다.
    """
    try:
        print(f"🤖 AI 기관 매핑 생성 API 호출 - HS: {request.hs_code}")
        
        mapper = get_hs_code_mapper()
        result = await mapper.generate_mapping(
            hs_code=request.hs_code,
            product_name=request.product_name,
            product_category=request.product_category
        )
        
        return result
        
    except Exception as e:
        print(f"❌ AI 기관 매핑 생성 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class BatchHsCodeMappingRequest(BaseModel):
    mappings: list  # [{"hs_code": "...", "name": "...", "category": "..."}]


@router.post("/batch-generate-agency-mappings")
async def batch_generate_agency_mappings(request: BatchHsCodeMappingRequest):
    """
    여러 HS 코드에 대해 배치로 기관 매핑 생성
    
    서버 시작 시 또는 대량 데이터 처리 시 사용
    """
    try:
        print(f"🔄 배치 AI 기관 매핑 생성 - {len(request.mappings)}개")
        
        mapper = get_hs_code_mapper()
        
        hs_codes = [m.get("hs_code") for m in request.mappings]
        products = request.mappings
        
        results = await mapper.batch_generate_mappings(hs_codes, products)
        
        return {
            "status": "success",
            "total": len(results),
            "results": results,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        print(f"❌ 배치 AI 기관 매핑 생성 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== 키워드 추출 API =====

class KeywordExtractionRequest(BaseModel):
    product_name: str
    product_description: Optional[str] = ""
    top_k: Optional[int] = 5
    method: Optional[str] = "auto"  # auto, openai, hf, heuristic


class KeywordExtractionResponse(BaseModel):
    keywords: list
    method_used: str
    confidence: float
    processing_time_ms: int


@router.get("/regulatory-updates/status")
async def get_regulatory_monitoring_status():
    """
    규제 변경 모니터링 상태 조회
    
    Returns:
        - is_active: 모니터링 활성화 여부
        - check_interval_days: 체크 주기 (7일)
        - monitored_agencies: 모니터링 대상 기관 목록
        - total_feeds: 모니터링 중인 RSS 피드 수
    """
    try:
        from app.services.requirements.regulatory_update_monitor import regulatory_monitor
        status = regulatory_monitor.get_monitoring_status()
        
        return {
            "status": "success",
            "monitoring": status,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@router.post("/regulatory-updates/check-now")
async def force_check_regulatory_updates():
    """
    규제 변경 즉시 체크 (수동 트리거)
    
    개발/테스트 목적으로 7일 주기를 기다리지 않고 즉시 체크
    """
    try:
        from app.services.requirements.regulatory_update_monitor import regulatory_monitor
        
        # 백그라운드로 체크 실행
        asyncio.create_task(regulatory_monitor.force_check_now())
        
        return {
            "status": "success",
            "message": "규제 변경 체크를 백그라운드로 시작했습니다",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@router.post("/extract-keywords", response_model=KeywordExtractionResponse)
async def extract_keywords(request: KeywordExtractionRequest):
    """
    제품명/설명에서 핵심 키워드 추출
    
    Methods:
    - auto: OpenAI → HF → Heuristic 순서로 시도
    - openai: OpenAI만 사용
    - hf: HuggingFace만 사용
    - heuristic: 휴리스틱만 사용
    """
    try:
        import time
        start_time = time.time()
        
        print(f"🔑 키워드 추출 요청 - 제품: {request.product_name}, 방법: {request.method}")
        
        keywords = []
        method_used = ""
        confidence = 0.0
        
        # Auto 모드: 우선순위대로 시도
        if request.method == "auto":
            # 1. OpenAI 시도
            try:
                extractor = OpenAiKeywordExtractor()
                keywords = extractor.extract(
                    request.product_name, 
                    request.product_description, 
                    request.top_k
                )
                if keywords:
                    method_used = "openai"
                    confidence = 0.9
            except Exception as e:
                print(f"⚠️ OpenAI 추출 실패: {e}")
            
            # 2. HuggingFace 시도
            if not keywords:
                try:
                    extractor = HfKeywordExtractor()
                    keywords = extractor.extract(
                        request.product_name,
                        request.product_description,
                        request.top_k
                    )
                    if keywords:
                        method_used = "huggingface"
                        confidence = 0.7
                except Exception as e:
                    print(f"⚠️ HF 추출 실패: {e}")
            
            # 3. Heuristic 폴백
            if not keywords:
                extractor = KeywordExtractor()
                keywords = extractor.extract(
                    request.product_name,
                    request.product_description,
                    request.top_k
                )
                method_used = "heuristic"
                confidence = 0.5
        
        # 특정 방법 지정
        elif request.method == "openai":
            extractor = OpenAiKeywordExtractor()
            keywords = extractor.extract(request.product_name, request.product_description, request.top_k)
            method_used = "openai"
            confidence = 0.9
        
        elif request.method == "hf":
            extractor = HfKeywordExtractor()
            keywords = extractor.extract(request.product_name, request.product_description, request.top_k)
            method_used = "huggingface"
            confidence = 0.7
        
        else:  # heuristic
            extractor = KeywordExtractor()
            keywords = extractor.extract(request.product_name, request.product_description, request.top_k)
            method_used = "heuristic"
            confidence = 0.5
        
        processing_time = int((time.time() - start_time) * 1000)
        
        print(f"✅ 키워드 추출 완료 - 방법: {method_used}, 키워드: {keywords}")
        
        return {
            "keywords": keywords,
            "method_used": method_used,
            "confidence": confidence,
            "processing_time_ms": processing_time
        }
        
    except Exception as e:
        print(f"❌ 키워드 추출 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))
