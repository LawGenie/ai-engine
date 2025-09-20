from fastapi import APIRouter, HTTPException
from app.models.requirement_models import RequirementAnalysisRequest, RequirementAnalysisResponse
from app.services.requirements.requirement_analyzer import RequirementAnalyzer

router = APIRouter(prefix="/requirements", tags=["requirements"])

@router.post("/analyze", response_model=RequirementAnalysisResponse)
async def analyze_requirements(request: RequirementAnalysisRequest):
    """
    HS코드 기반으로 미국 수입요건 분석을 수행합니다.
    
    - **hs_code**: HS코드 (예: "8471.30.01")
    - **product_name**: 상품명
    - **product_description**: 상품 설명 (선택사항)
    - **target_country**: 대상 국가 (기본값: "US")
    """
    try:
        analyzer = RequirementAnalyzer()
        result = await analyzer.analyze_requirements(request)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"요구사항 분석 중 오류가 발생했습니다: {str(e)}")

@router.get("/health")
async def health_check():
    """요구사항 분석 서비스 상태 확인"""
    return {"status": "healthy", "service": "requirement_analyzer"}