from langgraph.graph import StateGraph, END
from typing import TypedDict, List, Dict, Any
from vector_service import VectorService
from llm_service import LLMService
from models import HsCodeAnalysisResponse, HsCodeSuggestion, HierarchicalDescription
import uuid
import logging
import asyncio
import time

logger = logging.getLogger(__name__)

# 상수 정의
RECIPROCAL_TARIFF_RATE = 0.15  # 2025년 8월 7일부터 적용되는 미국 상호관세율 (15%)
DEFAULT_TOP_K = 5  # 벡터 검색 후보 수
FINAL_TOP_K = 3    # 최종 반환 결과 수

def _enhance_cosmetic_food_query(product_name: str, product_description: str) -> str:
    """화장품/식품 특화 검색 쿼리 강화"""
    
    # 기본 쿼리
    base_query = f"{product_name} | {product_description}"
    
    # 화장품 관련 키워드
    cosmetic_keywords = [
        'cosmetic', 'beauty', 'skincare', 'makeup', 'cream', 'lotion', 'serum',
        'foundation', 'lipstick', 'mascara', 'perfume', 'shampoo', 'conditioner',
        'soap', 'cleanser', 'moisturizer', 'sunscreen', 'toner', 'essence',
        '화장품', '미용', '스킨케어', '메이크업', '크림', '로션', '세럼',
        '파운데이션', '립스틱', '마스카라', '향수', '샴푸', '컨디셔너',
        '비누', '클렌저', '보습제', '자외선차단제', '토너', '에센스'
    ]
    
    # 식품 관련 키워드
    food_keywords = [
        'food', 'beverage', 'drink', 'snack', 'supplement', 'vitamin', 'protein',
        'tea', 'coffee', 'juice', 'water', 'milk', 'yogurt', 'cheese', 'meat',
        'fish', 'vegetable', 'fruit', 'grain', 'cereal', 'bread', 'candy', 'chocolate',
        '식품', '음료', '음식', '간식', '보충제', '비타민', '단백질',
        '차', '커피', '주스', '물', '우유', '요구르트', '치즈', '고기',
        '생선', '야채', '과일', '곡물', '시리얼', '빵', '사탕', '초콜릿'
    ]
    
    # 화장품/식품 특성 키워드 추출
    description_lower = (product_name + " " + product_description).lower()
    
    found_cosmetic = [kw for kw in cosmetic_keywords if kw.lower() in description_lower]
    found_food = [kw for kw in food_keywords if kw.lower() in description_lower]
    
    enhanced_parts = [base_query]
    
    # 화장품 관련 강화
    if found_cosmetic:
        enhanced_parts.append(f"cosmetic beauty skincare: {' '.join(found_cosmetic[:3])}")
        # 화장품 특화 HS 코드 힌트 추가
        enhanced_parts.append("chapter 33 cosmetic preparations")
    
    # 식품 관련 강화  
    if found_food:
        enhanced_parts.append(f"food beverage edible: {' '.join(found_food[:3])}")
        # 식품 특화 HS 코드 힌트 추가
        enhanced_parts.append("chapter 04 19 20 21 22 food preparations")
    
    # 성분/재료 키워드 추가
    ingredient_keywords = [
        'organic', 'natural', 'extract', 'oil', 'powder', 'liquid', 'gel',
        '유기농', '천연', '추출물', '오일', '파우더', '액체', '젤'
    ]
    
    found_ingredients = [kw for kw in ingredient_keywords if kw.lower() in description_lower]
    if found_ingredients:
        enhanced_parts.append(f"ingredients: {' '.join(found_ingredients[:2])}")
    
    return " | ".join(enhanced_parts)

class WorkflowState(TypedDict):
    product_name: str
    product_description: str
    origin_country: str
    suggestions: List[Dict[str, Any]]

def _generate_tariff_reasoning(base_tariff_rate: float, reciprocal_tariff_rate: float, origin_country: str = "KOR") -> str:
    """관세율 적용 근거 생성"""
    if base_tariff_rate == 0 and reciprocal_tariff_rate > 0:
        return f"기본 관세율은 0%입니다. 그러나 2025년 8월 7일부터 발효된 미국 상호관세 정책에 따라 {reciprocal_tariff_rate * 100:.1f}%의 추가 관세가 부과되어, 최종 관세율은 {reciprocal_tariff_rate * 100:.1f}%가 적용됩니다."
    elif reciprocal_tariff_rate > 0:
        total = base_tariff_rate + reciprocal_tariff_rate
        return f"기본 관세율 {base_tariff_rate * 100:.1f}%가 적용되며, 2025년 8월 7일부터 발효된 미국 상호관세 정책에 따라 {reciprocal_tariff_rate * 100:.1f}%의 추가 관세가 부과됩니다. 따라서 최종 관세율은 {total * 100:.1f}%입니다."
    elif base_tariff_rate == 0:
        return f"기본 관세율이 0% 적용됩니다."
    else:
        return f"현재 기본 관세율 {base_tariff_rate * 100:.1f}%가 적용됩니다."

async def vector_search_node(state: WorkflowState) -> WorkflowState:
    """벡터 검색으로 후보 찾기 (화장품/식품 특화 쿼리)"""
    start_time = time.time()
    logger.info("🔍 Starting vector search...")
    
    vector_service = VectorService()
    
    # 화장품/식품 특화 강화 쿼리 생성
    enhanced_query = _enhance_cosmetic_food_query(
        state['product_name'], 
        state['product_description']
    )
    
    logger.info(f"📝 Enhanced query: {enhanced_query}")
    
    # 벡터 검색 실행
    candidates = await asyncio.to_thread(
        vector_service.search_similar, enhanced_query, top_k=DEFAULT_TOP_K
    )
    
    suggestions = []
    for i, candidate in enumerate(candidates):
        # 관세율 계산
        base_tariff_rate = candidate["final_rate_for_korea"]
        total_tariff_rate = base_tariff_rate + RECIPROCAL_TARIFF_RATE
        
        # 관세율 적용 근거 생성
        tariff_reasoning = _generate_tariff_reasoning(
            base_tariff_rate, 
            RECIPROCAL_TARIFF_RATE, 
            state["origin_country"]
        )
        
        suggestions.append({
            "hsCode": candidate["hts_number"],
            "description": candidate["description"],
            "confidenceScore": candidate["similarity"],
            "usTariffRate": total_tariff_rate,
            "baseTariffRate": base_tariff_rate,
            "reciprocalTariffRate": RECIPROCAL_TARIFF_RATE,
            "reasoning": "",  # LLM에서 생성
            "tariffReasoning": tariff_reasoning,
            "hierarchicalDescription": candidate.get("hierarchical_description", {})
        })
        
        # 로깅
        logger.info(f"  #{i+1}: {candidate['hts_number']} (score: {candidate['similarity']:.3f}, base: {base_tariff_rate:.1%}, reciprocal: +{RECIPROCAL_TARIFF_RATE:.1%}, total: {total_tariff_rate:.1%})")
    
    state["suggestions"] = suggestions
    
    elapsed_time = time.time() - start_time
    logger.info(f"✅ Vector search completed: {len(suggestions)} candidates in {elapsed_time:.2f}s")
    
    return state

async def llm_reasoning_node(state: WorkflowState) -> WorkflowState:
    """LLM으로 추천 이유 생성"""
    start_time = time.time()
    logger.info("🤖 Starting LLM reasoning generation...")
    
    # VectorService 인스턴스 재사용
    vector_service = VectorService() if not hasattr(llm_reasoning_node, '_vector_service') else llm_reasoning_node._vector_service
    llm_reasoning_node._vector_service = vector_service
    
    llm_service = LLMService(vector_service=vector_service)
    
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
        candidates=candidates,
        origin_country=state["origin_country"]
    )
    
    for suggestion in state["suggestions"]:
        suggestion["reasoning"] = reasoning_map.get(
            suggestion["hsCode"], 
            "벡터 유사도 기반으로 선정된 HS 코드입니다."
        )
    
    elapsed_time = time.time() - start_time
    logger.info(f"✅ LLM reasoning completed in {elapsed_time:.2f}s")
    return state

async def finalize_node(state: WorkflowState) -> WorkflowState:
    """최종 정렬 및 Top N 선별"""
    start_time = time.time()
    logger.info("🎯 Finalizing results...")
    
    # 신뢰도 순으로 정렬
    state["suggestions"].sort(key=lambda x: x["confidenceScore"], reverse=True)
    
    # 최고 정확도 Top N만 선별
    state["suggestions"] = state["suggestions"][:FINAL_TOP_K]
    
    elapsed_time = time.time() - start_time
    logger.info(f"✅ Finalized Top {FINAL_TOP_K} results in {elapsed_time:.3f}s")
    
    # 최종 결과 로깅 (계층적 설명 포함)
    for i, s in enumerate(state["suggestions"]):
        logger.info(f"  🏆 #{i+1}: {s['hsCode']} (confidence: {s['confidenceScore']:.3f}, total tariff: {s['usTariffRate']:.1%} = base {s.get('baseTariffRate', 0):.1%} + reciprocal 15%)")
        
        # 계층적 설명 로깅
        hierarchical_desc = s.get('hierarchicalDescription', {})
        if hierarchical_desc and not hierarchical_desc.get('error'):
            logger.info(f"    📋 Combined: {hierarchical_desc.get('combined_description', 'N/A')}")
            logger.info(f"    📋 Heading: {hierarchical_desc.get('heading', 'N/A')}")
            logger.info(f"    📋 Subheading: {hierarchical_desc.get('subheading', 'N/A')}")
            logger.info(f"    📋 Tertiary: {hierarchical_desc.get('tertiary', 'N/A')}")
    
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
    
    # 전체 분석 시작 시간
    total_start_time = time.time()
    session_id = f"graph_{uuid.uuid4().hex[:8]}"
    
    logger.info("="*60)
    logger.info(f"🚀 HS CODE ANALYSIS STARTED - Session: {session_id}")
    logger.info(f"📦 Product: {product_name}")
    logger.info(f"📝 Description: {product_description}")
    logger.info(f"🌍 Origin: {origin_country}")
    logger.info("="*60)
    
    initial_state: WorkflowState = {
        "product_name": product_name,
        "product_description": product_description,
        "origin_country": origin_country,
        "suggestions": []
    }
    
    try:
        # ainvoke 사용 (비동기)
        result = await workflow.ainvoke(initial_state)
        
        suggestions = []
        for s in result["suggestions"]:
            # 계층적 설명 처리
            hierarchical_desc = None
            if s.get("hierarchicalDescription") and not s["hierarchicalDescription"].get("error"):
                hierarchical_desc = HierarchicalDescription(
                    heading=s["hierarchicalDescription"]["heading"],
                    subheading=s["hierarchicalDescription"]["subheading"],
                    tertiary=s["hierarchicalDescription"]["tertiary"],
                    combinedDescription=s["hierarchicalDescription"]["combined_description"],
                    headingCode=s["hierarchicalDescription"]["heading_code"],
                    subheadingCode=s["hierarchicalDescription"]["subheading_code"],
                    tertiaryCode=s["hierarchicalDescription"]["tertiary_code"]
                )
            
            # USITC URL 생성 (점 제거)
            hs_code_for_url = s["hsCode"].replace('.', '')
            usitc_url = f"https://hts.usitc.gov/search?query={hs_code_for_url}"
            
            suggestions.append(HsCodeSuggestion(
                hsCode=s["hsCode"],
                description=s["description"],
                confidenceScore=s["confidenceScore"],
                reasoning=s["reasoning"],
                tariffReasoning=s.get("tariffReasoning", ""),
                usTariffRate=s["usTariffRate"],
                baseTariffRate=s.get("baseTariffRate"),
                reciprocalTariffRate=s.get("reciprocalTariffRate"),
                usitcUrl=usitc_url,
                hierarchicalDescription=hierarchical_desc
            ))
        
        # 전체 분석 완료 시간
        total_elapsed_time = time.time() - total_start_time
        
        logger.info("="*60)
        logger.info(f"🎉 HS CODE ANALYSIS COMPLETED - Session: {session_id}")
        logger.info(f"⏱️  Total Analysis Time: {total_elapsed_time:.2f} seconds")
        logger.info(f"📊 Final Results: {len(suggestions)} HS codes")
        logger.info("="*60)
        
        return HsCodeAnalysisResponse(
            analysisSessionId=session_id,
            suggestions=suggestions
        )
        
    except Exception as e:
        total_elapsed_time = time.time() - total_start_time
        logger.error("="*60)
        logger.error(f"❌ HS CODE ANALYSIS FAILED - Session: {session_id}")
        logger.error(f"⏱️  Failed after: {total_elapsed_time:.2f} seconds")
        logger.error(f"🚨 Error: {str(e)}")
        logger.error("="*60)
        raise