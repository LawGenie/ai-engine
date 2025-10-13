#!/usr/bin/env python3
"""
유효기간/갱신 분석 서비스 (Phase 4)
- 인증서 유효기간
- 갱신 주기 및 절차
- 갱신 비용
- 만료 전 알림 시사점
"""

from typing import Dict, Any, List, Optional
from datetime import datetime

from .tavily_search import TavilySearchService


class ValidityService:
    """유효기간 및 갱신 분석 전용 서비스 (Phase 4)"""
    
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
        
        # HS 코드별 유효기간 매핑 (상세화)
        self.hs_validity_mapping = self._build_validity_mapping()
    
    def _build_validity_mapping(self) -> Dict[str, Dict[str, Any]]:
        """HS 코드별 유효기간 및 갱신 맞춤 쿼리 정의"""
        return {
            # 화장품 (3304)
            "3304": {
                "category": "cosmetics",
                "certificate_types": ["establishment_registration", "product_listing"],
                "specific_queries": {
                    "FDA": [
                        "FDA cosmetic voluntary registration VCRP renewal",
                        "FDA cosmetic establishment registration validity",
                        "FDA cosmetic product listing renewal procedures"
                    ]
                },
                "typical_validity": "annual",
                "renewal_required": True
            },
            # 건강보조식품 (2106)
            "2106": {
                "category": "dietary_supplements",
                "certificate_types": ["facility_registration", "NDI_notification"],
                "specific_queries": {
                    "FDA": [
                        "FDA dietary supplement facility registration renewal",
                        "FDA NDI notification validity period",
                        "FDA supplement facility biennial renewal",
                        "FDA supplement registration fee cost"
                    ],
                    "USDA": [
                        "USDA organic certification validity period",
                        "USDA organic annual renewal procedures",
                        "USDA organic certification cost"
                    ]
                },
                "typical_validity": "1-2 years",
                "renewal_required": True
            },
            # 전자제품 (8471)
            "8471": {
                "category": "electronics",
                "certificate_types": ["FCC_authorization", "equipment_certification"],
                "specific_queries": {
                    "FCC": [
                        "FCC equipment authorization validity period",
                        "FCC certification renewal requirements",
                        "FCC grant authorization expiration",
                        "FCC TCB certification validity"
                    ]
                },
                "typical_validity": "indefinite",  # FCC 인증은 일반적으로 무기한
                "renewal_required": False
            },
            # 식품 (1904)
            "1904": {
                "category": "prepared_foods",
                "certificate_types": ["facility_registration", "prior_notice"],
                "specific_queries": {
                    "FDA": [
                        "FDA food facility registration biennial renewal",
                        "FDA food facility renewal deadline October",
                        "FDA food import prior notice validity"
                    ],
                    "USDA": [
                        "USDA food import permit validity",
                        "USDA food establishment approval renewal"
                    ]
                },
                "typical_validity": "2 years",
                "renewal_required": True
            }
        }

    def _build_queries(self, hs_code: str, product_name: str) -> Dict[str, str]:
        """🚀 최적화된 유효기간 쿼리 생성 (중복 제거 + 통합)"""
        queries: Dict[str, str] = {}
        
        # HS 코드에서 4자리 추출
        hs_4digit = hs_code.split('.')[0] if '.' in hs_code else hs_code[:4]
        
        # HS 코드별 맞춤 쿼리
        mapping = self.hs_validity_mapping.get(hs_4digit)
        
        if mapping:
            # 🚀 초통합 쿼리 전략 (기존 4-6개 → 1개!) - 모든 정보를 하나의 쿼리로
            print(f"  🎯 {mapping['category']} 맞춤형 유효기간 쿼리 생성 (초통합 최적화)")
            
            # 모든 기관과 인증 유형을 하나의 쿼리로 통합
            all_agencies = " OR ".join([f"site:{agency.lower()}.gov" for agency in mapping.get("specific_queries", {}).keys()])
            cert_types = " ".join(mapping.get("certificate_types", [])) if mapping.get("certificate_types") else ""
            
            queries["validity_comprehensive"] = f"({all_agencies}) {cert_types} certificate validity renewal duration cost procedures reminder {product_name} {hs_code}"
        else:
            # 🚀 일반 통합 쿼리 (기존 여러 개 → 1개)
            print(f"  ⚠️ HS 코드 매핑 없음 - 통합 쿼리 사용")
            queries["general_integrated"] = f"site:.gov certificate validity renewal duration cost reminder {product_name} {hs_code}"
        
        print(f"  📊 초통합 최적화 쿼리 수: {len(queries)}개 (기존 대비 ~90% 감소)")
        return queries

    def _infer_agency(self, url: str) -> Optional[str]:
        for agency, domain in self.agency_domains.items():
            if domain in url:
                return agency
        return None

    def _classify(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        data = {
            "validity": [],
            "renewal": [],
            "costs": [],
            "reminders": [],
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

            if any(k in lower for k in ["validity", "effective", "expires in", "valid for", "expiration"]):
                data["validity"].append({"title": title, "url": url, "snippet": content[:400], "agency": agency, "score": score})
            if any(k in lower for k in ["renewal", "renew", "procedure", "process", "reapply"]):
                data["renewal"].append({"title": title, "url": url, "snippet": content[:400], "agency": agency, "score": score})
            if any(k in lower for k in ["cost", "fee", "$", "usd"]):
                data["costs"].append({"title": title, "url": url, "snippet": content[:400], "agency": agency, "score": score})
            if any(k in lower for k in ["notice", "reminder", "prior to expiration", "advance notice"]):
                data["reminders"].append({"title": title, "url": url, "snippet": content[:400], "agency": agency, "score": score})

            if agency and agency not in data["agencies"]:
                data["agencies"].append(agency)
            data["sources"].append({"title": title, "url": url, "agency": agency or "Unknown", "score": score})
        return data

    def _synthesize(self, extracted: Dict[str, Any]) -> Dict[str, Any]:
        validity_hint = "unknown"
        text = " ".join(i["snippet"].lower() for i in extracted["validity"]) if extracted["validity"] else ""
        if any(k in text for k in ["1 year", "12 months"]):
            validity_hint = "1_year"
        elif any(k in text for k in ["2 years", "24 months"]):
            validity_hint = "2_years"
        elif any(k in text for k in ["3 years", "36 months"]):
            validity_hint = "3_years"

        renewal_hint = "procedure_required" if extracted["renewal"] else "unknown"

        cost_hint = "unknown"
        cost_text = " ".join(i["snippet"].lower() for i in extracted["costs"]) if extracted["costs"] else ""
        if any(k in cost_text for k in ["$50", "$100"]):
            cost_hint = "low"
        elif any(k in cost_text for k in ["$500", "$1000", "$1,000"]):
            cost_hint = "medium"
        elif any(k in cost_text for k in ["$5000", "$10,000"]):
            cost_hint = "high"

        reminder_hint = "recommended"
        if extracted["reminders"]:
            reminder_hint = "official_notice_referenced"

        return {
            "validity_hint": validity_hint,
            "renewal_hint": renewal_hint,
            "renewal_cost_band": cost_hint,
            "reminder_policy": reminder_hint
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
        summary = self._synthesize(extracted)

        return {
            "hs_code": hs_code,
            "product_name": product_name,
            "analysis_timestamp": datetime.utcnow().isoformat() + "Z",
            "agencies": extracted["agencies"],
            "validity": summary["validity_hint"],
            "renewal": {
                "procedure": summary["renewal_hint"],
                "cost_band": summary["renewal_cost_band"]
            },
            "reminders": summary["reminder_policy"],
            "sources": extracted["sources"],
            "evidence": extracted
        }


validity_service = ValidityService()


