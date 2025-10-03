"""
LangGraph Nodes for Requirements Analysis
각 단계별로 처리하는 노드들
"""

from typing import Dict, Any, List
from .tools import RequirementsTools
from app.services.requirements.keyword_extractor import KeywordExtractor, HfKeywordExtractor, OpenAiKeywordExtractor
from app.services.requirements.tavily_search import TavilySearchService
from app.services.requirements.web_scraper import WebScraper
from app.models.requirement_models import RequirementAnalysisRequest
from datetime import datetime


class RequirementsNodes:
    """요구사항 분석을 위한 LangGraph 노드들"""
    
    def __init__(self):
        # RequirementsTools에서 프로바이더를 가져와서 사용
        self.tools = RequirementsTools()
        self.web_scraper = WebScraper()
        self.keyword_extractor = None
        self.hf_extractor = None
        self.openai_extractor = None

    async def extract_core_keywords(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """상품명/설명에서 핵심 키워드 추출 (간단 휴리스틱).
        - 영문/숫자만 남기고 분절
        - 불용어 제거
        - 길이 3 이상 단어 우선, 상위 3개 반환
        - 한글일 경우 간단 매핑 시도
        """
        request = state["request"]
        name = (request.product_name or "").strip()
        desc = (request.product_description or "").strip()
        # HF 추출기 시도 → 실패 시 휴리스틱
        if self.hf_extractor is None:
            try:
                self.hf_extractor = HfKeywordExtractor()
            except Exception:
                self.hf_extractor = None
        if self.keyword_extractor is None:
            self.keyword_extractor = KeywordExtractor()
        if self.openai_extractor is None:
            try:
                self.openai_extractor = OpenAiKeywordExtractor()
            except Exception:
                self.openai_extractor = None

        core_keywords = []
        try:
            # OpenAI 우선(플래그 활성 시) → HF → 휴리스틱
            if self.openai_extractor:
                core_keywords = self.openai_extractor.extract(name, desc, top_k=3)
        except Exception:
            core_keywords = []
        try:
            if self.hf_extractor:
                core_keywords = self.hf_extractor.extract(name, desc, top_k=3)
        except Exception:
            core_keywords = []
        if not core_keywords:
            core_keywords = self.keyword_extractor.extract(name, desc, top_k=3)
        
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
        
        # 각 기관별 검색 쿼리 (8자리와 6자리 모두)
        search_queries = {}
        
        # 8자리 HS코드 검색 (정확)
        search_queries.update({
            f"FDA_8digit": f"site:fda.gov import requirements {query_term} HS {hs_code_8digit}",
            f"FCC_8digit": f"site:fcc.gov device authorization requirements {query_term} HS {hs_code_8digit}",
            f"CBP_8digit": f"site:cbp.gov import documentation requirements HS {hs_code_8digit} {query_term}",
            f"USDA_8digit": f"site:usda.gov agricultural import requirements {query_term} HS {hs_code_8digit}",
            f"EPA_8digit": f"site:epa.gov environmental regulations {query_term} HS {hs_code_8digit}",
            f"CPSC_8digit": f"site:cpsc.gov consumer product safety {query_term} HS {hs_code_8digit}",
            f"KCS_8digit": f"site:customs.go.kr Korea customs import requirements {query_term} HS {hs_code_8digit}",
            f"MFDS_8digit": f"site:mfds.go.kr food drug safety import {query_term} HS {hs_code_8digit}",
            f"MOTIE_8digit": f"site:motie.go.kr trade policy import requirements {query_term} HS {hs_code_8digit}"
        })
        
        # 6자리 HS코드 검색 (유사)
        search_queries.update({
            f"FDA_6digit": f"site:fda.gov import requirements {query_term} HS {hs_code_6digit}",
            f"FCC_6digit": f"site:fcc.gov device authorization requirements {query_term} HS {hs_code_6digit}",
            f"CBP_6digit": f"site:cbp.gov import documentation requirements HS {hs_code_6digit} {query_term}",
            f"USDA_6digit": f"site:usda.gov agricultural import requirements {query_term} HS {hs_code_6digit}",
            f"EPA_6digit": f"site:epa.gov environmental regulations {query_term} HS {hs_code_6digit}",
            f"CPSC_6digit": f"site:cpsc.gov consumer product safety {query_term} HS {hs_code_6digit}",
            f"KCS_6digit": f"site:customs.go.kr Korea customs import requirements {query_term} HS {hs_code_6digit}",
            f"MFDS_6digit": f"site:mfds.go.kr food drug safety import {query_term} HS {hs_code_6digit}",
            f"MOTIE_6digit": f"site:motie.go.kr trade policy import requirements {query_term} HS {hs_code_6digit}"
        })
        
        search_results = {}
        
        for agency, query in search_queries.items():
            print(f"\n  📡 {agency} 검색 중...")
            print(f"    쿼리: {query}")
            
            # 프로바이더를 통한 검색 시도 (더 많은 결과 수집)
            results = await self.tools.search_provider.search(query, max_results=15)  # 검색 결과를 15개로 확장
            print(f"    📊 {self.tools.search_provider.provider_name} 검색 결과: {len(results)}개")
            
            if not results and self.tools.search_provider.provider_name == "disabled":
                print(f"    🔇 검색 비활성화 모드: '{query}' 스킵됨")
            elif not results:
                print(f"    💡 팁: TAVILY_API_KEY를 설정하면 더 정확한 검색 결과를 얻을 수 있습니다.")
            
                # 여러 링크 수집 (최대 10개로 확장)
                chosen_urls = []
                
                if results:
                    # 각 결과 상세 출력
                    for i, result in enumerate(results, 1):
                        title = result.get('title', 'No title')
                        url = result.get('url', 'No URL')
                        print(f"      {i}. {title}")
                        print(f"         URL: {url}")
                    
                    # site: 쿼리로 검색했으므로 모든 결과가 공식 사이트 (최대 10개 선택)
                    chosen_urls = [result.get("url") for result in results[:10] if result.get("url")]
                    print(f"    ✅ {agency} 공식 사이트 결과 {len(chosen_urls)}개 선택")
            else:
                # TavilySearch 실패 시 기본 URL 사용
                agency_name = agency.split("_")[0]  # FDA_8digit -> FDA
                default_url = default_urls.get(agency_name)
                if default_url:
                    chosen_urls = [default_url]
                print(f"    🔄 {agency} TavilySearch 실패, 기본 URL 사용: {default_url}")
            
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
                result["hs_code_8digit"] = {
                    "urls": agency_data["8digit"]["urls"],
                    "results": result.get("certifications", []) + result.get("documents", [])
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
                    "8digit_hs_code_urls": sum(data.get("hs_code_8digit", {}).get("urls", []) for data in scraped_data.values() if data.get("hs_code_8digit", {}).get("urls")),
                    "6digit_hs_code_urls": sum(data.get("hs_code_6digit", {}).get("urls", []) for data in scraped_data.values() if data.get("hs_code_6digit", {}).get("urls")),
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
        
        # 참고: CBP 판례 수집 추가
        request = state.get("request")
        cbp = None
        precedents_fetch_start = datetime.now()
        if request:
            try:
                cbp = await self.tools.get_cbp_precedents(request.hs_code)
                precedents_fetch_end = datetime.now()
                precedents_fetch_time = (precedents_fetch_end - precedents_fetch_start).total_seconds() * 1000
                print(f"📊 CBP 판례 수집 성공: {len(cbp.get('precedents', []))}개 판례 확인됨 ({precedents_fetch_time:.0f}ms)")
            except Exception as e:
                cbp = {"error": "precedent_fetch_failed", "error_message": str(e)}
                precedents_fetch_end = datetime.now()
                precedents_fetch_time = (precedents_fetch_end - precedents_fetch_start).total_seconds() * 1000
                print(f"📊 CBP 판례 수집 실패: {e} ({precedents_fetch_time:.0f}ms)")

        # 하이브리드(API+웹) 결과도 통합 (Phase 2-4 포함)
        hybrid = state.get("hybrid_result") or {}
        hybrid_certifications = 0
        hybrid_documents = 0
        hybrid_sources = 0
        phase_2_4_counts = {"testing_procedures": 0, "penalties_enforcement": 0, "validity_periods": 0}
        
        if hybrid and not hybrid.get("error"):
            combined = hybrid.get("combined_results", {})
            if combined:
                hybrid_certifications = len(combined.get("certifications", []))
                hybrid_documents = len(combined.get("documents", []))
                hybrid_sources = len(combined.get("sources", []))
                
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

        # 상태 업데이트 (기존 상태 유지)
        state["consolidated_results"] = {
            "certifications": all_certifications,
            "documents": all_documents,
            "sources": all_sources,
            "precedents": cbp.get("precedents", []) if cbp else []
        }
        state["precedents_meta"] = cbp
        state["next_action"] = "complete"
        return state
