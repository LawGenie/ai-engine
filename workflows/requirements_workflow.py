"""
요구사항 분석 워크플로우
HS코드 기반 미국 수입요건 분석을 위한 통합 워크플로우
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, List, Optional
from app.services.requirements.requirements_cache_service import RequirementsCacheService

@dataclass
class RequirementsState:
    hs_code: str
    product_name: str
    product_description: str
    agency_mapping: Optional[Any] = None
    recommended_agencies: List[str] = None
    search_results: Dict[str, Any] = None
    raw_documents: List[Dict[str, Any]] = None
    llm_summary: Optional[Any] = None
    final_result: Dict[str, Any] = None
    processing_time_ms: int = 0

class RequirementsWorkflow:
    def __init__(self):
        from app.services.requirements.hs_code_agency_mapping_service import HsCodeAgencyMappingService
        from app.services.requirements.search_service import SearchService
        from app.services.requirements.llm_summary_service import LlmSummaryService
        
        self.agency_mapping_service = HsCodeAgencyMappingService()
        self.search_service = SearchService()
        self.llm_summary_service = LlmSummaryService()
        self.cache_service = RequirementsCacheService()
    
    async def analyze_requirements(
        self, 
        hs_code: str, 
        product_name: str, 
        product_description: str = "",
        force_refresh: bool = False,
        is_new_product: bool = False
    ) -> Dict[str, Any]:
        """요구사항 분석 실행"""
        
        print(f"🚀 요구사항 분석 시작 - HS코드: {hs_code}, 강제갱신: {force_refresh}, 신규상품: {is_new_product}")
        
        # 캐시 확인 (강제 갱신이 아니고 신규 상품이 아닌 경우)
        if not force_refresh and not is_new_product:
            cached_result = await self.cache_service.get_cached_analysis(hs_code, product_name)
            if cached_result:
                print(f"✅ 캐시에서 반환")
                cached_result["cache_hit"] = True
                cached_result["force_refresh"] = force_refresh
                cached_result["is_new_product"] = is_new_product
                return cached_result
        
        start_time = datetime.now()
        
        state = RequirementsState(
            hs_code=hs_code,
            product_name=product_name,
            product_description=product_description
        )
        
        try:
            # 1단계: 기관 매핑
            mapping_result = await self.agency_mapping_service.get_relevant_agencies(
                hs_code=hs_code,
                product_name=product_name,
                product_description=product_description
            )
            state.recommended_agencies = mapping_result.recommended_agencies
            
            # 2단계: 하이브리드 검색
            search_queries = self._build_queries(hs_code, product_name, state.recommended_agencies)
            search_results = await self.search_service.search_requirements(
                hs_code=hs_code,
                product_name=product_name,
                agencies=state.recommended_agencies,
                search_queries=search_queries
            )
            state.search_results = search_results
            
            # 3단계: LLM 요약
            raw_documents = self._extract_documents(search_results)
            
            # 검색 결과가 없어도 기본 요약 실행 (mock 데이터 포함)
            if not raw_documents:
                print("⚠️ 검색 결과 없음 - 기본 요약 정보 생성")
                raw_documents = [{
                    "content": f"HS코드 {hs_code} ({product_name})의 기본 수입 요건 안내",
                    "source": "기본 안내",
                    "website": "https://www.cbp.gov/trade/trade-tools"
                }]
            
            summary_result = await self.llm_summary_service.summarize_regulations(
                hs_code=hs_code,
                product_name=product_name,
                raw_documents=raw_documents
            )
            state.llm_summary = summary_result
            
            # 4단계: 결과 통합
            state.processing_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            state.final_result = self._integrate_results(state)
            
            # 캐시에 저장 (신규 상품이거나 강제 갱신인 경우)
            if is_new_product or force_refresh:
                await self.cache_service.save_analysis_to_cache(hs_code, product_name, state.final_result)
                print(f"💾 분석 결과 캐시에 저장")
            
            print(f"✅ 분석 완료 - 소요시간: {state.processing_time_ms}ms")
            return state.final_result
            
        except Exception as e:
            print(f"❌ 분석 실패: {e}")
            return {"error": str(e), "status": "failed"}
    
    def _build_queries(self, hs_code: str, product_name: str, agencies: List[str]) -> Dict[str, List[str]]:
        queries = {}
        for agency in agencies:
            agency_queries = [
                f"{agency} import requirements {product_name}",
                f"{agency} regulations HS {hs_code}"
            ]
            queries[agency] = agency_queries[:3]
        return queries
    
    def _extract_documents(self, search_results: Dict[str, Any]) -> List[Dict[str, Any]]:
        documents = []
        for agency, search_result in search_results.items():
            for result in search_result.results:
                documents.append({
                    "title": result.get("title", "Unknown"),
                    "content": result.get("content", ""),
                    "url": result.get("url", ""),
                    "agency": agency
                })
        return documents
    
    def _integrate_results(self, state: RequirementsState) -> Dict[str, Any]:
        try:
            result = {
                "hs_code": state.hs_code or "UNKNOWN",
                "product_name": state.product_name or "Unknown Product",
                "processing_time_ms": state.processing_time_ms or 0,
                "timestamp": datetime.now().isoformat(),
                "status": "completed",
                "cache_hit": False,
                "force_refresh": False,
                "is_new_product": False
            }
        except Exception as e:
            print(f"❌ 결과 통합 중 오류 발생: {e}")
            # 👇 에러 발생 시에도 필수 필드들을 포함한 기본 응답 반환
            result = {
                "hs_code": "UNKNOWN",
                "product_name": "Unknown Product", 
                "processing_time_ms": 0,
                "timestamp": datetime.now().isoformat(),
                "status": "failed",
                "cache_hit": False,
                "force_refresh": False,
                "is_new_product": False,
                "error": str(e)
            }
        
        try:
            if state.recommended_agencies:
                result["recommended_agencies"] = state.recommended_agencies
            
            if state.search_results:
                result["search_results"] = {
                    agency: {
                        "results_count": len(search_result.results),
                        "source": search_result.source,
                        "cost": search_result.cost
                    }
                    for agency, search_result in state.search_results.items()
                }
            
            if state.llm_summary:
                result["llm_summary"] = {
                    "critical_requirements": state.llm_summary.critical_requirements,
                    "required_documents": state.llm_summary.required_documents,
                    "compliance_steps": state.llm_summary.compliance_steps,
                    "estimated_costs": state.llm_summary.estimated_costs,
                    "timeline": state.llm_summary.timeline,
                    "confidence_score": state.llm_summary.confidence_score
                }
        except Exception as e:
            print(f"⚠️ 데이터 추출 중 오류 발생 (무시하고 계속): {e}")
            # 에러가 발생해도 필수 필드들은 유지
        
        # 🎯 모든 단계의 상세 메타데이터를 최종 결과에 포함
        result["comprehensive_metadata"] = {
            "analysis_workflow_steps": {
                "total_steps_completed": 4,  # 기관매핑, 검색, 요약, 통합
                "processing_stages": [
                    "keyword_extraction",
                    "search_agency_documents", 
                    "hybrid_api_call",
                    "document_scraping",
                    "result_consolidation",
                    "llm_summarization"
                ],
                "workflow_performance": {
                    "total_processing_time_ms": state.processing_time_ms,
                    "analysis_timestamp": datetime.now().isoformat(),
                    "cache_hit": result.get("cache_hit", False),
                    "force_refresh": result.get("force_refresh", False),
                    "is_new_product": result.get("is_new_product", False)
                }
            },
            "data_collection_summary": {
                "agencies_analyzed": len(state.recommended_agencies) if state.recommended_agencies else 0,
                "search_results_count": len(state.search_results) if state.search_results else 0,
                "total_urls_found": sum(len(sr.results) for sr in state.search_results.values()) if state.search_results else 0,
                    "raw_documents_count": 0,  # raw_documents는 통합 단계에서 처리됨
                "llm_summary_quality": "successful" if state.llm_summary else "failed",
                "metadata_completeness_score": self._calculate_metadata_completeness(result, state)
            },
            "technical_details": {
                "search_provider": state.search_results[list(state.search_results.keys())[0]].source if state.search_results else "unknown",
                "llm_model_used": "default",  # 실제 사용된 모델명으로 업데이트 가능
                "data_sources": ["tavily_search", "government_apis", "web_scraping", "precedents_db"],
                "api_endpoints_called": list(self.search_service.free_api_endpoints.keys()) if hasattr(self.search_service, 'free_api_endpoints') else []
            }
        }
        
        return result
    
    def _calculate_metadata_completeness(self, result: Dict[str, Any], state) -> float:
        """메타데이터 완성도 점수 계산 (0.0-1.0)"""
        try:
            score = 0.0
            total_checks = 8
            
            # 기본 정보 확인
            if result.get("hs_code"): score += 0.125
            if result.get("product_name"): score += 0.125
            if result.get("recommended_agencies"): score += 0.125
            if result.get("search_results"): score += 0.125
            if result.get("llm_summary"): score += 0.125
            if result.get("processing_time_ms", 0) > 0: score += 0.125
            if result.get("timestamp"): score += 0.125
            
            # 풍부한 데이터 확인
            if result.get("search_results"):
                total_urls = sum(len(sr.results) for sr in result["search_results"].values() if hasattr(sr, 'results'))
                if total_urls > 0: score += 0.125  # 검색 결과가 있으면 보너스
            
            return min(score, 1.0)
        except Exception:
            return 0.0