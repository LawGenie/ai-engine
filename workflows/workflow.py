from langgraph import StateGraph
from langchain.tools import tool
from typing import Dict, Any, List
from app.services.hs_code_service import HSCodeService
from app.services.tariff_service import TariffService
from app.services.requirements_service import RequirementsService
from app.services.precedents_service import PrecedentsService

# 상태 정의
class ProductAnalysisState:
    def __init__(self):
        self.product_name: str = ""
        self.description: str = ""
        self.hs_code: str = ""
        self.tariff_analysis: Dict[str, Any] = {}
        self.requirements_analysis: Dict[str, Any] = {}
        self.precedents_analysis: Dict[str, Any] = {}
        self.final_result: Dict[str, Any] = {}

# Tools 정의
@tool
def recommend_hs_code_tool(product_name: str) -> str:
    """HS코드 추천 도구"""
    service = HSCodeService()
    result = service.recommend(product_name)
    return f"추천 HS코드: {result.recommended_codes[0]['code']} (신뢰도: {result.confidence})"

@tool
def calculate_tariff_tool(hs_code: str) -> str:
    """관세 계산 도구"""
    service = TariffService()
    result = service.calculate(hs_code)
    return f"관세율: {result['predicted_rate']}% (리스크: {result['risk_level']})"

@tool
def analyze_requirements_tool(hs_code: str) -> str:
    """요구사항 분석 도구"""
    service = RequirementsService()
    result = service.analyze(hs_code)
    return f"요구사항: {len(result['requirements'])}개 (준수도: {result['compliance_score']}%)"

@tool
def analyze_precedents_tool(hs_code: str) -> str:
    """판례 분석 도구"""
    service = PrecedentsService()
    result = service.analyze(hs_code)
    return f"통관 성공률: {result['success_rate']*100}% (판례: {result['precedents']}개)"

# Nodes 정의
def hs_code_analysis_node(state: ProductAnalysisState) -> Dict[str, Any]:
    """HS코드 분석 노드"""
    try:
        # Tool 호출
        hs_code_result = recommend_hs_code_tool(state.product_name)
        
        # 결과 파싱 (간단한 예시)
        recommended_code = "8471.30.01"  # 실제로는 결과에서 추출
        
        return {
            "hs_code": recommended_code,
            "hs_code_analysis": hs_code_result
        }
    except Exception as e:
        return {
            "hs_code": "9999.99.99",
            "hs_code_analysis": f"HS코드 추천 실패: {str(e)}"
        }

def tariff_analysis_node(state: ProductAnalysisState) -> Dict[str, Any]:
    """관세 분석 노드"""
    try:
        # Tool 호출
        tariff_result = calculate_tariff_tool(state.hs_code)
        
        return {
            "tariff_analysis": tariff_result
        }
    except Exception as e:
        return {
            "tariff_analysis": f"관세 분석 실패: {str(e)}"
        }

def requirements_analysis_node(state: ProductAnalysisState) -> Dict[str, Any]:
    """요구사항 분석 노드"""
    try:
        # Tool 호출
        requirements_result = analyze_requirements_tool(state.hs_code)
        
        return {
            "requirements_analysis": requirements_result
        }
    except Exception as e:
        return {
            "requirements_analysis": f"요구사항 분석 실패: {str(e)}"
        }

def precedents_analysis_node(state: ProductAnalysisState) -> Dict[str, Any]:
    """판례 분석 노드"""
    try:
        # Tool 호출
        precedents_result = analyze_precedents_tool(state.hs_code)
        
        return {
            "precedents_analysis": precedents_result
        }
    except Exception as e:
        return {
            "precedents_analysis": f"판례 분석 실패: {str(e)}"
        }

def final_integration_node(state: ProductAnalysisState) -> Dict[str, Any]:
    """최종 통합 노드"""
    try:
        # 모든 분석 결과 통합
        final_result = {
            "product_name": state.product_name,
            "hs_code": state.hs_code,
            "tariff_analysis": state.tariff_analysis,
            "requirements_analysis": state.requirements_analysis,
            "precedents_analysis": state.precedents_analysis,
            "overall_risk": "medium",  # 실제로는 계산
            "recommendation": "수출 가능성 높음"  # 실제로는 계산
        }
        
        return {
            "final_result": final_result
        }
    except Exception as e:
        return {
            "final_result": {"error": f"최종 통합 실패: {str(e)}"}
        }

# 조건부 엣지 함수
def should_continue_analysis(state: ProductAnalysisState) -> str:
    """분석 계속 여부 결정"""
    if state.hs_code and state.hs_code != "9999.99.99":
        return "continue"
    else:
        return "skip"

# 워크플로우 생성
def create_analysis_workflow():
    """AI 분석 워크플로우 생성"""
    workflow = StateGraph(ProductAnalysisState)
    
    # 노드 추가
    workflow.add_node("hs_code_analysis", hs_code_analysis_node)
    workflow.add_node("tariff_analysis", tariff_analysis_node)
    workflow.add_node("requirements_analysis", requirements_analysis_node)
    workflow.add_node("precedents_analysis", precedents_analysis_node)
    workflow.add_node("final_integration", final_integration_node)
    
    # 엣지 추가
    workflow.add_edge("hs_code_analysis", "tariff_analysis")
    workflow.add_edge("hs_code_analysis", "requirements_analysis")
    workflow.add_edge("hs_code_analysis", "precedents_analysis")
    
    # 조건부 엣지
    workflow.add_conditional_edges(
        "hs_code_analysis",
        should_continue_analysis,
        {
            "continue": "tariff_analysis",
            "skip": "final_integration"
        }
    )
    
    # 병렬 실행 후 통합
    workflow.add_edge("tariff_analysis", "final_integration")
    workflow.add_edge("requirements_analysis", "final_integration")
    workflow.add_edge("precedents_analysis", "final_integration")
    
    return workflow.compile()

# 워크플로우 인스턴스 생성
analysis_workflow = create_analysis_workflow()

# 워크플로우 실행 함수
async def run_analysis_workflow(product_name: str, description: str = "") -> Dict[str, Any]:
    """분석 워크플로우 실행"""
    try:
        # 초기 상태 설정
        initial_state = ProductAnalysisState()
        initial_state.product_name = product_name
        initial_state.description = description
        
        # 워크플로우 실행
        result = await analysis_workflow.ainvoke(initial_state)
        
        return result.final_result
        
    except Exception as e:
        return {"error": f"워크플로우 실행 실패: {str(e)}"}
