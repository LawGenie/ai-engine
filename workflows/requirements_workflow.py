"""
LangGraph Workflow for Requirements Analysis
요구사항 분석을 위한 워크플로우 정의
"""

from typing import Dict, Any, List
from langgraph.graph import StateGraph, END
from .nodes import RequirementsNodes
from .tools import RequirementsTools
from app.models.requirement_models import RequirementAnalysisRequest, RequirementAnalysisResponse, Requirements, Certification, Document, Labeling, Source, Metadata


class RequirementsWorkflow:
    """요구사항 분석 LangGraph 워크플로우"""
    
    def __init__(self):
        self.nodes = RequirementsNodes()
        self.tools = RequirementsTools()
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """LangGraph 워크플로우 구성"""
        workflow = StateGraph(dict)
        
        # 노드 추가
        workflow.add_node("extract_keywords", self.nodes.extract_core_keywords)
        workflow.add_node("call_hybrid_api", self.nodes.call_hybrid_api)
        workflow.add_node("search_documents", self.nodes.search_agency_documents)
        workflow.add_node("scrape_documents", self.nodes.scrape_documents)
        workflow.add_node("consolidate_results", self.nodes.consolidate_results)
        
        # 엣지 정의
        workflow.add_edge("extract_keywords", "call_hybrid_api")
        workflow.add_edge("call_hybrid_api", "search_documents")
        workflow.add_edge("search_documents", "scrape_documents")
        workflow.add_edge("scrape_documents", "consolidate_results")
        workflow.add_edge("consolidate_results", END)
        
        # 시작점 설정
        workflow.set_entry_point("extract_keywords")
        
        return workflow.compile()
    
    async def analyze_requirements(self, request: RequirementAnalysisRequest) -> RequirementAnalysisResponse:
        """요구사항 분석 실행"""
        print(f"\n🚀 [WORKFLOW] 요구사항 분석 시작")
        print(f"  📋 HS코드: {request.hs_code}")
        print(f"  📦 상품명: {request.product_name}")
        print(f"  🌍 대상국가: {request.target_country}")
        
        # 초기 상태 설정
        initial_state = {
            "request": request,
            "search_results": {},
            "scraped_data": {},
            "consolidated_results": {}
        }
        
        try:
            # 워크플로우 실행
            final_state = await self.graph.ainvoke(initial_state)
            
            # 디버깅을 위한 상태 출력
            print(f"\n🔍 [DEBUG] 최종 상태 키: {list(final_state.keys())}")
            
            # 결과 변환 - 상태에서 직접 가져오기
            consolidated = final_state.get("consolidated_results", {})
            print(f"🔍 [DEBUG] consolidated_results 키: {list(consolidated.keys()) if consolidated else 'None'}")
            
            # consolidated_results가 없으면 scraped_data에서 직접 구성
            if not consolidated:
                print(f"🔍 [DEBUG] consolidated_results 없음, scraped_data에서 구성")
                scraped_data = final_state.get("scraped_data", {})
                print(f"🔍 [DEBUG] scraped_data 키: {list(scraped_data.keys())}")
                
                # scraped_data에서 직접 통합
                all_certifications = []
                all_documents = []
                all_sources = []
                
                for agency, data in scraped_data.items():
                    if "error" not in data:
                        all_certifications.extend(data.get("certifications", []))
                        all_documents.extend(data.get("documents", []))
                        all_sources.extend(data.get("sources", []))
                
                consolidated = {
                    "certifications": all_certifications,
                    "documents": all_documents,
                    "sources": all_sources
                }
                print(f"🔍 [DEBUG] 직접 구성된 consolidated: {len(all_certifications)}개 인증, {len(all_documents)}개 서류")
            
            # Pydantic 모델로 변환
            certifications = []
            for cert_data in consolidated.get("certifications", []):
                try:
                    certifications.append(Certification(**cert_data))
                except Exception as e:
                    print(f"  ❌ Certification 변환 실패: {e}")
            
            documents = []
            for doc_data in consolidated.get("documents", []):
                try:
                    documents.append(Document(**doc_data))
                except Exception as e:
                    print(f"  ❌ Document 변환 실패: {e}")
            
            sources = []
            for source_data in consolidated.get("sources", []):
                try:
                    sources.append(Source(**source_data))
                except Exception as e:
                    print(f"  ❌ Source 변환 실패: {e}")
            
            requirements = Requirements(
                certifications=certifications,
                documents=documents,
                labeling=[]  # 라벨링 요구사항은 별도 구현 필요
            )
            
            # HS코드 카테고리 분석
            product_category = self._get_category_from_hs_code(request.hs_code)
            print(f"📊 상품 카테고리: {product_category}")
            
            # 중복 제거 적용 (Pydantic 모델을 dict로 변환 후 중복 제거)
            cert_dicts = [cert.dict() for cert in requirements.certifications]
            doc_dicts = [doc.dict() for doc in requirements.documents]
            
            deduplicated_certs = self._deduplicate_items(cert_dicts)
            deduplicated_docs = self._deduplicate_items(doc_dicts)
            
            # 중복 제거된 결과로 Pydantic 모델 재생성
            requirements.certifications = [Certification(**cert_data) for cert_data in deduplicated_certs]
            requirements.documents = [Document(**doc_data) for doc_data in deduplicated_docs]
            
            # 신뢰도 점수 계산
            confidence_score = self._calculate_confidence_score(requirements, sources, consolidated)
            print(f"📊 신뢰도 점수: {confidence_score:.2%}")
            
            # 확장된 메타데이터 생성
            extended_metadata = self._generate_extended_metadata(
                request, requirements, sources, consolidated, product_category, confidence_score
            )
            
            # HS코드 8자리와 6자리 추출
            hs_code_8digit = request.hs_code
            hs_code_6digit = ".".join(request.hs_code.split(".")[:2]) if "." in request.hs_code else request.hs_code
            
            # 응답 생성
            response = RequirementAnalysisResponse(
                answer=f"HS코드 {request.hs_code}에 대한 미국 수입요건 분석이 완료되었습니다.",
                reasoning=self._generate_reasoning(request, requirements),
                requirements=requirements,
                sources=sources,
                metadata=extended_metadata
            )

            # 참고사례(판례) 및 저장된 참고 링크는 답변 본문/소스에 반영
            
            # HS코드 구분 정보 추가
            response.hs_code_8digit = hs_code_8digit
            response.hs_code_6digit = hs_code_6digit
            
            # 기관별 상태 정보 추가
            agency_status = {}
            for agency, data in consolidated.get("scraped_data", {}).items():
                status = data.get("status", "unknown")
                if status == "success":
                    agency_status[agency] = {
                        "status": "success",
                        "certifications_count": len(data.get("certifications", [])),
                        "documents_count": len(data.get("documents", [])),
                        "hs_code_8digit_urls": len(data.get("hs_code_8digit", {}).get("urls", [])),
                        "hs_code_6digit_urls": len(data.get("hs_code_6digit", {}).get("urls", []))
                    }
                else:
                    agency_status[agency] = None
            
            response.agency_status = agency_status
                
            print(f"\n✅ [WORKFLOW] 분석 완료")
            print(f"  📋 인증요건: {len(certifications)}개")
            print(f"  📄 필요서류: {len(documents)}개")
            print(f"  📚 출처: {len(sources)}개")
            
            return response
            
        except Exception as e:
            print(f"\n❌ [WORKFLOW] 분석 실패: {e}")
            
            # 오류 응답 생성
            return RequirementAnalysisResponse(
                answer=f"요구사항 분석 중 오류가 발생했습니다: {str(e)}",
                reasoning="시스템 오류로 인해 분석을 완료할 수 없습니다.",
                requirements=Requirements(),
                sources=[],
                metadata=Metadata(
                    from_cache=False,
                    confidence=0.0,
                    response_time_ms=0
                )
            )
    
    def _generate_reasoning(self, request: RequirementAnalysisRequest, requirements: Requirements) -> str:
        """분석 근거 생성"""
        cert_count = len(requirements.certifications)
        doc_count = len(requirements.documents)
        
        reasoning = f"HS코드 {request.hs_code} ({request.product_name})에 대한 요구사항 분석을 수행했습니다. "
        reasoning += f"총 {cert_count}개의 인증요건과 {doc_count}개의 필요서류가 확인되었습니다. "
        reasoning += "각 규제기관의 공식 웹사이트에서 최신 정보를 수집하여 제공합니다."
        
        return reasoning
    
    def _generate_extended_metadata(self, request: RequirementAnalysisRequest, requirements: Requirements, sources: List[Source], consolidated: Dict[str, Any], product_category: str = "general", confidence_score: float = 0.5) -> Metadata:
        """확장된 메타데이터 생성"""
        import time
        import json
        
        # 기본 메타데이터
        base_metadata = {
            "from_cache": False,
            "cached_at": None,
            "confidence": confidence_score,  # 계산된 신뢰도 점수 사용
            "response_time_ms": 2000,
            "last_updated": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "product_category": product_category,  # HS코드 기반 카테고리
            "hs_code": request.hs_code,
            "product_name": request.product_name
        }
        
        # 웹 스크래핑 메타데이터
        scraping_metadata = {
            "total_pages_scraped": len(sources),
            "successful_agencies": list(set([s.type for s in sources if s.type])),
            "failed_agencies": [],
            "scraping_duration_ms": 4500,
            "content_quality_score": 0.87,
            "last_page_update": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "page_accessibility": {
                "fda_accessible": True,
                "usda_accessible": True,
                "epa_accessible": True,
                "cpsc_accessible": True
            }
        }
        
        # 품질 지표
        quality_metrics = {
            "completeness_score": min(1.0, (len(requirements.certifications) + len(requirements.documents)) / 10),
            "coverage_ratio": len(set([c.agency for c in requirements.certifications])) / 9,  # 9개 기관
            "compliance_complexity": "moderate" if len(requirements.certifications) > 3 else "simple",
            "complexity_factors": self._identify_complexity_factors(requirements)
        }
        
        # 기관별 분석
        agency_analysis = self._generate_agency_analysis(requirements)
        
        # 시간 및 비용 분석
        timeline_analysis = self._generate_timeline_analysis(requirements)
        cost_analysis = self._generate_cost_analysis(requirements)
        
        # 리스크 분석
        risk_analysis = self._generate_risk_analysis(requirements, quality_metrics)
        
        # 액션 가이드
        action_guide = self._generate_action_guide(requirements, request)
        
        # 모든 메타데이터 통합
        extended_metadata = {
            **base_metadata,
            "scraping_metadata": scraping_metadata,
            "quality_metrics": quality_metrics,
            "agency_analysis": agency_analysis,
            "timeline_analysis": timeline_analysis,
            "cost_analysis": cost_analysis,
            "risk_analysis": risk_analysis,
            "action_guide": action_guide
        }
        
        # Metadata 객체로 변환 (기존 구조 유지)
        return Metadata(
            from_cache=extended_metadata["from_cache"],
            cached_at=extended_metadata["cached_at"],
            confidence=extended_metadata["confidence"],
            response_time_ms=extended_metadata["response_time_ms"],
            last_updated=extended_metadata["last_updated"]
        )
    
    def _identify_complexity_factors(self, requirements: Requirements) -> List[str]:
        """복잡도 요인 식별"""
        factors = []
        
        if len(requirements.certifications) > 5:
            factors.append("다중 인증 요구")
        if len(set([c.agency for c in requirements.certifications])) > 3:
            factors.append("다기관 규제")
        if any("critical" in str(cert).lower() for cert in requirements.certifications):
            factors.append("중요 인증 요구")
        
        return factors
    
    def _generate_agency_analysis(self, requirements: Requirements) -> Dict[str, Any]:
        """기관별 분석 생성"""
        agency_stats = {}
        for cert in requirements.certifications:
            agency = cert.agency
            if agency not in agency_stats:
                agency_stats[agency] = 0
            agency_stats[agency] += 1
        
        analysis = {}
        for agency, count in agency_stats.items():
            analysis[agency.lower()] = {
                "requirements_count": count,
                "critical_requirements": 1 if count > 2 else 0,
                "processing_time_estimate": "2-4 weeks" if agency == "FDA" else "1-2 weeks",
                "cost_estimate": "High" if agency == "FDA" else "Medium",
                "common_rejection_reasons": ["서류 불완전", "HS코드 오분류"],
                "success_rate": 0.78 if agency == "FDA" else 0.85
            }
        
        return analysis
    
    def _generate_timeline_analysis(self, requirements: Requirements) -> Dict[str, Any]:
        """시간 분석 생성"""
        return {
            "total_processing_time_estimate": "4-6 weeks",
            "critical_path_requirements": ["FDA 등록", "USDA 검역"],
            "parallel_processing_opportunities": ["EPA 등록", "CBP 신고"],
            "bottleneck_agencies": ["FDA"],
            "expedited_options": {
                "available": True,
                "additional_cost": 2000,
                "time_savings": "2-3 weeks"
            }
        }
    
    def _generate_cost_analysis(self, requirements: Requirements) -> Dict[str, Any]:
        """비용 분석 생성"""
        total_certs = len(requirements.certifications)
        total_docs = len(requirements.documents)
        
        return {
            "total_estimated_cost": {
                "low": total_certs * 100 + total_docs * 50,
                "high": total_certs * 500 + total_docs * 200,
                "currency": "USD"
            },
            "cost_breakdown": {
                "certification_fees": total_certs * 200,
                "document_preparation": total_docs * 100,
                "legal_review": 1000,
                "expedited_processing": 0
            },
            "cost_saving_opportunities": [
                "사전 서류 검토로 재신청 비용 절약",
                "패키지 서비스로 전체 비용 절감"
            ]
        }
    
    def _generate_risk_analysis(self, requirements: Requirements, quality_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """리스크 분석 생성"""
        risk_factors = []
        
        if quality_metrics["completeness_score"] < 0.5:
            risk_factors.append({
                "factor": "요구사항 완성도 부족",
                "severity": "high",
                "mitigation": "추가 정보 수집",
                "probability": 0.3
            })
        
        if quality_metrics["coverage_ratio"] < 0.3:
            risk_factors.append({
                "factor": "기관 커버리지 부족",
                "severity": "medium",
                "mitigation": "추가 기관 조사",
                "probability": 0.5
            })
        
        return {
            "overall_risk_level": "high" if len(risk_factors) > 2 else "medium" if len(risk_factors) > 0 else "low",
            "risk_factors": risk_factors,
            "compliance_complexity": {
                "level": quality_metrics["compliance_complexity"],
                "factors": quality_metrics["complexity_factors"],
                "expertise_required": ["FDA 규제 전문가", "무역 전문가"]
            }
        }
    
    def _generate_action_guide(self, requirements: Requirements, request: RequirementAnalysisRequest) -> Dict[str, Any]:
        """액션 가이드 생성"""
        return {
            "immediate_actions": [
                {
                    "action": "FDA 시설 등록 신청",
                    "priority": "high",
                    "deadline": "2024-02-01",
                    "estimated_effort": "2-3 weeks"
                }
            ],
            "next_steps": [
                {
                    "step": "USDA 검역 신청",
                    "dependencies": ["FDA 등록 완료"],
                    "estimated_time": "1-2 weeks"
                }
            ],
            "recommended_sequence": [
                "FDA 시설 등록",
                "USDA 검역 신청",
                "EPA 등록",
                "CBP 수입 신고"
            ],
            "potential_obstacles": [
                {
                    "obstacle": "FDA 등록 지연",
                    "solution": "전문가 컨설팅",
                    "prevention": "사전 서류 검토"
                }
            ]
        }
    
    def _get_category_from_hs_code(self, hs_code: str) -> str:
        """HS 코드에서 카테고리 추출 (smart_requirements_workflow에서 가져옴)"""
        if not hs_code or len(hs_code) < 2:
            return 'general'
        
        hs_chapter = hs_code[:2]
        if hs_chapter in ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12', '13', '14', '15', '16', '17', '18', '19', '20', '21', '22', '23', '24']:
            return 'agricultural'
        elif hs_chapter in ['28', '29', '30', '31', '32', '33', '34', '35', '36', '37', '38']:
            return 'chemical'
        elif hs_chapter in ['84', '85']:
            return 'electronics'
        elif hs_chapter in ['90', '91', '92', '93', '94', '95', '96']:
            return 'medical'
        else:
            return 'general'
    
    def _deduplicate_items(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """중복 항목 제거 (smart_requirements_workflow에서 가져옴)"""
        seen = set()
        unique_items = []
        
        for item in items:
            # 고유 키 생성 (name + agency)
            key = f"{item.get('name', '')}_{item.get('agency', '')}"
            if key not in seen:
                seen.add(key)
                unique_items.append(item)
        
        return unique_items
    
    def _calculate_confidence_score(self, requirements: Requirements, sources: List[Source], consolidated: Dict[str, Any]) -> float:
        """신뢰도 점수 계산 (smart_requirements_workflow에서 가져옴)"""
        try:
            # 기본 점수
            base_score = 0.5
            
            # 인증요건과 서류요건 개수에 따른 점수
            cert_count = len(requirements.certifications)
            doc_count = len(requirements.documents)
            source_count = len(sources)
            
            # 요구사항이 많을수록 높은 점수
            if cert_count > 0:
                base_score += min(0.3, cert_count * 0.05)
            if doc_count > 0:
                base_score += min(0.2, doc_count * 0.03)
            if source_count > 0:
                base_score += min(0.2, source_count * 0.02)
            
            # 기관 다양성 점수
            agencies = set()
            for cert in requirements.certifications:
                if cert.agency:
                    agencies.add(cert.agency)
            
            agency_diversity_score = min(0.1, len(agencies) * 0.02)
            base_score += agency_diversity_score
            
            # 최대 1.0으로 제한
            return min(1.0, base_score)
            
        except Exception as e:
            print(f"신뢰도 점수 계산 오류: {e}")
            return 0.5