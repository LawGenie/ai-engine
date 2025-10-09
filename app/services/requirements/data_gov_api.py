"""
Data.gov API 서비스
미국 정부 데이터 API를 통한 요구사항 검색
"""

import asyncio
import httpx
import json
from typing import Dict, List, Any, Optional
from datetime import datetime
import os

class DataGovAPIService:
    """Data.gov API 서비스"""
    
    def __init__(self):
        self.api_key = os.getenv('API_DATA_GOV', '')
        self.base_url = "https://api.data.gov"
        self.timeout = 30.0
        self.headers = {
            'User-Agent': 'LawGenie-AI-Engine/1.0',
            'Accept': 'application/json'
        }
        
        # API 키가 없으면 기본값 설정
        if not self.api_key:
            print("⚠️ API_DATA_GOV 환경변수가 설정되지 않았습니다. 제한된 기능으로 작동합니다.")
    
    async def search_requirements_by_hs_code(self, hs_code: str, product_name: str) -> Dict[str, Any]:
        """HS코드 기반 요구사항 검색"""
        print(f"🔍 Data.gov API 검색 시작 - HS코드: {hs_code}, 상품: {product_name}")
        
        try:
            # API 키가 없으면 모의 데이터 반환
            if not self.api_key:
                return self._get_mock_data(hs_code, product_name)
            
            # 여러 API 엔드포인트에서 병렬 검색
            tasks = [
                self._search_fda_data(hs_code, product_name),
                self._search_epa_data(hs_code, product_name),
                self._search_usda_data(hs_code, product_name),
                self._search_cbp_data(hs_code, product_name)
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 결과 통합
            combined_results = self._combine_api_results(hs_code, product_name, results)
            
            print(f"✅ Data.gov API 검색 완료 - {combined_results.get('total_requirements', 0)}개 요구사항 발견")
            return combined_results
            
        except Exception as e:
            print(f"❌ Data.gov API 검색 실패: {e}")
            return {
                "hs_code": hs_code,
                "product_name": product_name,
                "error": str(e),
                "total_requirements": 0,
                "agencies": {}
            }
    
    async def _search_fda_data(self, hs_code: str, product_name: str) -> Dict[str, Any]:
        """FDA 데이터 검색"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout, headers=self.headers) as client:
                # FDA API 엔드포인트들
                endpoints = [
                    f"/drug/label.json?search=openfda.product_ndc:{hs_code}&limit=5",
                    f"/food/enforcement.json?search=product_description:{product_name}&limit=5",
                    f"/cosmetics/event.json?search=product_name:{product_name}&limit=5"
                ]
                
                fda_results = []
                for endpoint in endpoints:
                    try:
                        url = f"{self.base_url}/fda{endpoint}"
                        response = await client.get(url)
                        
                        if response.status_code == 200:
                            data = response.json()
                            if data.get('results'):
                                fda_results.extend(data['results'][:2])  # 최대 2개씩만
                    except Exception as e:
                        print(f"⚠️ FDA API 엔드포인트 실패: {e}")
                        continue
                
                return {
                    "agency": "FDA",
                    "status": "success" if fda_results else "no_results",
                    "results": fda_results,
                    "certifications": self._extract_fda_certifications(fda_results),
                    "documents": self._extract_fda_documents(fda_results),
                    "sources": self._extract_fda_sources(fda_results)
                }
                
        except Exception as e:
            return {
                "agency": "FDA",
                "status": "error",
                "error": str(e),
                "results": [],
                "certifications": [],
                "documents": [],
                "sources": []
            }
    
    async def _search_epa_data(self, hs_code: str, product_name: str) -> Dict[str, Any]:
        """EPA 데이터 검색"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout, headers=self.headers) as client:
                # EPA API 엔드포인트
                url = f"{self.base_url}/epa/efservice/srs.srs_chemicals/chem_name/LIKE/{product_name}/JSON"
                
                response = await client.get(url)
                
                if response.status_code == 200:
                    data = response.json()
                    results = data if isinstance(data, list) else [data]
                    
                    return {
                        "agency": "EPA",
                        "status": "success" if results else "no_results",
                        "results": results[:5],
                        "certifications": self._extract_epa_certifications(results),
                        "documents": self._extract_epa_documents(results),
                        "sources": self._extract_epa_sources(results)
                    }
                else:
                    return {
                        "agency": "EPA",
                        "status": "no_results",
                        "results": [],
                        "certifications": [],
                        "documents": [],
                        "sources": []
                    }
                    
        except Exception as e:
            return {
                "agency": "EPA",
                "status": "error",
                "error": str(e),
                "results": [],
                "certifications": [],
                "documents": [],
                "sources": []
            }
    
    async def _search_usda_data(self, hs_code: str, product_name: str) -> Dict[str, Any]:
        """USDA 데이터 검색"""
        try:
            usda_key = os.getenv('USDA_API_KEY', '')
            if not usda_key:
                return {
                    "agency": "USDA",
                    "status": "no_api_key",
                    "results": [],
                    "certifications": [],
                    "documents": [],
                    "sources": []
                }
            
            async with httpx.AsyncClient(timeout=self.timeout, headers=self.headers) as client:
                url = f"https://api.nal.usda.gov/fdc/v1/foods/search"
                params = {
                    "api_key": usda_key,
                    "query": product_name,
                    "pageSize": 5
                }
                
                response = await client.get(url, params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    results = data.get('foods', [])
                    
                    return {
                        "agency": "USDA",
                        "status": "success" if results else "no_results",
                        "results": results,
                        "certifications": self._extract_usda_certifications(results),
                        "documents": self._extract_usda_documents(results),
                        "sources": self._extract_usda_sources(results)
                    }
                else:
                    return {
                        "agency": "USDA",
                        "status": "no_results",
                        "results": [],
                        "certifications": [],
                        "documents": [],
                        "sources": []
                    }
                    
        except Exception as e:
            return {
                "agency": "USDA",
                "status": "error",
                "error": str(e),
                "results": [],
                "certifications": [],
                "documents": [],
                "sources": []
            }
    
    async def _search_cbp_data(self, hs_code: str, product_name: str) -> Dict[str, Any]:
        """CBP 데이터 검색 (모의 데이터)"""
        # CBP API는 실제로는 제한적이므로 모의 데이터 반환
        return {
            "agency": "CBP",
            "status": "mock_data",
            "results": [
                {
                    "hs_code": hs_code,
                    "product": product_name,
                    "import_requirements": "Basic customs documentation required",
                    "tariff_rate": "Varies by product"
                }
            ],
            "certifications": [
                {
                    "name": "CBP Import Declaration",
                    "required": True,
                    "description": "Standard customs declaration form",
                    "agency": "CBP",
                    "url": "https://www.cbp.gov/trade/basic-import-export/importing-basics"
                }
            ],
            "documents": [
                {
                    "name": "Commercial Invoice",
                    "required": True,
                    "description": "Detailed invoice from supplier",
                    "url": "https://www.cbp.gov/trade/basic-import-export/importing-basics"
                },
                {
                    "name": "Bill of Lading",
                    "required": True,
                    "description": "Shipping document from carrier",
                    "url": "https://www.cbp.gov/trade/basic-import-export/importing-basics"
                }
            ],
            "sources": [
                {
                    "title": "CBP Import Basics",
                    "url": "https://www.cbp.gov/trade/basic-import-export/importing-basics",
                    "type": "Official Guide",
                    "relevance": "high"
                }
            ]
        }
    
    def _combine_api_results(self, hs_code: str, product_name: str, results: List[Any]) -> Dict[str, Any]:
        """API 결과들을 통합"""
        combined = {
            "hs_code": hs_code,
            "product_name": product_name,
            "total_requirements": 0,
            "agencies": {},
            "certifications": [],
            "documents": [],
            "sources": [],
            "search_timestamp": datetime.now().isoformat()
        }
        
        for result in results:
            if isinstance(result, Exception):
                print(f"⚠️ API 검색 예외: {result}")
                continue
            
            if isinstance(result, dict) and "agency" in result:
                agency = result["agency"]
                combined["agencies"][agency] = result
                
                # 결과 통합
                combined["certifications"].extend(result.get("certifications", []))
                combined["documents"].extend(result.get("documents", []))
                combined["sources"].extend(result.get("sources", []))
        
        combined["total_requirements"] = len(combined["certifications"]) + len(combined["documents"])
        
        return combined
    
    def _get_mock_data(self, hs_code: str, product_name: str) -> Dict[str, Any]:
        """API 키가 없을 때 모의 데이터 반환"""
        return {
            "hs_code": hs_code,
            "product_name": product_name,
            "total_requirements": 3,
            "agencies": {
                "FDA": {
                    "agency": "FDA",
                    "status": "mock_data",
                    "certifications": [
                        {
                            "name": "FDA Registration",
                            "required": True,
                            "description": "Food and Drug Administration registration required",
                            "agency": "FDA",
                            "url": "https://www.fda.gov/food/importing-food-products-imported-food"
                        }
                    ],
                    "documents": [
                        {
                            "name": "FDA Prior Notice",
                            "required": True,
                            "description": "Prior notice of imported food",
                            "url": "https://www.fda.gov/food/importing-food-products-imported-food"
                        }
                    ],
                    "sources": [
                        {
                            "title": "FDA Food Import Guide",
                            "url": "https://www.fda.gov/food/importing-food-products-imported-food",
                            "type": "Official Guide",
                            "relevance": "high"
                        }
                    ]
                },
                "CBP": {
                    "agency": "CBP",
                    "status": "mock_data",
                    "certifications": [],
                    "documents": [
                        {
                            "name": "Commercial Invoice",
                            "required": True,
                            "description": "Standard commercial invoice",
                            "url": "https://www.cbp.gov/trade/basic-import-export/importing-basics"
                        }
                    ],
                    "sources": [
                        {
                            "title": "CBP Import Basics",
                            "url": "https://www.cbp.gov/trade/basic-import-export/importing-basics",
                            "type": "Official Guide",
                            "relevance": "high"
                        }
                    ]
                }
            },
            "certifications": [
                {
                    "name": "FDA Registration",
                    "required": True,
                    "description": "Food and Drug Administration registration required",
                    "agency": "FDA",
                    "url": "https://www.fda.gov/food/importing-food-products-imported-food"
                }
            ],
            "documents": [
                {
                    "name": "FDA Prior Notice",
                    "required": True,
                    "description": "Prior notice of imported food",
                    "url": "https://www.fda.gov/food/importing-food-products-imported-food"
                },
                {
                    "name": "Commercial Invoice",
                    "required": True,
                    "description": "Standard commercial invoice",
                    "url": "https://www.cbp.gov/trade/basic-import-export/importing-basics"
                }
            ],
            "sources": [
                {
                    "title": "FDA Food Import Guide",
                    "url": "https://www.fda.gov/food/importing-food-products-imported-food",
                    "type": "Official Guide",
                    "relevance": "high"
                },
                {
                    "title": "CBP Import Basics",
                    "url": "https://www.cbp.gov/trade/basic-import-export/importing-basics",
                    "type": "Official Guide",
                    "relevance": "high"
                }
            ],
            "search_timestamp": datetime.now().isoformat(),
            "note": "Mock data - API key not configured"
        }
    
    # 각 기관별 데이터 추출 메서드들
    def _extract_fda_certifications(self, results: List[Dict]) -> List[Dict]:
        """FDA 결과에서 인증 요구사항 추출"""
        certifications = []
        for result in results:
            if result.get('openfda'):
                certifications.append({
                    "name": "FDA Drug Registration",
                    "required": True,
                    "description": f"FDA registered drug: {result.get('openfda', {}).get('brand_name', ['Unknown'])[0] if result.get('openfda', {}).get('brand_name') else 'Unknown'}",
                    "agency": "FDA",
                    "url": f"https://www.fda.gov/drugs/{result.get('application_number', '')}"
                })
        return certifications
    
    def _extract_fda_documents(self, results: List[Dict]) -> List[Dict]:
        """FDA 결과에서 문서 요구사항 추출"""
        documents = []
        for result in results:
            if result.get('product_description'):
                documents.append({
                    "name": "FDA Product Documentation",
                    "required": True,
                    "description": f"Documentation for: {result.get('product_description', 'Unknown')}",
                    "url": f"https://www.fda.gov/food/enforcement/{result.get('recall_number', '')}"
                })
        return documents
    
    def _extract_fda_sources(self, results: List[Dict]) -> List[Dict]:
        """FDA 결과에서 출처 정보 추출"""
        sources = []
        for result in results:
            sources.append({
                "title": "FDA Enforcement Report",
                "url": f"https://www.fda.gov/food/enforcement/{result.get('recall_number', '')}",
                "type": "Official Report",
                "relevance": "high"
            })
        return sources
    
    def _extract_epa_certifications(self, results: List[Dict]) -> List[Dict]:
        """EPA 결과에서 인증 요구사항 추출"""
        certifications = []
        for result in results:
            if result.get('chem_name'):
                certifications.append({
                    "name": "EPA Chemical Registration",
                    "required": True,
                    "description": f"EPA registered chemical: {result.get('chem_name', 'Unknown')}",
                    "agency": "EPA",
                    "url": "https://www.epa.gov/chemical-data-reporting"
                })
        return certifications
    
    def _extract_epa_documents(self, results: List[Dict]) -> List[Dict]:
        """EPA 결과에서 문서 요구사항 추출"""
        documents = []
        for result in results:
            documents.append({
                "name": "EPA Chemical Data Report",
                "required": True,
                "description": "Chemical data reporting documentation",
                "url": "https://www.epa.gov/chemical-data-reporting"
            })
        return documents
    
    def _extract_epa_sources(self, results: List[Dict]) -> List[Dict]:
        """EPA 결과에서 출처 정보 추출"""
        sources = []
        for result in results:
            sources.append({
                "title": "EPA Chemical Database",
                "url": "https://www.epa.gov/chemical-data-reporting",
                "type": "Official Database",
                "relevance": "high"
            })
        return sources
    
    def _extract_usda_certifications(self, results: List[Dict]) -> List[Dict]:
        """USDA 결과에서 인증 요구사항 추출"""
        certifications = []
        for result in results:
            if result.get('description'):
                certifications.append({
                    "name": "USDA Food Certification",
                    "required": True,
                    "description": f"USDA food certification for: {result.get('description', 'Unknown')}",
                    "agency": "USDA",
                    "url": "https://www.usda.gov/topics"
                })
        return certifications
    
    def _extract_usda_documents(self, results: List[Dict]) -> List[Dict]:
        """USDA 결과에서 문서 요구사항 추출"""
        documents = []
        for result in results:
            documents.append({
                "name": "USDA Food Documentation",
                "required": True,
                "description": "USDA food safety documentation",
                "url": "https://www.usda.gov/topics"
            })
        return documents
    
    def _extract_usda_sources(self, results: List[Dict]) -> List[Dict]:
        """USDA 결과에서 출처 정보 추출"""
        sources = []
        for result in results:
            sources.append({
                "title": "USDA Food Database",
                "url": "https://www.usda.gov/topics",
                "type": "Official Database",
                "relevance": "high"
            })
        return sources
