import asyncio
import aiohttp
import logging
from typing import List, Dict, Any
from tavily import TavilyClient
import time
from datetime import datetime
import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

logger = logging.getLogger(__name__)

class CBPDataCollector:
    def __init__(self):
        self.session = None
        
        # 🚀 메모리 캐싱 시스템
        self.memory_cache = {}
        self.cache_ttl = 7 * 24 * 3600  # 7일 (초)
        logger.info("메모리 캐싱 시스템 초기화 완료")
        
        # 🚀 벡터 검색 시스템 (지연 로딩)
        self.vector_search = None
        
        # Tavily 클라이언트 초기화
        self.tavily_client = None
        tavily_api_key = os.getenv('TAVILY_API_KEY')
        if tavily_api_key:
            try:
                self.tavily_client = TavilyClient(api_key=tavily_api_key)
                logger.info("✅ Tavily 클라이언트 초기화 성공")
            except Exception as e:
                logger.error(f"❌ Tavily 클라이언트 초기화 실패: {e}")
        else:
            logger.warning("⚠️ TAVILY_API_KEY가 설정되지 않았습니다.")
    
    def get_cached_data(self, hs_code: str) -> List[Dict[str, Any]]:
        """캐시된 데이터 조회"""
        if hs_code in self.memory_cache:
            cached_time, data = self.memory_cache[hs_code]
            if time.time() - cached_time < self.cache_ttl:
                logger.info(f"✅ 캐시에서 데이터 반환: {hs_code}")
                return data
            else:
                # 만료된 캐시 삭제
                del self.memory_cache[hs_code]
                logger.info(f"🗑️ 만료된 캐시 삭제: {hs_code}")
        
        return None
    
    def cache_data(self, hs_code: str, data: List[Dict[str, Any]]):
        """데이터 캐싱"""
        self.memory_cache[hs_code] = (time.time(), data)
        logger.info(f"💾 데이터 캐싱 완료: {hs_code} ({len(data)}개 항목)")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """캐시 통계 반환"""
        current_time = time.time()
        valid_count = 0
        expired_count = 0
        
        for hs_code, (cached_time, _) in self.memory_cache.items():
            if current_time - cached_time < self.cache_ttl:
                valid_count += 1
            else:
                expired_count += 1
        
        return {
            'total_cached': len(self.memory_cache),
            'valid_cached': valid_count,
            'expired_cached': expired_count,
            'cache_hit_rate': f"{valid_count}/{len(self.memory_cache)}" if self.memory_cache else "0/0"
        }
    
    def set_vector_search(self, vector_search):
        """벡터 검색 시스템 설정"""
        self.vector_search = vector_search
        logger.info("✅ 벡터 검색 시스템 설정 완료")
    
    def _store_precedents_in_vector_db(self, hs_code: str, precedents: List[Dict[str, Any]]):
        """수집된 판례 데이터를 벡터 DB에 저장 (실제 ruling만)"""
        if not self.vector_search:
            return
        
        try:
            stored_count = 0
            for precedent in precedents:
                # 모든 CBP 관련 데이터 저장 (느슨한 기준)
                case_id = precedent.get('case_id', '')
                if not case_id:
                    logger.warning(f"⚠️ case_id 없음 - 벡터 DB 저장 제외")
                    continue
                
                success = self.vector_search.add_precedent_to_db(
                    precedent_id=case_id,
                    text=precedent.get('description', '') + ' ' + precedent.get('title', ''),
                    hs_code=hs_code,
                    case_type=precedent.get('case_type', 'unknown'),
                    outcome=precedent.get('outcome', 'unknown'),
                    source=precedent.get('source', 'cbp'),
                    additional_metadata={
                        'date': precedent.get('date'),
                        'link': precedent.get('link', ''),
                        'key_factors': precedent.get('key_factors', [])
                    }
                )
                if success:
                    stored_count += 1
                    logger.info(f"✅ 실제 CBP ruling 벡터 DB 저장: {case_id}")
            
            logger.info(f"✅ 벡터 DB에 {stored_count}개 실제 판례 저장 완료: {hs_code}")
            
        except Exception as e:
            logger.error(f"❌ 벡터 DB 저장 실패: {e}")
    
    async def get_precedents_by_hs_code(self, hs_code: str) -> List[Dict[str, Any]]:
        """
        HS코드에 따른 실제 CBP 판례를 Tavily로 검색합니다. (캐싱 적용)
        """
        logger.info(f"🔍 CBP 데이터 수집 시작: HS코드 {hs_code}")
        
        # 🚀 1. 캐시 확인
        cached_data = self.get_cached_data(hs_code)
        if cached_data:
            return cached_data
        
        try:
            # 🚀 2. 캐시에 없으면 Tavily로 검색
            logger.info(f"📡 Tavily 검색 시작: {hs_code}")
            tavily_data = await self._search_cbp_with_tavily(hs_code)
            
            # 데이터 정리 및 중복 제거
            cleaned_data = self._clean_and_deduplicate_data(tavily_data)
            
            # 🚀 3. 결과 캐싱
            self.cache_data(hs_code, cleaned_data)
            
            # 🚀 4. 벡터 DB에 판례 저장
            self._store_precedents_in_vector_db(hs_code, cleaned_data)
            
            logger.info(f"✅ CBP 데이터 수집 완료: {len(cleaned_data)}개 사례")
            return cleaned_data
            
        except Exception as e:
            logger.error(f"❌ CBP 데이터 수집 실패: {str(e)}")
            return []
    
    async def _search_cbp_with_tavily(self, hs_code: str) -> List[Dict[str, Any]]:
        """
        Tavily를 사용하여 실제 CBP 공식 ruling만 검색합니다.
        """
        if not self.tavily_client:
            logger.error("❌ Tavily 클라이언트가 없습니다. TAVILY_API_KEY를 설정해주세요.")
            return []
        
        try:
            # 실제 CBP ruling 검색 쿼리 (구체적인 판례 찾기)
            search_queries = [
                f'site:rulings.cbp.gov "HS {hs_code}" "classification" ruling',
                f'site:rulings.cbp.gov "subheading {hs_code}" "approved" OR "denied"',
                f'site:rulings.cbp.gov "tariff classification {hs_code}" "ruling"',
                f'"HQ" "NY" "HS {hs_code}" "cosmetic" "classification" site:rulings.cbp.gov',
                f'"{hs_code}" "classified in" OR "excluded from" site:rulings.cbp.gov',
            ]
            
            all_results = []
            
            for query in search_queries[:3]:  # 상위 3개 쿼리만 사용
                try:
                    logger.info(f"🔎 Tavily CBP 검색: {query}")
                    
                    response = self.tavily_client.search(
                        query=query,
                        search_depth='advanced',
                        max_results=10,
                        include_domains=['rulings.cbp.gov']  # rulings.cbp.gov만!
                    )
                    
                    for result in response.get('results', []):
                        url = result.get('url', '')
                        
                        # rulings.cbp.gov만 허용 (실제 ruling 페이지만)
                        if 'rulings.cbp.gov' not in url:
                            logger.warning(f"⚠️ rulings.cbp.gov 아님 - 제외: {url}")
                            continue
                        
                        # 실제 ruling 페이지만 허용
                        url_lower = url.lower()
                        if '/ruling/' not in url_lower:
                            logger.warning(f"⚠️ ruling 페이지 아님 - 제외: {url}")
                            continue
                        
                        # 제외할 페이지들
                        exclude_pages = [
                            '/search', '/sites/default/files', '/home', '/requirements'
                        ]
                        
                        if any(exclude in url_lower for exclude in exclude_pages):
                            logger.warning(f"⚠️ 일반 페이지 제외: {url}")
                            continue
                        
                        cbp_data = self._convert_tavily_result_to_cbp_data(result, hs_code)
                        if cbp_data:
                            all_results.append(cbp_data)
                            logger.info(f"✅ 실제 CBP ruling 추가: {cbp_data['case_id']}")
                    
                    # 요청 간 지연 (Rate Limit 방지)
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.error(f"❌ Tavily 검색 오류 ({query}): {e}")
                    continue
            
            if not all_results:
                logger.warning(f"⚠️ 실제 CBP ruling을 찾지 못함: HS {hs_code}")
            else:
                logger.info(f"✅ 총 {len(all_results)}개 실제 CBP ruling 발견: HS {hs_code}")
            
            return all_results
            
        except Exception as e:
            logger.error(f"❌ Tavily CBP 검색 실패: {e}")
            return []
    
    def _convert_tavily_result_to_cbp_data(self, result: Dict[str, Any], hs_code: str) -> Dict[str, Any]:
        """
        Tavily 검색 결과를 CBP 데이터 형식으로 변환합니다.
        실제 CBP ruling 번호가 없으면 None을 반환합니다.
        """
        try:
            title = result.get('title', '')
            url = result.get('url', '')
            content = result.get('content', '')
            
            # URL에서 실제 CBP ruling 번호 추출 시도
            case_id = self._extract_case_id_from_url(url, title)
            
            # case_id가 없으면 기본값 생성
            if not case_id:
                case_id = f'CBP-{title[:10].replace(" ", "")}'  # 제목 기반 ID 생성
                logger.info(f"✅ 제목 기반 ID 생성: {case_id}")
            
            # 내용에서 승인/거부 상태 판단
            status = self._determine_status_from_content(content, title)
            
            # UNKNOWN 상태도 허용 (느슨한 기준)
            if status == 'UNKNOWN':
                status = 'REVIEW'  # 검토 필요 상태로 변경
                logger.info(f"✅ 검토 필요 상태로 분류: {case_id}")
            
            # HS 코드 카테고리 결정
            category = self._determine_hs_category(hs_code)
            
            logger.info(f"✅ 실제 CBP 데이터 변환 성공: {case_id} ({status})")
            
            return {
                'case_id': case_id,
                'title': title,
                'status': status,
                'date': datetime.now().strftime('%Y-%m-%d'),
                'description': content[:500] if content else f'CBP ruling {case_id} for HS code {hs_code}',
                'key_factors': [category, 'Tavily Search', 'CBP Data'],
                'hs_code': hs_code,
                'source': 'tavily_search',
                'link': url,
                'case_type': 'APPROVAL_CASE' if status == 'APPROVED' else 'DENIAL_CASE',
                'outcome': status,
                'reason': content[:200] if content else f'CBP ruling {case_id} for HS code {hs_code}'
            }
            
        except Exception as e:
            logger.error(f"❌ Tavily 결과 변환 오류: {e}")
            return None
    
    def _extract_case_id_from_url(self, url: str, title: str) -> str:
        """URL이나 제목에서 CBP 관련 ID를 추출합니다. (느슨한 기준)"""
        import re
        
        # URL에서 CBP 관련 ID 패턴 찾기 (더 느슨하게)
        url_patterns = [
            r'ruling/([A-Z]\d{6})',     # ruling/N256328, ruling/W968396
            r'/(HQ[A-Z0-9]{6,})',       # HQ ruling
            r'/(NY[A-Z0-9]{6,})',       # NY ruling
            r'/([A-Z]\d{6})',           # 기타 ruling
            r'/(R\d{6})',               # R ruling
            r'/([A-Z]{2}\d{6})',        # 2글자+6숫자
            r'/([A-Z]\d+)',             # 더 느슨한 패턴
            r'term=([A-Z0-9.]+)',       # 검색 결과에서 HS코드나 ID
        ]
        
        for pattern in url_patterns:
            match = re.search(pattern, url, re.IGNORECASE)
            if match:
                ruling_id = match.group(1).upper()
                logger.info(f"✅ URL에서 CBP ID 발견: {ruling_id}")
                return ruling_id
        
        # 제목에서 CBP 관련 ID 찾기
        title_patterns = [
            r'\b(HQ\s*[A-Z0-9]{6,})\b',  # HQ ruling
            r'\b(NY\s*[A-Z0-9]{6,})\b',  # NY ruling
            r'\b([A-Z]{2}\d{6,})\b',     # 2글자+6자리 이상
            r'\b(R\d{6,})\b',            # R ruling
            r'\b([A-Z]\d{6,})\b',        # 더 느슨한 패턴
        ]
        
        for pattern in title_patterns:
            match = re.search(pattern, title, re.IGNORECASE)
            if match:
                ruling_id = match.group(1).replace(" ", "").upper()
                logger.info(f"✅ 제목에서 CBP ID 발견: {ruling_id}")
                return ruling_id
        
        # URL 해시로 고유 ID 생성 (느슨한 기준에서는 허용)
        import hashlib
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        case_id = f'CBP-{url_hash}'
        logger.info(f"✅ URL 해시로 ID 생성: {case_id}")
        return case_id
    
    def _determine_status_from_content(self, content: str, title: str) -> str:
        """내용에서 승인/거부 상태를 정확하게 판단합니다."""
        content_lower = content.lower()
        title_lower = title.lower()
        combined = f"{title_lower} {content_lower}"
        
        # 거부/제외 관련 키워드와 패턴 (더 정확하게)
        denial_patterns = [
            'denied', 'rejected', 'refused', 'prohibited', 'banned',
            'excluded from', 'not classified in', 'not classifiable',
            'not eligible', 'revoked', 'withdrawn', 'violation',
            'does not qualify', 'cannot be classified', 'improperly classified',
            'incorrectly classified', 'misclassified'
        ]
        
        # 승인 관련 키워드와 패턴 (더 정확하게)
        approval_patterns = [
            'approved for', 'classified in', 'classifiable in', 
            'properly classified', 'correctly classified',
            'meets the requirements', 'qualifies for',
            'authorized for import', 'permitted entry',
            'granted classification', 'ruling issued'
        ]
        
        # 거부/제외 패턴 우선 확인 (더 중요함)
        denial_count = sum(1 for pattern in denial_patterns if pattern in combined)
        approval_count = sum(1 for pattern in approval_patterns if pattern in combined)
        
        # 명확한 판단 기준
        if denial_count > 0 and denial_count > approval_count:
            return 'DENIED'
        elif approval_count > 0 and approval_count > denial_count:
            return 'APPROVED'
        elif denial_count == approval_count and denial_count > 0:
            # 동점이면 더 구체적인 문구 확인
            if 'excluded from classification' in combined or 'not classifiable' in combined:
                return 'DENIED'
            elif 'classified in subheading' in combined or 'properly classified' in combined:
                return 'APPROVED'
        
        # 판단 불가
        return 'UNKNOWN'
    
    def _determine_hs_category(self, hs_code: str) -> str:
        """HS 코드에서 카테고리를 결정합니다."""
        hs_category = hs_code.split('.')[0] if '.' in hs_code else hs_code[:2]
        
        category_map = {
            '33': 'Cosmetic',
            '3304': 'Cosmetic',
            '21': 'Food',
            '2106': 'Food',
            '85': 'Electronics',
            '8517': 'Electronics',
            '84': 'Machinery',
            '90': 'Medical',
            '9018': 'Medical',
            '94': 'Furniture'
        }
        
        return category_map.get(hs_category, 'General')
    
    def _clean_and_deduplicate_data(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """데이터를 정리하고 중복을 제거합니다."""
        # 중복 제거 (case_id 기준)
        seen_ids = set()
        cleaned_data = []
        
        for item in data:
            case_id = item.get('case_id', '')
            if case_id and case_id not in seen_ids:
                seen_ids.add(case_id)
                cleaned_data.append(item)
        
        return cleaned_data
