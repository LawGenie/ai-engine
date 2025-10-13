#!/usr/bin/env python3
"""
처벌 및 벌금 분석 서비스 (Phase 3)
- 벌금 금액 (최소/최대)
- 제품 압수/폐기, 수입 금지
- 집행/법적 책임 관련 근거 수집
"""

from typing import Dict, Any, List, Optional
from datetime import datetime

from .tavily_search import TavilySearchService


class PenaltiesService:
    """처벌 및 벌금 분석 전용 서비스 (Phase 3)"""
    
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
        
        # HS 코드별 처벌 정보 매핑 (상세화)
        self.hs_penalties_mapping = self._build_penalties_mapping()
    
    def _build_penalties_mapping(self) -> Dict[str, Dict[str, Any]]:
        """HS 코드별 처벌 및 벌금 맞춤 쿼리 정의"""
        return {
            # 화장품 (3304)
            "3304": {
                "category": "cosmetics",
                "violation_types": ["misbranding", "adulteration", "unauthorized_ingredients"],
                "specific_queries": {
                    "FDA": [
                        "FDA cosmetic violations penalties enforcement",
                        "FDA cosmetic misbranding fines",
                        "FDA cosmetic import refusal detention",
                        "FDA cosmetic seizure adulteration"
                    ],
                    "FTC": [
                        "FTC cosmetic false advertising penalties"
                    ]
                },
                "typical_fine_range": {"min": 1000, "max": 100000}
            },
            # 건강보조식품 (2106)
            "2106": {
                "category": "dietary_supplements",
                "violation_types": ["misbranding", "health_claims", "contamination"],
                "specific_queries": {
                    "FDA": [
                        "FDA dietary supplement violations penalties",
                        "FDA supplement misbranding enforcement actions",
                        "FDA supplement contamination seizure",
                        "FDA supplement health claims violations fines"
                    ]
                },
                "typical_fine_range": {"min": 5000, "max": 500000}
            },
            # 전자제품 (8471)
            "8471": {
                "category": "electronics",
                "violation_types": ["unauthorized_import", "emc_violations", "safety_violations"],
                "specific_queries": {
                    "FCC": [
                        "FCC unauthorized equipment penalties",
                        "FCC Part 15 violations fines",
                        "FCC equipment authorization violations enforcement"
                    ],
                    "CPSC": [
                        "CPSC electronic product safety violations penalties",
                        "CPSC recall enforcement actions computers"
                    ],
                    "CBP": [
                        "CBP customs violations penalties electronics",
                        "CBP import seizure electronics unauthorized"
                    ]
                },
                "typical_fine_range": {"min": 10000, "max": 1000000}
            },
            # 식품 (1904)
            "1904": {
                "category": "prepared_foods",
                "violation_types": ["contamination", "misbranding", "unsafe_conditions"],
                "specific_queries": {
                    "FDA": [
                        "FDA food import violations penalties",
                        "FDA food safety violations enforcement",
                        "FDA food refusal detention reasons",
                        "FDA FSMA violations penalties"
                    ],
                    "USDA": [
                        "USDA food inspection violations penalties"
                    ]
                },
                "typical_fine_range": {"min": 5000, "max": 250000}
            }
        }

    def _build_queries(self, hs_code: str, product_name: str) -> Dict[str, str]:
        """🚀 최적화된 처벌 정보 쿼리 생성 (중복 제거 + 통합)"""
        queries: Dict[str, str] = {}
        
        # HS 코드에서 4자리 추출
        hs_4digit = hs_code.split('.')[0] if '.' in hs_code else hs_code[:4]
        
        # HS 코드별 맞춤 쿼리
        mapping = self.hs_penalties_mapping.get(hs_4digit)
        
        if mapping:
            # 🚀 초통합 쿼리 전략 (기존 5-7개 → 1개!) - 모든 정보를 하나의 쿼리로
            print(f"  🎯 {mapping['category']} 맞춤형 처벌 쿼리 생성 (초통합 최적화)")
            
            # 모든 기관과 위반 유형을 하나의 쿼리로 통합
            all_agencies = " OR ".join([f"site:{agency.lower()}.gov" for agency in mapping.get("specific_queries", {}).keys()])
            violation_types = " ".join(mapping.get("violation_types", []))
            
            queries["penalties_comprehensive"] = f"({all_agencies}) {violation_types} violations penalties enforcement fines detention seizure {product_name} {hs_code}"
        else:
            # 🚀 일반 통합 쿼리 (기존 여러 개 → 1개)
            print(f"  ⚠️ HS 코드 매핑 없음 - 통합 쿼리 사용")
            queries["general_integrated"] = f"site:.gov penalties violations enforcement fines seizure import ban {product_name} {hs_code}"
        
        print(f"  📊 초통합 최적화 쿼리 수: {len(queries)}개 (기존 대비 ~90% 감소)")
        return queries

    def _infer_agency(self, url: str) -> Optional[str]:
        for agency, domain in self.agency_domains.items():
            if domain in url:
                return agency
        return None

    def _classify(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        data = {
            "fines": [],
            "seizure_or_ban": [],
            "enforcement": [],
            "legal_liability": [],
            "agencies": [],
            "sources": []
        }
        for r in results:
            url = r.get("url", "")
            title = r.get("title", "")
            content = (r.get("content", "") or "")
            score = r.get("score", 0)
            agency = self._infer_agency(url)
            lower = content.lower()

            if any(k in lower for k in ["fine", "penalt", "$", "usd", "per violation", "maximum", "minimum"]):
                data["fines"].append({"title": title, "url": url, "snippet": content[:400], "agency": agency, "score": score})
            if any(k in lower for k in ["seizure", "detention", "refuse admission", "import ban", "destroy", "disposal"]):
                data["seizure_or_ban"].append({"title": title, "url": url, "snippet": content[:400], "agency": agency, "score": score})
            if any(k in lower for k in ["enforcement", "civil", "criminal", "action", "sanction"]):
                data["enforcement"].append({"title": title, "url": url, "snippet": content[:400], "agency": agency, "score": score})
            if any(k in lower for k in ["liable", "responsibility", "strict liability", "criminal liability"]):
                data["legal_liability"].append({"title": title, "url": url, "snippet": content[:400], "agency": agency, "score": score})

            if agency and agency not in data["agencies"]:
                data["agencies"].append(agency)
            data["sources"].append({"title": title, "url": url, "agency": agency or "Unknown", "score": score})
        return data

    def _estimate_fine_range(self, fines: List[Dict[str, Any]]) -> Dict[str, Any]:
        # 텍스트 휴리스틱으로 범위 감지
        import re
        min_val, max_val = None, None
        for item in fines:
            text = (item.get("snippet") or "") + " " + (item.get("title") or "")
            for m in re.findall(r"\$\s?([0-9][0-9,]{0,6})", text):
                val = int(m.replace(",", ""))
                min_val = val if min_val is None else min(min_val, val)
                max_val = val if max_val is None else max(max_val, val)
        return {
            "min": min_val,
            "max": max_val,
            "confidence": 0.7 if (min_val is not None or max_val is not None) else 0.3
        }

    async def analyze(self, hs_code: str, product_name: str, product_description: str = "") -> Dict[str, Any]:
        queries = self._build_queries(hs_code, product_name)
        all_results: List[Dict[str, Any]] = []
        for q in queries.values():
            try:
                res = await self.tavily.search(q, max_results=20)  # 증가: 검색 횟수 감소, 더 많은 출처 확보
                all_results.extend(res)
            except Exception:
                continue

        extracted = self._classify(all_results)
        fine_range = self._estimate_fine_range(extracted["fines"])

        return {
            "hs_code": hs_code,
            "product_name": product_name,
            "analysis_timestamp": datetime.utcnow().isoformat() + "Z",
            "agencies": extracted["agencies"],
            "fine_range": fine_range,
            "measures": {
                "seizure_or_destruction": len(extracted["seizure_or_ban"]) > 0,
                "import_ban_possible": len(extracted["seizure_or_ban"]) > 0
            },
            "legal": {
                "enforcement_refs": extracted["enforcement"],
                "liability_refs": extracted["legal_liability"]
            },
            "sources": extracted["sources"]
        }


penalties_service = PenaltiesService()


