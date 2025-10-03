from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Dict, Any
import asyncio
from app.schemas.product import (
    ProductRegistrationRequest,
    ProductCompletionRequest,
    HSRecommendationResponse,
    AnalysisResult,
    AnalysisStatusResponse
)
from app.schemas.common import BaseResponse
from app.services.hs_code_service import HSCodeService
from app.services.tariff_service import TariffService
from app.services.requirements.requirements_cache_service import RequirementsCacheService
from app.services.precedents_service import PrecedentsService

router = APIRouter(prefix="/products", tags=["products"])

# 임시 저장소 (실제로는 DB 사용)
analysis_results = {}
analysis_status = {}

@router.post("/register", response_model=HSRecommendationResponse)
async def register_product(request: ProductRegistrationRequest):
    """상품 등록 시 HS코드 추천 (동기)"""
    try:
        hs_service = HSCodeService()
        recommendations = await hs_service.recommend(
            product_name=request.product_name,
            description=request.description
        )
        return recommendations
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"HS코드 추천 중 오류가 발생했습니다: {str(e)}")

@router.post("/complete", response_model=BaseResponse)
async def complete_registration(request: ProductCompletionRequest, background_tasks: BackgroundTasks):
    """상품 등록 완료 후 AI 분석 시작 (비동기)"""
    try:
        # 분석 상태 초기화
        analysis_status[request.product_id] = {
            "status": "pending",
            "progress": 0,
            "estimated_completion": None
        }
        
        # 백그라운드 AI 분석 시작
        background_tasks.add_task(
            run_background_analysis,
            request.product_id,
            request.hs_code
        )
        
        return BaseResponse(
            success=True,
            message="AI 분석이 시작되었습니다.",
            data={"product_id": request.product_id, "status": "analysis_started"}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"상품 등록 완료 처리 중 오류가 발생했습니다: {str(e)}")

@router.get("/analysis/{product_id}", response_model=AnalysisResult)
async def get_analysis_result(product_id: str):
    """AI 분석 결과 조회 (챗봇용)"""
    try:
        if product_id not in analysis_results:
            raise HTTPException(status_code=404, detail="분석 결과를 찾을 수 없습니다.")
        
        return analysis_results[product_id]
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"분석 결과 조회 중 오류가 발생했습니다: {str(e)}")

@router.get("/analysis/{product_id}/status", response_model=AnalysisStatusResponse)
async def get_analysis_status(product_id: str):
    """AI 분석 상태 조회"""
    try:
        if product_id not in analysis_status:
            raise HTTPException(status_code=404, detail="분석 상태를 찾을 수 없습니다.")
        
        status_data = analysis_status[product_id]
        return AnalysisStatusResponse(
            product_id=product_id,
            status=status_data["status"],
            progress=status_data["progress"],
            estimated_completion=status_data.get("estimated_completion")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"분석 상태 조회 중 오류가 발생했습니다: {str(e)}")

async def run_background_analysis(product_id: str, hs_code: str):
    """백그라운드 AI 분석 실행"""
    try:
        # 분석 상태 업데이트
        analysis_status[product_id]["status"] = "processing"
        analysis_status[product_id]["progress"] = 10
        
        # 각 서비스 초기화
        tariff_service = TariffService()
        # requirements_service = RequirementsService()  # 임시 주석처리
        precedents_service = PrecedentsService()
        
        # 병렬로 AI 분석 실행
        analysis_status[product_id]["progress"] = 30
        
        # 임시 간단한 응답 반환
        tariff_result = await tariff_service.calculate(hs_code)
        precedents_result = await precedents_service.analyze(hs_code)
        
        analysis_status[product_id]["progress"] = 80
        
        # 결과 저장
        analysis_results[product_id] = AnalysisResult(
            product_id=product_id,
            hs_code=hs_code,
            tariff_analysis=results[0] if not isinstance(results[0], Exception) else {"error": str(results[0])},
            requirements_analysis=results[1] if not isinstance(results[1], Exception) else {"error": str(results[1])},
            precedents_analysis=results[2] if not isinstance(results[2], Exception) else {"error": str(results[2])},
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z"
        )
        
        # 분석 완료
        analysis_status[product_id]["status"] = "completed"
        analysis_status[product_id]["progress"] = 100
        
    except Exception as e:
        # 분석 실패
        analysis_status[product_id]["status"] = "failed"
        analysis_status[product_id]["progress"] = 0
        print(f"백그라운드 분석 실패: {str(e)}")
