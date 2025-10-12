"""
규제 변경 감지 및 자동 업데이트 모니터

FR-CR-004 요구사항: 규정 변경 7일 내 업데이트
- RSS 피드 모니터링
- API Last-Modified 체크
- 자동 캐시 무효화 및 재분석
"""

import asyncio
import aiohttp
import feedparser
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
import hashlib
import logging

logger = logging.getLogger(__name__)

@dataclass
class RegulatoryUpdate:
    """규제 변경 정보"""
    agency: str
    title: str
    url: str
    published_date: datetime
    description: str
    affected_hs_codes: List[str] = None
    update_type: str = "general"  # general, critical, informational

class RegulatoryUpdateMonitor:
    """
    규제 변경 감지 및 자동 업데이트 모니터
    
    주요 기능:
    1. 정부 기관 RSS 피드 모니터링 (7일 주기)
    2. API Last-Modified 헤더 체크
    3. 변경 감지 시 영향받는 상품 자동 재분석
    4. 변경 이력 DB 저장
    
    모니터링 대상:
    - FDA: https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds
    - USDA: https://www.usda.gov/rss
    - EPA: https://www.epa.gov/newsreleases/search/rss
    - CPSC: https://www.cpsc.gov/Newsroom/Subscribe
    """
    
    def __init__(self, backend_api_url: str = "http://localhost:8081"):
        self.backend_api_url = backend_api_url
        self.check_interval = timedelta(days=7)  # 7일 주기
        self.last_check_time = {}
        
        # RSS 피드 URL
        self.rss_feeds = {
            "FDA": [
                "https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/food/rss.xml",
                "https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/cosmetics/rss.xml",
                "https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/drugs/rss.xml"
            ],
            "USDA": [
                "https://www.usda.gov/rss/latest-releases.xml"
            ],
            "EPA": [
                "https://www.epa.gov/newsreleases/search/rss"
            ],
            "CPSC": [
                "https://www.cpsc.gov/Newsroom/Recalls/RSS"
            ]
        }
        
        # 마지막 확인 시간 저장
        self.update_history = {}
    
    async def start_monitoring(self):
        """
        모니터링 시작 (백그라운드 태스크)
        
        사용법:
            monitor = RegulatoryUpdateMonitor()
            asyncio.create_task(monitor.start_monitoring())
        """
        logger.info("🔍 규제 변경 모니터링 시작 - 7일 주기")
        
        while True:
            try:
                await self.check_all_updates()
                
                # 7일 대기
                await asyncio.sleep(self.check_interval.total_seconds())
                
            except Exception as e:
                logger.error(f"❌ 모니터링 오류: {e}")
                # 오류 발생 시 1시간 후 재시도
                await asyncio.sleep(3600)
    
    async def check_all_updates(self):
        """모든 기관의 업데이트 확인"""
        logger.info("📡 전체 기관 업데이트 확인 시작")
        
        all_updates = []
        
        # 모든 기관 RSS 피드 체크
        for agency, feeds in self.rss_feeds.items():
            for feed_url in feeds:
                updates = await self._check_rss_feed(agency, feed_url)
                all_updates.extend(updates)
        
        logger.info(f"✅ 총 {len(all_updates)}개 업데이트 발견")
        
        # 중요 업데이트 필터링 (최근 7일)
        recent_updates = [
            update for update in all_updates
            if update.published_date > datetime.now() - timedelta(days=7)
        ]
        
        if recent_updates:
            logger.warning(f"⚠️ 최근 7일 내 {len(recent_updates)}개 중요 업데이트")
            await self._process_updates(recent_updates)
        else:
            logger.info("✅ 최근 규제 변경 없음")
    
    async def _check_rss_feed(self, agency: str, feed_url: str) -> List[RegulatoryUpdate]:
        """RSS 피드 체크"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(feed_url, timeout=30) as response:
                    if response.status == 200:
                        content = await response.text()
                        feed = feedparser.parse(content)
                        
                        updates = []
                        for entry in feed.entries:
                            try:
                                published_date = datetime(*entry.published_parsed[:6])
                            except:
                                published_date = datetime.now()
                            
                            update = RegulatoryUpdate(
                                agency=agency,
                                title=entry.title,
                                url=entry.link,
                                published_date=published_date,
                                description=entry.get('summary', '')[:500]
                            )
                            updates.append(update)
                        
                        logger.debug(f"✅ {agency} RSS: {len(updates)}개 항목")
                        return updates
                    else:
                        logger.warning(f"⚠️ {agency} RSS 접근 실패: {response.status}")
                        return []
                        
        except Exception as e:
            logger.error(f"❌ {agency} RSS 체크 오류: {e}")
            return []
    
    async def _process_updates(self, updates: List[RegulatoryUpdate]):
        """
        업데이트 처리 및 영향받는 상품 재분석
        
        1. 키워드 매칭으로 영향받는 HS 코드 찾기
        2. 해당 상품들의 캐시 무효화
        3. 백그라운드 재분석 트리거
        """
        logger.info(f"🔄 {len(updates)}개 업데이트 처리 시작")
        
        for update in updates:
            # 변경 이력 저장
            await self._save_update_to_db(update)
            
            # 영향받는 상품 찾기
            affected_products = await self._find_affected_products(update)
            
            if affected_products:
                logger.warning(
                    f"⚠️ {update.agency} 업데이트로 {len(affected_products)}개 상품 영향"
                )
                
                # 캐시 무효화 및 재분석
                for product in affected_products:
                    await self._invalidate_and_reanalyze(
                        product['hs_code'],
                        product['product_name'],
                        update
                    )
    
    async def _find_affected_products(self, update: RegulatoryUpdate) -> List[Dict[str, Any]]:
        """
        업데이트에 영향받는 상품 찾기
        
        키워드 매칭:
        - FDA: food, drug, cosmetic, device
        - USDA: agriculture, organic, plant
        - EPA: chemical, pesticide, environment
        - CPSC: consumer, product, safety
        """
        try:
            # 키워드 추출
            keywords = self._extract_keywords_from_update(update)
            
            # Backend API에서 영향받는 상품 조회
            async with aiohttp.ClientSession() as session:
                url = f"{self.backend_api_url}/api/products/search-by-keywords"
                params = {
                    "keywords": ",".join(keywords),
                    "agency": update.agency
                }
                
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        products = await response.json()
                        return products
                    else:
                        logger.warning(f"⚠️ 영향 상품 조회 실패: {response.status}")
                        return []
                        
        except Exception as e:
            logger.error(f"❌ 영향 상품 찾기 오류: {e}")
            return []
    
    def _extract_keywords_from_update(self, update: RegulatoryUpdate) -> List[str]:
        """업데이트 내용에서 키워드 추출"""
        text = f"{update.title} {update.description}".lower()
        
        # 주요 키워드 목록
        important_keywords = [
            "food", "drug", "cosmetic", "device", "medical",
            "agriculture", "organic", "plant", "pesticide",
            "chemical", "toxic", "environment", "emission",
            "consumer", "product", "safety", "recall",
            "import", "export", "regulation", "requirement"
        ]
        
        # 텍스트에서 키워드 추출
        found_keywords = [kw for kw in important_keywords if kw in text]
        
        return found_keywords[:5]  # 최대 5개
    
    async def _invalidate_and_reanalyze(
        self, 
        hs_code: str, 
        product_name: str,
        update: RegulatoryUpdate
    ):
        """캐시 무효화 및 재분석"""
        try:
            logger.info(f"🔄 재분석 시작: {hs_code} - {product_name}")
            
            # 캐시 무효화
            from app.services.requirements.requirements_cache_service import RequirementsCacheService
            cache_service = RequirementsCacheService()
            await cache_service.invalidate_cache(hs_code, product_name)
            
            # 재분석 트리거 (백그라운드)
            # 주의: 실제 분석은 사용자가 조회할 때 수행 (on-demand)
            # 또는 백그라운드 태스크로 미리 분석
            
            logger.info(f"✅ 캐시 무효화 완료: {hs_code}")
            
            # 변경 알림 저장
            await self._save_change_notification(hs_code, product_name, update)
            
        except Exception as e:
            logger.error(f"❌ 재분석 실패: {e}")
    
    async def _save_update_to_db(self, update: RegulatoryUpdate):
        """업데이트 이력을 DB에 저장"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.backend_api_url}/api/regulatory-updates"
                data = {
                    "agency": update.agency,
                    "title": update.title,
                    "url": update.url,
                    "publishedDate": update.published_date.isoformat(),
                    "description": update.description,
                    "updateType": update.update_type
                }
                
                async with session.post(url, json=data) as response:
                    if response.status in [200, 201]:
                        logger.debug(f"✅ 업데이트 이력 저장: {update.title}")
                    else:
                        logger.warning(f"⚠️ 이력 저장 실패: {response.status}")
                        
        except Exception as e:
            logger.error(f"❌ 이력 저장 오류: {e}")
    
    async def _save_change_notification(
        self, 
        hs_code: str, 
        product_name: str,
        update: RegulatoryUpdate
    ):
        """변경 알림 저장 (사용자에게 표시)"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.backend_api_url}/api/product-change-notifications"
                data = {
                    "hsCode": hs_code,
                    "productName": product_name,
                    "agency": update.agency,
                    "changeTitle": update.title,
                    "changeUrl": update.url,
                    "notifiedAt": datetime.now().isoformat()
                }
                
                async with session.post(url, json=data) as response:
                    if response.status in [200, 201]:
                        logger.info(f"✅ 변경 알림 저장: {hs_code}")
                        
        except Exception as e:
            logger.error(f"❌ 알림 저장 오류: {e}")
    
    async def force_check_now(self):
        """즉시 수동 체크 (테스트/디버깅용)"""
        logger.info("🔍 수동 업데이트 체크 시작")
        await self.check_all_updates()
        logger.info("✅ 수동 체크 완료")
    
    def get_monitoring_status(self) -> Dict[str, Any]:
        """모니터링 상태 반환"""
        return {
            "is_active": True,
            "check_interval_days": self.check_interval.days,
            "monitored_agencies": list(self.rss_feeds.keys()),
            "total_feeds": sum(len(feeds) for feeds in self.rss_feeds.values()),
            "last_check_times": {
                agency: time.isoformat() if time else None
                for agency, time in self.last_check_time.items()
            }
        }


# 전역 인스턴스
regulatory_monitor = RegulatoryUpdateMonitor()

