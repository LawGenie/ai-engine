#!/usr/bin/env python3
"""
스마트 요구사항 분석 워크플로우
- HS 코드 기반 자동 기관 선택
- 다중 API 병렬 호출
- LangGraph 워크플로우 통합
- 실시간 성공률 기반 우선순위 조정
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from typing_extensions import Annotated

from .government_agencies_db import agencies_db, get_agencies_for_product
from .comprehensive_api_manager import comprehensive_api_manager

from typing import TypedDict

class RequirementsAnalysisState(TypedDict):
    """요구사항 분석 상태"""
    hs_code: str
    product_name: str
    product_description: str
    selected_agencies: List[Dict[str, Any]]
    api_results: Dict[str, Any]
    requirements: Dict[str, Any]
    confidence_score: float
    error_messages: List[str]
    processing_steps: List[str]

class SmartRequirementsWorkflow:
    """스마트 요구사항 분석 워크플로우"""
    
    def __init__(self):
        self.workflow = self._build_workflow()
        self.app = self.workflow.compile()
    
    def _build_workflow(self) -> StateGraph:
        """워크플로우 그래프 구축"""
        workflow = StateGraph(RequirementsAnalysisState)
        
        # 노드 추가
        workflow.add_node("analyze_product", self._analyze_product)
        workflow.add_node("select_agencies", self._select_agencies)
        workflow.add_node("call_apis", self._call_apis)
        workflow.add_node("process_results", self._process_results)
        workflow.add_node("generate_response", self._generate_response)
        
        # 엣지 추가 (단순한 순차 실행)
        workflow.add_edge("analyze_product", "select_agencies")
        workflow.add_edge("select_agencies", "call_apis")
        workflow.add_edge("call_apis", "process_results")
        workflow.add_edge("process_results", "generate_response")
        workflow.add_edge("generate_response", END)
        
        # 시작점 설정
        workflow.set_entry_point("analyze_product")
        
        return workflow
    
    async def _analyze_product(self, state: RequirementsAnalysisState) -> RequirementsAnalysisState:
        """상품 분석"""
        print(f"🔍 상품 분석: {state['product_name']} (HS: {state['hs_code']})")
        
        try:
            # HS 코드 유효성 검사
            if not state['hs_code'] or len(state['hs_code']) < 6:
                state['error_messages'].append("유효하지 않은 HS 코드")
                return state
            
            # 상품 카테고리 추출
            hs_chapter = state['hs_code'][:2]
            category = self._get_category_from_hs_code(hs_chapter)
            
            state['processing_steps'].append(f"상품 분석 완료: 카테고리 {category}")
            print(f"✅ 상품 분석 완료: {category}")
            
        except Exception as e:
            state['error_messages'].append(f"상품 분석 오류: {str(e)}")
            print(f"❌ 상품 분석 오류: {e}")
        
        return state
    
    async def _select_agencies(self, state: RequirementsAnalysisState) -> RequirementsAnalysisState:
        """적합한 기관 선택"""
        print(f"🏛️ 기관 선택: {state['hs_code']}")
        
        try:
            # HS 코드에 적합한 기관들 조회
            agencies = get_agencies_for_product(state['hs_code'], state['product_name'])
            
            if not agencies:
                state['error_messages'].append("적합한 기관을 찾을 수 없음")
                return state
            
            # 우선순위 기반으로 상위 5개 기관 선택
            selected_agencies = agencies[:5]
            state['selected_agencies'] = selected_agencies
            
            state['processing_steps'].append(f"기관 선택 완료: {len(selected_agencies)}개 기관")
            print(f"✅ 기관 선택 완료: {len(selected_agencies)}개")
            
            for agency in selected_agencies:
                print(f"  - {agency['name']} (우선순위: {agency['mapping_priority']})")
            
        except Exception as e:
            state['error_messages'].append(f"기관 선택 오류: {str(e)}")
            print(f"❌ 기관 선택 오류: {e}")
        
        return state
    
    async def _call_apis(self, state: RequirementsAnalysisState) -> RequirementsAnalysisState:
        """API 호출"""
        print(f"📡 API 호출: {len(state['selected_agencies'])}개 기관")
        
        try:
            # 각 기관별로 API 호출
            api_results = {}
            
            for agency in state['selected_agencies']:
                agency_id = agency['agency_id']
                print(f"📡 {agency['name']} API 호출 중...")
                
                try:
                    # 포괄적 API 매니저를 통한 검색
                    result = await comprehensive_api_manager.search_requirements_comprehensive(
                        state['hs_code'], 
                        state['product_name']
                    )
                    
                    api_results[agency_id] = {
                        "agency_info": agency,
                        "search_result": result,
                        "success": result["total_requirements"] > 0,
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    if result["total_requirements"] > 0:
                        print(f"✅ {agency['name']}: {result['total_requirements']}개 요구사항 발견")
                    else:
                        print(f"⚠️ {agency['name']}: 요구사항 없음")
                        
                except Exception as e:
                    api_results[agency_id] = {
                        "agency_info": agency,
                        "error": str(e),
                        "success": False,
                        "timestamp": datetime.now().isoformat()
                    }
                    print(f"❌ {agency['name']}: API 호출 실패 - {e}")
            
            state['api_results'] = api_results
            state['processing_steps'].append(f"API 호출 완료: {len(api_results)}개 기관")
            
        except Exception as e:
            state['error_messages'].append(f"API 호출 오류: {str(e)}")
            print(f"❌ API 호출 오류: {e}")
        
        return state
    
    async def _process_results(self, state: RequirementsAnalysisState) -> RequirementsAnalysisState:
        """결과 처리 및 통합"""
        print("🔄 결과 처리 중...")
        
        try:
            # API 결과 통합
            all_requirements = {
                "certifications": [],
                "documents": [],
                "labeling": [],
                "sources": [],
                "metadata": {
                    "total_agencies_searched": len(state['api_results']),
                    "successful_agencies": sum(1 for r in state['api_results'].values() if r.get("success", False)),
                    "processing_time": datetime.now().isoformat(),
                    "hs_code": state['hs_code'],
                    "product_name": state['product_name']
                }
            }
            
            # 각 기관의 결과 통합
            for agency_id, result in state['api_results'].items():
                if result.get("success", False) and "search_result" in result:
                    search_result = result["search_result"]
                    
                    # 인증요건 통합
                    for api in search_result.get("working_apis", []):
                        all_requirements["certifications"].append({
                            "name": f"{api['agency']} 인증",
                            "agency": api["agency"],
                            "required": True,
                            "description": f"{api['agency']}에서 요구하는 인증",
                            "url": api["url"],
                            "source": "api"
                        })
                    
                    # 서류요건 통합
                    all_requirements["documents"].append({
                        "name": f"{result['agency_info']['name']} 서류",
                        "required": True,
                        "description": f"{result['agency_info']['name']}에서 요구하는 서류",
                        "url": result['agency_info']['website'],
                        "source": "api"
                    })
                    
                    # 출처 정보 추가
                    all_requirements["sources"].append({
                        "title": f"{result['agency_info']['name']} API",
                        "url": result['agency_info']['website'],
                        "type": "공식 API",
                        "relevance": "high",
                        "agency": result['agency_info']['short_name']
                    })
            
            # 중복 제거
            all_requirements["certifications"] = self._deduplicate_items(all_requirements["certifications"])
            all_requirements["documents"] = self._deduplicate_items(all_requirements["documents"])
            all_requirements["sources"] = self._deduplicate_items(all_requirements["sources"])
            
            # 신뢰도 점수 계산
            success_rate = all_requirements["metadata"]["successful_agencies"] / all_requirements["metadata"]["total_agencies_searched"] if all_requirements["metadata"]["total_agencies_searched"] > 0 else 0
            state['confidence_score'] = success_rate
            
            state['requirements'] = all_requirements
            state['processing_steps'].append("결과 처리 완료")
            
            print(f"✅ 결과 처리 완료: 신뢰도 {state['confidence_score']:.2%}")
            
        except Exception as e:
            state['error_messages'].append(f"결과 처리 오류: {str(e)}")
            print(f"❌ 결과 처리 오류: {e}")
        
        return state
    
    async def _generate_response(self, state: RequirementsAnalysisState) -> RequirementsAnalysisState:
        """최종 응답 생성"""
        print("📝 최종 응답 생성 중...")
        
        try:
            # 응답 구조 생성
            response = {
                "answer": f"HS코드 {state['hs_code']} ({state['product_name']})에 대한 미국 수입요건 분석 결과입니다.",
                "reasoning": f"총 {len(state['selected_agencies'])}개 기관에서 검색하여 {state['requirements']['metadata']['successful_agencies']}개 기관에서 요구사항을 발견했습니다.",
                "requirements": state['requirements'],
                "sources": state['requirements'].get("sources", []),
                "metadata": {
                    **state['requirements']["metadata"],
                    "confidence_score": state['confidence_score'],
                    "processing_steps": state['processing_steps'],
                    "error_messages": state['error_messages']
                }
            }
            
            state['processing_steps'].append("응답 생성 완료")
            print("✅ 응답 생성 완료")
            
        except Exception as e:
            state['error_messages'].append(f"응답 생성 오류: {str(e)}")
            print(f"❌ 응답 생성 오류: {e}")
        
        return state
    
    
    def _get_category_from_hs_code(self, hs_chapter: str) -> str:
        """HS 코드에서 카테고리 추출"""
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
        """중복 항목 제거"""
        seen = set()
        unique_items = []
        
        for item in items:
            # 고유 키 생성 (name + agency)
            key = f"{item.get('name', '')}_{item.get('agency', '')}"
            if key not in seen:
                seen.add(key)
                unique_items.append(item)
        
        return unique_items
    
    async def analyze_requirements(self, hs_code: str, product_name: str, product_description: str = "") -> Dict[str, Any]:
        """요구사항 분석 실행"""
        print(f"🚀 스마트 요구사항 분석 시작: {product_name} (HS: {hs_code})")
        
        # 초기 상태 생성
        initial_state = {
            "hs_code": hs_code,
            "product_name": product_name,
            "product_description": product_description,
            "selected_agencies": [],
            "api_results": {},
            "requirements": {},
            "confidence_score": 0.0,
            "error_messages": [],
            "processing_steps": []
        }
        
        # 워크플로우 실행
        try:
            final_state = await self.app.ainvoke(initial_state)
            
            # 최종 응답 생성
            response = {
                "answer": f"HS코드 {hs_code} ({product_name})에 대한 미국 수입요건 분석 결과입니다.",
                "reasoning": f"총 {len(final_state['selected_agencies'])}개 기관에서 검색하여 {final_state['requirements'].get('metadata', {}).get('successful_agencies', 0)}개 기관에서 요구사항을 발견했습니다.",
                "requirements": final_state['requirements'],
                "sources": final_state['requirements'].get("sources", []),
                "metadata": {
                    **final_state['requirements'].get("metadata", {}),
                    "confidence_score": final_state['confidence_score'],
                    "processing_steps": final_state['processing_steps'],
                    "error_messages": final_state['error_messages']
                }
            }
            
            print(f"✅ 분석 완료: 신뢰도 {final_state['confidence_score']:.2%}")
            return response
            
        except Exception as e:
            print(f"❌ 워크플로우 실행 오류: {e}")
            return {
                "answer": f"HS코드 {hs_code} ({product_name})에 대한 분석 중 오류가 발생했습니다.",
                "reasoning": f"오류: {str(e)}",
                "requirements": {
                    "certifications": [],
                    "documents": [],
                    "labeling": [],
                    "sources": [],
                    "metadata": {"error": True, "error_message": str(e)}
                },
                "sources": [],
                "metadata": {
                    "confidence_score": 0.0,
                    "error": True,
                    "error_message": str(e)
                }
            }

# 전역 인스턴스
smart_workflow = SmartRequirementsWorkflow()

async def main():
    """테스트 실행"""
    workflow = SmartRequirementsWorkflow()
    
    # 테스트 상품들
    test_products = [
        ("8471.30.01", "노트북 컴퓨터", "휴대용 컴퓨터"),
        ("3304.99.00", "비타민C 세럼", "화장품"),
        ("0101.21.00", "소고기", "식품"),
        ("9018.90.00", "의료기기", "의료용 기기")
    ]
    
    for hs_code, product_name, description in test_products:
        print(f"\n{'='*80}")
        print(f"테스트: {product_name} (HS: {hs_code})")
        print(f"{'='*80}")
        
        result = await workflow.analyze_requirements(hs_code, product_name, description)
        
        print(f"📊 결과 요약:")
        print(f"  신뢰도: {result['metadata']['confidence_score']:.2%}")
        print(f"  인증요건: {len(result['requirements']['certifications'])}개")
        print(f"  서류요건: {len(result['requirements']['documents'])}개")
        print(f"  출처: {len(result['requirements']['sources'])}개")
        
        if result['requirements']['certifications']:
            print("\n인증요건:")
            for cert in result['requirements']['certifications'][:3]:
                print(f"  - {cert['name']} ({cert['agency']})")

if __name__ == "__main__":
    asyncio.run(main())
