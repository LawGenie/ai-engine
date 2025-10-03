"""
요구사항 분석 라우터
HS코드 기관 매핑 + 검색 + LLM 요약 통합 API
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, Any, Optional
from datetime import datetime
import asyncio

from workflows.requirements_workflow import RequirementsWorkflow

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
        
        # 강제 재분석 실행
        result = await enhanced_workflow.analyze_requirements(
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
    """향상된 요구사항 분석 통계 조회"""
    try:
        # 각 서비스별 통계 수집
        stats = {
            "agency_mapping_stats": await enhanced_workflow.agency_mapping_service.get_agency_statistics(),
            "search_stats": await enhanced_workflow.hybrid_search_service.get_search_statistics(),
            "summary_stats": await enhanced_workflow.llm_summary_service.get_summary_statistics()
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
