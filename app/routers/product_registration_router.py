"""
상품 등록 워크플로우 라우터
전체 상품 등록 프로세스 관리
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, Any, Optional
from datetime import datetime

from workflows.product_registration_workflow import ProductRegistrationWorkflow

router = APIRouter(prefix="/product-registration", tags=["product-registration"])

class ProductRegistrationRequest(BaseModel):
    product_id: str
    product_name: str
    product_description: str
    category: str

class ProductRegistrationResponse(BaseModel):
    product_id: str
    product_name: str
    selected_hs_code: str
    tariff_estimation: Dict[str, Any]
    requirements_analysis: Dict[str, Any]
    precedents_analysis: Dict[str, Any]
    verified_requirements: Dict[str, Any]
    processing_time_ms: int
    status: str
    timestamp: str

# 워크플로우 인스턴스
product_registration_workflow = ProductRegistrationWorkflow()

@router.post("/execute", response_model=ProductRegistrationResponse)
async def execute_product_registration(request: ProductRegistrationRequest):
    """
    상품 등록 워크플로우 실행
    
    전체 프로세스:
    1. HS코드 추천
    2. 예상 관세 계산
    3. 요구사항 분석 (현재 파트)
    4. 판례 분석
    5. 요구사항 재검증
    
    Args:
        request: 상품 등록 요청 정보
        
    Returns:
        ProductRegistrationResponse: 전체 워크플로우 결과
    """
    try:
        print(f"🚀 상품 등록 워크플로우 요청 - 상품ID: {request.product_id}")
        
        # 전체 워크플로우 실행
        result = await product_registration_workflow.execute_product_registration_workflow(
            product_id=request.product_id,
            product_name=request.product_name,
            product_description=request.product_description,
            category=request.category
        )
        
        if result.get("status") == "failed":
            raise HTTPException(status_code=500, detail=result.get("error", "워크플로우 실행 실패"))
        
        print(f"✅ 상품 등록 워크플로우 완료 - 상품ID: {request.product_id}")
        
        return ProductRegistrationResponse(**result)
        
    except Exception as e:
        print(f"❌ 상품 등록 워크플로우 실패: {e}")
        raise HTTPException(status_code=500, detail=f"워크플로우 실행 중 오류 발생: {str(e)}")

@router.post("/refresh-requirements/{product_id}")
async def refresh_requirements_only(
    product_id: str,
    hs_code: str,
    product_name: str,
    product_description: str = ""
):
    """요구사항 분석만 수동 갱신"""
    try:
        print(f"🔄 요구사항 분석 수동 갱신 - 상품ID: {product_id}")
        
        # 요구사항 분석만 강제 재실행
        result = await product_registration_workflow.requirements_workflow.analyze_requirements(
            hs_code=hs_code,
            product_name=product_name,
            product_description=product_description,
            force_refresh=True,
            is_new_product=False
        )
        
        return {
            "status": "success",
            "message": "요구사항 분석이 성공적으로 갱신되었습니다",
            "product_id": product_id,
            "requirements_analysis": result,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        print(f"❌ 요구사항 분석 갱신 실패: {e}")
        return {
            "status": "error",
            "message": f"요구사항 분석 갱신 실패: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }

@router.get("/workflow-status/{product_id}")
async def get_workflow_status(product_id: str):
    """워크플로우 상태 확인"""
    try:
        # TODO: DB에서 워크플로우 상태 조회
        return {
            "status": "success",
            "product_id": product_id,
            "workflow_status": "completed",
            "last_updated": datetime.now().isoformat()
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"워크플로우 상태 확인 실패: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }

@router.get("/health")
async def health_check():
    """상품 등록 워크플로우 서비스 상태 확인"""
    return {
        "status": "healthy",
        "service": "product-registration-workflow",
        "components": {
            "hs_code_recommendation": "active",
            "tariff_calculation": "active",
            "requirements_analysis": "active",
            "precedents_analysis": "active",
            "requirements_verification": "active"
        },
        "workflow_steps": [
            "1. HS코드 추천",
            "2. 예상 관세 계산", 
            "3. 요구사항 분석",
            "4. 판례 분석",
            "5. 요구사항 재검증"
        ]
    }
