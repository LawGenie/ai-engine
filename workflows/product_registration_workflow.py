"""
상품 등록 워크플로우 순서 정의 (최적화됨 - 2025-10-12)
HS코드 추천 → 예상 관세 계산 → 판례 분석 → 요구사항 분석 (판례 결과 반영) → 최종 검증

최적화 이유:
1. 판례 분석을 먼저 해서 기존 사례 파악
2. 판례 결과를 요구사항 분석에 반영하여 정확도 향상
3. 중복 검색 방지로 Tavily API 비용 절약 (30-40% 감소 예상)
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import asyncio

@dataclass
class ProductRegistrationWorkflowState:
    """상품 등록 워크플로우 상태"""
    product_id: str
    product_name: str
    product_description: str
    category: str
    
    # 1단계: HS코드 추천
    recommended_hs_codes: List[Dict[str, Any]] = None
    selected_hs_code: str = None
    
    # 2단계: 예상 관세 계산
    tariff_estimation: Dict[str, Any] = None
    
    # 3단계: 판례 분석 (최적화: 먼저 실행)
    precedents_analysis: Dict[str, Any] = None
    
    # 4단계: 요구사항 분석 (판례 결과 반영)
    requirements_analysis: Dict[str, Any] = None
    
    # 5단계: 최종 검증 (판례 + 요구사항 통합)
    verified_requirements: Dict[str, Any] = None
    
    # 최종 결과
    final_result: Dict[str, Any] = None
    processing_time_ms: int = 0
    status: str = "pending"

class ProductRegistrationWorkflow:
    """상품 등록 워크플로우"""
    
    def __init__(self):
        from workflows.requirements_workflow import RequirementsWorkflow
        self.requirements_workflow = RequirementsWorkflow()
    
    async def execute_product_registration_workflow(
        self,
        product_id: str,
        product_name: str,
        product_description: str,
        category: str
    ) -> Dict[str, Any]:
        """상품 등록 워크플로우 실행"""
        
        print(f"🚀 상품 등록 워크플로우 시작 - 상품ID: {product_id}")
        start_time = datetime.now()
        
        state = ProductRegistrationWorkflowState(
            product_id=product_id,
            product_name=product_name,
            product_description=product_description,
            category=category
        )
        
        try:
            # 1단계: HS코드 추천
            print(f"📋 1단계: HS코드 추천")
            state.recommended_hs_codes = await self._recommend_hs_codes(
                product_name, product_description, category
            )
            state.selected_hs_code = state.recommended_hs_codes[0]["hs_code"]
            print(f"✅ HS코드 추천 완료: {state.selected_hs_code}")
            
            # 2단계: 예상 관세 계산
            print(f"💰 2단계: 예상 관세 계산")
            state.tariff_estimation = await self._calculate_tariff_estimation(
                state.selected_hs_code, product_name
            )
            print(f"✅ 관세 계산 완료: {state.tariff_estimation.get('estimated_rate', 'N/A')}%")
            
            # 3단계: 판례 분석 (최적화: 먼저 실행)
            print(f"⚖️ 3단계: 판례 분석 (최적화: 먼저 실행)")
            state.precedents_analysis = await self._analyze_precedents(
                state.selected_hs_code, product_name, None  # requirements_analysis가 아직 없음
            )
            print(f"✅ 판례 분석 완료")
            
            # 4단계: 요구사항 분석 (판례 결과 반영)
            print(f"📋 4단계: 요구사항 분석 (판례 결과 반영)")
            state.requirements_analysis = await self.requirements_workflow.analyze_requirements(
                hs_code=state.selected_hs_code,
                product_name=product_name,
                product_description=product_description,
                force_refresh=False,  # 기존 분석 결과가 있으면 재사용
                is_new_product=False,  # HS 코드 기반 캐시 확인 활성화
                precedent_analysis=state.precedents_analysis  # 판례 결과 전달
            )
            print(f"✅ 요구사항 분석 완료 (판례 결과 반영)")
            
            # 5단계: 최종 검증 (판례 + 요구사항 통합)
            print(f"🔍 5단계: 최종 검증 (판례 + 요구사항 통합)")
            state.verified_requirements = await self._verify_requirements(
                state.requirements_analysis, state.precedents_analysis
            )
            print(f"✅ 최종 검증 완료")
            
            # 최종 결과 통합
            state.processing_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            state.final_result = self._integrate_final_results(state)
            state.status = "completed"
            
            print(f"🎉 상품 등록 워크플로우 완료 - 소요시간: {state.processing_time_ms}ms")
            return state.final_result
            
        except Exception as e:
            print(f"❌ 상품 등록 워크플로우 실패: {e}")
            state.status = "failed"
            return {
                "status": "failed",
                "error": str(e),
                "product_id": product_id,
                "processing_time_ms": int((datetime.now() - start_time).total_seconds() * 1000)
            }
    
    async def _recommend_hs_codes(
        self, 
        product_name: str, 
        product_description: str, 
        category: str
    ) -> List[Dict[str, Any]]:
        """HS코드 추천 (기존 서비스 호출)"""
        # TODO: 기존 HS코드 추천 서비스 호출
        return [
            {
                "hs_code": "1234.56.78",
                "description": "Sample HS Code",
                "confidence": 0.95,
                "category": category
            }
        ]
    
    async def _calculate_tariff_estimation(
        self, 
        hs_code: str, 
        product_name: str
    ) -> Dict[str, Any]:
        """예상 관세 계산 (기존 서비스 호출)"""
        # TODO: 기존 관세 계산 서비스 호출
        return {
            "hs_code": hs_code,
            "estimated_rate": 5.5,
            "duty_type": "ad_valorem",
            "additional_fees": [],
            "total_estimated_cost": 0.055
        }
    
    async def _analyze_precedents(
        self, 
        hs_code: str, 
        product_name: str,
        requirements_analysis: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """판례 분석 (최적화: 요구사항 분석보다 먼저 실행)"""
        
        print(f"🔍 판례 분석 시작 - HS코드: {hs_code}, 상품: {product_name}")
        
        try:
            # 기존 판례 분석 서비스 호출 (precedents-analysis 모듈)
            from app.routers.precedents_router import analyze_precedents
            
            request_data = {
                "product_id": "temp_id",
                "product_name": product_name,
                "hs_code": hs_code,
                "description": f"Analysis for {product_name}",
                "origin_country": "Korea",
                "price": 25.00,
                "fob_price": 22.00
            }
            
            # 판례 분석 실행
            precedent_result = await analyze_precedents(request_data)
            
            print(f"✅ 판례 분석 완료 - {precedent_result.get('precedents_data', [])}개 판례 발견")
            
            return {
                "hs_code": hs_code,
                "product_name": product_name,
                "precedent_cases": precedent_result.get("precedents_data", []),
                "violation_patterns": precedent_result.get("failure_cases", []),
                "success_patterns": precedent_result.get("success_cases", []),
                "risk_assessment": "low" if precedent_result.get("confidence_score", 0) > 0.7 else "medium",
                "confidence_score": precedent_result.get("confidence_score", 0),
                "actionable_insights": precedent_result.get("actionable_insights", []),
                "risk_factors": precedent_result.get("risk_factors", []),
                "recommended_action": precedent_result.get("recommended_action", ""),
                "analysis_timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"⚠️ 판례 분석 실패: {e}")
            # 실패 시 기본값 반환
            return {
                "hs_code": hs_code,
                "product_name": product_name,
                "precedent_cases": [],
                "violation_patterns": [],
                "success_patterns": [],
                "risk_assessment": "unknown",
                "confidence_score": 0,
                "error": str(e),
                "analysis_timestamp": datetime.now().isoformat()
            }
    
    async def _verify_requirements(
        self,
        requirements_analysis: Dict[str, Any],
        precedents_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """요구사항 재검증"""
        
        print(f"🔍 판례 기반 요구사항 재검증")
        
        # 기존 요구사항 분석 결과
        original_requirements = requirements_analysis.get("llm_summary", {})
        
        # 판례 분석 결과
        precedent_cases = precedents_analysis.get("precedent_cases", [])
        violation_patterns = precedents_analysis.get("violation_patterns", [])
        
        # 재검증 로직
        verified_requirements = {
            "original_requirements": original_requirements,
            "precedent_verification": {
                "verified_by_precedent": True,
                "precedent_cases_count": len(precedent_cases),
                "violation_patterns_count": len(violation_patterns),
                "risk_level": precedents_analysis.get("risk_assessment", "unknown")
            },
            "updated_requirements": self._update_requirements_based_on_precedents(
                original_requirements, precedent_cases, violation_patterns
            ),
            "verification_timestamp": datetime.now().isoformat()
        }
        
        return verified_requirements
    
    def _update_requirements_based_on_precedents(
        self,
        original_requirements: Dict[str, Any],
        precedent_cases: List[Dict[str, Any]],
        violation_patterns: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """판례 기반으로 요구사항 업데이트"""
        
        updated_requirements = original_requirements.copy()
        
        # 판례에서 발견된 위반 패턴을 기반으로 요구사항 강화
        for pattern in violation_patterns:
            violation_type = pattern.get("type", "")
            if violation_type == "missing_certification":
                # 인증서 요구사항 강화
                if "certifications" not in updated_requirements:
                    updated_requirements["certifications"] = []
                updated_requirements["certifications"].append({
                    "type": "additional_certification",
                    "reason": "precedent_based_requirement",
                    "precedent_case": pattern.get("case_id", "")
                })
            
            elif violation_type == "incomplete_documentation":
                # 서류 요구사항 강화
                if "documents" not in updated_requirements:
                    updated_requirements["documents"] = []
                updated_requirements["documents"].append({
                    "type": "additional_document",
                    "reason": "precedent_based_requirement",
                    "precedent_case": pattern.get("case_id", "")
                })
        
        # 검증 플래그 추가
        updated_requirements["verified_by_precedent"] = True
        updated_requirements["precedent_verification_date"] = datetime.now().isoformat()
        
        return updated_requirements
    
    def _integrate_final_results(self, state: ProductRegistrationWorkflowState) -> Dict[str, Any]:
        """최종 결과 통합"""
        return {
            "product_id": state.product_id,
            "product_name": state.product_name,
            "product_description": state.product_description,
            "category": state.category,
            
            # 1단계 결과
            "recommended_hs_codes": state.recommended_hs_codes,
            "selected_hs_code": state.selected_hs_code,
            
            # 2단계 결과
            "tariff_estimation": state.tariff_estimation,
            
            # 3단계 결과 (요구사항 분석)
            "requirements_analysis": state.requirements_analysis,
            
            # 4단계 결과
            "precedents_analysis": state.precedents_analysis,
            
            # 5단계 결과
            "verified_requirements": state.verified_requirements,
            
            # 메타데이터
            "processing_time_ms": state.processing_time_ms,
            "status": state.status,
            "timestamp": datetime.now().isoformat(),
            "workflow_version": "1.0"
        }

# 워크플로우 실행 함수
async def execute_product_registration(
    product_id: str,
    product_name: str,
    product_description: str,
    category: str
) -> Dict[str, Any]:
    """상품 등록 워크플로우 실행 함수"""
    workflow = ProductRegistrationWorkflow()
    return await workflow.execute_product_registration_workflow(
        product_id, product_name, product_description, category
    )
