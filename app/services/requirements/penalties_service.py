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
            queries[f"{agency}_penalties"] = f"site:{a}.gov penalties violations {product_name} HS {hs_code}"
            queries[f"{agency}_enforcement"] = f"site:{a}.gov enforcement actions {product_name} HS {hs_code}"
            queries[f"{agency}_fines"] = f"site:{a}.gov civil penalties fines {product_name} HS {hs_code}"
            queries[f"{agency}_seizure_importban"] = f"site:{a}.gov seizure import ban refuse admission {product_name} HS {hs_code}"
        queries["general_penalties"] = f"penalties enforcement fines seizure import ban {product_name} HS {hs_code} site:.gov"
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
                res = await self.tavily.search(q, max_results=5)
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


