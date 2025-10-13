#!/usr/bin/env python3
"""
검사 절차 및 방법 분석 서비스 (Phase 2)
- 검사 주기 (연간, 수입시마다, 샘플링)
- 검사 기관 (FDA, USDA, CPSC 등)
- 검사 방법 (물리적 검사, 화학적 분석)
- 검사 비용 및 소요 시간 추정
"""

from typing import Dict, Any, List, Optional
from datetime import datetime

from .tavily_search import TavilySearchService


class TestingProceduresService:
    """검사 절차 및 방법 분석 전용 서비스 (Phase 2)"""

    def __init__(self) -> None:
        self.tavily = TavilySearchService()
        self.agency_domains = {
            "FDA": "fda.gov",
            "USDA": "usda.gov",
            "EPA": "epa.gov",
            "FCC": "fcc.gov",
            "CPSC": "cpsc.gov",
            "CBP": "cbp.gov"
        }
        
        # HS 코드별 검사 절차 매핑 (상세화)
        self.hs_testing_mapping = self._build_testing_mapping()
    
    def _build_testing_mapping(self) -> Dict[str, Dict[str, Any]]:
        """HS 코드별 검사 절차 맞춤 쿼리 정의"""
        return {
            # 화장품 (3304)
            "3304": {
                "category": "cosmetics",
                "testing_focus": ["ingredient_testing", "safety_assessment", "labeling_compliance"],
                "specific_queries": {
                    "FDA": [
                        "FDA cosmetic product testing requirements",
                        "FDA cosmetic ingredient safety testing",
                        "FDA cosmetic voluntary cosmetic registration program VCRP",
                        "FDA cosmetic inspection frequency import"
                    ],
                    "EPA": [
                        "EPA cosmetic chemical testing requirements",
                        "EPA chemical safety assessment cosmetics"
                    ],
                    "CPSC": [
                        "CPSC cosmetic product safety testing"
                    ]
                },
                "estimated_cycle": "sampling",
                "typical_cost_range": "medium"
            },
            # 건강보조식품 (2106)
            "2106": {
                "category": "dietary_supplements",
                "testing_focus": ["ingredient_testing", "contamination_testing", "label_verification"],
                "specific_queries": {
                    "FDA": [
                        "FDA dietary supplement testing requirements",
                        "FDA supplement cGMP compliance testing",
                        "FDA supplement inspection procedures",
                        "FDA supplement contamination testing heavy metals"
                    ],
                    "USDA": [
                        "USDA organic supplement certification testing",
                        "USDA organic testing procedures requirements"
                    ]
                },
                "estimated_cycle": "per_import",
                "typical_cost_range": "high"
            },
            # 전자제품 (8471)
            "8471": {
                "category": "electronics",
                "testing_focus": ["emc_testing", "safety_testing", "certification"],
                "specific_queries": {
                    "FCC": [
                        "FCC equipment authorization testing procedures",
                        "FCC Part 15 testing requirements computers",
                        "FCC EMC testing accredited labs",
                        "FCC certification cost timeline computers"
                    ],
                    "CPSC": [
                        "CPSC electronic product safety testing",
                        "CPSC computer safety standards testing"
                    ]
                },
                "estimated_cycle": "per_import",
                "typical_cost_range": "high"
            },
            # 식품 (1904, 2005)
            "1904": {
                "category": "prepared_foods",
                "testing_focus": ["microbial_testing", "pesticide_testing", "nutritional_analysis"],
                "specific_queries": {
                    "FDA": [
                        "FDA food import testing requirements",
                        "FDA FSMA foreign supplier verification FSVP",
                        "FDA food facility inspection frequency",
                        "FDA food testing labs accredited"
                    ],
                    "USDA": [
                        "USDA food inspection procedures import",
                        "USDA food testing requirements"
                    ]
                },
                "estimated_cycle": "per_import",
                "typical_cost_range": "medium"
            }
        }

    def _build_queries(self, hs_code: str, product_name: str) -> Dict[str, str]:
        """🚀 최적화된 검사 절차 쿼리 생성 (중복 제거 + 통합)"""
        queries: Dict[str, str] = {}
        
        # HS 코드에서 4자리 추출
        hs_4digit = hs_code.split('.')[0] if '.' in hs_code else hs_code[:4]
        
        # HS 코드별 맞춤 쿼리
        mapping = self.hs_testing_mapping.get(hs_4digit)
        
        if mapping:
            # 🚀 맞춤형 통합 쿼리 (기존 8-10개 → 2-3개)
            print(f"  🎯 {mapping['category']} 맞춤형 검사 쿼리 생성 (통합 최적화)")
            
            # 기관별 쿼리를 하나로 통합
            for agency, agency_queries in mapping.get("specific_queries", {}).items():
                # 모든 agency_queries를 하나의 통합 쿼리로
                # 각 쿼리에서 처음 3개 단어를 추출한 후 문자열로 조합
                combined_keywords = " ".join([" ".join(q.replace(f"{agency} ", "").split()[0:3]) for q in agency_queries[:2]])
                queries[f"{agency}_integrated"] = f"site:{agency.lower()}.gov {combined_keywords} {product_name} {hs_code}"
            
            # testing_focus도 하나로 통합
            if mapping.get("testing_focus"):
                focus_combined = " ".join(mapping.get("testing_focus", []))
                queries["focus_integrated"] = f"{focus_combined} testing procedures {product_name} site:.gov"
        else:
            # 🚀 최적화된 일반 통합 쿼리 (기존 3개 → 1개)
            print(f"  ⚠️ HS 코드 매핑 없음 - 통합 쿼리 사용")
            queries["general_integrated"] = f"site:.gov testing procedures inspection cost timeline {product_name} {hs_code}"
        
        print(f"  📊 통합 최적화 쿼리 수: {len(queries)}개 (기존 대비 ~85% 감소)")
        return queries

    def _infer_agency(self, url: str) -> Optional[str]:
        for agency, domain in self.agency_domains.items():
            if domain in url:
                return agency
        return None

    def _classify_and_extract(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        data = {
            "cycles": [],
            "agencies": [],
            "methods": [],
            "costs": [],
            "durations": [],
            "sources": []
        }
        for r in results:
            url = r.get("url", "")
            title = r.get("title", "")
            content_raw = r.get("content", "")
            
            # 🔧 content가 리스트인 경우 문자열로 변환
            if isinstance(content_raw, list):
                content = " ".join([str(item) for item in content_raw if item])
            elif content_raw:
                content = str(content_raw)
            else:
                content = ""
            
            score = r.get("score", 0)
            agency = self._infer_agency(url)
            lower = content.lower()
            
            # snippet은 항상 문자열로 저장
            snippet = content[:300] if content else ""

            if any(k in lower for k in ["every import", "per shipment", "per import", "annual", "yearly", "sampling", "random sample", "periodic"]):
                data["cycles"].append({"snippet": snippet, "title": title, "url": url, "agency": agency, "score": score})
            if any(k in lower for k in ["inspection", "visual", "physical", "chemical", "analysis", "laboratory", "lab test", "testing method"]):
                data["methods"].append({"snippet": snippet, "title": title, "url": url, "agency": agency, "score": score})
            if any(k in lower for k in ["fee", "cost", "charge", "payment", "$", "usd"]):
                data["costs"].append({"snippet": snippet, "title": title, "url": url, "agency": agency, "score": score})
            if any(k in lower for k in ["within", "days", "weeks", "processing time", "turnaround", "timeline"]):
                data["durations"].append({"snippet": snippet, "title": title, "url": url, "agency": agency, "score": score})

            if agency and agency not in data["agencies"]:
                data["agencies"].append(agency)
            data["sources"].append({
                "title": title,
                "url": url,
                "agency": agency or "Unknown",
                "score": score
            })
        return data

    def _estimate_cost_time(self, extracted: Dict[str, Any]) -> Dict[str, Any]:
        def avg_score(items: List[Dict[str, Any]]) -> float:
            if not items:
                return 0.0
            return sum(i.get("score", 0) for i in items) / max(1, len(items))

        cost_band = "unknown"
        if extracted["costs"]:
            # snippet은 이제 항상 문자열이므로 간단하게 처리
            text = " ".join([i.get("snippet", "").lower() for i in extracted["costs"] if isinstance(i, dict)])
            if any(k in text for k in ["$50", "$100", "fee"]):
                cost_band = "low"
            if any(k in text for k in ["$500", "$1,000", "laboratory"]):
                cost_band = "medium"
            if any(k in text for k in ["$5,000", "$10,000", "comprehensive"]):
                cost_band = "high"

        duration_band = "unknown"
        if extracted["durations"]:
            # snippet은 이제 항상 문자열이므로 간단하게 처리
            text = " ".join([i.get("snippet", "").lower() for i in extracted["durations"] if isinstance(i, dict)])
            if any(k in text for k in ["1-3 days", "2 days", "48 hours", "72 hours"]):
                duration_band = "short"
            if any(k in text for k in ["1-2 weeks", "5-10 business days"]):
                duration_band = "medium"
            if any(k in text for k in ["3-6 weeks", "2 months"]):
                duration_band = "long"

        return {
            "estimated_cost_band": cost_band,
            "estimated_duration_band": duration_band,
            "cost_confidence": round(min(1.0, avg_score(extracted["costs"]) * 1.2), 2),
            "duration_confidence": round(min(1.0, avg_score(extracted["durations"]) * 1.2), 2)
        }

    async def analyze(self, hs_code: str, product_name: str, product_description: str = "") -> Dict[str, Any]:
        queries = self._build_queries(hs_code, product_name)
        aggregate_results: List[Dict[str, Any]] = []
        for _, q in queries.items():
            try:
                res = await self.tavily.search(q, max_results=20)  # 증가: 검색 횟수 감소, 더 많은 출처 확보
                aggregate_results.extend(res)
            except Exception:
                continue

        extracted = self._classify_and_extract(aggregate_results)
        estimates = self._estimate_cost_time(extracted)

        cycle_label = "unknown"
        if extracted["cycles"]:
            # snippet은 이제 항상 문자열이므로 간단하게 처리
            joined_cycles = " ".join([i.get("snippet", "").lower() for i in extracted["cycles"] if isinstance(i, dict)])
            if any(k in joined_cycles for k in ["every import", "per shipment", "per import"]):
                cycle_label = "per_import"
            elif any(k in joined_cycles for k in ["annual", "yearly"]):
                cycle_label = "annual"
            elif any(k in joined_cycles for k in ["sampling", "random sample", "periodic"]):
                cycle_label = "sampling"

        methods_label = []
        if extracted["methods"]:
            for m in extracted["methods"]:
                if isinstance(m, dict):
                    snippet_text = m.get("snippet", "").lower()
                    # 키워드 매칭
                    if snippet_text:
                        if any(k in snippet_text for k in ["chemical", "analysis", "lab"]) and "chemical" not in methods_label:
                            methods_label.append("chemical")
                        if any(k in snippet_text for k in ["visual", "physical", "inspection"]) and "physical" not in methods_label:
                            methods_label.append("physical")

        return {
            "hs_code": hs_code,
            "product_name": product_name,
            "product_description": product_description,
            "analysis_timestamp": datetime.utcnow().isoformat() + "Z",
            "agencies": extracted["agencies"],
            "inspection_cycle": cycle_label,
            "methods": methods_label,
            "estimates": estimates,
            "evidence": {
                "cycles": extracted["cycles"],
                "methods": extracted["methods"],
                "costs": extracted["costs"],
                "durations": extracted["durations"]
            },
            "sources": extracted["sources"]
        }


testing_procedures_service = TestingProceduresService()


