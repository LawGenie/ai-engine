#!/usr/bin/env python3
"""
동적 API 엔드포인트 관리 시스템
- 실시간으로 API 엔드포인트를 발견하고 테스트
- 실패한 엔드포인트는 자동으로 대체 엔드포인트 시도
- 모든 상품에 대해 적절한 API 매칭
"""

import asyncio
import httpx
import json
import re
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
import sqlite3

@dataclass
class APIEndpoint:
    """API 엔드포인트 정의"""
    name: str
    url: str
    method: str  # GET, POST
    params: Dict[str, Any]
    headers: Dict[str, str]
    success_rate: float
    last_success: Optional[datetime]
    last_failure: Optional[datetime]
    failure_count: int
    category: str
    hs_codes: List[str]  # 지원하는 HS 코드 패턴

@dataclass
class ProductAPIMapping:
    """상품-API 매핑"""
    hs_code: str
    product_name: str
    category: str
    suitable_apis: List[str]
    working_apis: List[str]
    failed_apis: List[str]
    last_updated: datetime

class DynamicAPIManager:
    """동적 API 관리자"""
    
    def __init__(self, db_path: str = "api_endpoints.db"):
        self.db_path = db_path
        self.endpoints: Dict[str, APIEndpoint] = {}
        self.mappings: Dict[str, ProductAPIMapping] = {}
        self.init_database()
        self.load_from_database()
    
    def init_database(self):
        """데이터베이스 초기화"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # API 엔드포인트 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS api_endpoints (
                name TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                method TEXT DEFAULT 'GET',
                params TEXT,  -- JSON
                headers TEXT,  -- JSON
                success_rate REAL DEFAULT 0.0,
                last_success TEXT,
                last_failure TEXT,
                failure_count INTEGER DEFAULT 0,
                category TEXT,
                hs_codes TEXT  -- JSON
            )
        ''')
        
        # 상품-API 매핑 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS product_api_mappings (
                hs_code TEXT PRIMARY KEY,
                product_name TEXT,
                category TEXT,
                suitable_apis TEXT,  -- JSON
                working_apis TEXT,   -- JSON
                failed_apis TEXT,    -- JSON
                last_updated TEXT
            )
        ''')
        
        # API 테스트 로그 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS api_test_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                api_name TEXT,
                hs_code TEXT,
                success BOOLEAN,
                response_time REAL,
                error_message TEXT,
                timestamp TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def load_from_database(self):
        """데이터베이스에서 로드"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # API 엔드포인트 로드
        cursor.execute('SELECT * FROM api_endpoints')
        for row in cursor.fetchall():
            name, url, method, params, headers, success_rate, last_success, last_failure, failure_count, category, hs_codes = row
            
            self.endpoints[name] = APIEndpoint(
                name=name,
                url=url,
                method=method,
                params=json.loads(params) if params else {},
                headers=json.loads(headers) if headers else {},
                success_rate=success_rate,
                last_success=datetime.fromisoformat(last_success) if last_success else None,
                last_failure=datetime.fromisoformat(last_failure) if last_failure else None,
                failure_count=failure_count,
                category=category,
                hs_codes=json.loads(hs_codes) if hs_codes else []
            )
        
        # 상품-API 매핑 로드
        cursor.execute('SELECT * FROM product_api_mappings')
        for row in cursor.fetchall():
            hs_code, product_name, category, suitable_apis, working_apis, failed_apis, last_updated = row
            
            self.mappings[hs_code] = ProductAPIMapping(
                hs_code=hs_code,
                product_name=product_name,
                category=category,
                suitable_apis=json.loads(suitable_apis) if suitable_apis else [],
                working_apis=json.loads(working_apis) if working_apis else [],
                failed_apis=json.loads(failed_apis) if failed_apis else [],
                last_updated=datetime.fromisoformat(last_updated) if last_updated else datetime.now()
            )
        
        conn.close()
        print(f"✅ 데이터베이스에서 {len(self.endpoints)}개 API, {len(self.mappings)}개 매핑 로드됨")
    
    def save_to_database(self):
        """데이터베이스에 저장"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # API 엔드포인트 저장
        for endpoint in self.endpoints.values():
            cursor.execute('''
                INSERT OR REPLACE INTO api_endpoints 
                (name, url, method, params, headers, success_rate, last_success, last_failure, failure_count, category, hs_codes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                endpoint.name,
                endpoint.url,
                endpoint.method,
                json.dumps(endpoint.params),
                json.dumps(endpoint.headers),
                endpoint.success_rate,
                endpoint.last_success.isoformat() if endpoint.last_success else None,
                endpoint.last_failure.isoformat() if endpoint.last_failure else None,
                endpoint.failure_count,
                endpoint.category,
                json.dumps(endpoint.hs_codes)
            ))
        
        # 상품-API 매핑 저장
        for mapping in self.mappings.values():
            cursor.execute('''
                INSERT OR REPLACE INTO product_api_mappings
                (hs_code, product_name, category, suitable_apis, working_apis, failed_apis, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                mapping.hs_code,
                mapping.product_name,
                mapping.category,
                json.dumps(mapping.suitable_apis),
                json.dumps(mapping.working_apis),
                json.dumps(mapping.failed_apis),
                mapping.last_updated.isoformat()
            ))
        
        conn.commit()
        conn.close()
    
    async def discover_new_endpoints(self, hs_code: str, product_name: str):
        """새로운 엔드포인트 자동 발견"""
        print(f"🔍 새로운 엔드포인트 발견: {product_name} (HS: {hs_code})")
        
        # 기존 EPA API 카탈로그에서 적합한 API 찾기
        from app.services.requirements.epa_api_catalog import epa_catalog
        suitable_apis = epa_catalog.get_api_for_hs_code(hs_code)
        
        for api in suitable_apis:
            endpoint_name = f"epa_{api.name.lower().replace(' ', '_')}"
            
            if endpoint_name not in self.endpoints:
                # 새로운 엔드포인트 생성
                new_endpoint = APIEndpoint(
                    name=endpoint_name,
                    url=api.base_url,
                    method="GET",
                    params={"api_key": "YOUR_API_KEY", "limit": 10},
                    headers={"X-Api-Key": "YOUR_API_KEY"},
                    success_rate=0.0,
                    last_success=None,
                    last_failure=None,
                    failure_count=0,
                    category=api.category,
                    hs_codes=[hs_code[:2]]  # HS 챕터
                )
                
                self.endpoints[endpoint_name] = new_endpoint
                print(f"➕ 새 엔드포인트 추가: {endpoint_name}")
        
        self.save_to_database()
    
    async def test_endpoint(self, endpoint_name: str, hs_code: str, product_name: str) -> Tuple[bool, float, str]:
        """엔드포인트 테스트"""
        if endpoint_name not in self.endpoints:
            return False, 0.0, "엔드포인트 없음"
        
        endpoint = self.endpoints[endpoint_name]
        start_time = datetime.now()
        
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                if endpoint.method == "GET":
                    response = await client.get(
                        endpoint.url,
                        params=endpoint.params,
                        headers=endpoint.headers
                    )
                else:
                    response = await client.post(
                        endpoint.url,
                        json=endpoint.params,
                        headers=endpoint.headers
                    )
                
                response_time = (datetime.now() - start_time).total_seconds()
                response.raise_for_status()
                
                # 성공 로그
                self._log_api_test(endpoint_name, hs_code, True, response_time, None)
                
                # 성공률 업데이트
                endpoint.last_success = datetime.now()
                endpoint.success_rate = min(1.0, endpoint.success_rate + 0.1)
                
                return True, response_time, "성공"
                
        except Exception as e:
            response_time = (datetime.now() - start_time).total_seconds()
            error_msg = str(e)
            
            # 실패 로그
            self._log_api_test(endpoint_name, hs_code, False, response_time, error_msg)
            
            # 실패률 업데이트
            endpoint.last_failure = datetime.now()
            endpoint.failure_count += 1
            endpoint.success_rate = max(0.0, endpoint.success_rate - 0.1)
            
            return False, response_time, error_msg
    
    def _log_api_test(self, api_name: str, hs_code: str, success: bool, response_time: float, error_message: Optional[str]):
        """API 테스트 로그 저장"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO api_test_logs (api_name, hs_code, success, response_time, error_message, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (api_name, hs_code, success, response_time, error_message, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
    
    def get_best_endpoints_for_product(self, hs_code: str, product_name: str) -> List[str]:
        """상품에 가장 적합한 엔드포인트 목록 반환"""
        # 기존 매핑 확인
        if hs_code in self.mappings:
            mapping = self.mappings[hs_code]
            if mapping.last_updated > datetime.now() - timedelta(hours=24):
                return mapping.working_apis
        
        # 새로운 매핑 생성
        suitable_endpoints = []
        
        for endpoint_name, endpoint in self.endpoints.items():
            # HS 코드 매칭 확인
            hs_chapter = hs_code[:2]
            if hs_chapter in endpoint.hs_codes or not endpoint.hs_codes:
                # 성공률 기반 정렬
                if endpoint.success_rate > 0.5:
                    suitable_endpoints.append(endpoint_name)
        
        # 성공률 순으로 정렬
        suitable_endpoints.sort(key=lambda x: self.endpoints[x].success_rate, reverse=True)
        
        # 매핑 저장
        self.mappings[hs_code] = ProductAPIMapping(
            hs_code=hs_code,
            product_name=product_name,
            category=self._get_category_from_hs_code(hs_code),
            suitable_apis=suitable_endpoints,
            working_apis=suitable_endpoints[:5],  # 상위 5개만
            failed_apis=[],
            last_updated=datetime.now()
        )
        
        self.save_to_database()
        return suitable_endpoints[:5]
    
    def _get_category_from_hs_code(self, hs_code: str) -> str:
        """HS 코드에서 카테고리 추출"""
        hs_chapter = hs_code[:2]
        
        if hs_chapter in ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12', '13', '14', '15', '16', '17', '18', '19', '20', '21', '22', '23', '24']:
            return 'agricultural'
        elif hs_chapter in ['28', '29', '30', '31', '32', '33', '34', '35', '36', '37', '38']:
            return 'chemical'
        elif hs_chapter in ['84', '85']:
            return 'electronics'
        elif hs_chapter in ['90', '91', '92', '93', '94', '95', '96']:
            return 'medical'
        else:
            return 'general'
    
    async def auto_discover_and_test(self, hs_code: str, product_name: str):
        """자동 발견 및 테스트"""
        print(f"🚀 자동 발견 및 테스트: {product_name} (HS: {hs_code})")
        
        # 1. 새로운 엔드포인트 발견
        await self.discover_new_endpoints(hs_code, product_name)
        
        # 2. 적합한 엔드포인트 찾기
        suitable_endpoints = self.get_best_endpoints_for_product(hs_code, product_name)
        
        # 3. 각 엔드포인트 테스트
        working_endpoints = []
        failed_endpoints = []
        
        for endpoint_name in suitable_endpoints:
            success, response_time, message = await self.test_endpoint(endpoint_name, hs_code, product_name)
            
            if success:
                working_endpoints.append(endpoint_name)
                print(f"✅ {endpoint_name}: 성공 ({response_time:.2f}초)")
            else:
                failed_endpoints.append(endpoint_name)
                print(f"❌ {endpoint_name}: 실패 - {message}")
        
        # 4. 매핑 업데이트
        if hs_code in self.mappings:
            self.mappings[hs_code].working_apis = working_endpoints
            self.mappings[hs_code].failed_apis = failed_endpoints
            self.mappings[hs_code].last_updated = datetime.now()
            self.save_to_database()
        
        return working_endpoints, failed_endpoints

# 전역 인스턴스
api_manager = DynamicAPIManager()

async def main():
    """테스트 실행"""
    manager = DynamicAPIManager()
    
    # 테스트 상품들
    test_products = [
        ("8471.30.01", "노트북 컴퓨터"),
        ("3304.99.00", "비타민C 세럼"),
        ("0101.21.00", "소고기"),
        ("2801.10.00", "염소"),
        ("8517.12.00", "무선 전화기")
    ]
    
    for hs_code, product_name in test_products:
        print(f"\n{'='*60}")
        print(f"테스트: {product_name} (HS: {hs_code})")
        print(f"{'='*60}")
        
        working, failed = await manager.auto_discover_and_test(hs_code, product_name)
        
        print(f"✅ 작동하는 API: {len(working)}개")
        print(f"❌ 실패한 API: {len(failed)}개")
        
        if working:
            print("작동하는 API 목록:")
            for api in working:
                endpoint = manager.endpoints[api]
                print(f"  - {api}: {endpoint.url} (성공률: {endpoint.success_rate:.2f})")

if __name__ == "__main__":
    asyncio.run(main())
