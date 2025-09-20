"""
LangGraph Tools for Requirements Analysis
특정 작업을 수행하는 도구들
"""

from typing import Dict, Any, List
from app.services.requirements.tavily_search import TavilySearchService
from app.services.requirements.web_scraper import WebScraper


class RequirementsTools:
    """요구사항 분석을 위한 LangGraph 도구들"""
    
    def __init__(self):
        self.search_service = TavilySearchService()
        self.web_scraper = WebScraper()
    
    async def search_fda_documents(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        """FDA 관련 문서 검색 도구"""
        print(f"🔧 [TOOL] FDA 문서 검색: {query}")
        
        results = await self.search_service.search(query, max_results)
        
        # FDA 공식 도메인 필터링
        fda_results = []
        for result in results:
            url = result.get("url", "")
            if "fda.gov" in url:
                fda_results.append(result)
                print(f"  ✅ FDA 공식 문서 발견: {result.get('title', 'No title')}")
            else:
                print(f"  ❌ FDA 외부 문서 제외: {result.get('title', 'No title')}")
        
        return {
            "agency": "FDA",
            "query": query,
            "total_results": len(results),
            "fda_results": fda_results,
            "selected_url": fda_results[0]["url"] if fda_results else None
        }
    
    async def search_fcc_documents(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        """FCC 관련 문서 검색 도구"""
        print(f"🔧 [TOOL] FCC 문서 검색: {query}")
        
        results = await self.search_service.search(query, max_results)
        
        # FCC 공식 도메인 필터링
        fcc_results = []
        for result in results:
            url = result.get("url", "")
            if "fcc.gov" in url:
                fcc_results.append(result)
                print(f"  ✅ FCC 공식 문서 발견: {result.get('title', 'No title')}")
            else:
                print(f"  ❌ FCC 외부 문서 제외: {result.get('title', 'No title')}")
        
        return {
            "agency": "FCC",
            "query": query,
            "total_results": len(results),
            "fcc_results": fcc_results,
            "selected_url": fcc_results[0]["url"] if fcc_results else None
        }
    
    async def search_cbp_documents(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        """CBP 관련 문서 검색 도구"""
        print(f"🔧 [TOOL] CBP 문서 검색: {query}")
        
        results = await self.search_service.search(query, max_results)
        
        # CBP 공식 도메인 필터링
        cbp_results = []
        for result in results:
            url = result.get("url", "")
            if "cbp.gov" in url:
                cbp_results.append(result)
                print(f"  ✅ CBP 공식 문서 발견: {result.get('title', 'No title')}")
            else:
                print(f"  ❌ CBP 외부 문서 제외: {result.get('title', 'No title')}")
        
        return {
            "agency": "CBP",
            "query": query,
            "total_results": len(results),
            "cbp_results": cbp_results,
            "selected_url": cbp_results[0]["url"] if cbp_results else None
        }
    
    async def scrape_document(self, agency: str, url: str, hs_code: str) -> Dict[str, Any]:
        """특정 문서 스크래핑 도구"""
        print(f"🔧 [TOOL] {agency} 문서 스크래핑")
        print(f"  URL: {url}")
        print(f"  HS코드: {hs_code}")
        
        try:
            if agency == "FDA":
                result = await self.web_scraper.scrape_fda_requirements(hs_code, url)
            elif agency == "FCC":
                result = await self.web_scraper.scrape_fcc_requirements(hs_code, url)
            elif agency == "CBP":
                result = await self.web_scraper.scrape_cbp_requirements(hs_code, url)
            else:
                return {"error": f"Unknown agency: {agency}"}
            
            # 스크래핑 결과 상세 로깅
            certs = result.get("certifications", [])
            docs = result.get("documents", [])
            
            print(f"  ✅ {agency} 스크래핑 성공:")
            print(f"    📋 인증요건: {len(certs)}개")
            for i, cert in enumerate(certs, 1):
                print(f"      {i}. {cert.get('name', 'Unknown')} ({cert.get('agency', 'Unknown')})")
                print(f"         설명: {cert.get('description', 'No description')}")
            
            print(f"    📄 필요서류: {len(docs)}개")
            for i, doc in enumerate(docs, 1):
                print(f"      {i}. {doc.get('name', 'Unknown')}")
                print(f"         설명: {doc.get('description', 'No description')}")
            
            return result
            
        except Exception as e:
            print(f"  ❌ {agency} 스크래핑 실패: {e}")
            return {
                "agency": agency,
                "error": str(e),
                "certifications": [],
                "documents": []
            }
    
    async def analyze_requirements(self, requirements_data: Dict[str, Any]) -> Dict[str, Any]:
        """요구사항 분석 도구"""
        print(f"🔧 [TOOL] 요구사항 분석 시작")
        
        certifications = requirements_data.get("certifications", [])
        documents = requirements_data.get("documents", [])
        
        # 분석 통계
        total_certs = len(certifications)
        total_docs = len(documents)
        
        # 기관별 통계
        agency_stats = {}
        for cert in certifications:
            agency = cert.get("agency", "Unknown")
            agency_stats[agency] = agency_stats.get(agency, 0) + 1
        
        print(f"  📊 분석 결과:")
        print(f"    📋 총 인증요건: {total_certs}개")
        print(f"    📄 총 필요서류: {total_docs}개")
        print(f"    🏢 기관별 인증요건:")
        for agency, count in agency_stats.items():
            print(f"      • {agency}: {count}개")
        
        # 우선순위 분석
        high_priority = [c for c in certifications if c.get("priority") == "high"]
        required_docs = [d for d in documents if d.get("required", False)]
        
        print(f"    ⚠️ 고우선순위 인증요건: {len(high_priority)}개")
        print(f"    📋 필수 서류: {len(required_docs)}개")
        
        return {
            "total_certifications": total_certs,
            "total_documents": total_docs,
            "agency_stats": agency_stats,
            "high_priority_count": len(high_priority),
            "required_docs_count": len(required_docs),
            "analysis_complete": True
        }
