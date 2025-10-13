"""
LangGraph Nodes for Requirements Analysis
각 단계별로 처리하는 노드들
(Updated: 2025-10-10 - LLM 요약 추가, 타입 에러 수정)
(Updated: 2025-10-11 - Phase 2-4 전문 서비스 연결)
"""

from typing import Dict, Any, List
from .tools import RequirementsTools
from app.services.requirements.keyword_extractor import KeywordExtractor, HfKeywordExtractor, OpenAiKeywordExtractor
from app.services.requirements.tavily_search import TavilySearchService
from app.services.requirements.web_scraper import WebScraper
from app.services.requirements.error_handler import error_handler, WorkflowError, ErrorSeverity, ErrorRecoveryStrategy
from app.models.requirement_models import RequirementAnalysisRequest
from datetime import datetime
import asyncio

# Phase 2-4 전문 서비스 import
from app.services.requirements.detailed_regulations_service import detailed_regulations_service
from app.services.requirements.testing_procedures_service import testing_procedures_service
from app.services.requirements.penalties_service import penalties_service
from app.services.requirements.validity_service import validity_service
from app.services.requirements.cross_validation_service import CrossValidationService


class RequirementsNodes:
    """요구사항 분석을 위한 LangGraph 노드들"""
    
    def __init__(self):
        # RequirementsTools에서 프로바이더를 가져와서 사용
        self.tools = RequirementsTools()
        self.web_scraper = WebScraper()
        self.keyword_extractor = None
        self.hf_extractor = None
        self.openai_extractor = None
        
        # Phase 2-4 전문 서비스 초기화
        self.detailed_regulations = detailed_regulations_service
        self.testing_procedures = testing_procedures_service
        self.penalties = penalties_service
        self.validity = validity_service
        self.cross_validation = CrossValidationService()
        
        print("✅ RequirementsNodes 초기화 완료 (Phase 2-4 서비스 포함)")

    async def extract_core_keywords(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """상품명/설명에서 핵심 키워드 추출 (간단 휴리스틱).
        - 영문/숫자만 남기고 분절
        - 불용어 제거
        - 길이 3 이상 단어 우선, 상위 3개 반환
        - 한글일 경우 간단 매핑 시도
        """
        try:
            request = state["request"]
            name = (request.product_name or "").strip()
            desc = (request.product_description or "").strip()
            
            # HF 추출기 시도 → 실패 시 휴리스틱
            if self.hf_extractor is None:
                try:
                    self.hf_extractor = HfKeywordExtractor()
                except Exception as e:
                    self.hf_extractor = None
                    print(f"⚠️ HF 키워드 추출기 초기화 실패: {e}")
            
            if self.keyword_extractor is None:
                self.keyword_extractor = KeywordExtractor()
            
            if self.openai_extractor is None:
                try:
                    self.openai_extractor = OpenAiKeywordExtractor()
                except Exception as e:
                    self.openai_extractor = None
                    print(f"⚠️ OpenAI 키워드 추출기 초기화 실패: {e}")

            core_keywords = []
            
            # 키워드 추출 시도 (우선순위: OpenAI → HF → 휴리스틱)
            try:
                if self.openai_extractor:
                    core_keywords = self.openai_extractor.extract(name, desc, top_k=3)
                    print(f"✅ OpenAI 키워드 추출 성공: {core_keywords}")
            except Exception as e:
                print(f"⚠️ OpenAI 키워드 추출 실패: {e}")
                core_keywords = []
            
            if not core_keywords:
                try:
                    if self.hf_extractor:
                        core_keywords = self.hf_extractor.extract(name, desc, top_k=3)
                        print(f"✅ HF 키워드 추출 성공: {core_keywords}")
                except Exception as e:
                    print(f"⚠️ HF 키워드 추출 실패: {e}")
                    core_keywords = []
            
            if not core_keywords:
                try:
                    core_keywords = self.keyword_extractor.extract(name, desc, top_k=3)
                    print(f"✅ 휴리스틱 키워드 추출 성공: {core_keywords}")
                except Exception as e:
                    print(f"❌ 휴리스틱 키워드 추출 실패: {e}")
                    # 최종 폴백: 상품명에서 기본 키워드 추출
                    core_keywords = self._extract_fallback_keywords(name, desc)
                    print(f"🔄 폴백 키워드 추출: {core_keywords}")
            
        except Exception as e:
            print(f"❌ 키워드 추출 노드 전체 실패: {e}")
            # 에러 처리
            error_result = error_handler.handle_error(
                WorkflowError(
                    f"키워드 추출 실패: {str(e)}",
                    ErrorSeverity.MEDIUM,
                    ErrorRecoveryStrategy.FALLBACK,
                    {'step': 'keyword_extraction', 'hs_code': request.hs_code}
                ),
                {'step': 'keyword_extraction', 'state': state}
            )
            
            if error_result['continue_workflow']:
                core_keywords = error_result.get('fallback_data', {}).get('keywords', ['default'])
                print(f"🔄 에러 복구 후 폴백 키워드 사용: {core_keywords}")
            else:
                raise WorkflowError("키워드 추출 실패로 워크플로우 중단", ErrorSeverity.HIGH)
        
        # 상위 3개 키워드를 단계적으로 시도할 수 있도록 저장
        state["core_keywords"] = core_keywords
        state["keyword_strategies"] = [
            {"strategy": "top1", "keywords": core_keywords[:1]},
            {"strategy": "top2", "keywords": core_keywords[:2]},
            {"strategy": "top3", "keywords": core_keywords[:3]}
        ]
        
        # 🎯 키워드 추출 단계의 상세 metadata 수집
        keyword_metadata = {
            "extraction_step": {
                "hs_code": request.hs_code,
                "product_name": request.product_name,
                "product_description": request.product_description,
                "extraction_methods_tried": [
                    {"method": "OpenAI", "success": self.openai_extractor is not None, "keywords_found": core_keywords if self.openai_extractor else []},
                    {"method": "HuggingFace", "success": self.hf_extractor is not None, "keywords_found": core_keywords if self.hf_extractor else []},
                    {"method": "Heuristic", "success": True, "keywords_found": core_keywords}
                ],
                "final_keywords": core_keywords,
                "keyword_count": len(core_keywords),
                "extraction_timestamp": datetime.now().isoformat(),
                "keyword_sources": {
                    "from_product_name": name,
                    "from_description": desc,
                    "combined_text": f"{name} {desc}".strip()
                }
            }
        }
        state["detailed_metadata"] = state.get("detailed_metadata", {})
        state["detailed_metadata"].update(keyword_metadata)
        
        print(f"\n🔎 [NODE] 핵심 키워드: {core_keywords}")
        print(f"🔎 [NODE] 키워드 전략: {[s['strategy'] for s in state['keyword_strategies']]}")
        print(f"🔎 [METADATA] 키워드 추출 상세 정보 저장됨")
        state["next_action"] = "call_hybrid_api"
        return state
    
    def _extract_fallback_keywords(self, product_name: str, product_description: str) -> List[str]:
        """폴백 키워드 추출 (기본 휴리스틱)"""
        text = f"{product_name} {product_description}".lower()
        
        # 기본 키워드 매핑
        keyword_mapping = {
            'vitamin': ['vitamin', 'supplement', 'health'],
            'serum': ['serum', 'skincare', 'beauty'],
            'cream': ['cream', 'moisturizer', 'skincare'],
            'food': ['food', 'nutrition', 'diet'],
            'cosmetic': ['cosmetic', 'beauty', 'makeup'],
            'electronic': ['electronic', 'device', 'technology'],
            'toy': ['toy', 'children', 'play'],
            'clothing': ['clothing', 'garment', 'textile']
        }
        
        # 매핑된 키워드 찾기
        for key, keywords in keyword_mapping.items():
            if key in text:
                return keywords[:3]
        
        # 기본 키워드 추출
        words = text.split()
        keywords = []
        for word in words:
            if len(word) > 3 and word.isalpha():
                keywords.append(word)
                if len(keywords) >= 3:
                    break
        
        return keywords if keywords else ['product', 'import', 'requirement']
    
    async def search_agency_documents(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """기관별 문서 검색 노드"""
        request = state["request"]
        hs_code = request.hs_code
        product_name = request.product_name
        keywords = state.get("core_keywords") or []
        keyword_strategies = state.get("keyword_strategies", [])
        
        # 키워드 전략을 단계적으로 시도 (top1 → top2 → top3)
        query_terms = []
        for strategy in keyword_strategies:
            if strategy["keywords"]:
                query_terms.append(" ".join(strategy["keywords"]))
        
        # 기본값으로 상품명 사용
        if not query_terms:
            query_terms = [product_name]
        
        query_term = query_terms[0]  # 첫 번째 전략 사용
        
        print(f"\n🔍 [NODE] 기관별 문서 검색 시작")
        print(f"  📋 HS코드: {hs_code}")
        print(f"  📦 상품명: {product_name}")
        
        # 기본 URL 폴백 (TavilySearch 실패 시 사용) - 9개 기관 모두
        default_urls = {
            "FDA": "https://www.fda.gov",
            "FCC": "https://www.fcc.gov",
            "CBP": "https://www.cbp.gov",
            "USDA": "https://www.usda.gov",
            "EPA": "https://www.epa.gov",
            "CPSC": "https://www.cpsc.gov",
            "KCS": "https://www.customs.go.kr",
            "MFDS": "https://www.mfds.go.kr",
            "MOTIE": "https://www.motie.go.kr"
        }
        
        # HS코드 8자리와 6자리 추출
        hs_code_8digit = hs_code
        hs_code_6digit = ".".join(hs_code.split(".")[:2]) if "." in hs_code else hs_code
        
        print(f"  📋 8자리 HS코드: {hs_code_8digit}")
        print(f"  📋 6자리 HS코드: {hs_code_6digit}")
        
        # 타겟 기관 결정 (AI 매핑 또는 하드코딩 또는 챕터 기반 추론)
        target_agencies_data = await self.tools._get_target_agencies_for_hs_code(hs_code, product_name)
        target_agencies = target_agencies_data.get("primary_agencies", [])
        
        # 타겟 기관이 없으면 최소한 FDA는 포함
        if not target_agencies:
            target_agencies = ["FDA"]
            print(f"  ⚠️ 타겟 기관 없음 - 기본값 FDA 사용")
        
        print(f"  🎯 타겟 기관: {', '.join(target_agencies)} ({target_agencies_data.get('source', 'unknown')})")
        print(f"  💰 Tavily 검색 최적화: {len(target_agencies)}개 기관만 검색")
        
        # 각 기관별 검색 쿼리 (8자리와 6자리 모두) - 타겟 기관만!
        search_queries = {}
        
        # 기관별 사이트 도메인 매핑
        agency_domains = {
            "FDA": "fda.gov",
            "FCC": "fcc.gov",
            "CBP": "cbp.gov",
            "USDA": "usda.gov",
            "EPA": "epa.gov",
            "CPSC": "cpsc.gov",
            "KCS": "customs.go.kr",
            "MFDS": "mfds.go.kr",
            "MOTIE": "motie.go.kr"
        }
        
        # 타겟 기관만 검색 쿼리 생성
        for agency in target_agencies:
            domain = agency_domains.get(agency, f"{agency.lower()}.gov")
            
            # 8자리 HS코드 검색
            if agency == "FDA":
                search_queries[f"{agency}_8digit"] = f"site:{domain} import requirements {query_term} HS {hs_code_8digit}"
            elif agency == "FCC":
                search_queries[f"{agency}_8digit"] = f"site:{domain} device authorization requirements {query_term} HS {hs_code_8digit}"
            elif agency == "CBP":
                search_queries[f"{agency}_8digit"] = f"site:{domain} import documentation requirements HS {hs_code_8digit} {query_term}"
            elif agency == "USDA":
                search_queries[f"{agency}_8digit"] = f"site:{domain} agricultural import requirements {query_term} HS {hs_code_8digit}"
            elif agency == "EPA":
                search_queries[f"{agency}_8digit"] = f"site:{domain} environmental regulations {query_term} HS {hs_code_8digit}"
            elif agency == "CPSC":
                search_queries[f"{agency}_8digit"] = f"site:{domain} consumer product safety {query_term} HS {hs_code_8digit}"
            elif agency == "KCS":
                search_queries[f"{agency}_8digit"] = f"site:{domain} Korea customs import requirements {query_term} HS {hs_code_8digit}"
            elif agency == "MFDS":
                search_queries[f"{agency}_8digit"] = f"site:{domain} food drug safety import {query_term} HS {hs_code_8digit}"
            elif agency == "MOTIE":
                search_queries[f"{agency}_8digit"] = f"site:{domain} trade policy import requirements {query_term} HS {hs_code_8digit}"
        
        # 6자리 HS코드 검색 (유사) - 타겟 기관만!
        for agency in target_agencies:
            domain = agency_domains.get(agency, f"{agency.lower()}.gov")
            
            # 6자리 HS코드 검색
            if agency == "FDA":
                search_queries[f"{agency}_6digit"] = f"site:{domain} import requirements {query_term} HS {hs_code_6digit}"
            elif agency == "FCC":
                search_queries[f"{agency}_6digit"] = f"site:{domain} device authorization requirements {query_term} HS {hs_code_6digit}"
            elif agency == "CBP":
                search_queries[f"{agency}_6digit"] = f"site:{domain} import documentation requirements HS {hs_code_6digit} {query_term}"
            elif agency == "USDA":
                search_queries[f"{agency}_6digit"] = f"site:{domain} agricultural import requirements {query_term} HS {hs_code_6digit}"
            elif agency == "EPA":
                search_queries[f"{agency}_6digit"] = f"site:{domain} environmental regulations {query_term} HS {hs_code_6digit}"
            elif agency == "CPSC":
                search_queries[f"{agency}_6digit"] = f"site:{domain} consumer product safety {query_term} HS {hs_code_6digit}"
            elif agency == "KCS":
                search_queries[f"{agency}_6digit"] = f"site:{domain} Korea customs import requirements {query_term} HS {hs_code_6digit}"
            elif agency == "MFDS":
                search_queries[f"{agency}_6digit"] = f"site:{domain} food drug safety import {query_term} HS {hs_code_6digit}"
            elif agency == "MOTIE":
                search_queries[f"{agency}_6digit"] = f"site:{domain} trade policy import requirements {query_term} HS {hs_code_6digit}"
        
        search_results = {}
        
        for agency, query in search_queries.items():
            print(f"\n  📡 {agency} 검색 중...")
            print(f"    쿼리: {query}")
            
            # 프로바이더를 통한 검색 시도 (더 많은 결과 수집)
            results = await self.tools.search_provider.search(query, max_results=15)  # 검색 결과를 15개로 확장
            print(f"    📊 {self.tools.search_provider.provider_name} 검색 결과: {len(results)}개")
            
            # 검색 결과 처리
            chosen_urls = []
            
            if not results and self.tools.search_provider.provider_name == "disabled":
                print(f"    🔇 검색 비활성화 모드: '{query}' 스킵됨")
                agency_name = agency.split("_")[0]
                default_url = default_urls.get(agency_name)
                if default_url:
                    chosen_urls = [default_url]
            elif not results:
                print(f"    💡 팁: TAVILY_API_KEY를 설정하면 더 정확한 검색 결과를 얻을 수 있습니다.")
                agency_name = agency.split("_")[0]
                default_url = default_urls.get(agency_name)
                if default_url:
                    chosen_urls = [default_url]
                print(f"    🔄 {agency} TavilySearch 실패, 기본 URL 사용: {default_url}")
            else:
                # 검색 성공 - 여러 링크 수집 (최대 10개)
                for i, result in enumerate(results, 1):
                    title = result.get('title', 'No title')
                    url = result.get('url', 'No URL')
                    print(f"      {i}. {title}")
                    print(f"         URL: {url}")
                
                # site: 쿼리로 검색했으므로 모든 결과가 공식 사이트 (최대 10개 선택)
                chosen_urls = [result.get("url") for result in results[:10] if result.get("url")]
                print(f"    ✅ {agency} 공식 사이트 결과 {len(chosen_urls)}개 선택")
            
            search_results[agency] = {
                "urls": chosen_urls,  # 여러 URL 저장
                "all_results": results,
                "query": query,
                "is_fallback": not results,  # 폴백 사용 여부 표시
                "hs_code_type": "8digit" if "8digit" in agency else "6digit",
                "agency": agency.split("_")[0]  # FDA_8digit -> FDA
            }
        
        # 요약 카운트: 하나 이상의 URL 보유한 항목 수
        found_count = sum(1 for v in search_results.values() if v.get("urls"))
        print(f"\n📋 [NODE] 검색 완료 - {found_count}개 URL 세트 발견")
        
        # 🎯 기관별 검색 단계의 상세 metadata 수집
        search_metadata = {
            "search_step": {
                "hs_code_8digit": hs_code_8digit,
                "hs_code_6digit": hs_code_6digit,
                "query_term": query_term,
                "search_strategies": search_queries,
                "search_provider": self.tools.search_provider.provider_name if hasattr(self.tools, 'search_provider') else "unknown",
                "total_urls_found": found_count,
                "search_results_per_agency": {
                    agency: {
                        "url_count": len(search_data["urls"]),
                        "query": search_data["query"],
                        "hs_code_type": search_data["hs_code_type"],
                        "is_fallback": search_data["is_fallback"],
                        "search_timestamp": datetime.now().isoformat()
                    } for agency, search_data in search_results.items()
                },
                "default_urls_used": default_urls,
                "search_performance": {
                    "total_queries_executed": len(search_queries),
                    "successful_searches": len([sr for sr in search_results.values() if not sr.get("is_fallback", False)]),
                    "fallback_searches": len([sr for sr in search_results.values() if sr.get("is_fallback", False)])
                }
            }
        }
        state["detailed_metadata"] = state.get("detailed_metadata", {})
        state["detailed_metadata"].update(search_metadata)

        # 상태 업데이트 (기존 상태 유지)
        state["search_results"] = search_results
        # 참고 링크 저장
        request = state["request"]
        save_meta = self.tools.save_reference_links(request.hs_code, request.product_name, search_results)
        state["references_saved"] = save_meta
        
        print(f"🔍 [METADATA] 기관별 검색 상세 정보 저장됨 - 총 {found_count}개 URL 발견")
        state["next_action"] = "scrape_documents"
        return state

    async def call_hybrid_api(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """하이브리드 API 호출 노드 (Data.gov/USDA/EPA + 웹 검색 통합 + Phase 2-4)."""
        request = state["request"]
        hs_code = request.hs_code
        product_name = request.product_name
        product_description = request.product_description or ""
        keywords = state.get("core_keywords") or []
        query_term = (keywords[0] if keywords else product_name) or ""
        print(f"\n📡 [NODE] 하이브리드 API 호출 시작: {hs_code} / {product_name}")
        try:
            # Phase 2-4 포함된 하이브리드 검색
            hybrid_start_time = datetime.now()
            hybrid = await self.tools.search_requirements_hybrid(hs_code, query_term, product_description)
            hybrid_end_time = datetime.now()
            
            # 🎯 하이브리드 검색 단계의 상세 metadata 수집
            hybrid_metadata = {
                "hybrid_api_step": {
                    "hs_code": hs_code,
                    "query_term": query_term,
                    "product_description": product_description[:100] if product_description else "",  # 처음 100자만
                    "api_parameters": {
                        "hs_code": hs_code,
                        "query": query_term,
                        "description_length": len(product_description) if product_description else 0,
                        "keywords_length": len(keywords)
                    },
                    "api_response": {
                        "success": not hybrid.get("error"),
                        "response_time_ms": int((hybrid_end_time - hybrid_start_time).total_seconds() * 1000),
                        "data_keys": list(hybrid.keys()) if isinstance(hybrid, dict) else [],
                        "error_message": hybrid.get("error") if hybrid.get("error") else None
                    },
                    "timestamp": hybrid_end_time.isoformat()
                }
            }
            state["detailed_metadata"] = state.get("detailed_metadata", {})
            state["detailed_metadata"].update(hybrid_metadata)
            
            state["hybrid_result"] = hybrid
            print(f"📡 [METADATA] 하이브리드 API 검색 상세 정보 저장됨 - 응답시간: {(hybrid_end_time - hybrid_start_time).total_seconds()*1000:.0f}ms")
            state["next_action"] = "scrape_documents"
        except Exception as e:
            print(f"  ❌ 하이브리드 호출 실패: {e}")
            
            # 오류 발생 시에도 메타데이터 수집
            hybrid_metadata = {
                "hybrid_api_step": {
                    "hs_code": hs_code,
                    "query_term": query_term,
                    "product_description": product_description[:100] if product_description else "",
                    "api_parameters": {
                        "hs_code": hs_code,
                        "query": query_term,
                        "description_length": len(product_description) if product_description else 0,
                        "keywords_length": len(keywords)
                    },
                    "api_response": {
                        "success": False,
                        "response_time_ms": None,
                        "data_keys": [],
                        "error_message": str(e)
                    },
                    "timestamp": datetime.now().isoformat()
                }
            }
            state["detailed_metadata"] = state.get("detailed_metadata", {})
            state["detailed_metadata"].update(hybrid_metadata)
            
            state["hybrid_result"] = {"error": str(e)}
            print(f"📡 [METADATA] 하이브리드 API 오류 정보 저장됨: {e}")
            state["next_action"] = "scrape_documents"
        return state
    
    async def scrape_documents(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """문서 스크래핑 노드"""
        search_results = state["search_results"]
        request = state["request"]
        hs_code = request.hs_code
        
        print(f"\n🔍 [NODE] 문서 스크래핑 시작")
        
        scraped_data = {}
        
        # 기관별로 8자리와 6자리 결과 통합
        agency_results = {}
        
        for agency_key, search_data in search_results.items():
            agency_name = search_data["agency"]
            hs_code_type = search_data["hs_code_type"]
            
            if agency_name not in agency_results:
                agency_results[agency_name] = {
                    "8digit": {"urls": [], "results": []},
                    "6digit": {"urls": [], "results": []}
                }
            
            agency_results[agency_name][hs_code_type]["urls"] = search_data["urls"]
        
        # 각 기관별로 스크래핑 수행
        for agency_name, agency_data in agency_results.items():
            print(f"\n  📄 {agency_name} 스크래핑 중...")
            
            # 8자리와 6자리 URL 모두 수집
            all_urls = agency_data["8digit"]["urls"] + agency_data["6digit"]["urls"]
            
            if not all_urls:
                print(f"    ❌ {agency_name}: 스크래핑할 URL 없음")
                # URL이 없어도 None으로 결과 저장
                scraped_data[agency_name] = {
                    "certifications": [],
                    "documents": [],
                    "labeling": [],
                    "sources": [],
                    "status": "no_urls_found",
                    "hs_code_8digit": {"urls": agency_data["8digit"]["urls"], "results": []},
                    "hs_code_6digit": {"urls": agency_data["6digit"]["urls"], "results": []}
                }
                continue
            
            print(f"    📋 8자리 URL: {len(agency_data['8digit']['urls'])}개")
            print(f"    📋 6자리 URL: {len(agency_data['6digit']['urls'])}개")
            print(f"    📋 총 URL: {len(all_urls)}개")
            
            try:
                # 9개 기관 모두 처리
                if agency_name == "FDA":
                    result = await self.web_scraper.scrape_fda_requirements(hs_code, all_urls[0])
                elif agency_name == "FCC":
                    result = await self.web_scraper.scrape_fcc_requirements(hs_code, all_urls[0])
                elif agency_name == "CBP":
                    result = await self.web_scraper.scrape_cbp_requirements(hs_code, all_urls[0])
                elif agency_name == "USDA":
                    result = await self.web_scraper.scrape_usda_requirements(hs_code, all_urls[0])
                elif agency_name == "EPA":
                    result = await self.web_scraper.scrape_epa_requirements(hs_code, all_urls[0])
                elif agency_name == "CPSC":
                    result = await self.web_scraper.scrape_cpsc_requirements(hs_code, all_urls[0])
                elif agency_name == "KCS":
                    result = await self.web_scraper.scrape_kcs_requirements(hs_code, all_urls[0])
                elif agency_name == "MFDS":
                    result = await self.web_scraper.scrape_mfds_requirements(hs_code, all_urls[0])
                elif agency_name == "MOTIE":
                    result = await self.web_scraper.scrape_motie_requirements(hs_code, all_urls[0])
                else:
                    print(f"    ❌ {agency_name}: 지원되지 않는 기관")
                    continue
                
                # 스크래핑 결과 상세 로깅
                certs = result.get("certifications", [])
                docs = result.get("documents", [])
                
                print(f"    ✅ {agency_name} 스크래핑 성공:")
                print(f"      📋 인증요건: {len(certs)}개")
                for cert in certs:
                    print(f"        • {cert.get('name', 'Unknown')} ({cert.get('agency', 'Unknown')})")
                
                print(f"      📄 필요서류: {len(docs)}개")
                for doc in docs:
                    print(f"        • {doc.get('name', 'Unknown')}")
                
                # HS코드 구분 정보 추가
                # 안전하게 리스트로 변환 (타입 에러 방지)
                certs_list = result.get("certifications", [])
                docs_list = result.get("documents", [])
                if not isinstance(certs_list, list):
                    certs_list = []
                if not isinstance(docs_list, list):
                    docs_list = []
                
                result["hs_code_8digit"] = {
                    "urls": agency_data["8digit"]["urls"],
                    "results": certs_list + docs_list
                }
                result["hs_code_6digit"] = {
                    "urls": agency_data["6digit"]["urls"],
                    "results": []
                }
                result["status"] = "success"
                
                scraped_data[agency_name] = result
                
            except Exception as e:
                print(f"    ❌ {agency_name} 스크래핑 실패: {e}")
                scraped_data[agency_name] = {
                    "certifications": [],
                    "documents": [],
                    "labeling": [],
                    "sources": [],
                    "status": "scraping_failed",
                    "error": str(e),
                    "hs_code_8digit": {"urls": agency_data["8digit"]["urls"], "results": []},
                    "hs_code_6digit": {"urls": agency_data["6digit"]["urls"], "results": []}
                }
        
        print(f"\n📋 [NODE] 스크래핑 완료 - {len(scraped_data)}개 기관 처리")
        
        # 🎯 웹 스크래핑 단계의 상세 metadata 수집
        scraping_metadata = {
            "scraping_step": {
                "hs_code": hs_code,
                "total_agencies_scraped": len(scraped_data),
                "scraping_performance": {
                    "successful_scraping": len([data for data in scraped_data.values() if data.get("status") == "success"]),
                    "failed_scraping": len([data for data in scraped_data.values() if data.get("status") in ["scraping_failed", "no_urls_found"]]) + len([data for data in scraped_data.values() if data.get("error")]),
                    "total_certifications_found": sum(len(data.get("certifications", [])) for data in scraped_data.values()),
                    "total_documents_found": sum(len(data.get("documents", [])) for data in scraped_data.values()),
                    "total_sources_collected": sum(len(data.get("sources", [])) for data in scraped_data.values())
                },
                "scraped_agencies_details": {
                    agency: {
                        "status": data.get("status", "unknown"),
                        "certifications_count": len(data.get("certifications", [])),
                        "documents_count": len(data.get("documents", [])),
                        "sources_count": len(data.get("sources", [])),
                        "has_raw_page_data": "raw_page_data" in data,
                        "hs_code_8digit_urls": len(data.get("hs_code_8digit", {}).get("urls", [])),
                        "hs_code_6digit_urls": len(data.get("hs_code_6digit", {}).get("urls", [])),
                        "error_message": data.get("error") if data.get("error") else None,
                        "scraping_timestamp": datetime.now().isoformat()
                    } for agency, data in scraped_data.items()
                },
                "scraping_statistics": {
                    "8digit_hs_code_urls": sum(len(data.get("hs_code_8digit", {}).get("urls", [])) for data in scraped_data.values()),
                    "6digit_hs_code_urls": sum(len(data.get("hs_code_6digit", {}).get("urls", [])) for data in scraped_data.values()),
                }
            }
        }
        state["detailed_metadata"] = state.get("detailed_metadata", {})
        state["detailed_metadata"].update(scraping_metadata)
        
        print(f"📋 [METADATA] 웹 스크래핑 상세 정보 저장됨 - 인증 요건: {scraping_metadata['scraping_step']['scraping_performance']['total_certifications_found']}개, 서류: {scraping_metadata['scraping_step']['scraping_performance']['total_documents_found']}개")
        
        # 상태 업데이트 (기존 상태 유지)
        state["scraped_data"] = scraped_data
        state["next_action"] = "consolidate_results"
        return state
    
    async def consolidate_results(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """결과 통합 노드"""
        scraped_data = state["scraped_data"]
        
        print(f"\n🔍 [NODE] 결과 통합 시작")
        
        all_certifications = []
        all_documents = []
        all_sources = []
        
        for agency, data in scraped_data.items():
            status = data.get("status", "unknown")
            
            if status == "no_urls_found":
                print(f"  ❌ {agency}: URL 없음 (None)")
                continue
            elif status == "scraping_failed":
                print(f"  ❌ {agency}: 스크래핑 실패 (None)")
                continue
            elif "error" in data:
                print(f"  ❌ {agency}: 오류로 인해 제외 (None)")
                continue
                
            print(f"  📊 {agency} 데이터 통합:")
            
            # 인증요건 통합
            certs = data.get("certifications", [])
            all_certifications.extend(certs)
            print(f"    📋 인증요건: {len(certs)}개 추가")
            
            # 필요서류 통합
            docs = data.get("documents", [])
            all_documents.extend(docs)
            print(f"    📄 필요서류: {len(docs)}개 추가")
            
            # 출처 통합
            sources = data.get("sources", [])
            all_sources.extend(sources)
            print(f"    📚 출처: {len(sources)}개 추가")
        
        print(f"\n📋 [NODE] 통합 완료:")
        print(f"  📋 총 인증요건: {len(all_certifications)}개")
        print(f"  📄 총 필요서류: {len(all_documents)}개")
        print(f"  📚 총 출처: {len(all_sources)}개")
        
        consolidation_start_time = datetime.now()
        
        # 🆕 FAISS DB에서 판례 수집 (API 호출 대신!)
        request = state.get("request")
        precedents_list = []
        precedents_fetch_start = datetime.now()
        
        if request:
            try:
                # FAISS DB에서 판례 가져오기
                from app.services.requirements.precedent_validation_service import get_precedent_validation_service
                precedent_validator = get_precedent_validation_service()
                
                precedents_list = await precedent_validator._get_precedents_from_db(
                    hs_code=request.hs_code,
                    product_name=request.product_name
                )
                
                precedents_fetch_end = datetime.now()
                precedents_fetch_time = (precedents_fetch_end - precedents_fetch_start).total_seconds() * 1000
                print(f"📊 FAISS DB 판례 수집 성공: {len(precedents_list)}개 판례 확인됨 ({precedents_fetch_time:.0f}ms)")
                
                cbp = {
                    "hs_code": request.hs_code,
                    "count": len(precedents_list),
                    "precedents": precedents_list,
                    "source": "faiss_db"
                }
                
            except Exception as e:
                cbp = {"error": "precedent_fetch_failed", "error_message": str(e)}
                precedents_fetch_end = datetime.now()
                precedents_fetch_time = (precedents_fetch_end - precedents_fetch_start).total_seconds() * 1000
                print(f"📊 FAISS DB 판례 수집 실패: {e} ({precedents_fetch_time:.0f}ms)")

        # 하이브리드(API+웹) 결과도 통합 (Phase 2-4 포함)
        hybrid = state.get("hybrid_result") or {}
        hybrid_certifications = 0
        hybrid_documents = 0
        hybrid_sources = 0
        phase_2_4_counts = {"testing_procedures": 0, "penalties_enforcement": 0, "validity_periods": 0}
        
        if hybrid and not hybrid.get("error"):
            combined = hybrid.get("combined_results", {})
            if combined:
                # 안전하게 int로 변환 (타입 에러 방지)
                certs = combined.get("certifications", [])
                docs = combined.get("documents", [])
                srcs = combined.get("sources", [])
                
                hybrid_certifications = len(certs) if isinstance(certs, list) else 0
                hybrid_documents = len(docs) if isinstance(docs, list) else 0
                hybrid_sources = len(srcs) if isinstance(srcs, list) else 0
                
                all_certifications.extend(combined.get("certifications", []))
                all_documents.extend(combined.get("documents", []))
                all_sources.extend(combined.get("sources", []))
                
                # Phase 2-4 결과 통합
                phase_2_4_counts = {
                    "testing_procedures": len(combined.get('testing_procedures', [])),
                    "penalties_enforcement": len(combined.get('penalties_enforcement', [])),
                    "validity_periods": len(combined.get('validity_periods', []))
                }
                print(f"  📊 Phase 2-4 결과 통합:")
                print(f"    🧪 검사 절차: {phase_2_4_counts['testing_procedures']}개")
                print(f"    ⚖️ 처벌 정보: {phase_2_4_counts['penalties_enforcement']}개")
                print(f"    ⏰ 유효기간: {phase_2_4_counts['validity_periods']}개")

        consolidation_end_time = datetime.now()
        consolidation_time = (consolidation_end_time - consolidation_start_time).total_seconds() * 1000

        # 🎯 결과 통합 단계의 상세 metadata 수집
        consolidation_metadata = {
            "consolidation_step": {
                "hs_code": request.hs_code if request else "unknown",
                "consolidation_performance": {
                    "total_processing_time_ms": consolidation_time,
                    "precedents_fetch_time_ms": precedents_fetch_time if 'precedents_fetch_time' in locals() else None,
                    "consolidation_timestamp": consolidation_end_time.isoformat()
                },
                "final_counts": {
                    "total_certifications": len(all_certifications),
                    "total_documents": len(all_documents),
                    "total_sources": len(all_sources),
                    "total_precedents": len(cbp.get("precedents", [])) if cbp else 0,
                    "hybrid_certifications_added": hybrid_certifications,
                    "hybrid_documents_added": hybrid_documents,
                    "hybrid_sources_added": hybrid_sources
                },
                "phase_2_4_counts": phase_2_4_counts,
                "cbp_precedents_info": {
                    "success": not cbp.get("error") if cbp else False,
                    "precedents_count": len(cbp.get("precedents", [])) if cbp else 0,
                    "error_message": cbp.get("error_message") if cbp and cbp.get("error") else None
                },
                "data_sources_summary": {
                    "web_scraping_results": len(all_certifications) - hybrid_certifications,
                    "hybrid_api_results": hybrid_certifications + hybrid_documents + hybrid_sources,
                    "cbp_precedents": len(cbp.get("precedents", [])) if cbp else 0
                }
            }
        }
        state["detailed_metadata"] = state.get("detailed_metadata", {})
        state["detailed_metadata"].update(consolidation_metadata)

        print(f"📋 [METADATA] 결과 통합 상세 정보 저장됨 - 총 시간: {consolidation_time:.0f}ms, 최종 결과: 인증 {len(all_certifications)}개, 서류 {len(all_documents)}개")

        # Citations 추출 (백엔드 API에서 제공)
        citations = []
        if hybrid and not hybrid.get("error"):
            citations = hybrid.get("citations", [])
            print(f"  📚 Citations 추출: {len(citations)}개")
        
        # LLM 요약 생성
        llm_summary = None
        try:
            from app.services.requirements.llm_summary_service import LlmSummaryService
            llm_service = LlmSummaryService()
            
            # 통합된 데이터를 문서 형태로 변환
            raw_documents = []
            
            # 인증요건을 문서로 변환
            for cert in all_certifications:
                raw_documents.append({
                    "title": cert.get("name", "Unknown"),
                    "content": cert.get("description", ""),
                    "url": cert.get("source_url", ""),
                    "agency": cert.get("agency", "")
                })
            
            # 필요서류를 문서로 변환
            for doc in all_documents:
                raw_documents.append({
                    "title": doc.get("name", "Unknown"),
                    "content": doc.get("description", ""),
                    "url": doc.get("source_url", ""),
                    "agency": doc.get("agency", "")
                })
            
            # Citations도 추가
            for citation in citations:
                raw_documents.append({
                    "title": citation.get("title", ""),
                    "content": citation.get("snippet", ""),
                    "url": citation.get("url", ""),
                    "agency": citation.get("agency", "")
                })
            
            print(f"  🤖 LLM 요약 생성 중... (문서 {len(raw_documents)}개)")
            
            # summarize_regulations 메서드 호출
            summary_result = await llm_service.summarize_regulations(
                hs_code=request.hs_code if request else "unknown",
                product_name=request.product_name if request else "unknown",
                raw_documents=raw_documents
            )
            
            # SummaryResult를 딕셔너리로 변환
            if summary_result:
                llm_summary = {
                    "critical_requirements": summary_result.critical_requirements,
                    "required_documents": summary_result.required_documents,
                    "compliance_steps": summary_result.compliance_steps,
                    "estimated_costs": summary_result.estimated_costs,
                    "timeline": summary_result.timeline,
                    "risk_factors": summary_result.risk_factors,
                    "recommendations": summary_result.recommendations,
                    "confidence_score": summary_result.confidence_score,
                    "model_used": summary_result.model_used,
                    "tokens_used": summary_result.tokens_used,
                    "cost": summary_result.cost
                }
                print(f"  ✅ LLM 요약 생성 완료 - 신뢰도: {summary_result.confidence_score:.2f}")
            
        except Exception as e:
            print(f"  ⚠️ LLM 요약 생성 실패: {e}")
            import traceback
            traceback.print_exc()
            llm_summary = None
        
        # ========================================
        # 🚀 Phase 1-4 전문 서비스 호출 (병렬 실행)
        # ========================================
        print(f"\n🚀 [PHASE 1-4] 전문 분석 서비스 실행 시작")
        phase_start = datetime.now()
        
        phase_1_result = None  # 세부 규정
        phase_2_result = None  # 검사 절차
        phase_3_result = None  # 처벌 벌금
        phase_4_result = None  # 유효기간
        detailed_regs_result = None  # Phase 1 결과
        cross_validation_result = None  # 교차 검증
        
        try:
            # 병렬 실행을 위한 태스크 생성 (판례 결과를 파라미터로 전달)
            tasks = []
            
            if request:
                # 1단계: 세부 규정 추출 (농약 잔류량, 화학성분 제한 등)
                task1 = asyncio.create_task(
                    self.detailed_regulations.analyze(
                        hs_code=request.hs_code,
                        product_name=request.product_name,
                        product_description=request.product_description or ""
                    )
                )
                tasks.append(("detailed_regulations", task1))
                
                # 2단계: 검사 절차 분석
                task2 = asyncio.create_task(
                    self.testing_procedures.analyze(
                        hs_code=request.hs_code,
                        product_name=request.product_name,
                        product_description=request.product_description or ""
                    )
                )
                tasks.append(("testing_procedures", task2))
                
                # 3단계: 처벌 벌금 분석
                task3 = asyncio.create_task(
                    self.penalties.analyze(
                        hs_code=request.hs_code,
                        product_name=request.product_name,
                        product_description=request.product_description or ""
                    )
                )
                tasks.append(("penalties", task3))
                
                # 4단계: 유효기간 분석
                task4 = asyncio.create_task(
                    self.validity.analyze(
                        hs_code=request.hs_code,
                        product_name=request.product_name,
                        product_description=request.product_description or ""
                    )
                )
                tasks.append(("validity", task4))
            
            # 병렬 실행 및 결과 수집
            if tasks:
                print(f"  🔄 {len(tasks)}개 분석 태스크 병렬 실행 중...")
                completed_tasks = await asyncio.gather(*[task for _, task in tasks], return_exceptions=True)
                
                # 결과 할당
                for i, (name, _) in enumerate(tasks):
                    result = completed_tasks[i]
                    if isinstance(result, Exception):
                        print(f"  ❌ {name} 분석 실패: {result}")
                    else:
                        print(f"  ✅ {name} 분석 완료 - {len(result.get('sources', []))}개 출처")
                        if name == "detailed_regulations":
                            detailed_regs_result = result
                        elif name == "testing_procedures":
                            phase_2_result = result
                        elif name == "penalties":
                            phase_3_result = result
                        elif name == "validity":
                            phase_4_result = result
            
            # 교차 검증 (모든 결과 수집 후 실행)
            if llm_summary and request:
                print(f"  🔍 교차 검증 실행 중...")
                try:
                    cross_validation_result = await self.cross_validation.validate_requirements(
                        hs_code=request.hs_code,
                        product_name=request.product_name,
                        llm_summary=llm_summary,
                        phase_results={
                            "detailed_regulations": detailed_regs_result,
                            "testing_procedures": phase_2_result,
                            "penalties": phase_3_result,
                            "validity": phase_4_result
                        }
                    )
                    print(f"  ✅ 교차 검증 완료 - 검증점수: {cross_validation_result.validation_score:.2f}, 충돌: {len(cross_validation_result.conflicts_found)}건")
                except Exception as e:
                    print(f"  ⚠️ 교차 검증 실패: {e}")
                    cross_validation_result = None
            
            # 💾 판례 검증 전 중간 결과 저장 (디버깅용)
            if request:
                try:
                    import json
                    from pathlib import Path
                    
                    # 순환 참조 방지를 위한 안전한 직렬화
                    def safe_serialize(obj):
                        """객체를 안전하게 dict로 변환"""
                        if obj is None:
                            return None
                        elif hasattr(obj, '__dict__'):
                            return {k: safe_serialize(v) for k, v in obj.__dict__.items()}
                        elif isinstance(obj, dict):
                            return {k: safe_serialize(v) for k, v in obj.items()}
                        elif isinstance(obj, list):
                            return [safe_serialize(item) for item in obj]
                        elif isinstance(obj, (str, int, float, bool)):
                            return obj
                        else:
                            return str(obj)
                    
                    intermediate_data = {
                        "timestamp": datetime.now().isoformat(),
                        "hs_code": request.hs_code,
                        "product_name": request.product_name,
                        "llm_summary": safe_serialize(llm_summary),
                        "phase_1_detailed_regulations": safe_serialize(detailed_regs_result),
                        "phase_2_testing_procedures": safe_serialize(phase_2_result),
                        "phase_3_penalties": safe_serialize(phase_3_result),
                        "phase_4_validity": safe_serialize(phase_4_result),
                        "cross_validation": safe_serialize(cross_validation_result),
                        "certifications": safe_serialize(all_certifications),
                        "documents": safe_serialize(all_documents),
                        "sources": safe_serialize(all_sources)
                    }
                    
                    # 안전한 파일명 생성
                    safe_filename = request.product_name.replace(" ", "_").replace("/", "_")[:50]
                    output_dir = Path("requirements_intermediate")
                    output_dir.mkdir(exist_ok=True)
                    
                    output_file = output_dir / f"intermediate_{safe_filename}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                    
                    with open(output_file, "w", encoding="utf-8") as f:
                        json.dump(intermediate_data, f, indent=2, ensure_ascii=False, default=str)
                    
                    print(f"  💾 중간 결과 저장 완료: {output_file}")
                    
                except Exception as e:
                    print(f"  ⚠️ 중간 결과 저장 실패 (계속 진행): {e}")
            
            # 🆕 판례 기반 검증 (FAISS DB 사용) - 교차 검증과 같은 위치에서 실행
            precedent_validation_result = None
            if request and precedents_list:
                print(f"  🔍 판례 기반 검증 실행 중...")
                try:
                    from app.services.requirements.precedent_validation_service import get_precedent_validation_service
                    precedent_validator = get_precedent_validation_service()
                    
                    precedent_validation_result = await precedent_validator.validate_requirements(
                        hs_code=request.hs_code,
                        product_name=request.product_name,
                        our_requirements={
                            "certifications": all_certifications,
                            "documents": all_documents
                        },
                        precedents=precedents_list
                    )
                    
                    print(f"  ✅ 판례 검증 완료 - 점수: {precedent_validation_result.validation_score:.2f}, 판정: {precedent_validation_result.verdict['status']}")
                    print(f"    📊 일치: {len(precedent_validation_result.matched_requirements)}개, 누락: {len(precedent_validation_result.missing_requirements)}개, Red Flags: {len(precedent_validation_result.red_flags)}개")
                    
                except Exception as e:
                    print(f"  ⚠️ 판례 검증 실패: {e}")
                    import traceback
                    traceback.print_exc()
                    precedent_validation_result = None
            
            # 🚀 LLM 요약에 Phase 1-4 결과 포함하여 재생성
            if request and (detailed_regs_result or phase_2_result or phase_3_result or phase_4_result):
                print(f"  🔄 Phase 1-4 결과를 포함한 LLM 요약 재생성...")
                try:
                    # Phase 1-4 결과를 raw_documents에 추가
                    phase_documents = []
                    
                    if detailed_regs_result:
                        phase_documents.append({
                            "title": f"Phase 1: 세부 규정 ({request.hs_code})",
                            "content": f"상세 규정 분석 결과: {detailed_regs_result.get('summary', '')}",
                            "url": "phase_1_result",
                            "source": "detailed_regulations_service"
                        })
                    
                    if phase_2_result:
                        phase_documents.append({
                            "title": f"Phase 2: 검사 절차 ({request.hs_code})",
                            "content": f"검사 절차 분석 결과: {phase_2_result.get('summary', '')}",
                            "url": "phase_2_result",
                            "source": "testing_procedures_service"
                        })
                    
                    if phase_3_result:
                        phase_documents.append({
                            "title": f"Phase 3: 처벌 정보 ({request.hs_code})",
                            "content": f"처벌 정보 분석 결과: {phase_3_result.get('summary', '')}",
                            "url": "phase_3_result",
                            "source": "penalties_service"
                        })
                    
                    if phase_4_result:
                        phase_documents.append({
                            "title": f"Phase 4: 유효기간 ({request.hs_code})",
                            "content": f"유효기간 분석 결과: {phase_4_result.get('summary', '')}",
                            "url": "phase_4_result",
                            "source": "validity_service"
                        })
                    
                    # 기존 문서와 Phase 결과 합치기
                    enhanced_documents = raw_documents + phase_documents
                    
                    # LLM 요약 재생성 (raw_summary로 받아서 확장 필드 포함)
                    enhanced_summary_raw = await llm_service._call_gpt_summary(
                        hs_code=request.hs_code,
                        product_name=request.product_name,
                        document_texts=llm_service._extract_document_texts(enhanced_documents)
                    )
                    
                    if enhanced_summary_raw:
                        # 기존 요약을 Phase 1-4 결과로 확장 (모든 GPT 필드 포함)
                        llm_summary = {
                            # 기본 필드
                            "critical_requirements": enhanced_summary_raw.get("critical_requirements", []),
                            "required_documents": enhanced_summary_raw.get("required_documents", []),
                            "compliance_steps": enhanced_summary_raw.get("compliance_steps", []),
                            "estimated_costs": enhanced_summary_raw.get("estimated_costs", {}),
                            "timeline": enhanced_summary_raw.get("timeline", "정보 없음"),
                            "risk_factors": enhanced_summary_raw.get("risk_factors", []),
                            "recommendations": enhanced_summary_raw.get("recommendations", []),
                            "confidence_score": enhanced_summary_raw.get("confidence_score", 0.0),
                            "model_used": "gpt-4o-mini",
                            "tokens_used": enhanced_summary_raw.get("tokens_used", 0),
                            "cost": enhanced_summary_raw.get("cost", 0.0),
                            # 확장 필드 (새로 추가된 것들)
                            "execution_checklist": enhanced_summary_raw.get("execution_checklist"),
                            "cost_breakdown": enhanced_summary_raw.get("cost_breakdown"),
                            "risk_matrix": enhanced_summary_raw.get("risk_matrix"),
                            "compliance_score": enhanced_summary_raw.get("compliance_score"),
                            "market_access": enhanced_summary_raw.get("market_access"),
                            # Phase 1-4 결과 추가
                            "phase_1_detailed_regulations": detailed_regs_result,
                            "phase_2_testing_procedures": phase_2_result,
                            "phase_3_penalties": phase_3_result,
                            "phase_4_validity": phase_4_result,
                            "cross_validation": cross_validation_result
                        }
                        print(f"  ✅ Phase 1-4 포함 LLM 요약 재생성 완료 (확장 필드 포함)")
                    
                except Exception as e:
                    print(f"  ⚠️ Phase 1-4 포함 LLM 요약 실패: {e}")
                    # 실패시 기존 요약 유지
            
        except Exception as e:
            print(f"  ❌ Phase 2-4 분석 전체 실패: {e}")
            import traceback
            traceback.print_exc()
        
        phase_end = datetime.now()
        phase_duration = (phase_end - phase_start).total_seconds() * 1000
        print(f"✅ [PHASE 2-4] 전문 분석 완료 - 소요시간: {phase_duration:.0f}ms")
        
        # Phase 2-4 결과를 메타데이터에 추가
        phase_metadata = {
            "phase_2_4_analysis": {
                "processing_time_ms": phase_duration,
                "detailed_regulations": {
                    "success": detailed_regs_result is not None,
                    "agencies": detailed_regs_result.get("agencies", []) if detailed_regs_result else [],
                    "sources_count": len(detailed_regs_result.get("sources", [])) if detailed_regs_result else 0
                },
                "testing_procedures": {
                    "success": phase_2_result is not None,
                    "inspection_cycle": phase_2_result.get("inspection_cycle") if phase_2_result else "unknown",
                    "estimated_cost": phase_2_result.get("estimates", {}).get("estimated_cost_band") if phase_2_result else "unknown"
                },
                "penalties": {
                    "success": phase_3_result is not None,
                    "fine_range": phase_3_result.get("fine_range", {}) if phase_3_result else {}
                },
                "validity": {
                    "success": phase_4_result is not None,
                    "validity_period": phase_4_result.get("validity") if phase_4_result else "unknown"
                },
                "cross_validation": {
                    "success": cross_validation_result is not None,
                    "validation_score": cross_validation_result.validation_score if cross_validation_result else 0.0,
                    "conflicts_found": len(cross_validation_result.conflicts_found) if cross_validation_result else 0
                }
            }
        }
        state["detailed_metadata"] = state.get("detailed_metadata", {})
        state["detailed_metadata"].update(phase_metadata)
        
        # Phase 1-4 결과 디버깅 로그
        print(f"  🔍 [DEBUG] Phase 결과 상태:")
        print(f"    📋 Phase 1 (detailed_regulations): {'✅' if detailed_regs_result else '❌'}")
        print(f"    🧪 Phase 2 (testing_procedures): {'✅' if phase_2_result else '❌'}")
        print(f"    ⚖️ Phase 3 (penalties): {'✅' if phase_3_result else '❌'}")
        print(f"    ⏰ Phase 4 (validity): {'✅' if phase_4_result else '❌'}")
        print(f"    🔍 교차 검증 (cross_validation): {'✅' if cross_validation_result else '❌'}")
        
        # 🎯 통합 신뢰도 계산 (판례 검증 + 교차 검증 + 출처 신뢰도)
        overall_confidence = None
        if precedent_validation_result or cross_validation_result:
            print(f"  📊 통합 신뢰도 계산 중...")
            try:
                # 출처 신뢰도 계산
                official_sources_count = len([s for s in all_sources if '.gov' in str(s.get('url', ''))])
                source_reliability_score = official_sources_count / len(all_sources) if all_sources else 0.5
                
                # 가중 평균 계산
                precedent_score = precedent_validation_result.validation_score if precedent_validation_result else 0.5
                cross_score = cross_validation_result.validation_score if cross_validation_result else 0.5
                
                overall_score = (precedent_score * 0.4) + (cross_score * 0.3) + (source_reliability_score * 0.3)
                
                # 모든 Red Flags 수집
                all_red_flags = []
                if precedent_validation_result:
                    all_red_flags.extend(precedent_validation_result.red_flags)
                if cross_validation_result:
                    for conflict in cross_validation_result.conflicts_found:
                        all_red_flags.append({
                            "type": "regulation_conflict",
                            "severity": conflict.severity,
                            "description": conflict.conflict_description,
                            "agencies": conflict.conflicting_agencies
                        })
                
                # 최종 판정
                if overall_score >= 0.85 and len(all_red_flags) == 0:
                    verdict_status = "RELIABLE"
                    confidence_level = "HIGH"
                elif overall_score >= 0.7:
                    verdict_status = "NEEDS_REVIEW"
                    confidence_level = "MEDIUM"
                else:
                    verdict_status = "UNRELIABLE"
                    confidence_level = "LOW"
                
                overall_confidence = {
                    "overall_score": overall_score,
                    "confidence_level": confidence_level,
                    "breakdown": {
                        "precedent_validation": {"score": precedent_score, "weight": 0.4},
                        "cross_validation": {"score": cross_score, "weight": 0.3},
                        "source_reliability": {"score": source_reliability_score, "weight": 0.3}
                    },
                    "red_flags": all_red_flags,
                    "red_flags_count": len(all_red_flags),
                    "verdict": {
                        "status": verdict_status,
                        "confidence": confidence_level,
                        "reason": f"판례 검증 {precedent_score:.0%}, 교차 검증 {cross_score:.0%}, 출처 신뢰도 {source_reliability_score:.0%}",
                        "action": "수입 진행 가능" if verdict_status == "RELIABLE" else 
                                 "추가 확인 필요" if verdict_status == "NEEDS_REVIEW" else 
                                 "전문가 상담 권장"
                    }
                }
                
                print(f"  ✅ 통합 신뢰도: {overall_score:.2f} ({confidence_level}) - {verdict_status}")
                
            except Exception as e:
                print(f"  ⚠️ 통합 신뢰도 계산 실패: {e}")
                overall_confidence = None
        
        # 상태 업데이트 (기존 상태 유지 + citations + llm_summary + Phase 1-4 결과 + 판례 검증 추가)
        state["consolidated_results"] = {
            "certifications": all_certifications,
            "documents": all_documents,
            "sources": all_sources,
            "llm_summary": llm_summary,
            "precedents": cbp.get("precedents", []) if cbp else [],
            "citations": citations,
            # Phase 1-4 전문 분석 결과 추가 (Phase 1도 포함!)
            "detailed_regulations": detailed_regs_result,  # Phase 1
            "testing_procedures": phase_2_result,         # Phase 2
            "penalties": phase_3_result,                  # Phase 3
            "validity": phase_4_result,                   # Phase 4
            "cross_validation": cross_validation_result,  # 교차 검증
            # 🆕 판례 기반 검증 결과
            "precedent_validation": {
                "validation_score": precedent_validation_result.validation_score if precedent_validation_result else None,
                "precedents_analyzed": precedent_validation_result.precedents_analyzed if precedent_validation_result else 0,
                "precedents_source": precedent_validation_result.precedents_source if precedent_validation_result else "none",
                "matched_requirements": precedent_validation_result.matched_requirements if precedent_validation_result else [],
                "missing_requirements": precedent_validation_result.missing_requirements if precedent_validation_result else [],
                "extra_requirements": precedent_validation_result.extra_requirements if precedent_validation_result else [],
                "red_flags": precedent_validation_result.red_flags if precedent_validation_result else [],
                "verdict": precedent_validation_result.verdict if precedent_validation_result else {}
            } if precedent_validation_result else None,
            # 🆕 통합 신뢰도
            "overall_confidence": overall_confidence,
            # 🆕 검증 요약 (Frontend용 간단 버전)
            "verification_summary": {
                "verdict": overall_confidence['verdict']['status'] if overall_confidence else "UNKNOWN",
                "confidence_score": overall_confidence['overall_score'] if overall_confidence else 0.5,
                "confidence_level": overall_confidence['confidence_level'] if overall_confidence else "MEDIUM",
                "red_flags_count": len(overall_confidence['red_flags']) if overall_confidence else 0,
                "action_recommendation": overall_confidence['verdict']['action'] if overall_confidence else "분석 결과 확인 필요"
            } if overall_confidence else None
        }
        state["precedents_meta"] = cbp
        state["next_action"] = "complete"
        
        # 💾 최종 결과 저장 (판례 검증 포함)
        if request:
            try:
                import json
                from pathlib import Path
                
                # 순환 참조 방지를 위한 안전한 직렬화
                def safe_serialize(obj):
                    """객체를 안전하게 dict로 변환"""
                    if obj is None:
                        return None
                    elif hasattr(obj, '__dict__'):
                        return {k: safe_serialize(v) for k, v in obj.__dict__.items()}
                    elif isinstance(obj, dict):
                        return {k: safe_serialize(v) for k, v in obj.items()}
                    elif isinstance(obj, list):
                        return [safe_serialize(item) for item in obj]
                    elif isinstance(obj, (str, int, float, bool)):
                        return obj
                    else:
                        return str(obj)
                
                # 안전한 파일명 생성
                safe_filename = request.product_name.replace(" ", "_").replace("/", "_")[:50]
                output_dir = Path("requirements_final")
                output_dir.mkdir(exist_ok=True)
                
                output_file = output_dir / f"final_{safe_filename}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                
                # 안전하게 직렬화
                final_data = safe_serialize(state["consolidated_results"])
                
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(final_data, f, indent=2, ensure_ascii=False, default=str)
                
                print(f"  💾 최종 결과 저장 완료: {output_file}")
                
            except Exception as e:
                print(f"  ⚠️ 최종 결과 저장 실패 (계속 진행): {e}")
                import traceback
                traceback.print_exc()
        
        return state
