"""
LangGraph Nodes for Requirements Analysis
각 단계별로 처리하는 노드들
"""

from typing import Dict, Any, List
from app.services.requirements.tavily_search import TavilySearchService
from app.services.requirements.web_scraper import WebScraper
from app.models.requirement_models import RequirementAnalysisRequest


class RequirementsNodes:
    """요구사항 분석을 위한 LangGraph 노드들"""
    
    def __init__(self):
        self.search_service = TavilySearchService()
        self.web_scraper = WebScraper()
    
    async def search_agency_documents(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """기관별 문서 검색 노드"""
        request = state["request"]
        hs_code = request.hs_code
        product_name = request.product_name
        
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
            f"FDA_8digit": f"site:fda.gov import requirements {product_name} HS {hs_code_8digit}",
            f"FCC_8digit": f"site:fcc.gov device authorization requirements {product_name} HS {hs_code_8digit}",
            f"CBP_8digit": f"site:cbp.gov import documentation requirements HS {hs_code_8digit} {product_name}",
            f"USDA_8digit": f"site:usda.gov agricultural import requirements {product_name} HS {hs_code_8digit}",
            f"EPA_8digit": f"site:epa.gov environmental regulations {product_name} HS {hs_code_8digit}",
            f"CPSC_8digit": f"site:cpsc.gov consumer product safety {product_name} HS {hs_code_8digit}",
            f"KCS_8digit": f"site:customs.go.kr Korea customs import requirements {product_name} HS {hs_code_8digit}",
            f"MFDS_8digit": f"site:mfds.go.kr food drug safety import {product_name} HS {hs_code_8digit}",
            f"MOTIE_8digit": f"site:motie.go.kr trade policy import requirements {product_name} HS {hs_code_8digit}"
        })
        
        # 6자리 HS코드 검색 (유사)
        search_queries.update({
            f"FDA_6digit": f"site:fda.gov import requirements {product_name} HS {hs_code_6digit}",
            f"FCC_6digit": f"site:fcc.gov device authorization requirements {product_name} HS {hs_code_6digit}",
            f"CBP_6digit": f"site:cbp.gov import documentation requirements HS {hs_code_6digit} {product_name}",
            f"USDA_6digit": f"site:usda.gov agricultural import requirements {product_name} HS {hs_code_6digit}",
            f"EPA_6digit": f"site:epa.gov environmental regulations {product_name} HS {hs_code_6digit}",
            f"CPSC_6digit": f"site:cpsc.gov consumer product safety {product_name} HS {hs_code_6digit}",
            f"KCS_6digit": f"site:customs.go.kr Korea customs import requirements {product_name} HS {hs_code_6digit}",
            f"MFDS_6digit": f"site:mfds.go.kr food drug safety import {product_name} HS {hs_code_6digit}",
            f"MOTIE_6digit": f"site:motie.go.kr trade policy import requirements {product_name} HS {hs_code_6digit}"
        })
        
        search_results = {}
        
        for agency, query in search_queries.items():
            print(f"\n  📡 {agency} 검색 중...")
            print(f"    쿼리: {query}")
            
            # TavilySearch 시도 (더 많은 결과 수집)
            results = await self.search_service.search(query, max_results=10)
            print(f"    📊 TavilySearch 결과: {len(results)}개")
            
            if not results:
                print(f"    💡 팁: TAVILY_API_KEY를 설정하면 더 정확한 검색 결과를 얻을 수 있습니다.")
            
            # 여러 링크 수집 (최대 5개)
            chosen_urls = []
            
            if results:
                # 각 결과 상세 출력
                for i, result in enumerate(results, 1):
                    title = result.get('title', 'No title')
                    url = result.get('url', 'No URL')
                    print(f"      {i}. {title}")
                    print(f"         URL: {url}")
                
                # site: 쿼리로 검색했으므로 모든 결과가 공식 사이트 (최대 5개 선택)
                chosen_urls = [result.get("url") for result in results[:5] if result.get("url")]
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
        
        print(f"\n📋 [NODE] 검색 완료 - {len([r for r in search_results.values() if r['url']])}개 URL 발견")
        
        # 상태 업데이트 (기존 상태 유지)
        state["search_results"] = search_results
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
        
        # 상태 업데이트 (기존 상태 유지)
        state["consolidated_results"] = {
            "certifications": all_certifications,
            "documents": all_documents,
            "sources": all_sources
        }
        state["next_action"] = "complete"
        return state
