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
            
        # HS 코드 기반 기관 매핑
        self.hs_code_agency_mapping = self._build_hs_code_mapping()
            
        # API 키 예외 처리
        try:
            self.web_scraper = WebScraper()
        except Exception as e:
            print(f"⚠️ WebScraper 초기화 실패: {e}")
            self.web_scraper = None
        
        try:
            self.data_gov_api = DataGovAPIService()
        except Exception as e:
            print(f"⚠️ DataGovAPIService 초기화 실패: {e}")
            self.data_gov_api = None
        
        try:
            self.precedent_collector = self._init_cbp_collector()
        except Exception as e:
            print(f"⚠️ CBP Collector 초기화 실패: {e}")
            self.precedent_collector = None
        
        self.references_store_path = Path("reference_links.json")
    def _build_hs_code_mapping(self) -> Dict[str, Dict[str, Any]]:
        """HS 코드 기반 정부기관 매핑 구축"""
        return {
            # 화장품 및 미용 제품 (33xx)
                    "3304": {
                        "primary_agencies": ["FDA", "CPSC"],
                        "secondary_agencies": ["FTC"],
                        "search_keywords": ["cosmetic", "skincare", "beauty", "serum", "cream"],
                        "requirements": ["cosmetic registration", "ingredient safety", "labeling compliance", "consumer safety"]
                    },
            "3307": {
                "primary_agencies": ["FDA"],
                "secondary_agencies": ["DOT"],  # 운송 관련 (알코올 함유)
                "search_keywords": ["perfume", "toilet water", "fragrance", "alcohol"],
                "requirements": ["cosmetic registration", "alcohol content", "shipping requirements"]
            },
            
            # 식품 및 건강보조식품 (21xx, 19xx, 20xx)
            "2106": {
                "primary_agencies": ["FDA"],
                "secondary_agencies": ["USDA"],
                "search_keywords": ["dietary supplement", "ginseng", "extract", "health"],
                "requirements": ["prior notice", "DSHEA compliance", "cGMP", "health claims"]
            },
            "1904": {
                "primary_agencies": ["FDA"],
                "secondary_agencies": ["USDA"],
                "search_keywords": ["rice", "cereal", "prepared food", "instant"],
                "requirements": ["prior notice", "nutritional labeling", "allergen declaration"]
            },
            "1905": {
                "primary_agencies": ["FDA"],
                "secondary_agencies": ["USDA"],
                "search_keywords": ["snack", "cracker", "cookie", "baker"],
                "requirements": ["prior notice", "nutritional labeling", "FALCPA", "inspection"]
            },
            "1902": {
                "primary_agencies": ["FDA"],
                "secondary_agencies": ["USDA"],
                "search_keywords": ["pasta", "noodle", "instant", "ramen"],
                "requirements": ["prior notice", "nutritional labeling", "allergen", "sodium"]
            },
            "2005": {
                "primary_agencies": ["FDA"],
                "secondary_agencies": ["USDA"],
                "search_keywords": ["vegetable", "kimchi", "fermented", "preserved"],
                "requirements": ["prior notice", "HARPC", "acidified foods", "refrigeration"]
            },
            
            # 전자제품 및 통신 (84xx, 85xx)
            "8471": {
                "primary_agencies": ["FCC"],
                "secondary_agencies": ["CPSC"],
                "search_keywords": ["computer", "electronic", "device", "equipment"],
                "requirements": ["device authorization", "EMC", "safety standards"]
            },
            "8517": {
                "primary_agencies": ["FCC"],
                "secondary_agencies": ["CPSC"],
                "search_keywords": ["telephone", "communication", "wireless", "radio"],
                "requirements": ["equipment authorization", "radio frequency", "EMC"]
            },
            
            # 의류 및 섬유 (61xx, 62xx)
            "6109": {
                "primary_agencies": ["CPSC"],
                "secondary_agencies": ["FTC"],
                "search_keywords": ["t-shirt", "clothing", "textile", "garment"],
                "requirements": ["flammability", "care labeling", "fiber content"]
            },
            
            # 장난감 및 어린이 제품 (95xx)
            "9503": {
                "primary_agencies": ["CPSC"],
                "secondary_agencies": ["FDA"],
                "search_keywords": ["toy", "children", "play", "game"],
                "requirements": ["safety standards", "lead content", "small parts", "age grading"]
            }
        }

    def _get_target_agencies_for_hs_code(self, hs_code: str) -> Dict[str, Any]:
        """HS 코드를 기반으로 타겟 기관 및 검색 전략 반환"""
        # HS 코드에서 4자리 코드 추출
        hs_4digit = hs_code.split('.')[0] if '.' in hs_code else hs_code[:4]
        
        # 매핑에서 해당 코드 찾기
        mapping = self.hs_code_agency_mapping.get(hs_4digit, {})
        
        if not mapping:
            # 기본 매핑 (모든 기관 검색)
            return {
                "primary_agencies": ["FDA", "USDA", "EPA", "FCC", "CPSC"],
                "secondary_agencies": [],
                "search_keywords": [],
                "requirements": [],
                "confidence": 0.3
            }
        
        return {
            **mapping,
            "confidence": 0.9
        }

    def _extract_keywords_from_product(self, product_name: str, product_description: str = "") -> List[str]:
        """상품명과 설명에서 핵심 키워드 추출"""
        keywords = []
        
        # 상품명에서 키워드 추출
        name_keywords = [
            "vitamin", "serum", "cream", "extract", "ginseng", "rice", "noodle", 
            "kimchi", "snack", "perfume", "cosmetic", "supplement", "food",
            "electronic", "device", "toy", "clothing", "textile"
        ]
        
        product_text = f"{product_name} {product_description}".lower()
        for keyword in name_keywords:
            if keyword in product_text:
                keywords.append(keyword)
        
        # 상품명에서 직접 추출
        words = product_name.lower().split()
        for word in words:
            if len(word) > 3 and word not in ["premium", "korean", "instant", "pack"]:
                keywords.append(word)
        
        return list(set(keywords))  # 중복 제거

    def _build_hs_code_based_queries(self, product_name: str, hs_code: str, target_agencies: Dict[str, Any]) -> Dict[str, str]:
        """HS 코드 기반 기본 검색 쿼리 생성"""
        queries = {}
        
        # 주요 기관별 검색 (HS 코드 기반)
        for agency in target_agencies.get("primary_agencies", []):
            agency_lower = agency.lower()
            
            # 기본 요구사항 검색
            queries[f"{agency}_hs_requirements"] = f"site:{agency_lower}.gov import requirements {product_name} HS {hs_code}"
            
            # 세부 규정 검색 (기관별 특화)
            if agency == "FDA":
                if "cosmetic" in target_agencies.get("search_keywords", []):
                    queries[f"{agency}_hs_cosmetic"] = f"site:{agency_lower}.gov cosmetic regulations HS {hs_code} ingredient safety"
                if "food" in target_agencies.get("search_keywords", []):
                    queries[f"{agency}_hs_food"] = f"site:{agency_lower}.gov food import requirements HS {hs_code} prior notice"
                if "supplement" in target_agencies.get("search_keywords", []):
                    queries[f"{agency}_hs_supplement"] = f"site:{agency_lower}.gov dietary supplement requirements HS {hs_code} DSHEA"
            
            elif agency == "USDA":
                queries[f"{agency}_hs_agricultural"] = f"site:{agency_lower}.gov agricultural import requirements HS {hs_code}"
                queries[f"{agency}_hs_organic"] = f"site:{agency_lower}.gov organic certification HS {hs_code}"
            
            elif agency == "EPA":
                queries[f"{agency}_hs_chemical"] = f"site:{agency_lower}.gov chemical regulations HS {hs_code}"
                queries[f"{agency}_hs_environmental"] = f"site:{agency_lower}.gov environmental standards HS {hs_code}"
            
            elif agency == "FCC":
                queries[f"{agency}_hs_device"] = f"site:{agency_lower}.gov device authorization HS {hs_code}"
                queries[f"{agency}_hs_emc"] = f"site:{agency_lower}.gov EMC electromagnetic compatibility HS {hs_code}"
            
            elif agency == "CPSC":
                queries[f"{agency}_hs_safety"] = f"site:{agency_lower}.gov safety standards HS {hs_code}"
                queries[f"{agency}_hs_recall"] = f"site:{agency_lower}.gov recall information HS {hs_code}"
        
        return queries

    def _build_keyword_based_queries(self, product_name: str, keywords: List[str], target_agencies: Dict[str, Any]) -> Dict[str, str]:
        """키워드 기반 추가 검색 쿼리 생성"""
        queries = {}
        
        # 주요 기관별 키워드 검색
        for agency in target_agencies.get("primary_agencies", []):
            agency_lower = agency.lower()
            
            for keyword in keywords[:3]:  # 상위 3개 키워드만 사용
                # 키워드별 특화 검색
                if keyword in ["vitamin", "serum", "cream", "cosmetic"]:
                    queries[f"{agency}_kw_{keyword}"] = f"site:{agency_lower}.gov cosmetic regulations {keyword} import requirements"
                elif keyword in ["ginseng", "extract", "supplement"]:
                    queries[f"{agency}_kw_{keyword}"] = f"site:{agency_lower}.gov dietary supplement {keyword} import requirements"
                elif keyword in ["rice", "noodle", "kimchi", "food"]:
                    queries[f"{agency}_kw_{keyword}"] = f"site:{agency_lower}.gov food import requirements {keyword}"
                elif keyword in ["electronic", "device"]:
                    queries[f"{agency}_kw_{keyword}"] = f"site:{agency_lower}.gov device authorization {keyword}"
                elif keyword in ["toy", "clothing", "textile"]:
                    queries[f"{agency}_kw_{keyword}"] = f"site:{agency_lower}.gov safety standards {keyword}"
        
        return queries

    def _build_phase_specific_queries(self, product_name: str, hs_code: str, target_agencies: Dict[str, Any]) -> Dict[str, str]:
        """Phase 2-4 전용 검색 쿼리 생성"""
        queries = {}
        
        for agency in target_agencies.get("primary_agencies", []):
            agency_lower = agency.lower()
            
            # Phase 2: 검사 절차 및 방법
            queries[f"{agency}_phase2_testing"] = f"site:{agency_lower}.gov testing procedures {product_name} HS {hs_code}"
            queries[f"{agency}_phase2_inspection"] = f"site:{agency_lower}.gov inspection methods {product_name} HS {hs_code}"
            queries[f"{agency}_phase2_authorization"] = f"site:{agency_lower}.gov authorization procedures {product_name} HS {hs_code}"
            
            # Phase 3: 처벌 및 벌금 정보
            queries[f"{agency}_phase3_penalties"] = f"site:{agency_lower}.gov penalties violations {product_name} HS {hs_code}"
            queries[f"{agency}_phase3_enforcement"] = f"site:{agency_lower}.gov enforcement actions {product_name} HS {hs_code}"
            queries[f"{agency}_phase3_fines"] = f"site:{agency_lower}.gov civil penalties {product_name} HS {hs_code}"
            
            # Phase 4: 유효기간 및 갱신 정보
            queries[f"{agency}_phase4_validity"] = f"site:{agency_lower}.gov certificate validity period {product_name} HS {hs_code}"
            queries[f"{agency}_phase4_renewal"] = f"site:{agency_lower}.gov certification renewal {product_name} HS {hs_code}"
            queries[f"{agency}_phase4_duration"] = f"site:{agency_lower}.gov permit duration {product_name} HS {hs_code}"
        
        return queries

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
    
    async def search_requirements_hybrid(self, hs_code: str, product_name: str, product_description: str = "") -> Dict[str, Any]:
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
        
        # 2. Tavily Search (HS 코드 기반 + 키워드 기반 복합 검색)
        try:
            print(f"\n  🔍 2단계: HS 코드 기반 + 키워드 기반 복합 검색")
            
            # HS 코드 기반 타겟 기관 분석
            target_agencies = self._get_target_agencies_for_hs_code(hs_code)
            
            # 상품명/설명에서 키워드 추출
            keywords = self._extract_keywords_from_product(product_name, product_description)
            
            # HS 코드 기반 기본 검색 쿼리 생성
            hs_queries = self._build_hs_code_based_queries(product_name, hs_code, target_agencies)
            
            # 키워드 기반 추가 검색 쿼리 생성
            keyword_queries = self._build_keyword_based_queries(product_name, keywords, target_agencies)
            
            # Phase 2-4 전용 검색 쿼리 생성
            phase_queries = self._build_phase_specific_queries(product_name, hs_code, target_agencies)
            
            # 복합 검색 쿼리 병합
            web_queries = {**hs_queries, **keyword_queries, **phase_queries}
            
            print(f"  🎯 타겟 기관: {', '.join(target_agencies.get('primary_agencies', []))}")
            print(f"  📊 검색 신뢰도: {target_agencies.get('confidence', 0):.1%}")
            print(f"  🔑 추출된 키워드: {', '.join(keywords[:5])}")
            print(f"  🔍 총 검색 쿼리: {len(web_queries)}개 (HS코드 {len(hs_queries)}개 + 키워드 {len(keyword_queries)}개 + Phase2-4 {len(phase_queries)}개)")
            
            web_results = {}
            for query_key, query in web_queries.items():
                try:
                    if self.search_provider:
                        search_results = await self.search_provider.search(query, max_results=5)
                    else:
                        print(f"    ⚠️ 검색 프로바이더 없음: {query_key} 스킵됨")
                        search_results = []
                    # 결과 분류 (HS 코드 기반 + 키워드 기반)
                    category = "basic_requirements"
                    search_type = "hs_code" if "hs_" in query_key else "keyword"
                    
                    # 쿼리 키워드 기반 카테고리 분류 (Phase 1-4)
                    if any(keyword in query_key for keyword in ["cosmetic", "regulations", "standards", "limits", "restrictions", "safety"]):
                        category = "detailed_regulations"
                    elif any(keyword in query_key for keyword in ["testing", "inspection", "procedures", "authorization", "phase2"]):
                        category = "testing_procedures"
                    elif any(keyword in query_key for keyword in ["penalties", "enforcement", "violations", "recall", "phase3"]):
                        category = "penalties_enforcement"
                    elif any(keyword in query_key for keyword in ["validity", "renewal", "duration", "period", "phase4"]):
                        category = "validity_periods"
                    
                    # 기관 추출
                    agency = query_key.split("_")[0].upper()
                    
                    web_results[query_key] = {
                        "query": query,
                        "results": search_results,
                        "urls": [r.get("url") for r in search_results if r.get("url")],
                        "agency": agency,
                        "category": category,
                        "search_type": search_type,
                        "result_count": len(search_results),
                        "target_confidence": target_agencies.get("confidence", 0.5)
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
        combined_results["target_agencies"] = target_agencies  # 타겟 기관 정보 추가
        combined_results["extracted_keywords"] = keywords  # 추출된 키워드 정보 추가
        results["combined_results"] = combined_results
        
        print(f"\n✅ [HS 코드 + 키워드 복합 검색] 완료")
        print(f"  🔍 검색 방법: {', '.join(results['search_methods'])}")
        print(f"  🎯 타겟 기관: {', '.join(target_agencies.get('primary_agencies', []))}")
        print(f"  📊 검색 신뢰도: {target_agencies.get('confidence', 0):.1%}")
        print(f"  🔑 추출된 키워드: {', '.join(keywords[:5])}")
        print(f"  📋 총 요구사항: {combined_results.get('total_requirements', 0)}개")
        print(f"  🏆 인증요건: {combined_results.get('total_certifications', 0)}개")
        print(f"  📄 필요서류: {combined_results.get('total_documents', 0)}개")
        
        # 카테고리별 결과 출력
        category_stats = combined_results.get('category_stats', {})
        print(f"  📊 카테고리별 검색 결과:")
        print(f"    🔍 기본 요구사항: {category_stats.get('basic_requirements', 0)}개")
        print(f"    📋 세부 규정: {category_stats.get('detailed_regulations', 0)}개")
        print(f"    🧪 검사 절차: {category_stats.get('testing_procedures', 0)}개")
        print(f"    ⚖️ 처벌 정보: {category_stats.get('penalties_enforcement', 0)}개")
        print(f"    ⏰ 유효기간: {category_stats.get('validity_periods', 0)}개")
        
        return results
    
    def _extract_requirements_from_web_results(self, web_results: Dict[str, Any]) -> Dict[str, Any]:
        """웹 검색 결과에서 요구사항 추출"""
        extracted_requirements = {
            "certifications": [],
            "documents": [],
            "sources": [],
            "detailed_regulations": [],
            "testing_procedures": [],
            "penalties_enforcement": [],
            "validity_periods": []
        }
        
        for query_key, result in web_results.items():
            if "error" in result:
                continue
                
            agency = result.get("agency", "Unknown")
            category = result.get("category", "basic_requirements")
            search_results = result.get("results", [])
            
            for search_result in search_results:
                url = search_result.get("url", "")
                title = search_result.get("title", "")
                content = search_result.get("content", "")
                score = search_result.get("score", 0)
                
                # 공식 사이트 vs 기타 사이트 구분
                is_official = any(domain in url for domain in [".gov", ".fda.gov", ".usda.gov", ".epa.gov", ".fcc.gov", ".cbp.gov", ".cpsc.gov"])
                source_type = "공식 사이트" if is_official else "기타 사이트"
                
                # 신뢰도 계산 (공식 사이트는 높은 점수)
                confidence = score * (1.2 if is_official else 0.8)
                
                # 카테고리별 요구사항 추출
                if category == "basic_requirements":
                    # 기본 요구사항: import, requirements, regulations 등이 포함된 경우
                    if any(keyword in content.lower() for keyword in ["import", "requirements", "regulations", "compliance", "standards"]):
                        extracted_requirements["certifications"].append({
                            "name": f"{agency} 수입 요구사항 ({title[:50]}...)",
                            "required": True,
                            "description": f"{source_type}에서 확인된 {agency} 수입 요구사항",
                            "agency": agency,
                            "url": url,
                            "confidence": confidence,
                            "source_type": source_type
                        })
                
                elif category == "detailed_regulations":
                    if any(keyword in content.lower() for keyword in ["regulation", "standard", "limit", "restriction"]):
                        extracted_requirements["detailed_regulations"].append({
                            "name": f"{agency} 세부 규정 ({title[:50]}...)",
                            "description": f"{source_type}에서 확인된 {agency} 세부 규정",
                            "agency": agency,
                            "url": url,
                            "confidence": confidence,
                            "source_type": source_type
                        })
                
                elif category == "testing_procedures":
                    if any(keyword in content.lower() for keyword in ["test", "inspection", "procedure", "authorization"]):
                        extracted_requirements["testing_procedures"].append({
                            "name": f"{agency} 검사 절차 ({title[:50]}...)",
                            "description": f"{source_type}에서 확인된 {agency} 검사 절차",
                            "agency": agency,
                            "url": url,
                            "confidence": confidence,
                            "source_type": source_type
                        })
                
                elif category == "penalties_enforcement":
                    if any(keyword in content.lower() for keyword in ["penalty", "enforcement", "violation", "fine"]):
                        extracted_requirements["penalties_enforcement"].append({
                            "name": f"{agency} 처벌 정보 ({title[:50]}...)",
                            "description": f"{source_type}에서 확인된 {agency} 처벌 정보",
                            "agency": agency,
                            "url": url,
                            "confidence": confidence,
                            "source_type": source_type
                        })
                
                elif category == "validity_periods":
                    if any(keyword in content.lower() for keyword in ["validity", "renewal", "duration", "period"]):
                        extracted_requirements["validity_periods"].append({
                            "name": f"{agency} 유효기간 ({title[:50]}...)",
                            "description": f"{source_type}에서 확인된 {agency} 유효기간 정보",
                            "agency": agency,
                            "url": url,
                            "confidence": confidence,
                            "source_type": source_type
                        })
                
                # 출처 정보 추가
                extracted_requirements["sources"].append({
                    "title": title,
                    "url": url,
                    "type": source_type,
                    "relevance": "high" if confidence > 0.7 else "medium" if confidence > 0.5 else "low",
                    "agency": agency,
                    "category": category
                })
        
        return extracted_requirements

    def _combine_search_results(self, api_results: Dict[str, Any], web_results: Dict[str, Any]) -> Dict[str, Any]:
        """API와 웹 검색 결과 통합"""
        # 웹 검색 결과에서 요구사항 추출
        web_requirements = self._extract_requirements_from_web_results(web_results)
        
        combined = {
            "certifications": [],
            "documents": [],
            "sources": [],
            "detailed_regulations": [],
            "testing_procedures": [],
            "penalties_enforcement": [],
            "validity_periods": [],
            "total_requirements": 0,
            "total_certifications": 0,
            "total_documents": 0,
            "agencies_found": [],
            "category_stats": {
                "basic_requirements": 0,
                "detailed_regulations": 0,
                "testing_procedures": 0,
                "penalties_enforcement": 0,
                "validity_periods": 0
            },
            "search_sources": {
                "api_success": "agencies" in api_results and "error" not in api_results,
                "web_success": len(web_results) > 0 and "error" not in web_results
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
        
        # 웹 검색 결과 통합 (새로운 추출 로직 사용)
        combined["certifications"].extend(web_requirements["certifications"])
        combined["documents"].extend(web_requirements["documents"])
        combined["sources"].extend(web_requirements["sources"])
        combined["detailed_regulations"].extend(web_requirements["detailed_regulations"])
        combined["testing_procedures"].extend(web_requirements["testing_procedures"])
        combined["penalties_enforcement"].extend(web_requirements["penalties_enforcement"])
        combined["validity_periods"].extend(web_requirements["validity_periods"])
        
        # 웹 검색에서 찾은 기관들 추가
        web_agencies = set()
        for source in web_requirements["sources"]:
            agency = source.get("agency", "Unknown")
            if agency != "Unknown":
                web_agencies.add(agency)
        
        for agency in web_agencies:
            if agency not in combined["agencies_found"]:
                combined["agencies_found"].append(agency)
        
        # 카테고리별 통계 계산
        combined["category_stats"]["basic_requirements"] = len(web_requirements["certifications"])
        combined["category_stats"]["detailed_regulations"] = len(web_requirements["detailed_regulations"])
        combined["category_stats"]["testing_procedures"] = len(web_requirements["testing_procedures"])
        combined["category_stats"]["penalties_enforcement"] = len(web_requirements["penalties_enforcement"])
        combined["category_stats"]["validity_periods"] = len(web_requirements["validity_periods"])
        
        # 통계 계산
        combined["total_certifications"] = len(combined["certifications"])
        combined["total_documents"] = len(combined["documents"])
        combined["total_requirements"] = combined["total_certifications"] + combined["total_documents"]
        
        return combined
