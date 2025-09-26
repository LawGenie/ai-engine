#!/usr/bin/env python3
"""
EPA API 카탈로그 자동 수집 및 관리 시스템
- EPA 공식 API 목록을 자동으로 수집
- 각 API의 엔드포인트와 문서를 파싱
- 데이터베이스에 저장하여 동적 관리
"""

import asyncio
import httpx
import json
import re
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from pathlib import Path

@dataclass
class EPAAPIDefinition:
    """EPA API 정의 클래스"""
    name: str
    description: str
    base_url: str
    endpoints: List[str]
    documentation_url: str
    category: str
    requires_api_key: bool
    rate_limit: str
    last_updated: datetime

class EPAAPICatalog:
    """EPA API 카탈로그 관리 클래스"""
    
    def __init__(self):
        self.catalog_file = Path("epa_api_catalog.json")
        self.apis: Dict[str, EPAAPIDefinition] = {}
        self.load_catalog()
    
    def load_catalog(self):
        """기존 카탈로그 로드"""
        if self.catalog_file.exists():
            try:
                with open(self.catalog_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for name, api_data in data.items():
                        self.apis[name] = EPAAPIDefinition(
                            name=api_data['name'],
                            description=api_data['description'],
                            base_url=api_data['base_url'],
                            endpoints=api_data['endpoints'],
                            documentation_url=api_data['documentation_url'],
                            category=api_data['category'],
                            requires_api_key=api_data['requires_api_key'],
                            rate_limit=api_data['rate_limit'],
                            last_updated=datetime.fromisoformat(api_data['last_updated'])
                        )
                print(f"✅ EPA API 카탈로그 로드됨: {len(self.apis)}개 API")
            except Exception as e:
                print(f"❌ 카탈로그 로드 실패: {e}")
                self.apis = {}
    
    def save_catalog(self):
        """카탈로그 저장"""
        data = {}
        for name, api in self.apis.items():
            data[name] = {
                'name': api.name,
                'description': api.description,
                'base_url': api.base_url,
                'endpoints': api.endpoints,
                'documentation_url': api.documentation_url,
                'category': api.category,
                'requires_api_key': api.requires_api_key,
                'rate_limit': api.rate_limit,
                'last_updated': api.last_updated.isoformat()
            }
        
        with open(self.catalog_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"💾 EPA API 카탈로그 저장됨: {self.catalog_file}")
    
    async def discover_epa_apis(self):
        """EPA 공식 페이지에서 API 목록 자동 발견"""
        print("🔍 EPA API 자동 발견 시작...")
        
        # EPA 공식 API 페이지 스크래핑
        epa_api_urls = [
            "https://www.epa.gov/data/application-programming-interface-api",
            "https://api.data.gov/docs/",
            "https://catalog.data.gov/organization/epa-gov"
        ]
        
        discovered_apis = []
        
        async with httpx.AsyncClient(timeout=30) as client:
            for url in epa_api_urls:
                try:
                    print(f"📡 스크래핑: {url}")
                    response = await client.get(url)
                    response.raise_for_status()
                    
                    # HTML에서 API 정보 추출
                    apis = self._extract_apis_from_html(response.text, url)
                    discovered_apis.extend(apis)
                    
                except Exception as e:
                    print(f"❌ 스크래핑 실패 {url}: {e}")
        
        # 발견된 API들을 카탈로그에 추가
        for api_info in discovered_apis:
            if api_info['name'] not in self.apis:
                self.apis[api_info['name']] = EPAAPIDefinition(
                    name=api_info['name'],
                    description=api_info['description'],
                    base_url=api_info['base_url'],
                    endpoints=api_info['endpoints'],
                    documentation_url=api_info['documentation_url'],
                    category=api_info['category'],
                    requires_api_key=api_info['requires_api_key'],
                    rate_limit=api_info['rate_limit'],
                    last_updated=datetime.now()
                )
                print(f"➕ 새 API 발견: {api_info['name']}")
        
        self.save_catalog()
        return discovered_apis
    
    def _extract_apis_from_html(self, html: str, source_url: str) -> List[Dict[str, Any]]:
        """HTML에서 API 정보 추출"""
        apis = []
        
        # EPA API 목록 패턴 매칭
        api_patterns = [
            r'<li[^>]*>([^<]*API[^<]*)</li>',
            r'<h[1-6][^>]*>([^<]*API[^<]*)</h[1-6]>',
            r'href="([^"]*api[^"]*)"',
            r'href="([^"]*\.gov[^"]*)"'
        ]
        
        for pattern in api_patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            for match in matches:
                if 'api' in match.lower():
                    api_info = self._parse_api_info(match, source_url)
                    if api_info:
                        apis.append(api_info)
        
        return apis
    
    def _parse_api_info(self, text: str, source_url: str) -> Optional[Dict[str, Any]]:
        """API 정보 파싱"""
        # 간단한 파싱 로직 (실제로는 더 정교하게 구현 필요)
        if 'api' not in text.lower():
            return None
        
        return {
            'name': text.strip(),
            'description': f"EPA API discovered from {source_url}",
            'base_url': self._guess_base_url(text),
            'endpoints': [],
            'documentation_url': source_url,
            'category': 'environmental',
            'requires_api_key': True,
            'rate_limit': '1000/hour'
        }
    
    def _guess_base_url(self, text: str) -> str:
        """텍스트에서 기본 URL 추측"""
        # URL 패턴 매칭
        url_pattern = r'https?://[^\s<>"]+'
        urls = re.findall(url_pattern, text)
        if urls:
            return urls[0]
        
        # EPA 도메인 추측
        if 'air' in text.lower():
            return 'https://aqs.epa.gov/data/api'
        elif 'water' in text.lower():
            return 'https://watersgeo.epa.gov/arcgis/rest/services'
        elif 'chemical' in text.lower():
            return 'https://comptox.epa.gov/dashboard/api'
        else:
            return 'https://api.data.gov'
    
    def get_api_for_hs_code(self, hs_code: str) -> List[EPAAPIDefinition]:
        """HS 코드에 적합한 API 목록 반환"""
        suitable_apis = []
        
        # HS 코드 기반 API 매칭
        hs_chapter = hs_code[:2]
        
        # 화학물질 관련 (28-38장)
        if hs_chapter in ['28', '29', '30', '31', '32', '33', '34', '35', '36', '37', '38']:
            for api in self.apis.values():
                if any(keyword in api.name.lower() for keyword in ['chemical', 'toxics', 'pesticide']):
                    suitable_apis.append(api)
        
        # 농산물 관련 (01-24장)
        elif hs_chapter in ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12', '13', '14', '15', '16', '17', '18', '19', '20', '21', '22', '23', '24']:
            for api in self.apis.values():
                if any(keyword in api.name.lower() for keyword in ['air', 'water', 'environmental']):
                    suitable_apis.append(api)
        
        # 전자제품 관련 (84-85장)
        elif hs_chapter in ['84', '85']:
            for api in self.apis.values():
                if any(keyword in api.name.lower() for keyword in ['air', 'environmental']):
                    suitable_apis.append(api)
        
        return suitable_apis
    
    def get_all_apis(self) -> Dict[str, EPAAPIDefinition]:
        """모든 API 반환"""
        return self.apis
    
    def add_custom_api(self, name: str, base_url: str, description: str = "", category: str = "custom"):
        """사용자 정의 API 추가"""
        self.apis[name] = EPAAPIDefinition(
            name=name,
            description=description,
            base_url=base_url,
            endpoints=[],
            documentation_url="",
            category=category,
            requires_api_key=True,
            rate_limit="1000/hour",
            last_updated=datetime.now()
        )
        self.save_catalog()
        print(f"➕ 사용자 정의 API 추가: {name}")

# 전역 인스턴스
epa_catalog = EPAAPICatalog()

async def main():
    """테스트 실행"""
    catalog = EPAAPICatalog()
    
    # EPA API 자동 발견
    discovered = await catalog.discover_epa_apis()
    print(f"🔍 발견된 API: {len(discovered)}개")
    
    # HS 코드별 적합한 API 찾기
    test_hs_codes = ["8471.30.01", "3304.99.00", "0101.21.00"]
    for hs_code in test_hs_codes:
        suitable_apis = catalog.get_api_for_hs_code(hs_code)
        print(f"📋 HS {hs_code}에 적합한 API: {len(suitable_apis)}개")
        for api in suitable_apis:
            print(f"  - {api.name}: {api.base_url}")

if __name__ == "__main__":
    asyncio.run(main())
