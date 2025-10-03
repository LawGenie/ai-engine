from langgraph.graph import StateGraph, END
from typing import TypedDict, List, Dict, Any
from vector_service import VectorService
from llm_service import LLMService
from models import HsCodeAnalysisResponse, HsCodeSuggestion
import uuid
import logging
import asyncio

logger = logging.getLogger(__name__)

class WorkflowState(TypedDict):
    product_name: str
    product_description: str
    origin_country: str
    suggestions: List[Dict[str, Any]]

async def vector_search_node(state: WorkflowState) -> WorkflowState:
    """벡터 검색으로 Top-3 후보 찾기"""
    logger.info("Starting vector search")
    
    vector_service = VectorService()
    query = f"{state['product_name']} | {state['product_description']}"
    
    # 검색 결과에 이미 관세율 포함되어 있음
    candidates = await asyncio.to_thread(
        vector_service.search_similar, query, top_k=3
    )
    
    suggestions = []
    for candidate in candidates:
        # 검색 결과에서 직접 가져오기 (get_tariff_rate 호출 불필요)
        suggestions.append({
            "hsCode": candidate["hts_number"],
            "description": candidate["description"],
            "confidenceScore": candidate["similarity"],
            "usTariffRate": candidate["final_rate_for_korea"],  # 이미 포함됨
            "reasoning": ""
        })
    
    state["suggestions"] = suggestions
    logger.info(f"Vector search completed: {len(suggestions)} candidates")
    
    # 로깅으로 확인
    for s in suggestions:
        logger.info(f"  → {s['hsCode']}: {s['usTariffRate']}% tariff")
    
    return state

async def llm_reasoning_node(state: WorkflowState) -> WorkflowState:
    """LLM으로 추천 이유 생성"""
    logger.info("Starting LLM reasoning generation")
    
    llm_service = LLMService()
    
    candidates = [
        {
            "hts_number": s["hsCode"],
            "description": s["description"],
            "similarity": s["confidenceScore"]
        }
        for s in state["suggestions"]
    ]
    
    reasoning_map = await llm_service.generate_reasoning(
        product_name=state["product_name"],
        product_description=state["product_description"],
        candidates=candidates
    )
    
    for suggestion in state["suggestions"]:
        suggestion["reasoning"] = reasoning_map.get(
            suggestion["hsCode"], 
            "Vector similarity-based match"
        )
    
    logger.info("LLM reasoning generation completed")
    return state

async def finalize_node(state: WorkflowState) -> WorkflowState:
    """최종 정렬 및 정리"""
    state["suggestions"].sort(key=lambda x: x["confidenceScore"], reverse=True)
    logger.info("Workflow finalized")
    return state

def create_workflow():
    """LangGraph 워크플로우 생성"""
    workflow = StateGraph(WorkflowState)
    
    workflow.add_node("vector_search", vector_search_node)
    workflow.add_node("llm_reasoning", llm_reasoning_node)
    workflow.add_node("finalize", finalize_node)
    
    workflow.add_edge("vector_search", "llm_reasoning")
    workflow.add_edge("llm_reasoning", "finalize")
    workflow.add_edge("finalize", END)
    
    workflow.set_entry_point("vector_search")
    
    return workflow.compile()

workflow = create_workflow()

async def run_hs_analysis_workflow(
    product_name: str, 
    product_description: str, 
    origin_country: str = "KOR"
) -> HsCodeAnalysisResponse:
    """HS 코드 분석 워크플로우 실행"""
    
    initial_state: WorkflowState = {
        "product_name": product_name,
        "product_description": product_description,
        "origin_country": origin_country,
        "suggestions": []
    }
    
    # ainvoke 사용 (비동기)
    result = await workflow.ainvoke(initial_state)
    
    suggestions = [
        HsCodeSuggestion(
            hsCode=s["hsCode"],
            description=s["description"],
            confidenceScore=s["confidenceScore"],
            reasoning=s["reasoning"],
            usTariffRate=s["usTariffRate"]
        )
        for s in result["suggestions"]
    ]
    
    return HsCodeAnalysisResponse(
        analysisSessionId=f"graph_{uuid.uuid4().hex[:8]}",
        suggestions=suggestions
    )