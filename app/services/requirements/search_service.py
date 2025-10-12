"""
검색 서비스

무료 정부 API와 유료 Tavily Search를 조합하여 비용 최적화된 규정 검색을 제공합니다.

검색 전략:
1. 우선순위: 무료 API (FDA, USDA, EPA 등) 먼저 시도
2. 폴백: Tavily Search (무료 API 실패 시)
3. 캐시: SearchResultCache 테이블 사용 (1시간 TTL)

지원 API:
- FDA: api.fda.gov (drug/label, food/enforcement)
- USDA: api.nal.usda.gov (ndb/search)
- EPA: api.epa.gov (chemicals)
- Tavily: api.tavily.com (유료, $0.001/검색)

사용 예:
    service = SearchService()
    results = await service.search_requirements(
        hs_code="3304.99",
        product_name="serum",
        agencies=["FDA", "EPA"],
        search_queries={"FDA": ["serum import", "cosmetic regulation"]}
    )
"""

import asyncio
import aiohttp
import json
import hashlib
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import os

@dataclass
class SearchResult:
    """검색 결과"""
    agency: str
    query: str
    results: List[Dict[str, Any]]
    source: str  # 'free_api', 'tavily', 'cache'
    cost: float = 0.0
    response_time_ms: int = 0

@dataclass
class SearchStrategy:
    """검색 전략"""
    agency: str
    provider: str  # 'free_api', 'tavily', 'hybrid'
    api_endpoint: str
    api_key_required: bool = False
    rate_limit_per_hour: int = 1000
    cost_per_request: float = 0.0
    is_active: bool = True

class SearchService:
    """검색 서비스 - 무료 정부 API + 유료 Tavily Search 조합"""
    
    def __init__(self, backend_api_url: str = "http://localhost:8081"):
        self.backend_api_url = backend_api_url
        self.tavily_api_key = os.getenv('TAVILY_API_KEY')
        self.cache_ttl = 3600  # 1시간
        self.search_strategies = {}
        
        # 무료 API 엔드포인트
        self.free_api_endpoints = {
            "FDA": "https://api.fda.gov",
            "USDA": "https://api.nal.usda.gov", 
            "EPA": "https://api.epa.gov",
            "FCC": "https://api.fcc.gov",
            "CPSC": "https://api.cpsc.gov"
        }
        
        # Tavily 검색 설정
        self.tavily_config = {
            "api_url": "https://api.tavily.com/search",
            "max_results": 5,
            "include_domains": [
                "fda.gov", "usda.gov", "epa.gov", 
                "fcc.gov", "cpsc.gov", "ftc.gov"
            ]
        }
    
    async def search_requirements(
        self, 
        hs_code: str, 
        product_name: str,
        agencies: List[str],
        search_queries: Dict[str, List[str]]
    ) -> Dict[str, SearchResult]:
        """요구사항 검색 (하이브리드 전략)"""
        
        print(f"🔍 하이브리드 검색 시작 - HS코드: {hs_code}, 기관: {agencies}")
        
        # 검색 전략 로드
        await self._load_search_strategies()
        
        # 검색 결과 저장소
        all_results = {}
        
        # 병렬 검색 실행
        tasks = []
        for agency in agencies:
            if agency in search_queries:
                queries = search_queries[agency]
                task = self._search_agency_requirements(
                    agency, hs_code, product_name, queries
                )
                tasks.append(task)
        
        # 모든 검색 완료 대기
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 결과 처리
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"❌ 검색 실패 ({agencies[i]}): {result}")
                continue
            
            if result:
                all_results[result.agency] = result
        
        print(f"✅ 하이브리드 검색 완료 - {len(all_results)}개 기관 결과 수집")
        return all_results
    
    async def _search_agency_requirements(
        self, 
        agency: str, 
        hs_code: str, 
        product_name: str,
        queries: List[str]
    ) -> Optional[SearchResult]:
        """특정 기관의 요구사항 검색"""
        
        strategy = self.search_strategies.get(agency)
        if not strategy or not strategy.is_active:
            print(f"⚠️ {agency} 검색 전략 비활성화")
            return None
        
        # 캐시 확인
        cached_result = await self._get_from_cache(agency, hs_code, product_name)
        if cached_result:
            print(f"✅ {agency} 캐시에서 조회")
            return cached_result
        
        # 🚀 하이브리드 검색 개선: 무료 API 우선, 실패시에만 Tavily
        result = None
        
        # 1단계: 무료 API 시도
        if strategy.provider in ["free_api", "hybrid"]:
            print(f"🆓 {agency} 무료 API 검색 시도...")
            result = await self._search_free_api(agency, queries)
            
            # 무료 API 성공시 Tavily 스킵
            if result and len(result.results) > 0:
                print(f"✅ {agency} 무료 API 성공 - Tavily 스킵으로 비용 절약!")
                result.source = "free_api"
            else:
                print(f"⚠️ {agency} 무료 API 실패 - Tavily 폴백")
                result = None
        
        # 2단계: Tavily 폴백 (무료 API 실패시 또는 tavily 전용)
        if not result and strategy.provider in ["tavily", "hybrid"]:
            print(f"💰 {agency} Tavily 검색 실행...")
            result = await self._search_tavily(agency, queries)
            if result:
                result.source = "tavily"
        elif not result:
            print(f"❌ {agency} 검색 실패 - 지원되는 제공자 없음")
            return None
        
        if result:
            # 캐시에 저장
            await self._save_to_cache(result, hs_code, product_name)
            print(f"✅ {agency} 검색 완료 - {len(result.results)}개 결과")
        
        return result
    
    async def _search_free_api(self, agency: str, queries: List[str]) -> Optional[SearchResult]:
        """무료 API 검색"""
        try:
            endpoint = self.free_api_endpoints.get(agency)
            if not endpoint:
                print(f"❌ {agency} 무료 API 엔드포인트 없음")
                return None
            
            all_results = []
            total_cost = 0.0
            start_time = datetime.now()
            
            # 각 쿼리별로 검색
            for query in queries[:3]:  # 최대 3개 쿼리만
                try:
                    api_results = await self._call_free_api(endpoint, query, agency)
                    if api_results:
                        all_results.extend(api_results)
                except Exception as e:
                    print(f"⚠️ {agency} API 호출 실패 ({query}): {e}")
            
            response_time = int((datetime.now() - start_time).total_seconds() * 1000)
            
            return SearchResult(
                agency=agency,
                query="; ".join(queries),
                results=all_results,
                source="free_api",
                cost=total_cost,
                response_time_ms=response_time
            )
            
        except Exception as e:
            print(f"❌ {agency} 무료 API 검색 실패: {e}")
            return None
    
    async def _search_tavily(self, agency: str, queries: List[str]) -> Optional[SearchResult]:
        """Tavily 검색"""
        try:
            if not self.tavily_api_key:
                print(f"❌ Tavily API 키 없음")
                return None
            
            all_results = []
            total_cost = 0.0
            start_time = datetime.now()
            
            # 각 쿼리별로 검색
            for query in queries[:2]:  # Tavily는 최대 2개 쿼리만
                try:
                    tavily_results = await self._call_tavily_api(query, agency)
                    if tavily_results:
                        all_results.extend(tavily_results)
                        total_cost += 0.001  # Tavily 비용
                except Exception as e:
                    print(f"⚠️ Tavily 검색 실패 ({query}): {e}")
            
            response_time = int((datetime.now() - start_time).total_seconds() * 1000)
            
            return SearchResult(
                agency=agency,
                query="; ".join(queries),
                results=all_results,
                source="tavily",
                cost=total_cost,
                response_time_ms=response_time
            )
            
        except Exception as e:
            print(f"❌ {agency} Tavily 검색 실패: {e}")
            return None
    
    async def _call_free_api(self, endpoint: str, query: str, agency: str) -> List[Dict[str, Any]]:
        """무료 API 호출"""
        try:
            async with aiohttp.ClientSession() as session:
                # API별 특화된 검색 로직
                if agency == "FDA":
                    url = f"{endpoint}/drug/label.json"
                    params = {"search": query, "limit": 5}
                elif agency == "USDA":
                    url = f"{endpoint}/ndb/search"
                    params = {"q": query, "max": 5}
                elif agency == "EPA":
                    url = f"{endpoint}/chemicals"
                    params = {"search": query, "limit": 5}
                else:
                    # 기본 검색
                    url = endpoint
                    params = {"q": query, "limit": 5}
                
                async with session.get(url, params=params, timeout=30) as response:
                    if response.status == 200:
                        data = await response.json()
                        return self._parse_api_response(data, agency)
                    else:
                        print(f"⚠️ {agency} API 응답 오류: {response.status}")
                        return []
                        
        except Exception as e:
            print(f"❌ {agency} API 호출 오류: {e}")
            return []
    
    async def _call_tavily_api(self, query: str, agency: str) -> List[Dict[str, Any]]:
        """Tavily API 호출"""
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "api_key": self.tavily_api_key,
                    "query": query,
                    "search_depth": "basic",
                    "include_answer": True,
                    "include_images": False,
                    "include_raw_content": False,
                    "max_results": self.tavily_config["max_results"],
                    "include_domains": [f"{agency.lower()}.gov"]
                }
                
                async with session.post(
                    self.tavily_config["api_url"], 
                    json=payload, 
                    timeout=30
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return self._parse_tavily_response(data)
                    else:
                        print(f"⚠️ Tavily API 응답 오류: {response.status}")
                        return []
                        
        except Exception as e:
            print(f"❌ Tavily API 호출 오류: {e}")
            return []
    
    def _parse_api_response(self, data: Dict[str, Any], agency: str) -> List[Dict[str, Any]]:
        """
        API 응답 파싱 (기관별 커스텀 로직)
        
        각 기관 API는 응답 형식이 다르므로 개별 파싱 로직 필요:
        - FDA: {"results": [{"openfda": {...}, "indications_and_usage": [...]}]}
        - USDA: {"list": {"item": [{"name": "...", "group": "..."}]}}
        - 기타: [{"title": "...", "description": "...", "url": "..."}] (기본 형식)
        
        Returns:
            표준 형식의 검색 결과 리스트:
            [{"title": str, "content": str, "url": str, "source": str, "agency": str}]
        """
        results = []
        
        try:
            if agency == "FDA" and "results" in data:
                for item in data["results"][:5]:
                    results.append({
                        "title": item.get("openfda", {}).get("brand_name", ["Unknown"])[0],
                        "content": item.get("indications_and_usage", ["No content"])[0],
                        "url": f"https://www.fda.gov/drugs/{item.get('application_number', '')}",
                        "source": "FDA API",
                        "agency": agency
                    })
            elif agency == "USDA" and "list" in data:
                for item in data["list"]["item"][:5]:
                    results.append({
                        "title": item.get("name", "Unknown"),
                        "content": item.get("group", "No content"),
                        "url": f"https://ndb.nal.usda.gov/ndb/foods/{item.get('ndbno', '')}",
                        "source": "USDA API",
                        "agency": agency
                    })
            else:
                # 기본 파싱
                if isinstance(data, list):
                    for item in data[:5]:
                        results.append({
                            "title": item.get("title", "Unknown"),
                            "content": item.get("description", "No content"),
                            "url": item.get("url", ""),
                            "source": f"{agency} API",
                            "agency": agency
                        })
                        
        except Exception as e:
            print(f"⚠️ {agency} 응답 파싱 오류: {e}")
        
        return results
    
    def _parse_tavily_response(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Tavily 응답 파싱"""
        results = []
        
        try:
            if "results" in data:
                for item in data["results"]:
                    results.append({
                        "title": item.get("title", "Unknown"),
                        "content": item.get("content", "No content"),
                        "url": item.get("url", ""),
                        "source": "Tavily Search",
                        "agency": "Multiple"
                    })
                    
        except Exception as e:
            print(f"⚠️ Tavily 응답 파싱 오류: {e}")
        
        return results
    
    async def _get_from_cache(self, agency: str, hs_code: str, product_name: str) -> Optional[SearchResult]:
        """캐시에서 검색 결과 조회"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.backend_api_url}/api/search-cache/search"
                params = {
                    "hs_code": hs_code,
                    "agency": agency,
                    "product_name": product_name
                }
                
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data:
                            return SearchResult(
                                agency=data["agency"],
                                query=data["searchQuery"],
                                results=json.loads(data["searchResults"]),
                                source="cache",
                                cost=0.0,
                                response_time_ms=0
                            )
        except Exception as e:
            print(f"⚠️ 캐시 조회 실패: {e}")
        
        return None
    
    async def _save_to_cache(self, result: SearchResult, hs_code: str, product_name: str):
        """검색 결과를 캐시에 저장"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.backend_api_url}/api/search-cache"
                data = {
                    "hsCode": hs_code,
                    "productName": product_name,
                    "agency": result.agency,
                    "searchQuery": result.query,
                    "searchResults": json.dumps(result.results),
                    "cacheKey": self._generate_cache_key(hs_code, product_name, result.agency),
                    "expiresAt": (datetime.now() + timedelta(seconds=self.cache_ttl)).isoformat()
                }
                
                async with session.post(url, json=data) as response:
                    if response.status in [200, 201]:
                        print(f"✅ {result.agency} 캐시 저장 완료")
                    else:
                        print(f"❌ {result.agency} 캐시 저장 실패: {response.status}")
                        
        except Exception as e:
            print(f"❌ 캐시 저장 오류: {e}")
    
    def _generate_cache_key(self, hs_code: str, product_name: str, agency: str) -> str:
        """캐시 키 생성"""
        key_string = f"{hs_code}_{product_name}_{agency}"
        return hashlib.md5(key_string.encode()).hexdigest()
    
    async def _load_search_strategies(self):
        """검색 전략 로드"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.backend_api_url}/api/agency-search-strategies"
                
                async with session.get(url) as response:
                    if response.status == 200:
                        strategies_data = await response.json()
                        for strategy_data in strategies_data:
                            strategy = SearchStrategy(
                                agency=strategy_data["agencyName"],
                                provider=strategy_data["searchProvider"],
                                api_endpoint=strategy_data["apiEndpoint"],
                                api_key_required=strategy_data["apiKeyRequired"],
                                rate_limit_per_hour=strategy_data["rateLimitPerHour"],
                                cost_per_request=float(strategy_data["costPerRequest"]),
                                is_active=strategy_data["isActive"]
                            )
                            self.search_strategies[strategy.agency] = strategy
                        
                        print(f"✅ 검색 전략 로드 완료 - {len(self.search_strategies)}개")
                    else:
                        print(f"❌ 검색 전략 로드 실패: {response.status}")
                        
        except Exception as e:
            print(f"❌ 검색 전략 로드 오류: {e}")
            # 기본 전략 설정
            self._set_default_strategies()
    
    def _set_default_strategies(self):
        """기본 검색 전략 설정"""
        default_strategies = {
            "FDA": SearchStrategy("FDA", "free_api", "https://api.fda.gov"),
            "USDA": SearchStrategy("USDA", "free_api", "https://api.nal.usda.gov"),
            "EPA": SearchStrategy("EPA", "free_api", "https://api.epa.gov"),
            "FCC": SearchStrategy("FCC", "free_api", "https://api.fcc.gov"),
            "CPSC": SearchStrategy("CPSC", "free_api", "https://api.cpsc.gov"),
            "Tavily": SearchStrategy("Tavily", "tavily", "https://api.tavily.com", True, 1000, 0.001)
        }
        
        self.search_strategies.update(default_strategies)
        print(f"✅ 기본 검색 전략 설정 완료")
    
    async def get_search_statistics(self) -> Dict[str, Any]:
        """검색 통계 조회"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.backend_api_url}/api/search-cache/statistics"
                
                async with session.get(url) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        return {"error": f"통계 조회 실패: {response.status}"}
                        
        except Exception as e:
            return {"error": f"통계 조회 오류: {e}"}
    
    def get_cost_summary(self, results: Dict[str, SearchResult]) -> Dict[str, Any]:
        """비용 요약"""
        total_cost = sum(result.cost for result in results.values())
        free_api_count = sum(1 for result in results.values() if result.source == "free_api")
        tavily_count = sum(1 for result in results.values() if result.source == "tavily")
        cache_count = sum(1 for result in results.values() if result.source == "cache")
        
        return {
            "total_cost": total_cost,
            "free_api_searches": free_api_count,
            "tavily_searches": tavily_count,
            "cache_hits": cache_count,
            "cost_savings": total_cost * 0.6  # 예상 절감액
        }
