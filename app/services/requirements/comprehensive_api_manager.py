#!/usr/bin/env python3
"""
포괄적 API 관리 시스템
- 모든 정부 기관의 API를 통합 관리
- HS 코드별 적절한 기관 자동 선택
- 실시간 API 상태 모니터링 및 대체
"""

import asyncio
import httpx
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path
import sqlite3
import os
from urllib.parse import quote_plus

@dataclass
class ComprehensiveAPIEndpoint:
    """포괄적 API 엔드포인트 정의"""
    name: str
    agency: str
    url: str
    method: str
    params: Dict[str, Any]
    headers: Dict[str, str]
    success_rate: float
    last_success: Optional[datetime]
    last_failure: Optional[datetime]
    failure_count: int
    category: str
    hs_codes: List[str]
    api_key_required: bool
    rate_limit: str

class ComprehensiveAPIManager:
    """포괄적 API 관리자"""
    
    def __init__(self, db_path: str = "comprehensive_api_endpoints.db"):
        self.db_path = db_path
        self.endpoints: Dict[str, ComprehensiveAPIEndpoint] = {}
        self.init_database()
        self.load_from_database()
        self.init_default_endpoints()

    async def _epa_fallback(self, client: httpx.AsyncClient, product_name: str) -> Tuple[bool, Dict[str, Any] | None, str]:
        """EPA CompTox 실패 시 SRS(CompTox SRS) API 폴백 시도.
        우선 chemname 검색(영문화된 제품명 또는 휴리스틱 매핑)으로 JSON을 회수한다.
        문서 예: https://cdxapps.epa.gov/ords/srs/srs_api/chemname/ascorbic%20acid
        """
        # 휴리스틱 매핑
        lower = (product_name or "").lower()
        if any(k in lower for k in ["vitamin c", "비타민", "ascorbic"]):
            query = "ascorbic acid"
        else:
            query = product_name or ""
        if not query:
            return False, None, "no query"
        url = f"https://cdxapps.epa.gov/ords/srs/srs_api/chemname/{quote_plus(query)}"
        try:
            headers = {"Accept": "application/json"}
            resp = await client.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
            try:
                data = resp.json()
            except Exception:
                data = {"raw": resp.text[:2000]}
            return True, data, "fallback_ok"
        except Exception as e:
            return False, None, str(e)

    def _build_epa_search_term(self, product_name: str, hs_code: str) -> str:
        """EPA CompTox 검색어 생성 (간단 휴리스틱)
        - 한글 화장품/화학 제품명 → 대표 성분 영어 키워드로 매핑
        - HS 코드로 화학류(28-38장)이면 일반적인 영어화 시도
        """
        if not product_name:
            return ""
        # 간단 매핑 (확장 가능)
        lower = product_name.lower()
        mappings = [
            ("비타민", "ascorbic acid"),
            ("세럼", "serum"),
            ("vitamin c", "ascorbic acid"),
        ]
        for key, val in mappings:
            if key in lower:
                return val
        # 비영문 제거, 공백 기준 단어 결합
        ascii_only = ''.join(ch if ord(ch) < 128 else ' ' for ch in product_name)
        ascii_only = ' '.join(ascii_only.split())
        if ascii_only:
            return ascii_only
        # 마지막 fallback
        return "chemical"
    
    def init_database(self):
        """데이터베이스 초기화"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS comprehensive_api_endpoints (
                name TEXT PRIMARY KEY,
                agency TEXT NOT NULL,
                url TEXT NOT NULL,
                method TEXT DEFAULT 'GET',
                params TEXT,  -- JSON
                headers TEXT,  -- JSON
                success_rate REAL DEFAULT 0.0,
                last_success TEXT,
                last_failure TEXT,
                failure_count INTEGER DEFAULT 0,
                category TEXT,
                hs_codes TEXT,  -- JSON
                api_key_required BOOLEAN DEFAULT FALSE,
                rate_limit TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def load_from_database(self):
        """데이터베이스에서 로드"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM comprehensive_api_endpoints')
        for row in cursor.fetchall():
            name, agency, url, method, params, headers, success_rate, last_success, last_failure, failure_count, category, hs_codes, api_key_required, rate_limit = row
            
            self.endpoints[name] = ComprehensiveAPIEndpoint(
                name=name,
                agency=agency,
                url=url,
                method=method,
                params=json.loads(params) if params else {},
                headers=json.loads(headers) if headers else {},
                success_rate=success_rate,
                last_success=datetime.fromisoformat(last_success) if last_success else None,
                last_failure=datetime.fromisoformat(last_failure) if last_failure else None,
                failure_count=failure_count,
                category=category,
                hs_codes=json.loads(hs_codes) if hs_codes else [],
                api_key_required=bool(api_key_required),
                rate_limit=rate_limit or "1000/hour"
            )
        
        conn.close()
        print(f"✅ 데이터베이스에서 {len(self.endpoints)}개 API 로드됨")
    
    def save_to_database(self):
        """데이터베이스에 저장"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        # 테이블 보장 (캐시 리셋 후에도 에러 방지)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS comprehensive_api_endpoints (
                name TEXT PRIMARY KEY,
                agency TEXT NOT NULL,
                url TEXT NOT NULL,
                method TEXT DEFAULT 'GET',
                params TEXT,
                headers TEXT,
                success_rate REAL DEFAULT 0.0,
                last_success TEXT,
                last_failure TEXT,
                failure_count INTEGER DEFAULT 0,
                category TEXT,
                hs_codes TEXT,
                api_key_required BOOLEAN DEFAULT FALSE,
                rate_limit TEXT
            )
        ''')
        
        for endpoint in self.endpoints.values():
            cursor.execute('''
                INSERT OR REPLACE INTO comprehensive_api_endpoints 
                (name, agency, url, method, params, headers, success_rate, last_success, last_failure, failure_count, category, hs_codes, api_key_required, rate_limit)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                endpoint.name,
                endpoint.agency,
                endpoint.url,
                endpoint.method,
                json.dumps(endpoint.params),
                json.dumps(endpoint.headers),
                endpoint.success_rate,
                endpoint.last_success.isoformat() if endpoint.last_success else None,
                endpoint.last_failure.isoformat() if endpoint.last_failure else None,
                endpoint.failure_count,
                endpoint.category,
                json.dumps(endpoint.hs_codes),
                endpoint.api_key_required,
                endpoint.rate_limit
            ))
        
        conn.commit()
        conn.close()
    
    def init_default_endpoints(self):
        """기본 API 엔드포인트 초기화"""
        if self.endpoints:
            return  # 이미 로드됨
        
        default_endpoints = [
            # FDA APIs
            {
                "name": "fda_food_enforcement",
                "agency": "FDA",
                "url": "https://api.fda.gov/food/enforcement.json",
                "method": "GET",
                "params": {"limit": 10},
                "headers": {},
                "category": "food",
                "hs_codes": ["09", "10", "11", "12", "13", "14", "15", "16", "17", "18", "19", "20", "21", "22", "23", "24"],
                "api_key_required": False,
                "rate_limit": "1000/day"
            },
            {
                "name": "fda_drug_event",
                "agency": "FDA", 
                "url": "https://api.fda.gov/drug/event.json",
                "method": "GET",
                "params": {"limit": 10},
                "headers": {},
                "category": "drug",
                "hs_codes": ["30", "31", "32"],
                "api_key_required": False,
                "rate_limit": "1000/day"
            },
            {
                "name": "fda_device_event",
                "agency": "FDA",
                "url": "https://api.fda.gov/device/event.json", 
                "method": "GET",
                "params": {"limit": 10},
                "headers": {},
                "category": "device",
                "hs_codes": ["84", "85", "90", "91", "92", "93", "94", "95", "96"],
                "api_key_required": False,
                "rate_limit": "1000/day"
            },
            {
                "name": "fda_cosmetic_event",
                "agency": "FDA",
                "url": "https://api.fda.gov/cosmetic/event.json",
                "method": "GET", 
                "params": {"limit": 10},
                "headers": {},
                "category": "cosmetic",
                "hs_codes": ["33", "34"],
                "api_key_required": False,
                "rate_limit": "1000/day"
            },
            
            # USDA APIs
            {
                "name": "usda_fooddata_central",
                "agency": "USDA",
                "url": "https://api.nal.usda.gov/fdc/v1/foods/search",
                "method": "GET",
                "params": {"pageSize": 10, "pageNumber": 1},
                "headers": {},
                "category": "agricultural",
                "hs_codes": ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12", "13", "14", "15", "16", "17", "18", "19", "20", "21", "22", "23", "24"],
                "api_key_required": True,
                "rate_limit": "1000/day"
            },
            
            # EPA APIs
            {
                "name": "epa_comptox_chemicals",
                "agency": "EPA",
                "url": "https://comptox.epa.gov/dashboard/api/search",
                "method": "GET",
                "params": {"limit": 10},
                "headers": {},
                "category": "chemical",
                "hs_codes": ["28", "29", "30", "31", "32", "33", "34", "35", "36", "37", "38"],
                "api_key_required": False,
                "rate_limit": "1000/hour"
            },
            # EPA SRS chemname 엔드포인트 (신규)
            {
                "name": "epa_srs_chemname",
                "agency": "EPA",
                "url": "https://cdxapps.epa.gov/ords/srs/srs_api/chemname/",
                "method": "GET",
                "params": {},
                "headers": {},
                "category": "chemical",
                "hs_codes": ["28", "29", "30", "31", "32", "33", "34", "35", "36", "37", "38"],
                "api_key_required": False,
                "rate_limit": "1000/hour"
            },
            
            # FCC APIs (실제 Data.gov 엔드포인트로 수정)
            {
                "name": "fcc_eas_equipment_authorization",
                "agency": "FCC",
                "url": "https://opendata.fcc.gov/api/views/",
                "method": "GET",
                "params": {"limit": 10, "format": "json"},
                "headers": {},
                "category": "electronics",
                "hs_codes": ["84", "85"],
                "api_key_required": False,
                "rate_limit": "1000/hour"
            },
            
            # FCC Device Authorization (검증된 URL)
            {
                "name": "fcc_device_authorization",
                "agency": "FCC",
                "url": "https://api.fcc.gov/device/authorization/grants",
                "method": "GET",
                "params": {"limit": 10, "format": "json"},
                "headers": {},
                "category": "electronics",
                "hs_codes": ["84", "85"],
                "api_key_required": False,
                "rate_limit": "1000/hour"
            },
            
            # CPSC APIs (SaferProducts Recalls REST로 교체)
            {
                "name": "cpsc_saferproducts_recalls",
                "agency": "CPSC",
                "url": "https://www.cpsc.gov/SaferProducts/",
                "method": "GET",
                "params": {"format": "json"},
                "headers": {},
                "category": "consumer",
                "hs_codes": ["84", "85", "94", "95", "96"],
                "api_key_required": False,
                "rate_limit": "1000/day"
            },
            
            # CBP APIs (Public Data Portal 접근 스텁: HTML 성공 시 통과)
            {
                "name": "cbp_public_data_portal",
                "agency": "CBP",
                "url": "https://www.cbp.gov/newsroom/stats/cbp-public-data-portal",
                "method": "GET",
                "params": {},
                "headers": {},
                "category": "trade",
                "hs_codes": ["99"],  # 모든 HS 코드
                "api_key_required": False,
                "rate_limit": "1000/day"
            },
            
            # CBP ACE Portal API
            {
                "name": "cbp_ace_portal_api",
                "agency": "CBP",
                "url": "https://api.cbp.gov/ace/",
                "method": "GET",
                "params": {"limit": 10, "format": "json"},
                "headers": {},
                "category": "trade",
                "hs_codes": ["99"],  # 모든 HS 코드
                "api_key_required": True,
                "rate_limit": "1000/day"
            },
            
            # EPA APIs (화학물질 관련) - api_endpoints.py와 통일
            {
                "name": "epa_chemical_api",
                "agency": "EPA",
                "url": "https://comptox.epa.gov/dashboard/api/chemical/search",
                "method": "GET",
                "params": {"limit": 10},
                "headers": {},
                "category": "chemical",
                "hs_codes": ["28", "29", "30", "31", "32", "33", "34", "35", "36", "37", "38"],
                "api_key_required": False,
                "rate_limit": "1000/hour"
            },
            
            # USDA APIs (농산물 관련)
            {
                "name": "usda_food_data_api",
                "agency": "USDA",
                "url": "https://api.nal.usda.gov/fdc/v1/foods/search",
                "method": "GET",
                "params": {"limit": 10, "format": "json"},
                "headers": {},
                "category": "agricultural",
                "hs_codes": ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12", "13", "14", "15", "16", "17", "18", "19", "20", "21", "22", "23", "24"],
                "api_key_required": True,
                "rate_limit": "1000/day"
            },
            
            # Commerce APIs (무역 통계 관련)
            {
                "name": "commerce_trade_data_api",
                "agency": "Commerce",
                "url": "https://api.census.gov/data/timeseries/intltrade/",
                "method": "GET",
                "params": {"limit": 10, "format": "json"},
                "headers": {},
                "category": "trade",
                "hs_codes": ["99"],  # 모든 HS 코드
                "api_key_required": True,
                "rate_limit": "1000/day"
            },
            
            # Steel Import Monitoring API
            {
                "name": "commerce_steel_import_api",
                "agency": "Commerce",
                "url": "https://www.trade.gov/steel-import-monitoring-analysis-system-sima",
                "method": "GET",
                "params": {"limit": 10, "format": "json"},
                "headers": {},
                "category": "trade",
                "hs_codes": ["72", "73"],  # 철강 관련 HS 코드
                "api_key_required": False,
                "rate_limit": "1000/day"
            },
            
            # Aluminum Import Monitor API
            {
                "name": "commerce_aluminum_import_monitor",
                "agency": "Commerce",
                "url": "https://www.trade.gov/aluminum-import-monitor",
                "method": "GET",
                "params": {"limit": 10, "format": "json"},
                "headers": {},
                "category": "trade",
                "hs_codes": ["76"],  # 알루미늄 관련 HS 코드
                "api_key_required": False,
                "rate_limit": "1000/day"
            }
        ]
        
        for endpoint_data in default_endpoints:
            endpoint = ComprehensiveAPIEndpoint(
                name=endpoint_data["name"],
                agency=endpoint_data["agency"],
                url=endpoint_data["url"],
                method=endpoint_data["method"],
                params=endpoint_data["params"],
                headers=endpoint_data["headers"],
                success_rate=0.0,
                last_success=None,
                last_failure=None,
                failure_count=0,
                category=endpoint_data["category"],
                hs_codes=endpoint_data["hs_codes"],
                api_key_required=endpoint_data["api_key_required"],
                rate_limit=endpoint_data["rate_limit"]
            )
            self.endpoints[endpoint.name] = endpoint
        
        self.save_to_database()
        print(f"✅ {len(default_endpoints)}개 기본 API 엔드포인트 초기화됨")
    
    def get_endpoints_for_hs_code(self, hs_code: str) -> List[ComprehensiveAPIEndpoint]:
        """HS 코드에 적합한 API 엔드포인트 목록 반환"""
        hs_chapter = hs_code[:2]
        suitable_endpoints = []
        
        for endpoint in self.endpoints.values():
            if hs_chapter in endpoint.hs_codes or "99" in endpoint.hs_codes:
                suitable_endpoints.append(endpoint)
        
        # 성공률 순으로 정렬
        suitable_endpoints.sort(key=lambda x: x.success_rate, reverse=True)
        
        return suitable_endpoints
    
    async def test_endpoint(self, endpoint_name: str, hs_code: str, product_name: str, api_key: str = None) -> Tuple[bool, float, str]:
        """엔드포인트 테스트"""
        if endpoint_name not in self.endpoints:
            return False, 0.0, "엔드포인트 없음"
        
        endpoint = self.endpoints[endpoint_name]
        start_time = datetime.now()
        
        # API 키 설정
        params = endpoint.params.copy()
        headers = endpoint.headers.copy()
        
        # USDA FoodData Central: 환경변수에서 API 키 자동 주입
        if endpoint.agency == "USDA" and endpoint.api_key_required:
            usda_key = api_key or os.getenv("USDA_API_KEY")
            if usda_key:
                params["api_key"] = usda_key
        # 일반적인 API 키 헤더/쿼리 주입 (있을 때만)
        if endpoint.api_key_required and api_key:
            if "api_key" in params:
                params["api_key"] = api_key
            if "X-Api-Key" in headers:
                headers["X-Api-Key"] = api_key

        # EPA CompTox 검색: search 파라미터 + 헤더 고정, CAS 우선
        if endpoint.agency == "EPA" and "chemical" in endpoint.name:
            # 비타민 C 케이스: CAS RN 우선 적용
            lower = (product_name or "").lower()
            cas = None
            if any(k in lower for k in ["vitamin c", "비타민", "ascorbic"]):
                cas = "50-81-7"
            params.clear()
            params["search"] = cas or self._build_epa_search_term(product_name, hs_code)
            headers = headers or {}
            headers["Accept"] = "application/json"
            # 진단 로그
            print(f"    EPA call → url={endpoint.url} params={params}")
        # EPA SRS chemname 엔드포인트: 경로 기반 쿼리 구성
        elif endpoint.name == "epa_srs_chemname":
            lower = (product_name or "").lower()
            if any(k in lower for k in ["vitamin c", "비타민", "ascorbic"]):
                query = "ascorbic acid"
            else:
                ascii_only = ''.join(ch if ord(ch) < 128 else ' ' for ch in (product_name or ""))
                query = ' '.join(ascii_only.split()) or (product_name or "")
            srs_full_url = f"{endpoint.url}{quote_plus(query)}"
            headers = headers or {}
            headers["Accept"] = "application/json"
        
        # 재시도 로직 (502 오류 대응)
        max_retries = 3
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    if endpoint.method == "GET":
                        # EPA SRS chemname은 경로에 쿼리를 포함
                        if endpoint.name == "epa_srs_chemname":
                            response = await client.get(
                                srs_full_url,
                                headers=headers
                            )
                        else:
                            response = await client.get(
                                endpoint.url,
                                params=params,
                                headers=headers
                            )
                    else:
                        response = await client.post(
                            endpoint.url,
                            json=params,
                            headers=headers
                        )
                    
                    response_time = (datetime.now() - start_time).total_seconds()
                    # EPA SRS: 200은 성공, 404는 기관 데이터 없음으로 처리
                    if endpoint.name == "epa_srs_chemname":
                        if response.status_code == 200:
                            pass
                        elif response.status_code == 404:
                            response_time = (datetime.now() - start_time).total_seconds()
                            endpoint.last_failure = datetime.now()
                            endpoint.failure_count += 1
                            endpoint.success_rate = max(0.0, endpoint.success_rate - 0.05)
                            return False, response_time, "EPA SRS: no data (404)"
                        else:
                            response.raise_for_status()
                    else:
                        response.raise_for_status()
                    
                    # 성공률 업데이트
                    endpoint.last_success = datetime.now()
                    endpoint.success_rate = min(1.0, endpoint.success_rate + 0.1)
                    
                    return True, response_time, "성공"
                    
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 502 and attempt < max_retries - 1:
                    print(f"    ⚠️ {endpoint.agency} API 502 오류, {attempt + 1}번째 재시도...")
                    await asyncio.sleep(2 ** attempt)  # 지수 백오프
                    continue
                else:
                    # EPA 404인 경우 SRS 폴백 시도
                    if endpoint.agency == "EPA" and e.response.status_code == 404:
                        fb_ok, fb_data, fb_msg = await self._epa_fallback(client, product_name)
                        if fb_ok:
                            endpoint.last_success = datetime.now()
                            endpoint.success_rate = min(1.0, endpoint.success_rate + 0.1)
                            print("    EPA fallback(SRS) 성공")
                            return True, (datetime.now() - start_time).total_seconds(), "fallback"
                    # 최종 실패
                    response_time = (datetime.now() - start_time).total_seconds()
                    error_msg = str(e)
                    
                    # 실패률 업데이트
                    endpoint.last_failure = datetime.now()
                    endpoint.failure_count += 1
                    endpoint.success_rate = max(0.0, endpoint.success_rate - 0.1)
                    
                    return False, response_time, error_msg
            
            except Exception as e:
                # 최종 실패
                response_time = (datetime.now() - start_time).total_seconds()
                error_msg = str(e)
                
                # 실패률 업데이트
                endpoint.last_failure = datetime.now()
                endpoint.failure_count += 1
                endpoint.success_rate = max(0.0, endpoint.success_rate - 0.1)
                
                return False, response_time, error_msg
    
    async def search_requirements_comprehensive(self, hs_code: str, product_name: str, api_key: str = None) -> Dict[str, Any]:
        """포괄적 요구사항 검색"""
        print(f"🔍 포괄적 요구사항 검색: {product_name} (HS: {hs_code})")
        
        # 적합한 엔드포인트 찾기
        suitable_endpoints = self.get_endpoints_for_hs_code(hs_code)
        
        if not suitable_endpoints:
            return {
                "hs_code": hs_code,
                "product_name": product_name,
                "agencies_searched": [],
                "working_apis": [],
                "failed_apis": [],
                "total_requirements": 0,
                "success_rate": 0.0
            }
        
        print(f"📋 발견된 적합한 API: {len(suitable_endpoints)}개")
        
        # 각 엔드포인트 테스트
        working_apis = []
        failed_apis = []
        agencies_searched = []
        
        for endpoint in suitable_endpoints[:5]:  # 상위 5개만 테스트
            agencies_searched.append(endpoint.agency)
            
            print(f"📡 {endpoint.agency} - {endpoint.name} 테스트 중...")
            success, response_time, message = await self.test_endpoint(endpoint.name, hs_code, product_name, api_key)
            
            if success:
                working_apis.append({
                    "agency": endpoint.agency,
                    "endpoint": endpoint.name,
                    "url": endpoint.url,
                    "response_time": response_time,
                    "success_rate": endpoint.success_rate
                })
                print(f"✅ {endpoint.agency}: 성공 ({response_time:.2f}초)")
            else:
                failed_apis.append({
                    "agency": endpoint.agency,
                    "endpoint": endpoint.name,
                    "url": endpoint.url,
                    "error": message,
                    "failure_count": endpoint.failure_count
                })
                print(f"❌ {endpoint.agency}: 실패 - {message}")
        
        # 결과 저장
        self.save_to_database()
        
        return {
            "hs_code": hs_code,
            "product_name": product_name,
            "agencies_searched": list(set(agencies_searched)),
            "working_apis": working_apis,
            "failed_apis": failed_apis,
            "total_requirements": len(working_apis),
            "success_rate": len(working_apis) / (len(working_apis) + len(failed_apis)) if (working_apis or failed_apis) else 0.0
        }

# 전역 인스턴스
comprehensive_api_manager = ComprehensiveAPIManager()

async def main():
    """테스트 실행"""
    manager = ComprehensiveAPIManager()
    
    # 테스트 상품들
    test_products = [
        ("8471.30.01", "노트북 컴퓨터"),
        ("3304.99.00", "비타민C 세럼"),
        ("0101.21.00", "소고기"),
        ("9018.90.00", "의료기기")
    ]
    
    for hs_code, product_name in test_products:
        print(f"\n{'='*60}")
        print(f"테스트: {product_name} (HS: {hs_code})")
        print(f"{'='*60}")
        
        result = await manager.search_requirements_comprehensive(hs_code, product_name)
        
        print(f"📊 검색된 기관: {len(result['agencies_searched'])}개")
        print(f"✅ 작동하는 API: {len(result['working_apis'])}개")
        print(f"❌ 실패한 API: {len(result['failed_apis'])}개")
        print(f"📈 성공률: {result['success_rate']:.2%}")
        
        if result['working_apis']:
            print("\n작동하는 API 목록:")
            for api in result['working_apis']:
                print(f"  - {api['agency']}: {api['endpoint']}")
                print(f"    URL: {api['url']}")
                print(f"    응답시간: {api['response_time']:.2f}초")
                print(f"    성공률: {api['success_rate']:.2%}")

if __name__ == "__main__":
    asyncio.run(main())
