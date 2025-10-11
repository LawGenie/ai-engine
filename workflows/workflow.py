"""
LangGraph 워크플로우 - 실제 precedents-analysis API 호출
"""

from langgraph.graph import StateGraph, END
from langchain.tools import tool
from typing import Dict, Any, List, TypedDict
import requests
import json
from tax_via_hs.query_service import HTSQueryService

# TypedDict로 상태 정의
class ProductAnalysisState(TypedDict):
    product_name: str
    description: str
    suggestions: List[Dict[str, Any]]
    final_result: Dict[str, Any]

# 동기 방식으로 precedents-analysis API 호출
def call_precedents_api_sync(hs_code: str, product_name: str = "", product_description: str = "") -> Dict[str, Any]:
    """동기 방식으로 precedents-analysis API를 호출하는 함수"""
    try:
        # precedents-analysis API 엔드포인트
        api_url = "http://localhost:8000/analyze-precedents"
        
        # 요청 데이터 구성
        request_data = {
            "product_id": f"PROD-{int(__import__('time').time())}",
            "product_name": product_name or f"HS코드 {hs_code} 상품",
            "description": product_description or f"HS코드 {hs_code}에 해당하는 상품",
            "hs_code": hs_code,
            "origin_country": "KOR",
            "price": 0.0,
            "fob_price": 0.0
        }
        
        print(f"🔍 [PRECEDENTS] 실제 API 호출 시작")
        print(f"  📋 HS코드: {hs_code}")
        print(f"  📦 상품명: {product_name}")
        print(f"  🌐 API URL: {api_url}")
        
        # HTTP 요청 (동기)
        response = requests.post(api_url, json=request_data, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            print(f"  ✅ API 호출 성공")
            print(f"  📊 성공 사례: {len(result.get('success_cases', []))}개")
            print(f"  📊 실패 사례: {len(result.get('failure_cases', []))}개")
            print(f"  📊 신뢰도: {result.get('confidence_score', 0)}")
            
            return result
        else:
            print(f"  ❌ API 호출 실패: {response.status_code}")
            print(f"  📄 오류 내용: {response.text}")
            
            # 실패 시 기본값 반환
            return {
                "success_cases": [],
                "failure_cases": [],
                "actionable_insights": ["API 호출 실패로 인한 분석 불가"],
                "risk_factors": ["데이터 수집 실패"],
                "recommended_action": "수동으로 판례 조사 필요",
                "confidence_score": 0.0,
                "is_valid": False
            }
            
    except Exception as e:
        print(f"  ❌ 예외 발생: {str(e)}")
        
        # 예외 시 기본값 반환
        return {
            "success_cases": [],
            "failure_cases": [],
            "actionable_insights": [f"분석 중 오류 발생: {str(e)}"],
            "risk_factors": ["시스템 오류"],
            "recommended_action": "관세사 상담 권장",
            "confidence_score": 0.0,
            "is_valid": False
        }

# Tools 정의 (기존 가짜 서비스들)
@tool
def recommend_hs_code_tool(product_name: str) -> str:
    """HS코드 추천 도구"""
    # 기존 가짜 서비스 호출 (나중에 실제 API로 교체)
    return f"추천 HS코드: 3304.99.50.00 (신뢰도: 0.85)"

@tool
def calculate_tariff_tool(hs_code: str) -> str:
    """관세 계산 도구"""
    # 기존 가짜 서비스 호출 (나중에 실제 API로 교체)
    return f"관세율: 0.0% (리스크: 낮음)"

@tool
def analyze_requirements_tool(hs_code: str) -> str:
    """요구사항 분석 도구"""
    # 기존 가짜 서비스 호출 (나중에 실제 API로 교체)
    return f"요구사항: 5개 (준수도: 85%)"

# 실제 precedents-analysis API를 호출하는 도구
@tool
def analyze_precedents_tool_real(hs_code: str, product_name: str = "", product_description: str = "") -> str:
    """실제 precedents-analysis API를 호출하는 판례 분석 도구"""
    try:
        # 실제 API 호출
        result = call_precedents_api_sync(hs_code, product_name, product_description)
        
        # 결과를 문자열로 변환
        success_count = len(result.get('success_cases', []))
        failure_count = len(result.get('failure_cases', []))
        confidence = result.get('confidence_score', 0.0)
        is_valid = result.get('is_valid', False)
        
        return f"실제 판례 분석 완료 - 성공사례: {success_count}개, 실패사례: {failure_count}개, 신뢰도: {confidence}, 유효성: {is_valid}"
        
    except Exception as e:
        return f"판례 분석 실패: {str(e)}"

# Nodes 정의
def hs_code_similarity_node(state: ProductAnalysisState) -> ProductAnalysisState:
    """FAISS 유사도 기반 HS코드 후보 3개 도출 및 관세율 부가"""
    try:
        print(f"\n🔍 [NODE] 유사도 검색 시작")
        print(f"  📦 상품명: {state['product_name']}")
        print(f"  📝 설명: {state['description'][:120]}...")

        service = HTSQueryService()
        top = service.search_by_description(f"{state['product_name']} | {state['description']}", top_k=3)
        suggestions: List[Dict[str, Any]] = []
        for rec in top:
            hs = rec.get("hts_number", "")
            rate = service.get_adjusted_rate(hs) or 0.0
            suggestions.append({
                "hsCode": hs,
                "description": rec.get("description", ""),
                "confidenceScore": float(rec.get("similarity", 0.0)),
                "reasoning": "Vector similarity match from HTS corpus",
                "usTariffRate": float(rate)
            })
        print(f"  ✅ 유사도 검색 완료: {len(suggestions)}개")
        state["suggestions"] = suggestions
        return state
    except Exception as e:
        print(f"  ❌ 유사도 검색 실패: {str(e)}")
        state["suggestions"] = []
        return state

def finalize_node(state: ProductAnalysisState) -> ProductAnalysisState:
    """최종 결과 구성 노드"""
    try:
        print(f"\n🔍 [NODE] 최종 결과 구성")
        state["final_result"] = {
            "suggestions": state.get("suggestions", []),
            "analysisSessionId": f"graph_{__import__('time').time_ns()}"
        }
        return state
    except Exception as e:
        state["final_result"] = {"suggestions": [], "error": str(e)}
        return state

def requirements_analysis_node(state: ProductAnalysisState) -> ProductAnalysisState:
    return state

def precedents_analysis_node(state: ProductAnalysisState) -> ProductAnalysisState:
    return state

def final_integration_node(state: ProductAnalysisState) -> ProductAnalysisState:
    return finalize_node(state)

# 워크플로우 생성
def create_analysis_workflow():
    """LangGraph 워크플로우 생성"""
    workflow = StateGraph(ProductAnalysisState)
    
    # 노드 추가
    workflow.add_node("hs_code_similarity", hs_code_similarity_node)
    workflow.add_node("requirements_analysis", requirements_analysis_node)
    workflow.add_node("precedents_analysis", precedents_analysis_node)
    workflow.add_node("final_integration", final_integration_node)
    
    # 엣지 추가 (순차 실행)
    workflow.add_edge("hs_code_similarity", "requirements_analysis")
    workflow.add_edge("requirements_analysis", "precedents_analysis")
    workflow.add_edge("precedents_analysis", "final_integration")
    workflow.add_edge("final_integration", END)
    
    # 시작점 설정
    workflow.set_entry_point("hs_code_similarity")
    
    return workflow.compile()

# 워크플로우 인스턴스 생성
analysis_workflow = create_analysis_workflow()

# 워크플로우 실행 함수
def run_analysis_workflow(product_name: str, description: str = "") -> Dict[str, Any]:
    """분석 워크플로우 실행"""
    try:
        # 초기 상태 설정
        initial_state: ProductAnalysisState = {
            "product_name": product_name,
            "description": description,
            "suggestions": [],
            "final_result": {}
        }
        
        print(f"📦 워크플로우 시작: {product_name}")
        print(f"📋 상품 설명: {description}")
        
        # 워크플로우 실행
        result = analysis_workflow.invoke(initial_state)
        
        return result.get("final_result", {})
        
    except Exception as e:
        return {"error": f"워크플로우 실행 실패: {str(e)}"}

# 테스트 함수
def test_workflow():
    """워크플로우 테스트"""
    print("🧪 LangGraph 워크플로우 테스트")
    print("=" * 50)
    
    result = run_analysis_workflow("화장품 세트", "립스틱과 파우더가 포함된 화장품 세트")
    
    print(f"\n✅ 워크플로우 실행 완료")
    print(f"📊 최종 결과:")
    print(f"  - HS코드: {result.get('hs_code', 'N/A')}")
    print(f"  - 관세 분석: {result.get('tariff_analysis', 'N/A')}")
    print(f"  - 요구사항 분석: {result.get('requirements_analysis', 'N/A')}")
    
    # 판례 분석 결과 상세 출력
    precedents = result.get('precedents_analysis', {})
    if isinstance(precedents, dict):
        print(f"  - 판례 분석:")
        print(f"    * 성공 사례: {len(precedents.get('success_cases', []))}개")
        print(f"    * 실패 사례: {len(precedents.get('failure_cases', []))}개")
        print(f"    * 신뢰도: {precedents.get('confidence_score', 0)}")
        print(f"    * 유효성: {precedents.get('is_valid', False)}")
        
        # 상세 내용 출력
        if precedents.get('success_cases'):
            print(f"\n📈 성공 사례:")
            for i, case in enumerate(precedents['success_cases'][:3], 1):
                print(f"  {i}. {case}")
        
        if precedents.get('failure_cases'):
            print(f"\n📉 실패 사례:")
            for i, case in enumerate(precedents['failure_cases'][:3], 1):
                print(f"  {i}. {case}")
        
        if precedents.get('actionable_insights'):
            print(f"\n💡 실행 가능한 인사이트:")
            for i, insight in enumerate(precedents['actionable_insights'][:3], 1):
                print(f"  {i}. {insight}")
        
        if precedents.get('risk_factors'):
            print(f"\n⚠️ 위험 요소:")
            for i, risk in enumerate(precedents['risk_factors'][:3], 1):
                print(f"  {i}. {risk}")
        
        print(f"\n🎯 권장 조치: {precedents.get('recommended_action', 'N/A')}")

if __name__ == "__main__":
    test_workflow()
