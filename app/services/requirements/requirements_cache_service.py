"""
요구사항 분석 캐시 서비스
DB 캐시 기반 요구사항 분석 결과 관리
"""

import asyncio
import json
import hashlib
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import aiohttp

@dataclass
class RequirementsCacheEntry:
    """요구사항 분석 캐시 엔트리"""
    hs_code: str
    product_name: str
    analysis_result: Dict[str, Any]
    created_at: datetime
    expires_at: datetime
    version: str = "1.0"

class RequirementsCacheService:
    """요구사항 분석 캐시 서비스"""
    
    def __init__(self, backend_api_url: str = "http://localhost:8081"):
        self.backend_api_url = backend_api_url
        self.cache_ttl = 86400 * 7  # 7일
        self.memory_cache = {}  # 메모리 캐시
    
    async def get_cached_analysis(
        self, 
        hs_code: str, 
        product_name: str
    ) -> Optional[Dict[str, Any]]:
        """캐시에서 분석 결과 조회"""
        
        print(f"🔍 캐시 조회 - HS코드: {hs_code}, 상품: {product_name}")
        
        # 1. 메모리 캐시 확인
        cache_key = self._generate_cache_key(hs_code, product_name)
        if cache_key in self.memory_cache:
            cached_entry = self.memory_cache[cache_key]
            if datetime.now() < cached_entry.expires_at:
                print(f"✅ 메모리 캐시에서 조회")
                return cached_entry.analysis_result
            else:
                # 만료된 캐시 제거
                del self.memory_cache[cache_key]
        
        # 2. DB 캐시 확인
        db_result = await self._get_from_db_cache(hs_code, product_name)
        if db_result:
            print(f"✅ DB 캐시에서 조회")
            # 메모리 캐시에 저장
            self._save_to_memory_cache(cache_key, db_result)
            return db_result.analysis_result
        
        print(f"❌ 캐시에 없음")
        return None
    
    async def save_analysis_to_cache(
        self, 
        hs_code: str, 
        product_name: str,
        analysis_result: Dict[str, Any]
    ) -> bool:
        """분석 결과를 캐시에 저장"""
        
        print(f"💾 캐시 저장 - HS코드: {hs_code}, 상품: {product_name}")
        
        try:
            # 캐시 엔트리 생성
            cache_entry = RequirementsCacheEntry(
                hs_code=hs_code,
                product_name=product_name,
                analysis_result=analysis_result,
                created_at=datetime.now(),
                expires_at=datetime.now() + timedelta(seconds=self.cache_ttl)
            )
            
            # 1. 메모리 캐시에 저장
            cache_key = self._generate_cache_key(hs_code, product_name)
            self._save_to_memory_cache(cache_key, cache_entry)
            
            # 2. DB 캐시에 저장
            success = await self._save_to_db_cache(cache_entry)
            
            if success:
                print(f"✅ 캐시 저장 완료")
                return True
            else:
                print(f"❌ 캐시 저장 실패")
                return False
                
        except Exception as e:
            print(f"❌ 캐시 저장 오류: {e}")
            return False
    
    async def invalidate_cache(self, hs_code: str, product_name: str) -> bool:
        """캐시 무효화"""
        
        print(f"🗑️ 캐시 무효화 - HS코드: {hs_code}, 상품: {product_name}")
        
        try:
            # 1. 메모리 캐시에서 제거
            cache_key = self._generate_cache_key(hs_code, product_name)
            if cache_key in self.memory_cache:
                del self.memory_cache[cache_key]
            
            # 2. DB 캐시에서 제거
            success = await self._delete_from_db_cache(hs_code, product_name)
            
            if success:
                print(f"✅ 캐시 무효화 완료")
                return True
            else:
                print(f"❌ 캐시 무효화 실패")
                return False
                
        except Exception as e:
            print(f"❌ 캐시 무효화 오류: {e}")
            return False
    
    async def is_cache_valid(self, hs_code: str, product_name: str) -> bool:
        """캐시 유효성 확인"""
        
        # 메모리 캐시 확인
        cache_key = self._generate_cache_key(hs_code, product_name)
        if cache_key in self.memory_cache:
            cached_entry = self.memory_cache[cache_key]
            return datetime.now() < cached_entry.expires_at
        
        # DB 캐시 확인
        db_result = await self._get_from_db_cache(hs_code, product_name)
        if db_result:
            return datetime.now() < db_result.expires_at
        
        return False
    
    def _generate_cache_key(self, hs_code: str, product_name: str) -> str:
        """캐시 키 생성"""
        key_string = f"{hs_code}_{product_name}"
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def _save_to_memory_cache(self, cache_key: str, cache_entry: RequirementsCacheEntry):
        """메모리 캐시에 저장"""
        self.memory_cache[cache_key] = cache_entry
        
        # 메모리 캐시 크기 제한 (최대 100개)
        if len(self.memory_cache) > 100:
            # 가장 오래된 항목 제거
            oldest_key = min(self.memory_cache.keys(), 
                           key=lambda k: self.memory_cache[k].created_at)
            del self.memory_cache[oldest_key]
    
    async def _get_from_db_cache(self, hs_code: str, product_name: str) -> Optional[RequirementsCacheEntry]:
        """ProductAnalysisCache 테이블에서 조회"""
        try:
            async with aiohttp.ClientSession() as session:
                # ProductAnalysisCache에서 requirements 분석 타입으로 조회
                url = f"{self.backend_api_url}/api/products/analysis/search"
                params = {
                    "hs_code": hs_code,
                    "analysis_type": "requirements"
                }
                
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data and len(data) > 0:
                            # 첫 번째 결과 사용 (같은 HS코드의 requirements 분석)
                            cache_data = data[0]
                            return RequirementsCacheEntry(
                                hs_code=hs_code,
                                product_name=product_name,
                                analysis_result=cache_data["analysisResult"],
                                created_at=datetime.fromisoformat(cache_data["createdAt"]),
                                expires_at=datetime.now() + timedelta(seconds=self.cache_ttl)  # ProductAnalysisCache에는 expires_at이 없으므로 생성
                            )
        except Exception as e:
            print(f"⚠️ ProductAnalysisCache 조회 실패: {e}")
        
        return None
    
    async def _save_to_db_cache(self, cache_entry: RequirementsCacheEntry) -> bool:
        """ProductAnalysisCache 테이블에 저장"""
        try:
            async with aiohttp.ClientSession() as session:
                # ProductAnalysisCache에 저장하기 위해 상품 ID가 필요함
                # 먼저 상품을 찾거나 생성해야 함
                url = f"{self.backend_api_url}/api/products/analysis/cache"
                # 실제 신뢰도 점수 추출
                confidence = self._extract_confidence_score(cache_entry.analysis_result)
                data = {
                    "hsCode": cache_entry.hs_code,
                    "productName": cache_entry.product_name,
                    "analysisType": "requirements",
                    "analysisResult": cache_entry.analysis_result,
                    "confidenceScore": confidence,
                    "isValid": True
                }
                
                async with session.post(url, json=data) as response:
                    return response.status in [200, 201]
                    
        except Exception as e:
            print(f"⚠️ ProductAnalysisCache 저장 실패: {e}")
            return False

    def _extract_confidence_score(self, analysis_result: Dict[str, Any]) -> float:
        """분석 결과에서 신뢰도 점수 추출. 없으면 0.95로 fallback."""
        try:
            # 1) llm_summary.confidence_score
            llm_summary = analysis_result.get("llm_summary")
            if isinstance(llm_summary, dict):
                score = llm_summary.get("confidence_score")
                if isinstance(score, (int, float)):
                    return float(score)

            # 2) top-level confidence
            score = analysis_result.get("confidence")
            if isinstance(score, (int, float)):
                return float(score)

        except Exception:
            pass
        return 0.95
    
    async def _delete_from_db_cache(self, hs_code: str, product_name: str) -> bool:
        """ProductAnalysisCache에서 삭제"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.backend_api_url}/api/products/analysis/cache"
                params = {
                    "hs_code": hs_code,
                    "analysis_type": "requirements"
                }
                
                async with session.delete(url, params=params) as response:
                    return response.status == 200
                    
        except Exception as e:
            print(f"⚠️ ProductAnalysisCache 삭제 실패: {e}")
            return False
    
    async def get_cache_statistics(self) -> Dict[str, Any]:
        """캐시 통계 조회"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.backend_api_url}/api/requirements-cache/statistics"
                
                async with session.get(url) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        return {"error": f"통계 조회 실패: {response.status}"}
                        
        except Exception as e:
            return {"error": f"통계 조회 오류: {e}"}
    
    def get_memory_cache_stats(self) -> Dict[str, Any]:
        """메모리 캐시 통계"""
        return {
            "memory_cache_size": len(self.memory_cache),
            "cache_ttl": self.cache_ttl,
            "cached_keys": list(self.memory_cache.keys())
        }
    
    def clear_memory_cache(self):
        """메모리 캐시 초기화"""
        self.memory_cache.clear()
        print("🧹 메모리 캐시 초기화 완료")
