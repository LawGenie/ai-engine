"""
Backend API 서비스
Java 백엔드의 요건 수집 API를 호출
"""

import asyncio
import httpx
import json
import os
from typing import Dict, List, Any, Optional
from datetime import datetime


class BackendAPIService:
    """Backend Requirements Collector API 서비스"""
    
    def __init__(self, base_url: str = None):
        """
        Args:
            base_url: 백엔드 API 기본 URL (기본값: http://localhost:8081)
        """
        self.base_url = base_url or os.getenv('BACKEND_API_URL', 'http://localhost:8081')
        self.timeout = 600.0  # 백엔드 API는 여러 외부 API를 호출하므로 타임아웃 10분
        self.headers = {
            'User-Agent': 'LawGenie-AI-Engine/1.0',
            'Accept': 'application/json; charset=UTF-8'
        }
        
        print(f"✅ BackendAPIService 초기화 완료 - Base URL: {self.base_url}")
    
    async def collect_requirements(
        self, 
        product: str, 
        hs_code: str = None,
        include_raw_data: bool = False
    ) -> Dict[str, Any]:
        """
        백엔드 API를 통해 요건 수집
        
        Args:
            product: 제품명 (한글/영문)
            hs_code: HS 코드 (선택)
            include_raw_data: 원본 API 응답 데이터 포함 여부
        
        Returns:
            {
                "product": str,
                "normalized_keyword": str,
                "chemical_name": str,
                "hs_code": str,
                "timestamp": str,
                "requirements": {
                    "total_count": int,
                    "certifications": [...],
                    "documents": [...],
                    "notices": [...],
                    "all_items": [...],
                    "category_stats": {...}
                },
                "citations": [
                    {
                        "agency": str,
                        "category": str,
                        "url": str,
                        "title": str
                    }
                ],
                "raw_data": {...}  # include_raw_data=True인 경우만
            }
        """
        print(f"🔍 백엔드 API 요건 수집 시작 - product: {product}, hs: {hs_code}")
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout, headers=self.headers) as client:
                # 쿼리 파라미터 구성
                params = {
                    "product": product,
                    "includeRawData": str(include_raw_data).lower()
                }
                
                if hs_code:
                    params["hs"] = hs_code
                
                # API 호출
                url = f"{self.base_url}/api/requirements/collect"
                print(f"  📡 요청 URL: {url}")
                print(f"  📋 파라미터: {params}")
                
                response = await client.get(url, params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # 결과 요약
                    req_count = data.get('requirements', {}).get('total_count', 0)
                    citations_count = len(data.get('citations', []))
                    
                    print(f"  ✅ 백엔드 API 호출 성공")
                    print(f"    - 총 요건: {req_count}개")
                    print(f"    - 출처: {citations_count}개")
                    
                    return data
                    
                elif response.status_code == 401:
                    print(f"  ❌ 인증 실패 (401) - 백엔드 API 접근 권한 확인 필요")
                    return self._get_error_response(product, hs_code, "Unauthorized")
                    
                else:
                    print(f"  ❌ 백엔드 API 호출 실패 - Status: {response.status_code}")
                    return self._get_error_response(product, hs_code, f"HTTP {response.status_code}")
                    
        except httpx.TimeoutException:
            print(f"  ⏱️ 백엔드 API 타임아웃 (>{self.timeout}초)")
            return self._get_error_response(product, hs_code, "Timeout")
            
        except httpx.ConnectError:
            print(f"  ❌ 백엔드 API 연결 실패 - 서버가 실행 중인지 확인하세요")
            return self._get_error_response(product, hs_code, "Connection failed")
            
        except Exception as e:
            print(f"  ❌ 백엔드 API 호출 중 예외 발생: {e}")
            return self._get_error_response(product, hs_code, str(e))
    
    def _get_error_response(self, product: str, hs_code: str, error_msg: str) -> Dict[str, Any]:
        """에러 응답 생성"""
        return {
            "product": product,
            "normalized_keyword": "",
            "chemical_name": "",
            "hs_code": hs_code or "",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "error": error_msg,
            "requirements": {
                "total_count": 0,
                "certifications": [],
                "documents": [],
                "notices": [],
                "all_items": [],
                "category_stats": {}
            },
            "citations": []
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """백엔드 API 헬스 체크"""
        try:
            async with httpx.AsyncClient(timeout=5.0, headers=self.headers) as client:
                response = await client.get(f"{self.base_url}/api/endpoints/health")
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"✅ 백엔드 API 정상 - {data.get('message', 'OK')}")
                    return {
                        "status": "UP",
                        "backend_url": self.base_url,
                        "response": data
                    }
                else:
                    return {
                        "status": "DOWN",
                        "backend_url": self.base_url,
                        "error": f"HTTP {response.status_code}"
                    }
                    
        except Exception as e:
            print(f"❌ 백엔드 API 헬스 체크 실패: {e}")
            return {
                "status": "DOWN",
                "backend_url": self.base_url,
                "error": str(e)
            }
    
    def format_for_ai_analysis(self, backend_response: Dict[str, Any]) -> Dict[str, Any]:
        """
        백엔드 응답을 AI 분석에 적합한 형태로 변환
        
        Args:
            backend_response: 백엔드 API 응답
        
        Returns:
            AI 워크플로에서 사용할 수 있는 형식
        """
        requirements = backend_response.get('requirements', {})
        citations = backend_response.get('citations', [])
        
        # AI가 분석하기 쉬운 형태로 재구성
        formatted = {
            "product_info": {
                "original": backend_response.get('product', ''),
                "normalized": backend_response.get('normalized_keyword', ''),
                "chemical_name": backend_response.get('chemical_name', ''),
                "hs_code": backend_response.get('hs_code', '')
            },
            "requirements_summary": {
                "total": requirements.get('total_count', 0),
                "by_category": requirements.get('category_stats', {})
            },
            "requirements_detail": {
                "certifications": requirements.get('certifications', []),
                "documents": requirements.get('documents', []),
                "notices": requirements.get('notices', []),
                "all_items": requirements.get('all_items', [])
            },
            "sources": [
                {
                    "agency": cite.get('agency'),
                    "title": cite.get('title'),
                    "url": cite.get('url'),
                    "category": cite.get('category')
                }
                for cite in citations
            ],
            "metadata": {
                "timestamp": backend_response.get('timestamp'),
                "has_error": "error" in backend_response
            }
        }
        
        return formatted


# 싱글톤 인스턴스
_backend_service_instance = None


def get_backend_service() -> BackendAPIService:
    """BackendAPIService 싱글톤 인스턴스 반환"""
    global _backend_service_instance
    
    if _backend_service_instance is None:
        _backend_service_instance = BackendAPIService()
    
    return _backend_service_instance


# 테스트용 메인
if __name__ == "__main__":
    async def test():
        service = BackendAPIService()
        
        # 헬스 체크
        health = await service.health_check()
        print(f"\n헬스 체크: {health}")
        
        # 요건 수집 테스트
        result = await service.collect_requirements(
            product="vitamin c serum",
            hs_code="330499",
            include_raw_data=False
        )
        
        print(f"\n수집 결과:")
        print(f"  - 제품: {result.get('product')}")
        print(f"  - 정규화: {result.get('normalized_keyword')}")
        print(f"  - 요건 수: {result.get('requirements', {}).get('total_count', 0)}")
        print(f"  - 출처 수: {len(result.get('citations', []))}")
        
        # AI 분석용 포맷 변환
        formatted = service.format_for_ai_analysis(result)
        print(f"\n포맷 변환:")
        print(json.dumps(formatted, indent=2, ensure_ascii=False))
    
    asyncio.run(test())

