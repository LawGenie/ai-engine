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
            a = agency.lower()
            queries[f"{agency}_validity"] = f"site:{a}.gov certificate validity period {product_name} HS {hs_code}"
            queries[f"{agency}_renewal"] = f"site:{a}.gov certification renewal {product_name} HS {hs_code}"
            queries[f"{agency}_duration"] = f"site:{a}.gov permit duration {product_name} HS {hs_code}"
            queries[f"{agency}_renewal_cost"] = f"site:{a}.gov renewal cost fee {product_name} HS {hs_code}"
            queries[f"{agency}_reminder"] = f"site:{a}.gov expiration notice reminder {product_name} HS {hs_code}"
        queries["general_validity"] = f"validity renewal duration cost reminder {product_name} HS {hs_code} site:.gov"
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
                res = await self.tavily.search(q, max_results=5)
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


