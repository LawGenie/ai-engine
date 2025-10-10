"""
실시간 규정 모니터링 서비스
Federal Register 및 기관별 공지사항 모니터링
"""

import asyncio
import aiohttp
try:
    import feedparser
    HAS_FEEDPARSER = True
except ImportError:
    print("⚠️ feedparser 패키지가 설치되지 않아 RSS 피드 기능이 비활성화됩니다.")
    feedparser = None
    HAS_FEEDPARSER = False
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import json
from datetime import datetime, timedelta
import re

@dataclass
class RegulationUpdate:
    """규정 업데이트 정보"""
    title: str
    agency: str
    publication_date: datetime
    effective_date: Optional[datetime]
    summary: str
    url: str
    impact_level: str  # "low", "medium", "high", "critical"
    affected_hs_codes: List[str]
    change_type: str  # "new", "amendment", "repeal", "clarification"

@dataclass
class MonitoringResult:
    """모니터링 결과"""
    hs_code: str
    product_name: str
    updates_found: List[RegulationUpdate]
    last_check: datetime
    next_check_recommended: datetime
    alert_level: str  # "none", "low", "medium", "high", "critical"

class LiveMonitoringService:
    """실시간 규정 모니터링 서비스"""
    
    def __init__(self):
        self.rss_feeds = self._build_rss_feeds()
        self.monitoring_keywords = self._build_monitoring_keywords()
        self.update_cache = {}  # 캐시: hs_code -> last_check_time
    
    def _build_rss_feeds(self) -> Dict[str, str]:
        """RSS 피드 URL 정의"""
        return {
            "federal_register": "https://www.federalregister.gov/api/v1/documents.rss",
            "fda_news": "https://www.fda.gov/news-events/press-announcements/rss.xml",
            "usda_news": "https://www.usda.gov/news/rss",
            "epa_news": "https://www.epa.gov/newsreleases/rss",
            "cpsc_news": "https://www.cpsc.gov/Newsroom/RSS",
            "fcc_news": "https://www.fcc.gov/news/rss"
        }
    
    def _build_monitoring_keywords(self) -> Dict[str, List[str]]:
        """HS코드별 모니터링 키워드"""
        return {
            "3304": ["cosmetic", "skincare", "beauty", "serum", "cream", "FDA cosmetic"],
            "3307": ["perfume", "fragrance", "toilet water", "alcohol content"],
            "2106": ["dietary supplement", "ginseng", "health supplement", "DSHEA"],
            "1904": ["rice", "cereal", "prepared food", "instant", "nutritional labeling"],
            "1905": ["snack", "cracker", "cookie", "baker", "FALCPA"],
            "1902": ["pasta", "noodle", "instant", "ramen", "sodium"],
            "2005": ["vegetable", "kimchi", "fermented", "preserved", "HARPC"],
            "8471": ["computer", "electronic", "device", "equipment", "FCC"],
            "8517": ["telephone", "communication", "wireless", "radio", "EMC"],
            "6109": ["clothing", "textile", "garment", "flammability"],
            "9503": ["toy", "children", "play", "game", "safety standards"]
        }
    
    async def monitor_regulation_updates(
        self, 
        hs_code: str, 
        product_name: str,
        check_interval_hours: int = 24
    ) -> MonitoringResult:
        """규정 업데이트 모니터링"""
        
        print(f"🔍 실시간 규정 모니터링 시작 - HS코드: {hs_code}, 상품: {product_name}")
        
        # 마지막 체크 시간 확인
        last_check = self.update_cache.get(hs_code, datetime.now() - timedelta(hours=check_interval_hours))
        
        # 모니터링 키워드 추출
        hs_4digit = hs_code.split('.')[0] if '.' in hs_code else hs_code[:4]
        keywords = self.monitoring_keywords.get(hs_4digit, [])
        
        # 키워드에 상품명 추가
        keywords.extend(product_name.lower().split())
        
        updates_found = []
        
        # 각 RSS 피드에서 업데이트 검색
        for agency, feed_url in self.rss_feeds.items():
            try:
                agency_updates = await self._check_feed_for_updates(
                    feed_url, keywords, last_check, agency
                )
                updates_found.extend(agency_updates)
            except Exception as e:
                print(f"⚠️ {agency} 피드 체크 실패: {e}")
        
        # Federal Register API 직접 호출
        try:
            fr_updates = await self._check_federal_register_api(keywords, last_check)
            updates_found.extend(fr_updates)
        except Exception as e:
            print(f"⚠️ Federal Register API 체크 실패: {e}")
        
        # 업데이트 정렬 및 필터링
        updates_found = self._filter_and_sort_updates(updates_found, hs_code)
        
        # 알림 레벨 결정
        alert_level = self._determine_alert_level(updates_found)
        
        # 다음 체크 시간 계산
        next_check = datetime.now() + timedelta(hours=check_interval_hours)
        
        # 캐시 업데이트
        self.update_cache[hs_code] = datetime.now()
        
        result = MonitoringResult(
            hs_code=hs_code,
            product_name=product_name,
            updates_found=updates_found,
            last_check=datetime.now(),
            next_check_recommended=next_check,
            alert_level=alert_level
        )
        
        print(f"✅ 모니터링 완료 - 업데이트 {len(updates_found)}개 발견, 알림레벨: {alert_level}")
        
        return result
    
    async def _check_feed_for_updates(
        self, 
        feed_url: str, 
        keywords: List[str], 
        last_check: datetime,
        agency: str
    ) -> List[RegulationUpdate]:
        """RSS 피드에서 업데이트 검색"""
        updates = []
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(feed_url, timeout=30) as response:
                    if response.status == 200:
                        content = await response.text()
                        if HAS_FEEDPARSER:
                            feed = feedparser.parse(content)
                        else:
                            print("⚠️ feedparser 패키지가 없어 RSS 피드를 건너뜁니다.")
                            feed = None
                        
                        feed_updates = []
                        if feed and hasattr(feed, 'entries'):
                            for entry in feed.entries:
                                # 발행일 확인 날짜 확인
                                pub_date = self._parse_feed_date(entry.get('published', ''))
                                if pub_date and pub_date > last_check:
                                    # 키워드 매칭 확인
                                    title = entry.get('title', '').lower()
                                    summary = entry.get('summary', '').lower()
                                    
                                    if self._contains_keywords(title + ' ' + summary, keywords):
                                        update = RegulationUpdate(
                                            title=entry.get('title', ''),
                                            agency=agency.upper(),
                                            publication_date=pub_date,
                                            effective_date=None,  # RSS에서는 보통 제공하지 않음
                                            summary=entry.get('summary', ''),
                                            url=entry.get('link', ''),
                                            impact_level=self._assess_impact_level(title, summary),
                                            affected_hs_codes=[],  # 나중에 분석
                                            change_type=self._determine_change_type(title, summary)
                                        )
                                        updates.append(update)
        except Exception as e:
            print(f"RSS 피드 파싱 오류 ({feed_url}): {e}")
        
        return updates
    
    async def _check_federal_register_api(
        self, 
        keywords: List[str], 
        last_check: datetime
    ) -> List[RegulationUpdate]:
        """Federal Register API에서 업데이트 검색"""
        updates = []
        
        try:
            # 최근 7일간의 문서 검색
            start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
            end_date = datetime.now().strftime('%Y-%m-%d')
            
            # 키워드별로 검색
            for keyword in keywords[:5]:  # 상위 5개 키워드만 사용
                api_url = (
                    f"https://www.federalregister.gov/api/v1/documents.json?"
                    f"per_page=20&"
                    f"publication_date[gte]={start_date}&"
                    f"publication_date[lte]={end_date}&"
                    f"q={keyword}"
                )
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(api_url, timeout=30) as response:
                        if response.status == 200:
                            data = await response.json()
                            
                            for doc in data.get('results', []):
                                pub_date = self._parse_api_date(doc.get('publication_date', ''))
                                if pub_date and pub_date > last_check:
                                    update = RegulationUpdate(
                                        title=doc.get('title', ''),
                                        agency=doc.get('agencies', [{}])[0].get('name', 'FEDERAL_REGISTER'),
                                        publication_date=pub_date,
                                        effective_date=self._parse_api_date(doc.get('effective_on', '')),
                                        summary=doc.get('abstract', ''),
                                        url=doc.get('html_url', ''),
                                        impact_level=self._assess_impact_level(
                                            doc.get('title', ''), 
                                            doc.get('abstract', '')
                                        ),
                                        affected_hs_codes=[],  # 나중에 분석
                                        change_type=self._determine_change_type(
                                            doc.get('title', ''), 
                                            doc.get('abstract', '')
                                        )
                                    )
                                    updates.append(update)
        except Exception as e:
            print(f"Federal Register API 오류: {e}")
        
        return updates
    
    def _parse_feed_date(self, date_str: str) -> Optional[datetime]:
        """RSS 피드 날짜 파싱"""
        try:
            # feedparser가 파싱한 시간 사용
            if hasattr(date_str, 'timetuple'):
                return datetime(*date_str.timetuple()[:6])
            return None
        except:
            return None
    
    def _parse_api_date(self, date_str: str) -> Optional[datetime]:
        """API 날짜 파싱"""
        try:
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except:
            return None
    
    def _contains_keywords(self, text: str, keywords: List[str]) -> bool:
        """텍스트에 키워드 포함 여부 확인"""
        text_lower = text.lower()
        return any(keyword.lower() in text_lower for keyword in keywords)
    
    def _assess_impact_level(self, title: str, summary: str) -> str:
        """영향 레벨 평가"""
        text = (title + ' ' + summary).lower()
        
        critical_keywords = ['ban', 'prohibit', 'recall', 'emergency', 'immediate']
        high_keywords = ['restrict', 'limit', 'require', 'mandatory', 'compliance']
        medium_keywords = ['update', 'revise', 'modify', 'clarify', 'guidance']
        
        if any(keyword in text for keyword in critical_keywords):
            return "critical"
        elif any(keyword in text for keyword in high_keywords):
            return "high"
        elif any(keyword in text for keyword in medium_keywords):
            return "medium"
        else:
            return "low"
    
    def _determine_change_type(self, title: str, summary: str) -> str:
        """변경 유형 결정"""
        text = (title + ' ' + summary).lower()
        
        if 'new' in text or 'establish' in text:
            return "new"
        elif 'amend' in text or 'revise' in text or 'update' in text:
            return "amendment"
        elif 'repeal' in text or 'remove' in text or 'eliminate' in text:
            return "repeal"
        elif 'clarify' in text or 'guidance' in text:
            return "clarification"
        else:
            return "amendment"  # 기본값
    
    def _filter_and_sort_updates(
        self, 
        updates: List[RegulationUpdate], 
        hs_code: str
    ) -> List[RegulationUpdate]:
        """업데이트 필터링 및 정렬"""
        # 중복 제거 (URL 기준)
        seen_urls = set()
        unique_updates = []
        for update in updates:
            if update.url not in seen_urls:
                seen_urls.add(update.url)
                unique_updates.append(update)
        
        # 발행일 기준 정렬 (최신순)
        unique_updates.sort(key=lambda x: x.publication_date, reverse=True)
        
        # 최대 10개만 반환
        return unique_updates[:10]
    
    def _determine_alert_level(self, updates: List[RegulationUpdate]) -> str:
        """알림 레벨 결정"""
        if not updates:
            return "none"
        
        # 가장 높은 영향 레벨 확인
        impact_levels = [update.impact_level for update in updates]
        
        if "critical" in impact_levels:
            return "critical"
        elif "high" in impact_levels:
            return "high"
        elif "medium" in impact_levels:
            return "medium"
        else:
            return "low"
    
    def format_monitoring_result(self, result: MonitoringResult) -> Dict[str, Any]:
        """모니터링 결과를 API 응답 형식으로 변환"""
        return {
            "live_updates": {
                "hs_code": result.hs_code,
                "product_name": result.product_name,
                "alert_level": result.alert_level,
                "updates_count": len(result.updates_found),
                "updates": [
                    {
                        "title": update.title,
                        "agency": update.agency,
                        "publication_date": update.publication_date.isoformat(),
                        "effective_date": update.effective_date.isoformat() if update.effective_date else None,
                        "summary": update.summary,
                        "url": update.url,
                        "impact_level": update.impact_level,
                        "change_type": update.change_type
                    }
                    for update in result.updates_found
                ],
                "last_check": result.last_check.isoformat(),
                "next_check_recommended": result.next_check_recommended.isoformat(),
                "status": "completed"
            }
        }
