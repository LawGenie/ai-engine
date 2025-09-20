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
        
        # 기본 URL 폴백 (TavilySearch 실패 시 사용) - 더 간단한 URL 사용
        default_urls = {
            "FDA": "https://www.fda.gov",
            "FCC": "https://www.fcc.gov",
            "CBP": "https://www.cbp.gov"
        }
        
        # 각 기관별 검색 쿼리
        search_queries = {
            "FDA": f"FDA import requirements {product_name} HS {hs_code}",
            "FCC": f"FCC device authorization requirements {product_name} HS {hs_code}",
            "CBP": f"CBP import documentation requirements HS {hs_code} {product_name}",
        }
        
        search_results = {}
        
        for agency, query in search_queries.items():
            print(f"\n  📡 {agency} 검색 중...")
            print(f"    쿼리: {query}")
            
            # TavilySearch 시도
            results = await self.search_service.search(query, max_results=5)
            print(f"    📊 TavilySearch 결과: {len(results)}개")
            
            if not results:
                print(f"    💡 팁: TAVILY_API_KEY를 설정하면 더 정확한 검색 결과를 얻을 수 있습니다.")
            
            chosen_url = None
            
            if results:
                # 각 결과 상세 출력
                for i, result in enumerate(results, 1):
                    title = result.get('title', 'No title')
                    url = result.get('url', 'No URL')
                    print(f"      {i}. {title}")
                    print(f"         URL: {url}")
                
                # 공식 도메인 우선 선택
                preferred_domains = {
                    "FDA": ["fda.gov"],
                    "FCC": ["fcc.gov"],
                    "CBP": ["cbp.gov"],
                }.get(agency, [])
                
                for result in results:
                    url = result.get("url", "")
                    if any(domain in url for domain in preferred_domains):
                        chosen_url = url
                        print(f"    ✅ {agency} 공식 도메인 선택: {url}")
                        break
                
                if not chosen_url:
                    chosen_url = results[0].get("url")
                    print(f"    🔄 {agency} 첫 번째 결과 사용: {chosen_url}")
            else:
                # TavilySearch 실패 시 기본 URL 사용
                chosen_url = default_urls.get(agency)
                print(f"    🔄 {agency} TavilySearch 실패, 기본 URL 사용: {chosen_url}")
            
            search_results[agency] = {
                "url": chosen_url,
                "all_results": results,
                "query": query,
                "is_fallback": not results  # 폴백 사용 여부 표시
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
        
        for agency, search_data in search_results.items():
            if not search_data["url"]:
                print(f"  ❌ {agency}: 스크래핑할 URL 없음")
                continue
                
            print(f"\n  📄 {agency} 스크래핑 중...")
            print(f"    URL: {search_data['url']}")
            
            try:
                if agency == "FDA":
                    result = await self.web_scraper.scrape_fda_requirements(hs_code, search_data["url"])
                elif agency == "FCC":
                    result = await self.web_scraper.scrape_fcc_requirements(hs_code, search_data["url"])
                elif agency == "CBP":
                    result = await self.web_scraper.scrape_cbp_requirements(hs_code, search_data["url"])
                else:
                    continue
                
                # 스크래핑 결과 상세 로깅
                certs = result.get("certifications", [])
                docs = result.get("documents", [])
                
                print(f"    ✅ {agency} 스크래핑 성공:")
                print(f"      📋 인증요건: {len(certs)}개")
                for cert in certs:
                    print(f"        • {cert.get('name', 'Unknown')} ({cert.get('agency', 'Unknown')})")
                
                print(f"      📄 필요서류: {len(docs)}개")
                for doc in docs:
                    print(f"        • {doc.get('name', 'Unknown')}")
                
                scraped_data[agency] = result
                
            except Exception as e:
                print(f"    ❌ {agency} 스크래핑 실패: {e}")
                scraped_data[agency] = {
                    "agency": agency,
                    "error": str(e),
                    "certifications": [],
                    "documents": []
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
            if "error" in data:
                print(f"  ❌ {agency}: 오류로 인해 제외")
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
