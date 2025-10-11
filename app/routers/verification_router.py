"""
규정 교차 검증 및 실시간 모니터링 통합 서비스
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional
import asyncio
from datetime import datetime

from app.services.requirements.cross_validation_service import CrossValidationService, CrossValidationResult
from app.services.requirements.live_monitoring_service import LiveMonitoringService, MonitoringResult

router = APIRouter(prefix="/verification", tags=["verification"])

class VerificationRequest(BaseModel):
    hs_code: str
    product_name: str
    fda_results: Optional[Dict[str, Any]] = None
    usda_results: Optional[Dict[str, Any]] = None
    epa_results: Optional[Dict[str, Any]] = None
    cpsc_results: Optional[Dict[str, Any]] = None
    fcc_results: Optional[Dict[str, Any]] = None
    enable_cross_validation: bool = True
    enable_live_monitoring: bool = True

class VerificationResponse(BaseModel):
    hs_code: str
    product_name: str
    cross_validation: Optional[Dict[str, Any]] = None
    live_updates: Optional[Dict[str, Any]] = None
    verification_summary: Dict[str, Any]
    timestamp: str

# 서비스 인스턴스
cross_validation_service = CrossValidationService()
live_monitoring_service = LiveMonitoringService()

@router.post("/analyze", response_model=VerificationResponse)
async def analyze_verification(request: VerificationRequest):
    """
    규정 교차 검증 및 실시간 모니터링 통합 분석
    
    Args:
        request: 검증 요청 정보
        
    Returns:
        VerificationResponse: 검증 결과
    """
    try:
        print(f"🔍 통합 검증 분석 시작 - HS코드: {request.hs_code}, 상품: {request.product_name}")
        
        cross_validation_result = None
        live_monitoring_result = None
        
        # 1. 교차 검증 수행
        if request.enable_cross_validation:
            try:
                cross_validation_result = await cross_validation_service.validate_regulations(
                    hs_code=request.hs_code,
                    product_name=request.product_name,
                    fda_results=request.fda_results,
                    usda_results=request.usda_results,
                    epa_results=request.epa_results,
                    cpsc_results=request.cpsc_results,
                    fcc_results=request.fcc_results
                )
                print(f"✅ 교차 검증 완료 - 충돌 {len(cross_validation_result.conflicts_found)}개 발견")
            except Exception as e:
                print(f"❌ 교차 검증 실패: {e}")
                cross_validation_result = None
        
        # 2. 실시간 모니터링 수행
        if request.enable_live_monitoring:
            try:
                live_monitoring_result = await live_monitoring_service.monitor_regulation_updates(
                    hs_code=request.hs_code,
                    product_name=request.product_name
                )
                print(f"✅ 실시간 모니터링 완료 - 업데이트 {len(live_monitoring_result.updates_found)}개 발견")
            except Exception as e:
                print(f"❌ 실시간 모니터링 실패: {e}")
                live_monitoring_result = None
        
        # 3. 검증 요약 생성
        verification_summary = _generate_verification_summary(
            cross_validation_result, 
            live_monitoring_result,
            request.hs_code,
            request.product_name
        )
        
        # 4. 응답 구성
        response_data = {
            "hs_code": request.hs_code,
            "product_name": request.product_name,
            "cross_validation": None,
            "live_updates": None,
            "verification_summary": verification_summary,
            "timestamp": datetime.now().isoformat()
        }
        
        # 교차 검증 결과 추가
        if cross_validation_result:
            response_data["cross_validation"] = cross_validation_service.format_cross_validation_result(
                cross_validation_result
            )["cross_validation"]
        
        # 실시간 모니터링 결과 추가
        if live_monitoring_result:
            response_data["live_updates"] = live_monitoring_service.format_monitoring_result(
                live_monitoring_result
            )["live_updates"]
        
        print(f"🎯 통합 검증 분석 완료 - HS코드: {request.hs_code}")
        
        return VerificationResponse(**response_data)
        
    except Exception as e:
        print(f"❌ 통합 검증 분석 실패: {e}")
        raise HTTPException(status_code=500, detail=f"검증 분석 중 오류 발생: {str(e)}")

@router.post("/cross-validation", response_model=Dict[str, Any])
async def cross_validate_regulations(request: VerificationRequest):
    """
    규정 교차 검증만 수행
    
    Args:
        request: 검증 요청 정보
        
    Returns:
        Dict: 교차 검증 결과
    """
    try:
        print(f"🔍 교차 검증 시작 - HS코드: {request.hs_code}")
        
        result = await cross_validation_service.validate_regulations(
            hs_code=request.hs_code,
            product_name=request.product_name,
            fda_results=request.fda_results,
            usda_results=request.usda_results,
            epa_results=request.epa_results,
            cpsc_results=request.cpsc_results,
            fcc_results=request.fcc_results
        )
        
        response = cross_validation_service.format_cross_validation_result(result)
        print(f"✅ 교차 검증 완료 - 충돌 {len(result.conflicts_found)}개 발견")
        
        return response
        
    except Exception as e:
        print(f"❌ 교차 검증 실패: {e}")
        raise HTTPException(status_code=500, detail=f"교차 검증 중 오류 발생: {str(e)}")

@router.post("/live-monitoring", response_model=Dict[str, Any])
async def monitor_live_updates(request: VerificationRequest):
    """
    실시간 모니터링만 수행
    
    Args:
        request: 모니터링 요청 정보
        
    Returns:
        Dict: 모니터링 결과
    """
    try:
        print(f"🔍 실시간 모니터링 시작 - HS코드: {request.hs_code}")
        
        result = await live_monitoring_service.monitor_regulation_updates(
            hs_code=request.hs_code,
            product_name=request.product_name
        )
        
        response = live_monitoring_service.format_monitoring_result(result)
        print(f"✅ 실시간 모니터링 완료 - 업데이트 {len(result.updates_found)}개 발견")
        
        return response
        
    except Exception as e:
        print(f"❌ 실시간 모니터링 실패: {e}")
        raise HTTPException(status_code=500, detail=f"실시간 모니터링 중 오류 발생: {str(e)}")

def _generate_verification_summary(
    cross_validation_result: Optional[CrossValidationResult],
    live_monitoring_result: Optional[MonitoringResult],
    hs_code: str,
    product_name: str
) -> Dict[str, Any]:
    """검증 요약 생성"""
    
    summary = {
        "overall_status": "completed",
        "verification_score": 1.0,
        "risk_level": "low",
        "recommendations": [],
        "next_actions": []
    }
    
    # 교차 검증 결과 반영
    if cross_validation_result:
        summary["verification_score"] = cross_validation_result.validation_score
        summary["conflicts_count"] = len(cross_validation_result.conflicts_found)
        
        # 위험 레벨 결정
        if cross_validation_result.validation_score < 0.5:
            summary["risk_level"] = "high"
        elif cross_validation_result.validation_score < 0.8:
            summary["risk_level"] = "medium"
        else:
            summary["risk_level"] = "low"
        
        # 권고사항 추가
        summary["recommendations"].extend(cross_validation_result.recommendations)
    
    # 실시간 모니터링 결과 반영
    if live_monitoring_result:
        summary["updates_count"] = len(live_monitoring_result.updates_found)
        summary["alert_level"] = live_monitoring_result.alert_level
        
        # 알림 레벨에 따른 권고사항 추가
        if live_monitoring_result.alert_level == "critical":
            summary["recommendations"].append("🚨 긴급 규정 변경사항 발견! 즉시 검토가 필요합니다.")
            summary["risk_level"] = "high"
        elif live_monitoring_result.alert_level == "high":
            summary["recommendations"].append("⚠️ 중요한 규정 변경사항 발견! 빠른 검토를 권장합니다.")
            if summary["risk_level"] == "low":
                summary["risk_level"] = "medium"
    
    # 다음 액션 아이템 생성
    if cross_validation_result and cross_validation_result.conflicts_found:
        summary["next_actions"].append("규정 충돌 해결을 위해 관련 기관에 문의")
    
    if live_monitoring_result and live_monitoring_result.updates_found:
        summary["next_actions"].append("최신 규정 변경사항 검토 및 대응 방안 수립")
    
    if not summary["recommendations"]:
        summary["recommendations"].append("현재 규정 상태가 양호합니다. 정기적인 모니터링을 계속하세요.")
    
    if not summary["next_actions"]:
        summary["next_actions"].append("정기적인 규정 업데이트 모니터링 유지")
    
    return summary
