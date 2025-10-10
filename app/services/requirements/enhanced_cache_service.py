"""
향상된 캐싱 시스템
다층 캐싱, TTL 관리, 캐시 무효화, 성능 메트릭 등을 포함
"""

import asyncio
import json
import hashlib
import pickle
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
import aiofiles
import logging
from collections import OrderedDict
import time

@dataclass
class CacheEntry:
    """캐시 엔트리"""
    key: str
    value: Any
    created_at: datetime
    expires_at: datetime
    access_count: int = 0
    last_accessed: datetime = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.last_accessed is None:
            self.last_accessed = self.created_at
        if self.metadata is None:
            self.metadata = {}

class EnhancedCacheService:
    """향상된 캐싱 서비스"""
    
    def __init__(
        self,
        memory_cache_size: int = 1000,
        disk_cache_dir: str = "cache",
        default_ttl: int = 3600,  # 1시간
        backend_api_url: str = "http://localhost:8081"
    ):
        self.logger = logging.getLogger(__name__)
        
        # 캐시 설정
        self.memory_cache_size = memory_cache_size
        self.disk_cache_dir = Path(disk_cache_dir)
        self.default_ttl = default_ttl
        self.backend_api_url = backend_api_url
        
        # 다층 캐시
        self.memory_cache: OrderedDict = OrderedDict()
        self.disk_cache_dir.mkdir(exist_ok=True)
        
        # 성능 메트릭
        self.metrics = {
            'hits': 0,
            'misses': 0,
            'memory_hits': 0,
            'disk_hits': 0,
            'backend_hits': 0,
            'evictions': 0,
            'total_requests': 0
        }
        
        # 캐시 무효화 패턴
        self.invalidation_patterns = set()
        
        self.logger.info(f"✅ 향상된 캐싱 서비스 초기화 완료")
        self.logger.info(f"   메모리 캐시 크기: {memory_cache_size}")
        self.logger.info(f"   디스크 캐시 디렉토리: {disk_cache_dir}")
        self.logger.info(f"   기본 TTL: {default_ttl}초")
    
    def _generate_cache_key(self, *args, **kwargs) -> str:
        """캐시 키 생성"""
        key_data = {'args': args, 'kwargs': sorted(kwargs.items())}
        key_str = json.dumps(key_data, sort_keys=True, default=str)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    async def get(
        self,
        key: str,
        default: Any = None,
        update_access: bool = True
    ) -> Any:
        """캐시에서 값 조회"""
        self.metrics['total_requests'] += 1
        
        try:
            # 1. 메모리 캐시 확인
            if key in self.memory_cache:
                entry = self.memory_cache[key]
                if datetime.now() < entry.expires_at:
                    if update_access:
                        entry.access_count += 1
                        entry.last_accessed = datetime.now()
                        # LRU 업데이트
                        self.memory_cache.move_to_end(key)
                    self.metrics['hits'] += 1
                    self.metrics['memory_hits'] += 1
                    self.logger.debug(f"✅ 메모리 캐시 히트: {key}")
                    return entry.value
                else:
                    # 만료된 캐시 제거
                    del self.memory_cache[key]
                    self.metrics['evictions'] += 1
            
            # 2. 디스크 캐시 확인
            disk_value = await self._get_from_disk(key)
            if disk_value is not None:
                if update_access:
                    # 메모리 캐시에 다시 로드
                    await self.set(key, disk_value, ttl=self.default_ttl)
                self.metrics['hits'] += 1
                self.metrics['disk_hits'] += 1
                self.logger.debug(f"✅ 디스크 캐시 히트: {key}")
                return disk_value
            
            # 3. 백엔드 캐시 확인
            backend_value = await self._get_from_backend(key)
            if backend_value is not None:
                if update_access:
                    # 로컬 캐시에 저장
                    await self.set(key, backend_value, ttl=self.default_ttl)
                self.metrics['hits'] += 1
                self.metrics['backend_hits'] += 1
                self.logger.debug(f"✅ 백엔드 캐시 히트: {key}")
                return backend_value
            
            # 캐시 미스
            self.metrics['misses'] += 1
            self.logger.debug(f"❌ 캐시 미스: {key}")
            return default
            
        except Exception as e:
            self.logger.error(f"❌ 캐시 조회 실패: {key}, 에러: {e}")
            self.metrics['misses'] += 1
            return default
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: int = None,
        metadata: Dict[str, Any] = None
    ) -> bool:
        """캐시에 값 저장"""
        try:
            ttl = ttl or self.default_ttl
            now = datetime.now()
            
            entry = CacheEntry(
                key=key,
                value=value,
                created_at=now,
                expires_at=now + timedelta(seconds=ttl),
                metadata=metadata or {}
            )
            
            # 메모리 캐시에 저장
            await self._set_to_memory(key, entry)
            
            # 디스크 캐시에 저장 (중요한 데이터만)
            if self._should_save_to_disk(entry):
                await self._set_to_disk(key, entry)
            
            self.logger.debug(f"✅ 캐시 저장 완료: {key}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 캐시 저장 실패: {key}, 에러: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """캐시에서 값 삭제"""
        try:
            # 메모리 캐시에서 삭제
            if key in self.memory_cache:
                del self.memory_cache[key]
            
            # 디스크 캐시에서 삭제
            await self._delete_from_disk(key)
            
            # 백엔드 캐시에서 삭제
            await self._delete_from_backend(key)
            
            self.logger.debug(f"✅ 캐시 삭제 완료: {key}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 캐시 삭제 실패: {key}, 에러: {e}")
            return False
    
    async def invalidate_pattern(self, pattern: str) -> int:
        """패턴에 맞는 캐시 무효화"""
        invalidated_count = 0
        
        try:
            # 메모리 캐시에서 패턴 매칭 삭제
            keys_to_delete = []
            for key in self.memory_cache.keys():
                if pattern in key:
                    keys_to_delete.append(key)
            
            for key in keys_to_delete:
                del self.memory_cache[key]
                invalidated_count += 1
            
            # 디스크 캐시에서 패턴 매칭 삭제
            disk_invalidated = await self._invalidate_disk_pattern(pattern)
            invalidated_count += disk_invalidated
            
            self.logger.info(f"✅ 패턴 무효화 완료: {pattern}, {invalidated_count}개 삭제")
            return invalidated_count
            
        except Exception as e:
            self.logger.error(f"❌ 패턴 무효화 실패: {pattern}, 에러: {e}")
            return 0
    
    async def clear(self) -> bool:
        """모든 캐시 클리어"""
        try:
            # 메모리 캐시 클리어
            self.memory_cache.clear()
            
            # 디스크 캐시 클리어
            for cache_file in self.disk_cache_dir.glob("*.cache"):
                cache_file.unlink()
            
            # 백엔드 캐시 클리어
            await self._clear_backend_cache()
            
            self.logger.info("✅ 모든 캐시 클리어 완료")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 캐시 클리어 실패: {e}")
            return False
    
    async def cleanup_expired(self) -> int:
        """만료된 캐시 정리"""
        cleaned_count = 0
        now = datetime.now()
        
        try:
            # 메모리 캐시 정리
            keys_to_delete = []
            for key, entry in self.memory_cache.items():
                if now >= entry.expires_at:
                    keys_to_delete.append(key)
            
            for key in keys_to_delete:
                del self.memory_cache[key]
                cleaned_count += 1
            
            # 디스크 캐시 정리
            disk_cleaned = await self._cleanup_disk_expired()
            cleaned_count += disk_cleaned
            
            self.logger.info(f"✅ 만료된 캐시 정리 완료: {cleaned_count}개")
            return cleaned_count
            
        except Exception as e:
            self.logger.error(f"❌ 캐시 정리 실패: {e}")
            return 0
    
    def get_metrics(self) -> Dict[str, Any]:
        """캐시 성능 메트릭 반환"""
        total_requests = self.metrics['total_requests']
        hit_rate = (self.metrics['hits'] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'hit_rate': round(hit_rate, 2),
            'total_requests': total_requests,
            'hits': self.metrics['hits'],
            'misses': self.metrics['misses'],
            'memory_hits': self.metrics['memory_hits'],
            'disk_hits': self.metrics['disk_hits'],
            'backend_hits': self.metrics['backend_hits'],
            'evictions': self.metrics['evictions'],
            'memory_cache_size': len(self.memory_cache),
            'memory_cache_limit': self.memory_cache_size,
            'disk_cache_files': len(list(self.disk_cache_dir.glob("*.cache"))),
            'timestamp': datetime.now().isoformat()
        }
    
    # 내부 메서드들
    
    async def _set_to_memory(self, key: str, entry: CacheEntry):
        """메모리 캐시에 저장"""
        # LRU 캐시 크기 관리
        while len(self.memory_cache) >= self.memory_cache_size:
            # 가장 오래된 항목 제거
            oldest_key, oldest_entry = self.memory_cache.popitem(last=False)
            self.metrics['evictions'] += 1
            self.logger.debug(f"🗑️ 메모리 캐시 eviction: {oldest_key}")
        
        self.memory_cache[key] = entry
    
    async def _get_from_disk(self, key: str) -> Any:
        """디스크 캐시에서 조회"""
        try:
            cache_file = self.disk_cache_dir / f"{key}.cache"
            if not cache_file.exists():
                return None
            
            async with aiofiles.open(cache_file, 'rb') as f:
                data = await f.read()
                entry = pickle.loads(data)
                
                # 만료 확인
                if datetime.now() >= entry.expires_at:
                    cache_file.unlink()
                    return None
                
                return entry.value
                
        except Exception as e:
            self.logger.warning(f"⚠️ 디스크 캐시 조회 실패: {key}, 에러: {e}")
            return None
    
    async def _set_to_disk(self, key: str, entry: CacheEntry):
        """디스크 캐시에 저장"""
        try:
            cache_file = self.disk_cache_dir / f"{key}.cache"
            async with aiofiles.open(cache_file, 'wb') as f:
                data = pickle.dumps(entry)
                await f.write(data)
        except Exception as e:
            self.logger.warning(f"⚠️ 디스크 캐시 저장 실패: {key}, 에러: {e}")
    
    async def _delete_from_disk(self, key: str):
        """디스크 캐시에서 삭제"""
        try:
            cache_file = self.disk_cache_dir / f"{key}.cache"
            if cache_file.exists():
                cache_file.unlink()
        except Exception as e:
            self.logger.warning(f"⚠️ 디스크 캐시 삭제 실패: {key}, 에러: {e}")
    
    async def _get_from_backend(self, key: str) -> Any:
        """백엔드 캐시에서 조회"""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                url = f"{self.backend_api_url}/api/cache/{key}"
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get('value')
                    return None
        except Exception as e:
            self.logger.debug(f"⚠️ 백엔드 캐시 조회 실패: {key}, 에러: {e}")
            return None
    
    async def _delete_from_backend(self, key: str):
        """백엔드 캐시에서 삭제"""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                url = f"{self.backend_api_url}/api/cache/{key}"
                async with session.delete(url) as response:
                    return response.status == 200
        except Exception as e:
            self.logger.debug(f"⚠️ 백엔드 캐시 삭제 실패: {key}, 에러: {e}")
            return False
    
    async def _clear_backend_cache(self):
        """백엔드 캐시 클리어"""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                url = f"{self.backend_api_url}/api/cache/clear"
                async with session.delete(url) as response:
                    return response.status == 200
        except Exception as e:
            self.logger.debug(f"⚠️ 백엔드 캐시 클리어 실패: {e}")
            return False
    
    def _should_save_to_disk(self, entry: CacheEntry) -> bool:
        """디스크에 저장할지 판단"""
        # 메타데이터에 disk_save 플래그가 있으면 저장
        if entry.metadata.get('disk_save', False):
            return True
        
        # 큰 데이터는 디스크에 저장
        try:
            size = len(pickle.dumps(entry.value))
            return size > 1024 * 1024  # 1MB 이상
        except:
            return False
    
    async def _invalidate_disk_pattern(self, pattern: str) -> int:
        """디스크 캐시에서 패턴 무효화"""
        invalidated_count = 0
        try:
            for cache_file in self.disk_cache_dir.glob("*.cache"):
                if pattern in cache_file.stem:
                    cache_file.unlink()
                    invalidated_count += 1
        except Exception as e:
            self.logger.warning(f"⚠️ 디스크 패턴 무효화 실패: {pattern}, 에러: {e}")
        return invalidated_count
    
    async def _cleanup_disk_expired(self) -> int:
        """디스크 캐시에서 만료된 항목 정리"""
        cleaned_count = 0
        now = datetime.now()
        
        try:
            for cache_file in self.disk_cache_dir.glob("*.cache"):
                try:
                    async with aiofiles.open(cache_file, 'rb') as f:
                        data = await f.read()
                        entry = pickle.loads(data)
                        
                        if now >= entry.expires_at:
                            cache_file.unlink()
                            cleaned_count += 1
                except Exception:
                    # 손상된 파일 삭제
                    cache_file.unlink()
                    cleaned_count += 1
        except Exception as e:
            self.logger.warning(f"⚠️ 디스크 캐시 정리 실패: {e}")
        
        return cleaned_count

# 전역 캐시 서비스 인스턴스
enhanced_cache = EnhancedCacheService()
