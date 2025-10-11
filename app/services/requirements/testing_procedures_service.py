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
    """검사 절차 및 방법 분석 전용 서비스"""

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

    def _build_queries(self, hs_code: str, product_name: str) -> Dict[str, str]:
        queries: Dict[str, str] = {}
        for agency in self.agency_domains.keys():
            agency_l = agency.lower()
            queries[f"{agency}_testing_procedures"] = f"site:{agency_l}.gov testing procedures {product_name} HS {hs_code}"
            queries[f"{agency}_inspection_methods"] = f"site:{agency_l}.gov inspection methods {product_name} HS {hs_code}"
            queries[f"{agency}_sampling_policy"] = f"site:{agency_l}.gov sampling policy {product_name} HS {hs_code}"
            queries[f"{agency}_frequency_schedule"] = f"site:{agency_l}.gov inspection frequency schedule {product_name} HS {hs_code}"
            queries[f"{agency}_cost_time"] = f"site:{agency_l}.gov inspection cost time {product_name} HS {hs_code}"
        queries["general_testing_terms"] = f"testing inspection sampling cost time {product_name} HS {hs_code} site:.gov"
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
            content = (r.get("content", "") or "")
            score = r.get("score", 0)
            agency = self._infer_agency(url)
            lower = content.lower()

            if any(k in lower for k in ["every import", "per shipment", "per import", "annual", "yearly", "sampling", "random sample", "periodic"]):
                data["cycles"].append({"snippet": content[:300], "title": title, "url": url, "agency": agency, "score": score})
            if any(k in lower for k in ["inspection", "visual", "physical", "chemical", "analysis", "laboratory", "lab test", "testing method"]):
                data["methods"].append({"snippet": content[:300], "title": title, "url": url, "agency": agency, "score": score})
            if any(k in lower for k in ["fee", "cost", "charge", "payment", "$", "usd"]):
                data["costs"].append({"snippet": content[:300], "title": title, "url": url, "agency": agency, "score": score})
            if any(k in lower for k in ["within", "days", "weeks", "processing time", "turnaround", "timeline"]):
                data["durations"].append({"snippet": content[:300], "title": title, "url": url, "agency": agency, "score": score})

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
            text = " ".join(i["snippet"].lower() for i in extracted["costs"])
            if any(k in text for k in ["$50", "$100", "fee"]):
                cost_band = "low"
            if any(k in text for k in ["$500", "$1,000", "laboratory"]):
                cost_band = "medium"
            if any(k in text for k in ["$5,000", "$10,000", "comprehensive"]):
                cost_band = "high"

        duration_band = "unknown"
        if extracted["durations"]:
            text = " ".join(i["snippet"].lower() for i in extracted["durations"])
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
                res = await self.tavily.search(q, max_results=5)
                aggregate_results.extend(res)
            except Exception:
                continue

        extracted = self._classify_and_extract(aggregate_results)
        estimates = self._estimate_cost_time(extracted)

        cycle_label = "unknown"
        joined_cycles = " ".join(i["snippet"].lower() for i in extracted["cycles"])
        if any(k in joined_cycles for k in ["every import", "per shipment", "per import"]):
            cycle_label = "per_import"
        elif any(k in joined_cycles for k in ["annual", "yearly"]):
            cycle_label = "annual"
        elif any(k in joined_cycles for k in ["sampling", "random sample", "periodic"]):
            cycle_label = "sampling"

        methods_label = list({
            ("chemical" if any(k in (m["snippet"].lower()) for k in ["chemical", "analysis", "lab"]) else None) or
            ("physical" if any(k in (m["snippet"].lower()) for k in ["visual", "physical", "inspection"]) else None)
            for m in extracted["methods"]
        } - {None})

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


