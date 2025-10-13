"""
HS코드 기관 매핑 서비스
GPT를 사용한 동적 기관 추천 및 DB 캐싱
"""

import asyncio
import json
import hashlib
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import aiohttp
from openai import AsyncOpenAI

@dataclass
class AgencyMappingResult:
    """기관 매핑 결과"""
    hs_code: str
    product_category: str
    recommended_agencies: List[str]
    confidence_score: float
    source: str  # 'cache', 'gpt', 'fallback'
    usage_count: int = 0

class HsCodeAgencyMappingService:
    """HS코드 기관 매핑 서비스"""
    
    def __init__(self, backend_api_url: str = "http://localhost:8081"):
        self.backend_api_url = backend_api_url
        self.openai_client = AsyncOpenAI()
        self.memory_cache = {}  # 메모리 캐시
        self.cache_ttl = 86400 * 30  # 30일 (HS 코드 매핑은 거의 안 바뀜)
        
        # GPT 프롬프트 템플릿
        self.gpt_prompt_template = """
HS코드 {hs_code}에 해당하는 상품: {product_description}

미국 수입 시 다음 기관 중에서 관련성이 높은 기관들을 우선순위대로 추천해주세요:

- FDA (식품의약국): 식품, 의약품, 화장품, 의료기기
- USDA (농무부): 농산물, 유기농 인증, 식물 검역
- EPA (환경보호청): 화학물질, 농약, 환경 기준
- FCC (연방통신위원회): 전자제품, 통신기기, EMC 기준
- CPSC (소비자제품안전위원회): 소비자 제품 안전, 장난감, 가구

응답 형식 (JSON):
{{
    "agencies": ["FDA", "USDA"],
    "reasoning": "추천 이유",
    "confidence": 0.85
}}

최대 3개 기관만 추천하고, confidence는 0.0-1.0 사이로 설정하세요.
"""
    
    async def get_relevant_agencies(
        self, 
        hs_code: str, 
        product_name: str,
        product_description: str = ""
    ) -> AgencyMappingResult:
        """관련 기관 조회 (캐시 우선, GPT 백업)"""
        
        print(f"🔍 기관 매핑 조회 - HS코드: {hs_code}, 상품: {product_name}")
        
        # 1. 메모리 캐시 확인
        cache_key = f"{hs_code}_{product_name}"
        if cache_key in self.memory_cache:
            cached_result = self.memory_cache[cache_key]
            if datetime.now() < cached_result.get('expires_at', datetime.min):
                print(f"✅ 메모리 캐시에서 조회: {cached_result['agencies']}")
                return AgencyMappingResult(
                    hs_code=hs_code,
                    product_category=product_name,
                    recommended_agencies=cached_result['agencies'],
                    confidence_score=cached_result['confidence'],
                    source='cache',
                    usage_count=cached_result.get('usage_count', 0)
                )
        
        # 2. DB 캐시 확인
        db_result = await self._get_from_db_cache(hs_code, product_name)
        if db_result:
            print(f"✅ DB 캐시에서 조회: {db_result.recommended_agencies}")
            # 메모리 캐시에 저장
            self._save_to_memory_cache(cache_key, db_result)
            return db_result
        
        # 3. GPT로 추천 받기
        gpt_result = await self._ask_gpt_for_agencies(hs_code, product_name, product_description)
        if gpt_result:
            print(f"✅ GPT 추천: {gpt_result.recommended_agencies}")
            # DB에 저장
            await self._save_to_db_cache(gpt_result)
            # 메모리 캐시에 저장
            self._save_to_memory_cache(cache_key, gpt_result)
            return gpt_result
        
        # 4. 폴백 (기본 매핑)
        fallback_result = self._get_fallback_agencies(hs_code)
        print(f"⚠️ 폴백 사용: {fallback_result.recommended_agencies}")
        return fallback_result
    
    async def _get_from_db_cache(self, hs_code: str, product_name: str) -> Optional[AgencyMappingResult]:
        """DB 캐시에서 조회"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.backend_api_url}/api/hs-code-agency-mappings/search"
                params = {
                    "hs_code": hs_code,
                    "product_name": product_name
                }
                
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data:
                            return AgencyMappingResult(
                                hs_code=data['hsCode'],
                                product_category=data['productCategory'],
                                recommended_agencies=json.loads(data['recommendedAgencies']),
                                confidence_score=float(data['confidenceScore']),
                                source='cache',
                                usage_count=data.get('usageCount', 0)
                            )
        except Exception as e:
            print(f"❌ DB 캐시 조회 실패: {e}")
        
        return None
    
    async def _ask_gpt_for_agencies(
        self, 
        hs_code: str, 
        product_name: str, 
        product_description: str
    ) -> Optional[AgencyMappingResult]:
        """GPT로 기관 추천 받기"""
        try:
            prompt = self.gpt_prompt_template.format(
                hs_code=hs_code,
                product_description=f"{product_name} - {product_description}" if product_description else product_name
            )
            
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            return AgencyMappingResult(
                hs_code=hs_code,
                product_category=product_name,
                recommended_agencies=result['agencies'],
                confidence_score=result['confidence'],
                source='gpt',
                usage_count=0
            )
            
        except Exception as e:
            print(f"❌ GPT 추천 실패: {e}")
            return None
    
    async def _save_to_db_cache(self, result: AgencyMappingResult):
        """DB 캐시에 저장"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.backend_api_url}/api/hs-code-agency-mappings"
                data = {
                    "hsCode": result.hs_code,
                    "productCategory": result.product_category,
                    "productDescription": "",
                    "recommendedAgencies": json.dumps(result.recommended_agencies),
                    "confidenceScore": result.confidence_score,
                    "usageCount": result.usage_count
                }
                
                async with session.post(url, json=data) as response:
                    if response.status in [200, 201]:
                        print(f"✅ DB 캐시 저장 완료: {result.hs_code}")
                    else:
                        print(f"❌ DB 캐시 저장 실패: {response.status}")
                        
        except Exception as e:
            print(f"❌ DB 캐시 저장 오류: {e}")
    
    def _save_to_memory_cache(self, cache_key: str, result: AgencyMappingResult):
        """메모리 캐시에 저장"""
        self.memory_cache[cache_key] = {
            'agencies': result.recommended_agencies,
            'confidence': result.confidence_score,
            'expires_at': datetime.now() + timedelta(seconds=self.cache_ttl),
            'usage_count': result.usage_count
        }
    
    def _get_fallback_agencies(self, hs_code: str) -> AgencyMappingResult:
        """폴백 기관 매핑 (기본 규칙)"""
        hs_4digit = hs_code.split('.')[0] if '.' in hs_code else hs_code[:4]
        
        fallback_mapping = {
            "3304": ["FDA", "CPSC"],  # 화장품
            "3307": ["FDA"],          # 향수
            "2106": ["FDA", "USDA"],  # 건강보조식품
            "1904": ["FDA", "USDA"],  # 식품
            "1905": ["FDA", "USDA"],  # 베이커리
            "1902": ["FDA", "USDA"],  # 파스타
            "2005": ["FDA", "USDA"],  # 보존식품
            "8471": ["FCC", "CPSC"],  # 컴퓨터
            "8517": ["FCC", "CPSC"],  # 통신기기
            "6109": ["CPSC"],         # 의류
            "9503": ["CPSC", "FDA"]   # 장난감
        }
        
        agencies = fallback_mapping.get(hs_4digit, ["FDA"])  # 기본값은 FDA
        
        return AgencyMappingResult(
            hs_code=hs_code,
            product_category="Unknown",
            recommended_agencies=agencies,
            confidence_score=0.5,  # 폴백은 낮은 신뢰도
            source='fallback',
            usage_count=0
        )
    
    async def update_usage_count(self, hs_code: str, product_name: str):
        """사용 횟수 업데이트"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.backend_api_url}/api/hs-code-agency-mappings/usage"
                data = {
                    "hsCode": hs_code,
                    "productName": product_name
                }
                
                async with session.put(url, json=data) as response:
                    if response.status == 200:
                        print(f"✅ 사용 횟수 업데이트 완료: {hs_code}")
                    else:
                        print(f"❌ 사용 횟수 업데이트 실패: {response.status}")
                        
        except Exception as e:
            print(f"❌ 사용 횟수 업데이트 오류: {e}")
    
    async def get_agency_statistics(self) -> Dict[str, Any]:
        """기관 매핑 통계 조회"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.backend_api_url}/api/hs-code-agency-mappings/statistics"
                
                async with session.get(url) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        return {"error": f"통계 조회 실패: {response.status}"}
                        
        except Exception as e:
            return {"error": f"통계 조회 오류: {e}"}
    
    def clear_memory_cache(self):
        """메모리 캐시 초기화"""
        self.memory_cache.clear()
        print("🧹 메모리 캐시 초기화 완료")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """캐시 통계 조회"""
        return {
            "memory_cache_size": len(self.memory_cache),
            "cache_ttl": self.cache_ttl,
            "cached_keys": list(self.memory_cache.keys())
        }
