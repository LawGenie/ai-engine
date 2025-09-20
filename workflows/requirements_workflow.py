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
        workflow.add_node("search_documents", self.nodes.search_agency_documents)
        workflow.add_node("scrape_documents", self.nodes.scrape_documents)
        workflow.add_node("consolidate_results", self.nodes.consolidate_results)
        
        # 엣지 정의
        workflow.add_edge("search_documents", "scrape_documents")
        workflow.add_edge("scrape_documents", "consolidate_results")
        workflow.add_edge("consolidate_results", END)
        
        # 시작점 설정
        workflow.set_entry_point("search_documents")
        
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
            
            # 응답 생성
            response = RequirementAnalysisResponse(
                answer=f"HS코드 {request.hs_code}에 대한 미국 수입요건 분석이 완료되었습니다.",
                reasoning=self._generate_reasoning(request, requirements),
                requirements=requirements,
                sources=sources,
                metadata=Metadata(
                    from_cache=False,
                    confidence=0.85,
                    response_time_ms=2000
                )
            )
            
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
