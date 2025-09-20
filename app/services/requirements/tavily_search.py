import os
from typing import List, Dict

# Tavily 패키지 import 시도
try:
    from langchain_community.tools.tavily_search.tool import TavilySearchResults
    TAVILY_AVAILABLE = True
    TAVILY_TYPE = "langchain_community"
    print("✅ langchain_community.tavily_search 사용")
except ImportError:
    try:
        from tavily_python import TavilySearchResults
        TAVILY_AVAILABLE = True
        TAVILY_TYPE = "tavily_python"
        print("✅ tavily_python 사용")
    except ImportError:
        try:
            from tavily import TavilyClient
            TAVILY_AVAILABLE = True
            TAVILY_TYPE = "tavily"
            print("✅ tavily 사용")
        except ImportError:
            TAVILY_AVAILABLE = False
            TAVILY_TYPE = None
            print("⚠️ Tavily 패키지가 설치되지 않았습니다. pip install tavily-python==0.3.3 실행하세요.")


class TavilySearchService:
    """Tavily Search API 공식 SDK wrapper with graceful fallback."""

    def __init__(self):
        # 환경변수에서 API 키 로드
        self.api_key = os.getenv("TAVILY_API_KEY")
        print(f"🔑 TavilySearchService 초기화 - API 키: {'설정됨' if self.api_key else '없음'}")
        if self.api_key:
            print(f"   📝 API 키 앞 10자리: {self.api_key[:10]}...")
        self.client = None
        self.timeout = 20.0

    def is_enabled(self) -> bool:
        if not TAVILY_AVAILABLE:
            print("  ⚠️ Tavily 패키지가 설치되지 않았습니다.")
            return False
        if not self.api_key:
            print("  ⚠️ TAVILY_API_KEY가 설정되지 않았습니다.")
            return False
        return True

    def _get_client(self):
        """Tavily 클라이언트 초기화 (지연 로딩)"""
        if not self.client and self.is_enabled():
            try:
                print(f"  🔧 Tavily 클라이언트 초기화 - 타입: {TAVILY_TYPE}")
                if TAVILY_TYPE == "langchain_community":
                    # langchain_community 방식 (제공된 코드와 동일)
                    self.client = TavilySearchResults()
                    print(f"  ✅ TavilySearchResults 클라이언트 초기화 완료")
                elif TAVILY_TYPE == "tavily_python":
                    # tavily-python 방식
                    self.client = TavilySearchResults(api_key=self.api_key)
                    print(f"  ✅ TavilySearchResults (tavily_python) 클라이언트 초기화 완료")
                elif TAVILY_TYPE == "tavily":
                    # tavily 방식
                    self.client = TavilyClient(api_key=self.api_key)
                    print(f"  ✅ TavilyClient 클라이언트 초기화 완료")
                else:
                    print("  ❌ Tavily 클라이언트를 사용할 수 없습니다.")
                    return None
            except Exception as e:
                print(f"  ❌ Tavily 클라이언트 초기화 실패: {e}")
                return None
        return self.client

    async def search(self, query: str, max_results: int = 5) -> List[Dict]:
        if not self.is_enabled():
            print(f"  🔄 TavilySearch 비활성화, 빈 결과 반환")
            return []

        client = self._get_client()
        if not client:
            print(f"  🔄 TavilySearch 클라이언트 생성 실패, 빈 결과 반환")
            return []

        try:
            print(f"  🔍 TavilySearch 실행 - 쿼리: {query}")
            print(f"  🔑 API 키 사용: {'예' if self.api_key else '아니오'}")
            
            # Tavily 검색 실행
            print(f"  🔍 TavilySearch 실행 - 타입: {TAVILY_TYPE}")
            if TAVILY_TYPE == "langchain_community":
                # langchain_community 방식 (제공된 코드와 동일)
                print(f"  🔧 langchain_community 방식 사용")
                results = client.invoke({"query": query})
                print(f"  📊 TavilySearch 결과: {len(results) if isinstance(results, list) else 'N/A'}개")
            elif TAVILY_TYPE == "tavily_python":
                # tavily-python 방식
                print(f"  🔧 tavily_python 방식 사용")
                if hasattr(client, 'search'):
                    response = client.search(
                        query=query,
                        max_results=max_results,
                        include_answer=False,
                        search_depth="advanced"
                    )
                    results = response.get("results", [])
                else:
                    results = client.run(query)
            elif TAVILY_TYPE == "tavily":
                # tavily 방식
                print(f"  🔧 tavily 방식 사용")
                response = client.search(
                    query=query,
                    max_results=max_results,
                    include_answer=False,
                    search_depth="advanced"
                )
                results = response.get("results", [])
            else:
                print(f"  ❌ 알 수 없는 Tavily 타입: {TAVILY_TYPE}")
                results = []
            
            print(f"  📊 Tavily 검색 결과: {len(results)}개")
            
            return results
            
        except Exception as e:
            print(f"  ❌ Tavily 검색 실패: {e}")
            return []


