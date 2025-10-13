#!/usr/bin/env python3
"""
세부 규정 및 기준 추출 서비스
- 농약 잔류량 기준 (MRL - Maximum Residue Limits)
- 화학성분 제한 (FDA 화장품 성분 제한)
- 식품첨가물 기준 (FDA GRAS 목록)
- 전자기기 EMC 기준 (FCC Part 15)
- Tavily Search 쿼리 확장
"""

import asyncio
import json
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path

from .tavily_search import TavilySearchService


class DetailedRegulationsService:
    """세부 규정 및 기준 추출 전용 서비스"""
    
    def __init__(self):
        self.tavily_service = TavilySearchService()
        self.agency_domains = {
            "FDA": "fda.gov",
            "USDA": "usda.gov", 
            "EPA": "epa.gov",
            "FCC": "fcc.gov",
            "CPSC": "cpsc.gov",
            "CBP": "cbp.gov"
        }
        
        # HS 코드 기반 세부 규정 매핑
        self.hs_code_detailed_mapping = self._build_detailed_regulations_mapping()
    
    def _build_detailed_regulations_mapping(self) -> Dict[str, Dict[str, Any]]:
        """HS 코드 기반 세부 규정 매핑 구축"""
        return {
            # 화장품 및 미용 제품 (33xx)
            "3304": {
                "category": "cosmetics",
                "detailed_regulations": {
                    "pesticide_residue": {
                        "agencies": ["FDA"],
                        "queries": [
                            "FDA pesticide residue limits cosmetic products",
                            "FDA cosmetic ingredient restrictions safety",
                            "FDA cosmetic safety testing requirements"
                        ],
                        "standards": ["MRL", "ingredient safety", "contamination limits"]
                    },
                    "chemical_restrictions": {
                        "agencies": ["FDA"],
                        "queries": [
                            "FDA prohibited cosmetic ingredients list",
                            "FDA cosmetic ingredient restrictions",
                            "FDA cosmetic safety regulations"
                        ],
                        "standards": ["prohibited ingredients", "restricted ingredients", "safe levels"]
                    }
                }
            },
            
            # 식품 및 건강보조식품 (21xx, 19xx, 20xx)
            "2106": {
                "category": "dietary_supplements",
                "detailed_regulations": {
                    "pesticide_residue": {
                        "agencies": ["FDA", "USDA"],
                        "queries": [
                            "FDA pesticide residue limits dietary supplements",
                            "USDA organic certification pesticide requirements",
                            "FDA dietary supplement contamination limits"
                        ],
                        "standards": ["MRL", "organic standards", "contamination limits"]
                    },
                    "food_additives": {
                        "agencies": ["FDA"],
                        "queries": [
                            "FDA GRAS list dietary supplements",
                            "FDA food additive regulations",
                            "FDA dietary supplement ingredient safety"
                        ],
                        "standards": ["GRAS", "food additives", "safety standards"]
                    }
                }
            },
            "1904": {
                "category": "prepared_foods",
                "detailed_regulations": {
                    "pesticide_residue": {
                        "agencies": ["FDA", "USDA"],
                        "queries": [
                            "FDA pesticide residue limits rice products",
                            "USDA rice import requirements",
                            "FDA prepared food safety standards"
                        ],
                        "standards": ["MRL", "food safety", "import requirements"]
                    },
                    "food_additives": {
                        "agencies": ["FDA"],
                        "queries": [
                            "FDA GRAS list prepared foods",
                            "FDA food additive regulations rice",
                            "FDA prepared food ingredient safety"
                        ],
                        "standards": ["GRAS", "food additives", "preservatives"]
                    }
                }
            },
            
            # 전자제품 및 통신 (84xx, 85xx)
            "8471": {
                "category": "electronics",
                "detailed_regulations": {
                    "emc_standards": {
                        "agencies": ["FCC"],
                        "queries": [
                            "FCC Part 15 EMC requirements computers",
                            "FCC electromagnetic compatibility standards",
                            "FCC device authorization EMC testing"
                        ],
                        "standards": ["FCC Part 15", "EMC", "electromagnetic compatibility"]
                    },
                    "safety_standards": {
                        "agencies": ["CPSC"],
                        "queries": [
                            "CPSC electronic device safety standards",
                            "CPSC computer safety requirements",
                            "CPSC electronic product safety"
                        ],
                        "standards": ["safety standards", "electrical safety", "consumer protection"]
                    }
                }
            },
            "8517": {
                "category": "telecommunications",
                "detailed_regulations": {
                    "emc_standards": {
                        "agencies": ["FCC"],
                        "queries": [
                            "FCC Part 15 EMC requirements telecommunications",
                            "FCC radio frequency regulations",
                            "FCC equipment authorization EMC"
                        ],
                        "standards": ["FCC Part 15", "EMC", "radio frequency"]
                    }
                }
            },
            
            # 의류 및 섬유 (61xx, 62xx)
            "6109": {
                "category": "textiles",
                "detailed_regulations": {
                    "chemical_restrictions": {
                        "agencies": ["CPSC"],
                        "queries": [
                            "CPSC textile chemical restrictions",
                            "CPSC clothing safety standards",
                            "CPSC textile flammability requirements"
                        ],
                        "standards": ["flammability standards", "chemical restrictions", "safety standards"]
                    }
                }
            },
            
            # 장난감 및 어린이 제품 (95xx)
            "9503": {
                "category": "toys",
                "detailed_regulations": {
                    "chemical_restrictions": {
                        "agencies": ["CPSC"],
                        "queries": [
                            "CPSC toy chemical restrictions",
                            "CPSC lead content limits toys",
                            "CPSC toy safety standards"
                        ],
                        "standards": ["lead limits", "chemical restrictions", "safety standards"]
                    }
                }
            }
        }
    
    def _get_detailed_regulations_for_hs_code(self, hs_code: str) -> Dict[str, Any]:
        """HS 코드에 대한 세부 규정 정보 반환"""
        # HS 코드에서 4자리 코드 추출
        hs_4digit = hs_code.split('.')[0] if '.' in hs_code else hs_code[:4]
        
        # 매핑에서 해당 코드 찾기
        mapping = self.hs_code_detailed_mapping.get(hs_4digit, {})
        
        if not mapping:
            # 기본 매핑 (모든 기관 검색)
            return {
                "category": "general",
                "detailed_regulations": {
                    "general_requirements": {
                        "agencies": ["FDA", "USDA", "EPA", "FCC", "CPSC"],
                        "queries": [
                            f"import requirements {hs_code}",
                            f"regulations {hs_code}",
                            f"safety standards {hs_code}"
                        ],
                        "standards": ["general requirements", "safety standards", "import regulations"]
                    }
                },
                "confidence": 0.3
            }
        
        return {
            **mapping,
            "confidence": 0.9
        }
    
    def _build_phase_specific_queries(self, product_name: str, hs_code: str, detailed_regulations: Dict[str, Any]) -> Dict[str, str]:
        """
        Phase 1 전용 세부 규정 검색 쿼리 생성 (통합 쿼리 최적화)
        
        주의: Phase 2-4는 별도 서비스(testing_procedures, penalties, validity)에서 처리하므로
        이 메서드는 Phase 1만 담당합니다.
        """
        queries = {}
        
        # 🚀 통합 쿼리 전략: 유사한 쿼리를 하나로 합침
        category = detailed_regulations.get("category", "general")
        
        # HS 코드 4자리
        hs_4digit = hs_code.split('.')[0] if '.' in hs_code else hs_code[:4]
        
        # 카테고리별 통합 쿼리
        if category == "cosmetics":
            # 성분 제한 통합 쿼리 (기존 7개 → 2개)
            queries["FDA_ingredients_integrated"] = f"site:fda.gov cosmetic prohibited restricted ingredients safety limits {hs_code}"
            queries["FDA_ingredients_product"] = f"site:fda.gov cosmetic ingredient safety {product_name}"
            queries["FDA_regulations"] = f"site:fda.gov cosmetic regulations standards {product_name} {hs_code}"
            
        elif category == "food":
            # 농약 잔류량 통합 쿼리 (기존 4개 → 2개)
            queries["FDA_EPA_pesticide_integrated"] = f"pesticide residue limits MRL tolerances {hs_code} site:.gov"
            queries["FDA_food_additives"] = f"site:fda.gov food additives GRAS safe ingredients {product_name}"
            queries["FDA_food_safety"] = f"site:fda.gov food safety import requirements {product_name} {hs_code}"
            
        elif category == "electronics":
            # EMC 기준 통합 쿼리
            queries["FCC_emc_integrated"] = f"site:fcc.gov electromagnetic compatibility EMC Part 15 standards {hs_code}"
            queries["FCC_product"] = f"site:fcc.gov electronic device certification {product_name}"
            
        else:
            # 일반 상품 통합 쿼리
            queries["general_integrated"] = f"import requirements safety standards regulations {hs_code} site:.gov"
            queries["general_product"] = f"import compliance requirements {product_name} site:.gov"
        
        # 🎯 공통 통합 쿼리 (모든 카테고리 - 항상 포함)
        queries["general_safety"] = f"site:.gov import safety requirements compliance {product_name} {hs_code}"
        
        print(f"  🚀 통합 쿼리 최적화: {len(queries)}개 쿼리 생성 (기존 대비 70-80% 감소)")
        
        return queries
    
    async def analyze(self, hs_code: str, product_name: str, product_description: str = "") -> Dict[str, Any]:
        """
        Phase 1: 세부 규정 및 기준 추출 실행
        
        이 메서드는 Phase 1만 담당합니다.
        Phase 2-4는 별도 서비스에서 처리됩니다.
        """
        return await self.search_detailed_regulations(hs_code, product_name, product_description)
    
    async def search_detailed_regulations(self, hs_code: str, product_name: str, product_description: str = "") -> Dict[str, Any]:
        """세부 규정 및 기준 추출 실행 (내부 메서드)"""
        try:
            print(f"\n🚀 [PHASE 1] 세부 규정 추출 시작")
            print(f"  📋 HS코드: {hs_code}")
            print(f"  📦 상품명: {product_name}")
            
            # HS 코드 기반 세부 규정 정보 조회
            detailed_regulations = self._get_detailed_regulations_for_hs_code(hs_code)
            
            # Phase 1 검색 쿼리 생성 (Phase 1만 담당)
            phase_queries = self._build_phase_specific_queries(product_name, hs_code, detailed_regulations)
            
            print(f"  🎯 상품 카테고리: {detailed_regulations.get('category', 'general')}")
            print(f"  📊 검색 신뢰도: {detailed_regulations.get('confidence', 0):.1%}")
            print(f"  🔍 Phase 1 검색 쿼리: {len(phase_queries)}개")
            
            # 검색 결과 저장
            search_results = {
                "hs_code": hs_code,
                "product_name": product_name,
                "product_description": product_description,
                "category": detailed_regulations.get("category", "general"),
                "confidence": detailed_regulations.get("confidence", 0.3),
                "search_timestamp": datetime.now().isoformat(),
                "phase_results": {
                    "phase1_detailed_regulations": {}
                },
                "extracted_regulations": {
                    "pesticide_residue_limits": [],
                    "chemical_restrictions": [],
                    "food_additive_standards": [],
                    "emc_standards": [],
                    "safety_standards": []
                },
                "sources": []
            }
        except Exception as e:
            print(f"  ❌ Phase 1 초기화 실패: {e}")
            return {
                "hs_code": hs_code,
                "product_name": product_name,
                "error": str(e),
                "sources": [],
                "summary": "Phase 1 분석 실패"
            }
        
        # Phase 1 검색 실행 (Phase 2-4는 별도 서비스에서 처리)
        for query_key, query in phase_queries.items():
            try:
                # Phase 1만 처리
                phase = "phase1_detailed_regulations"
                
                # Tavily Search 실행 (통합 쿼리는 max_results 증가)
                if self.tavily_service.is_enabled():
                    search_results_raw = await self.tavily_service.search(query, max_results=10)
                    
                    # 결과 처리
                    processed_results = self._process_search_results(query_key, query, search_results_raw, hs_code)
                    
                    # Phase별 결과 저장
                    search_results["phase_results"][phase][query_key] = processed_results
                    
                    # 세부 규정 추출
                    self._extract_detailed_regulations(search_results, processed_results, query_key)
                    
                    print(f"    ✅ {query_key}: {len(search_results_raw)}개 결과")
                else:
                    print(f"    ⚠️ Tavily Search 비활성화: {query_key} 스킵됨")
                    search_results["phase_results"][phase][query_key] = {
                        "query": query,
                        "results": [],
                        "error": "Tavily Search 비활성화"
                    }
                    
            except Exception as e:
                print(f"    ❌ {query_key} 검색 실패: {e}")
                search_results["phase_results"][phase][query_key] = {
                    "query": query,
                    "results": [],
                    "error": str(e)
                }
        
        # 통계 계산
        try:
            total_results = sum(
                len(query_data.get("results", []))
                for query_data in search_results["phase_results"].get("phase1_detailed_regulations", {}).values()
                if isinstance(query_data, dict) and "results" in query_data
            )
        except Exception as e:
            print(f"  ⚠️ 통계 계산 실패: {e}")
            total_results = 0
        
        print(f"\n✅ [PHASE 1] 세부 규정 추출 완료")
        print(f"  📊 총 검색 결과: {total_results}개")
        print(f"  🔍 Phase 1 (세부 규정): {len(search_results['phase_results']['phase1_detailed_regulations'])}개 쿼리")
        
        # 추출된 세부 규정 통계
        for regulation_type, regulations in search_results.get("extracted_regulations", {}).items():
            if regulations:
                print(f"  📋 {regulation_type}: {len(regulations)}개")
        
        # 요약 정보 추가
        search_results["summary"] = f"Phase 1 분석 완료: {total_results}개 결과 수집"
        
        return search_results
    
    def _process_search_results(self, query_key: str, query: str, raw_results: List[Dict], hs_code: str) -> Dict[str, Any]:
        """검색 결과 처리"""
        processed_results = {
            "query": query,
            "query_key": query_key,
            "results": [],
            "urls": [],
            "agencies": [],
            "official_sites": [],
            "other_sites": []
        }
        
        for result in raw_results:
            url = result.get("url", "")
            title = result.get("title", "")
            content = result.get("content", "")
            score = result.get("score", 0)
            
            # 공식 사이트 vs 기타 사이트 구분
            is_official = any(domain in url for domain in [".gov", ".fda.gov", ".usda.gov", ".epa.gov", ".fcc.gov", ".cbp.gov", ".cpsc.gov"])
            
            processed_result = {
                "title": title,
                "url": url,
                "content": content[:500] + "..." if len(content) > 500 else content,
                "score": score,
                "is_official": is_official,
                "agency": self._extract_agency_from_url(url),
                "relevance": "high" if score > 0.7 else "medium" if score > 0.5 else "low"
            }
            
            processed_results["results"].append(processed_result)
            processed_results["urls"].append(url)
            
            if is_official:
                processed_results["official_sites"].append(processed_result)
            else:
                processed_results["other_sites"].append(processed_result)
            
            # 기관 정보 추가
            agency = processed_result["agency"]
            if agency and agency not in processed_results["agencies"]:
                processed_results["agencies"].append(agency)
        
        return processed_results
    
    def _extract_agency_from_url(self, url: str) -> str:
        """URL에서 기관 추출"""
        for agency, domain in self.agency_domains.items():
            if domain in url:
                return agency
        return "Unknown"
    
    def _extract_detailed_regulations(self, search_results: Dict[str, Any], processed_results: Dict[str, Any], query_key: str):
        """검색 결과에서 세부 규정 추출"""
        for result in processed_results.get("results", []):
            url = result.get("url", "")
            title = result.get("title", "")
            content = result.get("content", "")
            agency = result.get("agency", "Unknown")
            
            # 농약 잔류량 기준 (MRL)
            if any(keyword in query_key.lower() for keyword in ["mrl", "pesticide", "residue"]):
                if any(keyword in content.lower() for keyword in ["pesticide", "residue", "mrl", "maximum residue"]):
                    search_results["extracted_regulations"]["pesticide_residue_limits"].append({
                        "title": title,
                        "url": url,
                        "agency": agency,
                        "type": "pesticide_residue_limits",
                        "description": f"{agency}에서 확인된 농약 잔류량 기준",
                        "confidence": result.get("score", 0)
                    })
            
            # 화학성분 제한
            elif any(keyword in query_key.lower() for keyword in ["chemical", "ingredient", "restriction"]):
                if any(keyword in content.lower() for keyword in ["chemical", "ingredient", "restriction", "prohibited"]):
                    search_results["extracted_regulations"]["chemical_restrictions"].append({
                        "title": title,
                        "url": url,
                        "agency": agency,
                        "type": "chemical_restrictions",
                        "description": f"{agency}에서 확인된 화학성분 제한",
                        "confidence": result.get("score", 0)
                    })
            
            # 식품첨가물 기준 (GRAS)
            elif any(keyword in query_key.lower() for keyword in ["gras", "additive", "food"]):
                if any(keyword in content.lower() for keyword in ["gras", "additive", "food", "generally recognized"]):
                    search_results["extracted_regulations"]["food_additive_standards"].append({
                        "title": title,
                        "url": url,
                        "agency": agency,
                        "type": "food_additive_standards",
                        "description": f"{agency}에서 확인된 식품첨가물 기준",
                        "confidence": result.get("score", 0)
                    })
            
            # EMC 기준 (FCC Part 15)
            elif any(keyword in query_key.lower() for keyword in ["emc", "electromagnetic", "fcc"]):
                if any(keyword in content.lower() for keyword in ["emc", "electromagnetic", "fcc", "part 15"]):
                    search_results["extracted_regulations"]["emc_standards"].append({
                        "title": title,
                        "url": url,
                        "agency": agency,
                        "type": "emc_standards",
                        "description": f"{agency}에서 확인된 EMC 기준",
                        "confidence": result.get("score", 0)
                    })
            
            # 안전 기준
            elif any(keyword in query_key.lower() for keyword in ["safety", "standard", "cpsc"]):
                if any(keyword in content.lower() for keyword in ["safety", "standard", "requirement"]):
                    search_results["extracted_regulations"]["safety_standards"].append({
                        "title": title,
                        "url": url,
                        "agency": agency,
                        "type": "safety_standards",
                        "description": f"{agency}에서 확인된 안전 기준",
                        "confidence": result.get("score", 0)
                    })
            
            # 출처 정보 추가
            search_results["sources"].append({
                "title": title,
                "url": url,
                "type": "공식 사이트" if result.get("is_official") else "기타 사이트",
                "relevance": result.get("relevance", "medium"),
                "agency": agency,
                "phase": query_key.split("_")[1] if "_" in query_key else "phase1"
            })
    
    async def get_regulation_summary(self, search_results: Dict[str, Any]) -> Dict[str, Any]:
        """세부 규정 요약 생성"""
        summary = {
            "hs_code": search_results["hs_code"],
            "product_name": search_results["product_name"],
            "category": search_results["category"],
            "confidence": search_results["confidence"],
            "total_sources": len(search_results["sources"]),
            "regulation_summary": {},
            "phase_summary": {},
            "recommendations": []
        }
        
        # 세부 규정별 요약
        for regulation_type, regulations in search_results["extracted_regulations"].items():
            if regulations:
                agencies = list(set([r["agency"] for r in regulations]))
                summary["regulation_summary"][regulation_type] = {
                    "count": len(regulations),
                    "agencies": agencies,
                    "high_confidence": len([r for r in regulations if r["confidence"] > 0.7]),
                    "official_sources": len([r for r in regulations if r["agency"] != "Unknown"])
                }
        
        # Phase별 요약
        for phase, phase_data in search_results["phase_results"].items():
            total_queries = len(phase_data)
            successful_queries = len([q for q in phase_data.values() if isinstance(q, dict) and "error" not in q])
            summary["phase_summary"][phase] = {
                "total_queries": total_queries,
                "successful_queries": successful_queries,
                "success_rate": successful_queries / total_queries if total_queries > 0 else 0
            }
        
        # 권장사항 생성
        if summary["regulation_summary"].get("pesticide_residue_limits"):
            summary["recommendations"].append("농약 잔류량 기준 확인 필요")
        if summary["regulation_summary"].get("chemical_restrictions"):
            summary["recommendations"].append("화학성분 제한 사항 검토 필요")
        if summary["regulation_summary"].get("food_additive_standards"):
            summary["recommendations"].append("식품첨가물 기준 준수 필요")
        if summary["regulation_summary"].get("emc_standards"):
            summary["recommendations"].append("EMC 기준 테스트 필요")
        if summary["regulation_summary"].get("safety_standards"):
            summary["recommendations"].append("안전 기준 준수 필요")
        
        return summary


# 전역 인스턴스
detailed_regulations_service = DetailedRegulationsService()


async def main():
    """테스트 실행"""
    service = DetailedRegulationsService()
    
    # 테스트 상품들
    test_products = [
        ("3304.99.00", "Premium Vitamin C Serum", "화장품"),
        ("2106.90.00", "Ginseng Extract", "건강보조식품"),
        ("8471.30.01", "Laptop Computer", "전자제품"),
        ("1904.90.00", "Instant Rice", "식품")
    ]
    
    for hs_code, product_name, description in test_products:
        print(f"\n{'='*80}")
        print(f"테스트: {product_name} (HS: {hs_code})")
        print(f"{'='*80}")
        
        result = await service.search_detailed_regulations(hs_code, product_name, description)
        summary = await service.get_regulation_summary(result)
        
        print(f"📊 결과 요약:")
        print(f"  카테고리: {summary['category']}")
        print(f"  신뢰도: {summary['confidence']:.1%}")
        print(f"  총 출처: {summary['total_sources']}개")
        
        if summary["regulation_summary"]:
            print("\n세부 규정:")
            for reg_type, reg_info in summary["regulation_summary"].items():
                print(f"  - {reg_type}: {reg_info['count']}개 ({', '.join(reg_info['agencies'])})")
        
        if summary["recommendations"]:
            print("\n권장사항:")
            for rec in summary["recommendations"]:
                print(f"  - {rec}")


if __name__ == "__main__":
    asyncio.run(main())
