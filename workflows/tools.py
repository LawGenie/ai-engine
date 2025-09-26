"""
LangGraph Tools for Requirements Analysis
특정 작업을 수행하는 도구들
"""

from typing import Dict, Any, List, Optional
import asyncio
import httpx
from pathlib import Path
import json
from pypdf import PdfReader
from io import BytesIO
from datetime import datetime
import importlib.util
import sys
from abc import ABC, abstractmethod
from app.services.requirements.tavily_search import TavilySearchService
from app.services.requirements.web_scraper import WebScraper
from app.services.requirements.data_gov_api import DataGovAPIService


class SearchProvider(ABC):
    """검색 프로바이더 추상화 클래스"""
    
    @abstractmethod
    async def search(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """검색 실행"""
        pass
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """프로바이더 이름"""
        pass


class TavilyProvider(SearchProvider):
    """Tavily 검색 프로바이더"""
    
    def __init__(self):
        self.service = TavilySearchService()
    
    async def search(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        try:
            results = await self.service.search(query, **kwargs)
            return results if results else []
        except Exception as e:
            print(f"❌ Tavily 검색 실패: {e}")
            return []
    
    @property
    def provider_name(self) -> str:
        return "tavily"


class DisabledProvider(SearchProvider):
    """검색 비활성화 프로바이더 (Tavily 432 에러 시 사용)"""
    
    async def search(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        print(f"🔇 검색 비활성화 모드: '{query}' 스킵됨")
        return []
    
    @property
    def provider_name(self) -> str:
        return "disabled"


class RequirementsTools:
    """요구사항 분석을 위한 LangGraph 도구들"""
    
    def __init__(self, search_provider: Optional[SearchProvider] = None):
        # 검색 프로바이더 설정 (기본값: Tavily, 환경변수로 제어 가능)
        import os
        provider_mode = os.getenv("SEARCH_PROVIDER", "tavily").lower()
        
        if provider_mode == "disabled":
            self.search_provider = DisabledProvider()
        else:
            self.search_provider = TavilyProvider()
        
        # 외부에서 제공된 프로바이더가 있으면 사용
        if search_provider:
            self.search_provider = search_provider
            
        self.web_scraper = WebScraper()
        self.data_gov_api = DataGovAPIService()
        self.precedent_collector = self._init_cbp_collector()
        self.references_store_path = Path("reference_links.json")
    def _init_cbp_collector(self):
        """precedents-analysis/cbp_scraper.py의 CBPDataCollector를 동적 로드한다."""
        try:
            base_dir = Path(__file__).resolve().parents[1]  # ai-engine/app
            project_root = base_dir.parent  # ai-engine
            target_path = project_root / "precedents-analysis" / "cbp_scraper.py"
            if not target_path.exists():
                return None
            spec = importlib.util.spec_from_file_location("cbp_scraper", str(target_path))
            if spec is None or spec.loader is None:
                return None
            module = importlib.util.module_from_spec(spec)
            sys.modules["cbp_scraper"] = module
            spec.loader.exec_module(module)
            if hasattr(module, "CBPDataCollector"):
                return module.CBPDataCollector()
        except Exception:
            return None
        return None

        
        # 기관별 도메인 매핑
        self.agency_domains = {
            "FDA": "fda.gov",
            "FCC": "fcc.gov", 
            "CBP": "cbp.gov",
            "USDA": "usda.gov",
            "EPA": "epa.gov",
            "CPSC": "cpsc.gov",
            "KCS": "customs.go.kr",  # 한국 관세청
            "MFDS": "mfds.go.kr",    # 식품의약품안전처
            "MOTIE": "motie.go.kr"   # 산업통상자원부
        }
    
    async def search_agency_documents(self, agency: str, query: str, max_results: int = 5) -> Dict[str, Any]:
        """기관별 문서 검색 도구 (통합)"""
        print(f"🔧 [TOOL] {agency} 문서 검색: {query}")
        
        results = await self.search_provider.search(query, max_results=max_results)
        
        # 기관별 도메인 필터링
        agency_domain = self.agency_domains.get(agency, "")
        agency_results = []
        
        for result in results:
            url = result.get("url", "")
            if agency_domain in url:
                agency_results.append(result)
                print(f"  ✅ {agency} 공식 문서 발견: {result.get('title', 'No title')}")
            else:
                print(f"  ❌ {agency} 외부 문서 제외: {result.get('title', 'No title')}")
        
        return {
            "agency": agency,
            "query": query,
            "total_results": len(results),
            "agency_results": agency_results,
            "selected_url": agency_results[0]["url"] if agency_results else None,
            "domain": agency_domain
        }
    
    async def search_fda_documents(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        """FDA 관련 문서 검색 도구 (하위 호환성)"""
        return await self.search_agency_documents("FDA", query, max_results)
    
    # 미국 정부 기관들
    async def search_fcc_documents(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        """FCC 관련 문서 검색 도구"""
        return await self.search_agency_documents("FCC", query, max_results)
    
    async def search_cbp_documents(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        """CBP 관련 문서 검색 도구"""
        return await self.search_agency_documents("CBP", query, max_results)
    
    async def search_usda_documents(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        """USDA 관련 문서 검색 도구"""
        return await self.search_agency_documents("USDA", query, max_results)
    
    async def search_epa_documents(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        """EPA 관련 문서 검색 도구"""
        return await self.search_agency_documents("EPA", query, max_results)
    
    async def search_cpsc_documents(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        """CPSC 관련 문서 검색 도구"""
        return await self.search_agency_documents("CPSC", query, max_results)
    
    # 한국 정부 기관들
    async def search_kcs_documents(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        """한국 관세청 관련 문서 검색 도구"""
        return await self.search_agency_documents("KCS", query, max_results)
    
    async def search_mfds_documents(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        """식품의약품안전처 관련 문서 검색 도구"""
        return await self.search_agency_documents("MFDS", query, max_results)
    
    async def search_motie_documents(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        """산업통상자원부 관련 문서 검색 도구"""
        return await self.search_agency_documents("MOTIE", query, max_results)
    
    async def scrape_document(self, agency: str, url: str, hs_code: str) -> Dict[str, Any]:
        """특정 문서 스크래핑 도구 (확장)"""
        print(f"🔧 [TOOL] {agency} 문서 스크래핑")
        print(f"  URL: {url}")
        print(f"  HS코드: {hs_code}")
        
        try:
            # 기관별 스크래핑 메서드 매핑
            scraper_methods = {
                "FDA": "scrape_fda_requirements",
                "FCC": "scrape_fcc_requirements", 
                "CBP": "scrape_cbp_requirements",
                "USDA": "scrape_usda_requirements",
                "EPA": "scrape_epa_requirements",
                "CPSC": "scrape_cpsc_requirements",
                "KCS": "scrape_kcs_requirements",
                "MFDS": "scrape_mfds_requirements",
                "MOTIE": "scrape_motie_requirements"
            }
            
            method_name = scraper_methods.get(agency)
            if not method_name:
                return {"error": f"Unknown agency: {agency}"}
            
            # 동적으로 스크래핑 메서드 호출
            scraper_method = getattr(self.web_scraper, method_name, None)
            if not scraper_method:
                return {"error": f"Scraper method not implemented for {agency}"}
            
            result = await scraper_method(hs_code, url)
            
            # 스크래핑 결과 상세 로깅
            certs = result.get("certifications", [])
            docs = result.get("documents", [])
            sources = result.get("sources", [])
            
            print(f"  ✅ {agency} 스크래핑 성공:")
            print(f"    📋 인증요건: {len(certs)}개")
            for i, cert in enumerate(certs, 1):
                print(f"      {i}. {cert.get('name', 'Unknown')} ({cert.get('agency', 'Unknown')})")
                print(f"         설명: {cert.get('description', 'No description')}")
            
            print(f"    📄 필요서류: {len(docs)}개")
            for i, doc in enumerate(docs, 1):
                print(f"      {i}. {doc.get('name', 'Unknown')}")
                print(f"         설명: {doc.get('description', 'No description')}")
            
            print(f"    📚 출처: {len(sources)}개")
            for i, source in enumerate(sources, 1):
                print(f"      {i}. {source.get('title', 'Unknown')} ({source.get('type', 'Unknown')})")
            
            return result
            
        except Exception as e:
            print(f"  ❌ {agency} 스크래핑 실패: {e}")
            return {
                "agency": agency,
                "error": str(e),
                "certifications": [],
                "documents": [],
                "sources": []
            }

    async def get_cbp_precedents(self, hs_code: str) -> Dict[str, Any]:
        """CBP 판례/결정 사례 조회 도구."""
        try:
            if not self.precedent_collector:
                return {"hs_code": hs_code, "count": 0, "precedents": [], "error": "cbp_collector_not_available"}
            precedents = await self.precedent_collector.get_precedents_by_hs_code(hs_code)
            return {
                "hs_code": hs_code,
                "count": len(precedents),
                "precedents": precedents
            }
        except Exception as e:
            return {"hs_code": hs_code, "count": 0, "precedents": [], "error": str(e)}

    async def summarize_pdf(self, url: str, max_pages: int = 5) -> Dict[str, Any]:
        """PDF 문서를 다운로드하여 앞부분을 요약(발췌)한다."""
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data = BytesIO(resp.content)
                reader = PdfReader(data)
                num_pages = min(len(reader.pages), max_pages)
                text_chunks: List[str] = []
                for i in range(num_pages):
                    try:
                        text_chunks.append(reader.pages[i].extract_text() or "")
                    except Exception:
                        continue
                combined = "\n".join([t.strip() for t in text_chunks if t and t.strip()])
                preview = (combined[:1200] + "…") if len(combined) > 1200 else combined
                return {
                    "url": url,
                    "pages_read": num_pages,
                    "excerpt": preview,
                    "char_count": len(preview)
                }
        except Exception as e:
            return {"url": url, "error": str(e)}

    def save_reference_links(self, hs_code: str, product_name: str, search_results: Dict[str, Any]) -> Dict[str, Any]:
        """검색된 참고 링크들을 로컬 JSON에 저장/병합한다."""
        try:
            existing: Dict[str, Any] = {}
            if self.references_store_path.exists():
                existing = json.loads(self.references_store_path.read_text(encoding="utf-8"))
            key = f"{hs_code}:{product_name}"
            payload = {
                "hs_code": hs_code,
                "product_name": product_name,
                "saved_at": datetime.utcnow().isoformat() + "Z",
                "agencies": {}
            }
            for k, v in search_results.items():
                agency = v.get("agency") or k
                urls = v.get("urls", [])
                payload["agencies"].setdefault(agency, {"urls": []})
                # 병합
                payload["agencies"][agency]["urls"] = list({*payload["agencies"][agency]["urls"], *urls})
            existing[key] = payload
            self.references_store_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
            return {"saved": True, "reference_key": key, "agencies": list(payload["agencies"].keys())}
        except Exception as e:
            return {"saved": False, "error": str(e)}
    
    async def analyze_requirements(self, requirements_data: Dict[str, Any]) -> Dict[str, Any]:
        """요구사항 분석 도구 (확장)"""
        print(f"🔧 [TOOL] 요구사항 분석 시작")
        
        certifications = requirements_data.get("certifications", [])
        documents = requirements_data.get("documents", [])
        sources = requirements_data.get("sources", [])
        
        # 기본 분석 통계
        total_certs = len(certifications)
        total_docs = len(documents)
        total_sources = len(sources)
        
        # 기관별 통계
        agency_stats = {}
        for cert in certifications:
            agency = cert.get("agency", "Unknown")
            agency_stats[agency] = agency_stats.get(agency, 0) + 1
        
        # 우선순위 분석
        high_priority = [c for c in certifications if c.get("priority") == "high"]
        required_docs = [d for d in documents if d.get("required", False)]
        
        # 품질 지표 계산
        completeness_score = min(1.0, (total_certs + total_docs) / 10)  # 0-1 스케일
        coverage_ratio = len(agency_stats) / len(self.agency_domains)  # 기관 커버리지
        
        # 복잡도 분석
        complexity_factors = []
        if total_certs > 5:
            complexity_factors.append("다중 인증 요구")
        if len(agency_stats) > 3:
            complexity_factors.append("다기관 규제")
        if any("critical" in str(cert).lower() for cert in certifications):
            complexity_factors.append("중요 인증 요구")
        
        compliance_complexity = "simple" if len(complexity_factors) == 0 else "moderate" if len(complexity_factors) <= 2 else "complex"
        
        # 비용 추정 (간단한 휴리스틱)
        estimated_cost_low = total_certs * 100 + total_docs * 50  # USD
        estimated_cost_high = total_certs * 500 + total_docs * 200
        
        # 리스크 분석
        risk_factors = []
        if total_certs == 0:
            risk_factors.append("인증 요구사항 불명확")
        if len(required_docs) > 10:
            risk_factors.append("서류 요구사항 과다")
        if coverage_ratio < 0.3:
            risk_factors.append("기관 커버리지 부족")
        
        overall_risk_level = "low" if len(risk_factors) == 0 else "medium" if len(risk_factors) <= 2 else "high"
        
        print(f"  📊 분석 결과:")
        print(f"    📋 총 인증요건: {total_certs}개")
        print(f"    📄 총 필요서류: {total_docs}개")
        print(f"    📚 총 출처: {total_sources}개")
        print(f"    🏢 기관별 인증요건:")
        for agency, count in agency_stats.items():
            print(f"      • {agency}: {count}개")
        print(f"    ⚠️ 고우선순위 인증요건: {len(high_priority)}개")
        print(f"    📋 필수 서류: {len(required_docs)}개")
        print(f"    📈 완성도 점수: {completeness_score:.2f}")
        print(f"    🎯 기관 커버리지: {coverage_ratio:.2f}")
        print(f"    ⚡ 복잡도: {compliance_complexity}")
        print(f"    💰 예상 비용: ${estimated_cost_low}-${estimated_cost_high}")
        print(f"    ⚠️ 리스크 레벨: {overall_risk_level}")
        
        return {
            # 기본 통계
            "total_certifications": total_certs,
            "total_documents": total_docs,
            "total_sources": total_sources,
            "agency_stats": agency_stats,
            "high_priority_count": len(high_priority),
            "required_docs_count": len(required_docs),
            
            # 품질 지표
            "quality_metrics": {
                "completeness_score": completeness_score,
                "coverage_ratio": coverage_ratio,
                "compliance_complexity": compliance_complexity,
                "complexity_factors": complexity_factors
            },
            
            # 비용 분석
            "cost_analysis": {
                "estimated_cost_low": estimated_cost_low,
                "estimated_cost_high": estimated_cost_high,
                "currency": "USD"
            },
            
            # 리스크 분석
            "risk_analysis": {
                "overall_risk_level": overall_risk_level,
                "risk_factors": risk_factors
            },
            
            "analysis_complete": True
        }
    
    async def search_requirements_hybrid(self, hs_code: str, product_name: str) -> Dict[str, Any]:
        """하이브리드 검색: Data.gov API + Tavily Search"""
        print(f"\n🚀 [HYBRID] 하이브리드 검색 시작")
        print(f"  📋 HS코드: {hs_code}")
        print(f"  📦 상품명: {product_name}")
        
        results = {
            "hs_code": hs_code,
            "product_name": product_name,
            "search_timestamp": None,
            "api_results": {},
            "web_results": {},
            "combined_results": {},
            "search_methods": []
        }
        
        # 1. Data.gov API 검색 (HS코드 직접 검색)
        try:
            print(f"\n  🔍 1단계: Data.gov API 검색")
            api_results = await self.data_gov_api.search_requirements_by_hs_code(hs_code, product_name)
            results["api_results"] = api_results
            results["search_methods"].append("data_gov_api")
            print(f"    ✅ API 검색 완료: {api_results.get('total_requirements', 0)}개 요구사항")
        except Exception as e:
            print(f"    ❌ API 검색 실패: {e}")
            results["api_results"] = {"error": str(e)}
        
        # 2. Tavily Search (웹 검색)
        try:
            print(f"\n  🔍 2단계: Tavily Search 웹 검색")
            # 8자리와 6자리 HS코드로 검색
            hs_code_8digit = hs_code
            hs_code_6digit = ".".join(hs_code.split(".")[:2]) if "." in hs_code else hs_code
            
            web_queries = {
                f"FDA_8digit": f"site:fda.gov import requirements {product_name} HS {hs_code_8digit}",
                f"USDA_8digit": f"site:usda.gov agricultural import requirements {product_name} HS {hs_code_8digit}",
                f"EPA_8digit": f"site:epa.gov environmental regulations {product_name} HS {hs_code_8digit}",
                f"FCC_8digit": f"site:fcc.gov device authorization requirements {product_name} HS {hs_code_8digit}",
                f"CBP_8digit": f"site:cbp.gov import documentation requirements HS {hs_code_8digit} {product_name}",
                f"CPSC_8digit": f"site:cpsc.gov consumer product safety {product_name} HS {hs_code_8digit}",
                f"FDA_6digit": f"site:fda.gov import requirements {product_name} HS {hs_code_6digit}",
                f"USDA_6digit": f"site:usda.gov agricultural import requirements {product_name} HS {hs_code_6digit}",
                f"EPA_6digit": f"site:epa.gov environmental regulations {product_name} HS {hs_code_6digit}",
                f"FCC_6digit": f"site:fcc.gov device authorization requirements {product_name} HS {hs_code_6digit}",
                f"CBP_6digit": f"site:cbp.gov import documentation requirements HS {hs_code_6digit} {product_name}",
                f"CPSC_6digit": f"site:cpsc.gov consumer product safety {product_name} HS {hs_code_6digit}"
            }
            
            web_results = {}
            for query_key, query in web_queries.items():
                try:
                    search_results = await self.search_provider.search(query, max_results=5)
                    web_results[query_key] = {
                        "query": query,
                        "results": search_results,
                        "urls": [r.get("url") for r in search_results if r.get("url")],
                        "hs_code_type": "8digit" if "8digit" in query_key else "6digit",
                        "agency": query_key.split("_")[0]
                    }
                except Exception as e:
                    web_results[query_key] = {"error": str(e)}
            
            results["web_results"] = web_results
            results["search_methods"].append("tavily_search")
            print(f"    ✅ 웹 검색 완료: {len(web_results)}개 쿼리")
            
        except Exception as e:
            print(f"    ❌ 웹 검색 실패: {e}")
            results["web_results"] = {"error": str(e)}
        
        # 3. 결과 통합
        print(f"\n  🔄 3단계: 결과 통합")
        combined_results = self._combine_search_results(results["api_results"], results["web_results"])
        results["combined_results"] = combined_results
        
        print(f"\n✅ [HYBRID] 검색 완료")
        print(f"  🔍 검색 방법: {', '.join(results['search_methods'])}")
        print(f"  📋 총 요구사항: {combined_results.get('total_requirements', 0)}개")
        print(f"  🏆 인증요건: {combined_results.get('total_certifications', 0)}개")
        print(f"  📄 필요서류: {combined_results.get('total_documents', 0)}개")
        
        return results
    
    def _combine_search_results(self, api_results: Dict[str, Any], web_results: Dict[str, Any]) -> Dict[str, Any]:
        """API와 웹 검색 결과 통합"""
        combined = {
            "certifications": [],
            "documents": [],
            "sources": [],
            "total_requirements": 0,
            "total_certifications": 0,
            "total_documents": 0,
            "agencies_found": [],
            "search_sources": {
                "api_success": "api_results" in api_results and "error" not in api_results,
                "web_success": "web_results" in web_results and "error" not in web_results
            }
        }
        
        # API 결과 통합
        if "agencies" in api_results and "error" not in api_results:
            agencies = api_results.get("agencies", {})
            for agency, data in agencies.items():
                if data.get("status") == "success":
                    combined["certifications"].extend(data.get("certifications", []))
                    combined["documents"].extend(data.get("documents", []))
                    combined["sources"].extend(data.get("sources", []))
                    combined["agencies_found"].append(agency)
        
        # 웹 결과 통합 (기본 요구사항 추가)
        if "web_results" in web_results and "error" not in web_results:
            # 웹 검색에서 찾은 기관들에 대한 기본 요구사항 추가
            found_agencies = set()
            for query_key, data in web_results.items():
                if "error" not in data and data.get("urls"):
                    agency = data.get("agency")
                    found_agencies.add(agency)
            
            # 찾은 기관들에 대한 기본 요구사항 추가
            for agency in found_agencies:
                if agency not in combined["agencies_found"]:
                    combined["certifications"].append({
                        "name": f"{agency} 기본 등록 요구사항",
                        "required": True,
                        "description": f"{agency}에서 요구하는 기본 등록 요구사항",
                        "agency": agency,
                        "url": f"https://www.{agency.lower()}.gov"
                    })
                    combined["agencies_found"].append(agency)
        
        # 통계 계산
        combined["total_certifications"] = len(combined["certifications"])
        combined["total_documents"] = len(combined["documents"])
        combined["total_requirements"] = combined["total_certifications"] + combined["total_documents"]
        
        return combined
