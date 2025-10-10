"""
통합 워크플로우 (Unified Workflow)

이 워크플로우는 LangGraph를 사용하여 요구사항 분석을 수행합니다.

워크플로우 단계:
1. extract_keywords: 제품명에서 핵심 키워드 추출
2. search_documents: 정부 기관 문서 검색 (무료 API + Tavily)
3. hybrid_api_call: 하이브리드 API 호출 (HS코드 매핑 + 검색)
4. scrape_documents: 문서 스크래핑
5. consolidate_results: 결과 통합 (LLM 요약 포함)
6. finalize_results: 최종 결과 포맷팅

특징:
- 병렬 처리 지원 (API 상태에 따라 자동 전환)
- 다층 캐시 (메모리 + 디스크)
- 에러 핸들링 및 폴백
- 신뢰도 계산 (가중치 기반 + 5단계 등급)

사용 예:
    workflow = UnifiedRequirementsWorkflow()
    result = await workflow.analyze_requirements(
        hs_code="3304.99",
        product_name="vitamin c serum"
    )
"""

from langgraph.graph import StateGraph
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime
import asyncio
from .nodes import RequirementsNodes
from .tools import RequirementsTools
from app.services.requirements.error_handler import error_handler, WorkflowError, ErrorSeverity
from app.services.requirements.env_manager import env_manager
from app.services.requirements.parallel_processor import parallel_processor, ProcessingTask, ProcessingMode
from app.services.requirements.enhanced_cache_service import enhanced_cache
from app.services.requirements.confidence_calculator import get_confidence_calculator

@dataclass
class UnifiedWorkflowState:
    """통합 워크플로우 상태"""
    # 입력 데이터
    hs_code: str
    product_name: str
    product_description: str = ""
    
    # 중간 결과
    core_keywords: List[str] = None
    keyword_strategies: List[Dict[str, Any]] = None
    search_results: Dict[str, Any] = None
    hybrid_result: Dict[str, Any] = None
    scraped_data: Dict[str, Any] = None
    consolidated_results: Dict[str, Any] = None
    
    # 메타데이터
    detailed_metadata: Dict[str, Any] = None
    processing_time_ms: int = 0
    status: str = "pending"
    errors: List[Dict[str, Any]] = None
    
    # 최종 결과
    final_result: Dict[str, Any] = None

class UnifiedRequirementsWorkflow:
    """통합 요구사항 분석 워크플로우"""
    
    def __init__(self):
        self.nodes = RequirementsNodes()
        self.tools = RequirementsTools()
        self.workflow = self._create_workflow()
        
        # API 상태 확인
        api_status = env_manager.get_api_status_summary()
        print(f"🚀 통합 워크플로우 초기화 완료")
        print(f"📊 API 상태: {api_status['available_api_keys']}/{api_status['total_api_keys']}개 키 사용 가능")
    
    def _create_workflow(self) -> StateGraph:
        """워크플로우 생성"""
        workflow = StateGraph(UnifiedWorkflowState)
        
        # 노드 추가
        workflow.add_node("extract_keywords", self._extract_keywords_node)
        workflow.add_node("search_documents", self._search_documents_node)
        workflow.add_node("hybrid_api_call", self._hybrid_api_call_node)
        workflow.add_node("scrape_documents", self._scrape_documents_node)
        workflow.add_node("consolidate_results", self._consolidate_results_node)
        workflow.add_node("finalize_results", self._finalize_results_node)
        
        # 엣지 추가 (순차 실행)
        workflow.add_edge("extract_keywords", "search_documents")
        workflow.add_edge("search_documents", "hybrid_api_call")
        workflow.add_edge("hybrid_api_call", "scrape_documents")
        workflow.add_edge("scrape_documents", "consolidate_results")
        workflow.add_edge("consolidate_results", "finalize_results")
        
        # 시작점과 끝점 설정
        workflow.set_entry_point("extract_keywords")
        workflow.set_finish_point("finalize_results")
        
        return workflow.compile()
    
    async def _extract_keywords_node(self, state: UnifiedWorkflowState) -> UnifiedWorkflowState:
        """키워드 추출 노드"""
        try:
            print(f"\n🔎 [UNIFIED] 키워드 추출 시작")
            
            # RequirementsNodes의 extract_core_keywords 메서드 호출
            temp_state = {"request": type('Request', (), {
                'hs_code': state.hs_code,
                'product_name': state.product_name,
                'product_description': state.product_description
            })()}
            
            result_state = await self.nodes.extract_core_keywords(temp_state)
            
            # 결과를 UnifiedWorkflowState에 복사
            state.core_keywords = result_state.get("core_keywords", [])
            state.keyword_strategies = result_state.get("keyword_strategies", [])
            state.detailed_metadata = result_state.get("detailed_metadata", {})
            
            print(f"✅ 키워드 추출 완료: {state.core_keywords}")
            
        except Exception as e:
            print(f"❌ 키워드 추출 실패: {e}")
            error_handler.handle_error(
                WorkflowError(
                    f"키워드 추출 실패: {str(e)}",
                    ErrorSeverity.MEDIUM
                ),
                {'step': 'extract_keywords', 'state': state}
            )
            # 폴백 키워드 사용
            state.core_keywords = ['product', 'import', 'requirement']
            state.keyword_strategies = [{"strategy": "fallback", "keywords": state.core_keywords}]
        
        return state
    
    async def _search_documents_node(self, state: UnifiedWorkflowState) -> UnifiedWorkflowState:
        """문서 검색 노드"""
        try:
            print(f"\n🔍 [UNIFIED] 문서 검색 시작")
            
            # RequirementsNodes의 search_agency_documents 메서드 호출
            temp_state = {
                "request": type('Request', (), {
                    'hs_code': state.hs_code,
                    'product_name': state.product_name,
                    'product_description': state.product_description
                })(),
                "core_keywords": state.core_keywords,
                "keyword_strategies": state.keyword_strategies,
                "detailed_metadata": state.detailed_metadata or {}
            }
            
            result_state = await self.nodes.search_agency_documents(temp_state)
            
            # 결과 복사
            state.search_results = result_state.get("search_results", {})
            state.detailed_metadata = result_state.get("detailed_metadata", {})
            
            print(f"✅ 문서 검색 완료: {len(state.search_results)}개 기관 결과")
            
        except Exception as e:
            print(f"❌ 문서 검색 실패: {e}")
            error_handler.handle_error(
                WorkflowError(
                    f"문서 검색 실패: {str(e)}",
                    ErrorSeverity.MEDIUM
                ),
                {'step': 'search_documents', 'state': state}
            )
            # 빈 검색 결과로 계속 진행
            state.search_results = {}
        
        return state
    
    async def _hybrid_api_call_node(self, state: UnifiedWorkflowState) -> UnifiedWorkflowState:
        """하이브리드 API 호출 노드"""
        try:
            print(f"\n📡 [UNIFIED] 하이브리드 API 호출 시작")
            
            # RequirementsNodes의 call_hybrid_api 메서드 호출
            temp_state = {
                "request": type('Request', (), {
                    'hs_code': state.hs_code,
                    'product_name': state.product_name,
                    'product_description': state.product_description
                })(),
                "core_keywords": state.core_keywords,
                "keyword_strategies": state.keyword_strategies,
                "search_results": state.search_results,
                "detailed_metadata": state.detailed_metadata or {}
            }
            
            result_state = await self.nodes.call_hybrid_api(temp_state)
            
            # 결과 복사
            state.hybrid_result = result_state.get("hybrid_result", {})
            state.detailed_metadata = result_state.get("detailed_metadata", {})
            
            print(f"✅ 하이브리드 API 호출 완료")
            
        except Exception as e:
            print(f"❌ 하이브리드 API 호출 실패: {e}")
            error_handler.handle_error(
                WorkflowError(
                    f"하이브리드 API 호출 실패: {str(e)}",
                    ErrorSeverity.LOW
                ),
                {'step': 'hybrid_api_call', 'state': state}
            )
            # 빈 결과로 계속 진행
            state.hybrid_result = {}
        
        return state
    
    async def _scrape_documents_node(self, state: UnifiedWorkflowState) -> UnifiedWorkflowState:
        """문서 스크래핑 노드"""
        try:
            print(f"\n🔍 [UNIFIED] 문서 스크래핑 시작")
            
            # RequirementsNodes의 scrape_documents 메서드 호출
            temp_state = {
                "request": type('Request', (), {
                    'hs_code': state.hs_code,
                    'product_name': state.product_name,
                    'product_description': state.product_description
                })(),
                "search_results": state.search_results,
                "detailed_metadata": state.detailed_metadata or {}
            }
            
            result_state = await self.nodes.scrape_documents(temp_state)
            
            # 결과 복사
            state.scraped_data = result_state.get("scraped_data", {})
            state.detailed_metadata = result_state.get("detailed_metadata", {})
            
            print(f"✅ 문서 스크래핑 완료: {len(state.scraped_data)}개 기관 처리")
            
        except Exception as e:
            print(f"❌ 문서 스크래핑 실패: {e}")
            error_handler.handle_error(
                WorkflowError(
                    f"문서 스크래핑 실패: {str(e)}",
                    ErrorSeverity.MEDIUM
                ),
                {'step': 'scrape_documents', 'state': state}
            )
            # 빈 스크래핑 결과로 계속 진행
            state.scraped_data = {}
        
        return state
    
    async def _consolidate_results_node(self, state: UnifiedWorkflowState) -> UnifiedWorkflowState:
        """결과 통합 노드"""
        try:
            print(f"\n🔍 [UNIFIED] 결과 통합 시작")
            
            # RequirementsNodes의 consolidate_results 메서드 호출
            temp_state = {
                "request": type('Request', (), {
                    'hs_code': state.hs_code,
                    'product_name': state.product_name,
                    'product_description': state.product_description
                })(),
                "search_results": state.search_results,
                "hybrid_result": state.hybrid_result,
                "scraped_data": state.scraped_data,
                "detailed_metadata": state.detailed_metadata or {}
            }
            
            result_state = await self.nodes.consolidate_results(temp_state)
            
            # 결과 복사
            state.consolidated_results = result_state.get("consolidated_results", {})
            state.detailed_metadata = result_state.get("detailed_metadata", {})
            
            print(f"✅ 결과 통합 완료")
            
        except Exception as e:
            print(f"❌ 결과 통합 실패: {e}")
            error_handler.handle_error(
                WorkflowError(
                    f"결과 통합 실패: {str(e)}",
                    ErrorSeverity.HIGH
                ),
                {'step': 'consolidate_results', 'state': state}
            )
            # 기본 통합 결과 생성
            state.consolidated_results = {
                "certifications": [],
                "documents": [],
                "sources": [],
                "precedents": []
            }
        
        return state
    
    async def _finalize_results_node(self, state: UnifiedWorkflowState) -> UnifiedWorkflowState:
        """최종 결과 정리 노드"""
        try:
            print(f"\n🎯 [UNIFIED] 최종 결과 정리 시작")
            
            # 최종 결과 구성
            state.final_result = {
                "hs_code": state.hs_code,
                "product_name": state.product_name,
                "product_description": state.product_description,
                "processing_time_ms": state.processing_time_ms,
                "timestamp": datetime.now().isoformat(),
                "status": "completed",
                
                # 분석 결과
                "core_keywords": state.core_keywords,
                
                # Citations (출처 정보)
                "citations": state.consolidated_results.get("citations", []) if state.consolidated_results else [],
                
                # 신뢰도 계산 (가중치 기반 + 5단계 등급)
                "confidence_analysis": self._calculate_confidence_analysis(state),
                
                "search_results_summary": {
                    "total_agencies": len(state.search_results) if state.search_results else 0,
                    "agencies_processed": list(state.search_results.keys()) if state.search_results else []
                },
                "hybrid_api_summary": {
                    "success": not state.hybrid_result.get("error") if state.hybrid_result else False,
                    "error": state.hybrid_result.get("error") if state.hybrid_result else None
                },
                "scraping_summary": {
                    "total_agencies_scraped": len(state.scraped_data) if state.scraped_data else 0,
                    "successful_scraping": len([d for d in state.scraped_data.values() 
                                               if d.get("status") == "success"]) if state.scraped_data else 0
                },
                "consolidated_results": state.consolidated_results,
                
                # LLM 요약 (가장 중요!)
                "llm_summary": state.consolidated_results.get("llm_summary") if state.consolidated_results else None,
                
                # 메타데이터
                "detailed_metadata": state.detailed_metadata,
                "api_status": env_manager.get_api_status_summary(),
                "error_summary": error_handler.get_error_summary()
            }
            
            state.status = "completed"
            print(f"✅ 최종 결과 정리 완료")
            
        except Exception as e:
            print(f"❌ 최종 결과 정리 실패: {e}")
            error_handler.handle_error(
                WorkflowError(
                    f"최종 결과 정리 실패: {str(e)}",
                    ErrorSeverity.HIGH
                ),
                {'step': 'finalize_results', 'state': state}
            )
            state.status = "failed"
            state.final_result = {
                "error": str(e),
                "status": "failed",
                "timestamp": datetime.now().isoformat()
            }
        
        return state
    
    def _calculate_confidence_analysis(self, state: UnifiedWorkflowState) -> Dict[str, Any]:
        """신뢰도 분석 계산"""
        try:
            calculator = get_confidence_calculator()
            
            # 데이터 추출
            consolidated = state.consolidated_results or {}
            citations = consolidated.get("citations", [])
            
            # 요건 데이터 (모든 항목)
            requirements = []
            if consolidated.get("certifications"):
                requirements.extend(consolidated["certifications"])
            if consolidated.get("documents"):
                requirements.extend(consolidated["documents"])
            if consolidated.get("sources"):
                requirements.extend(consolidated["sources"])
            
            # 타겟 기관 (hybrid_result에서 추출)
            target_agencies = []
            target_agencies_data = None
            hs_mapping_confidence = 0.5  # 기본값
            
            if state.hybrid_result:
                target_agencies_data = state.hybrid_result.get("combined_results", {}).get("target_agencies", {})
                if target_agencies_data:
                    target_agencies = target_agencies_data.get("primary_agencies", [])
                    hs_mapping_confidence = target_agencies_data.get("confidence", 0.5)
            
            # 신뢰도 계산
            confidence_result = calculator.calculate_confidence(
                sources=citations,
                requirements=requirements,
                target_agencies=target_agencies,
                hs_code_mapping_confidence=hs_mapping_confidence
            )
            
            print(f"  📊 신뢰도 분석: {confidence_result['score']:.2f} ({confidence_result['level']})")
            
            return confidence_result
            
        except Exception as e:
            print(f"⚠️ 신뢰도 계산 실패: {e}")
            return {
                "score": 0.5,
                "level": "중",
                "level_enum": "MEDIUM",
                "breakdown": {},
                "factors": [],
                "warnings": ["신뢰도 계산 실패"]
            }
    
    async def analyze_requirements(
        self, 
        hs_code: str, 
        product_name: str, 
        product_description: str = "",
        force_refresh: bool = False,
        is_new_product: bool = False
    ) -> Dict[str, Any]:
        """요구사항 분석 실행 (통합 워크플로우 + 병렬 처리)"""
        
        print(f"🚀 통합 워크플로우 시작 - HS코드: {hs_code}, 상품: {product_name}")
        start_time = datetime.now()
        
        try:
            # 캐시 확인
            if not force_refresh and not is_new_product:
                cache_key = enhanced_cache._generate_cache_key(
                    "requirements_analysis", hs_code, product_name
                )
                cached_result = await enhanced_cache.get(cache_key)
                if cached_result:
                    print(f"✅ 캐시에서 결과 반환")
                    return cached_result
            
            # 초기 상태 설정
            initial_state = UnifiedWorkflowState(
                hs_code=hs_code,
                product_name=product_name,
                product_description=product_description,
                detailed_metadata={},
                errors=[]
            )
            
            # 병렬 처리 가능한 노드들을 식별하고 병렬 실행
            if self._can_parallelize():
                result_state = await self._execute_parallel_workflow(initial_state)
            else:
                # 순차 실행
                result_state = await self.workflow.ainvoke(initial_state)
            
            # 처리 시간 계산
            processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
            result_state.processing_time_ms = processing_time
            
            # 캐시에 저장
            if result_state.final_result and result_state.status == "completed":
                cache_key = enhanced_cache._generate_cache_key(
                    "requirements_analysis", hs_code, product_name
                )
                await enhanced_cache.set(
                    cache_key, 
                    result_state.final_result, 
                    ttl=3600,  # 1시간
                    metadata={'disk_save': True}
                )
            
            print(f"✅ 통합 워크플로우 완료 - 소요시간: {processing_time}ms")
            
            return result_state.final_result or {
                "error": "워크플로우 실행 실패",
                "status": "failed",
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"❌ 통합 워크플로우 실패: {e}")
            error_handler.handle_error(
                WorkflowError(
                    f"통합 워크플로우 실패: {str(e)}",
                    ErrorSeverity.CRITICAL
                ),
                {'hs_code': hs_code, 'product_name': product_name}
            )
            
            return {
                "error": str(e),
                "status": "failed",
                "timestamp": datetime.now().isoformat(),
                "processing_time_ms": int((datetime.now() - start_time).total_seconds() * 1000)
            }
    
    def _can_parallelize(self) -> bool:
        """병렬 처리 가능 여부 확인"""
        # API 상태와 리소스 상태를 확인하여 병렬 처리 가능 여부 판단
        api_status = env_manager.get_api_status_summary()
        return api_status['available_api_keys'] > 0
    
    async def _execute_parallel_workflow(self, state: UnifiedWorkflowState) -> UnifiedWorkflowState:
        """병렬 워크플로우 실행"""
        print(f"🔄 병렬 워크플로우 실행 시작")
        
        try:
            # 병렬 처리 가능한 작업들 정의
            tasks = [
                ProcessingTask(
                    id="extract_keywords",
                    func=self._extract_keywords_node,
                    args=(state,),
                    priority=1
                ),
                ProcessingTask(
                    id="search_documents",
                    func=self._search_documents_node,
                    args=(state,),
                    priority=2
                ),
                ProcessingTask(
                    id="hybrid_api_call",
                    func=self._hybrid_api_call_node,
                    args=(state,),
                    priority=3
                )
            ]
            
            # 병렬 실행
            results = await parallel_processor.process_parallel(
                tasks, 
                mode=ProcessingMode.PARALLEL,
                timeout=600.0  # 백엔드 API 타임아웃 10분
            )
            
            # 결과 통합
            for result in results:
                if result.success:
                    # 상태 업데이트는 각 노드에서 수행됨
                    pass
                else:
                    print(f"⚠️ 병렬 작업 실패: {result.task_id}, 에러: {result.error}")
            
            # 순차 처리해야 하는 나머지 노드들 실행
            state = await self._scrape_documents_node(state)
            state = await self._consolidate_results_node(state)
            state = await self._finalize_results_node(state)
            
            print(f"✅ 병렬 워크플로우 실행 완료")
            return state
            
        except Exception as e:
            print(f"❌ 병렬 워크플로우 실행 실패: {e}")
            # 폴백으로 순차 실행
            return await self.workflow.ainvoke(state)
    
    def get_workflow_status(self) -> Dict[str, Any]:
        """워크플로우 상태 반환"""
        return {
            "workflow_type": "unified",
            "nodes_count": 6,
            "api_status": env_manager.get_api_status_summary(),
            "dependency_status": self.tools.validate_dependencies(),
            "error_summary": error_handler.get_error_summary(),
            "cache_metrics": enhanced_cache.get_metrics(),
            "parallel_processing_metrics": parallel_processor.get_metrics(),
            "timestamp": datetime.now().isoformat()
        }

# 전역 인스턴스
unified_workflow = UnifiedRequirementsWorkflow()
