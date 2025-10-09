"""
환경변수 관리 서비스
API 키 및 설정값들을 중앙에서 관리
"""

import os
from typing import Dict, Optional, Any
from pathlib import Path
try:
    from dotenv import load_dotenv
except ImportError:
    # dotenv가 설치되지 않은 경우 기본 load_dotenv 함수 제공
    def load_dotenv(path=None):
        """기본 환경변수 로딩 (dotenv 없이)"""
        pass
import logging

class EnvManager:
    """환경변수 관리자"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._load_env_file()
        self.api_keys = self._load_api_keys()
        self.settings = self._load_settings()
    
    def _load_env_file(self):
        """환경변수 파일 로드"""
        # ai-engine 디렉토리에서 .env 파일 찾기
        current_dir = Path(__file__).resolve().parent
        ai_engine_dir = current_dir.parent.parent  # ai-engine 디렉토리
        env_path = ai_engine_dir / ".env"
        
        if env_path.exists():
            load_dotenv(env_path)
            self.logger.info(f"✅ 환경변수 파일 로드됨: {env_path}")
        else:
            self.logger.warning(f"⚠️ 환경변수 파일을 찾을 수 없음: {env_path}")
            # 시스템 환경변수에서 로드 시도
            self.logger.info("시스템 환경변수에서 로드 시도")
    
    def _load_api_keys(self) -> Dict[str, Optional[str]]:
        """API 키들 로드"""
        api_keys = {
            'TAVILY_API_KEY': os.getenv('TAVILY_API_KEY'),
            'OPENAI_API_KEY': os.getenv('OPENAI_API_KEY'),
            'API_DATA_GOV': os.getenv('API_DATA_GOV'),
            'USDA_API_KEY': os.getenv('USDA_API_KEY'),
            'HUGGINGFACE_TOKEN': os.getenv('HUGGINGFACE_TOKEN'),
            'ANTHROPIC_API_KEY': os.getenv('ANTHROPIC_API_KEY'),
            'EPA_API_KEY': os.getenv('EPA_API_KEY'),
            'FCC_API_KEY': os.getenv('FCC_API_KEY'),
            'CBP_API_KEY': os.getenv('CBP_API_KEY')
        }
        
        # API 키 상태 로깅
        for key, value in api_keys.items():
            if value:
                self.logger.info(f"✅ {key}: 설정됨")
            else:
                self.logger.warning(f"⚠️ {key}: 설정되지 않음")
        
        return api_keys
    
    def _load_settings(self) -> Dict[str, Any]:
        """기타 설정값들 로드"""
        settings = {
            'SEARCH_PROVIDER': os.getenv('SEARCH_PROVIDER', 'tavily').lower(),
            'DEFAULT_TIMEOUT': int(os.getenv('DEFAULT_TIMEOUT', '30')),
            'MAX_RETRIES': int(os.getenv('MAX_RETRIES', '3')),
            'CACHE_TTL': int(os.getenv('CACHE_TTL', '3600')),
            'DEBUG_MODE': os.getenv('DEBUG_MODE', 'false').lower() == 'true',
            'LOG_LEVEL': os.getenv('LOG_LEVEL', 'INFO'),
            'BACKEND_API_URL': os.getenv('BACKEND_API_URL', 'http://localhost:8081'),
            'AI_ENGINE_URL': os.getenv('AI_ENGINE_URL', 'http://localhost:8000')
        }
        
        self.logger.info(f"⚙️ 설정값 로드됨: {settings}")
        return settings
    
    def get_api_key(self, service: str) -> Optional[str]:
        """특정 서비스의 API 키 조회"""
        key_name = f"{service.upper()}_API_KEY"
        return self.api_keys.get(key_name)
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """설정값 조회"""
        return self.settings.get(key, default)
    
    def is_api_key_available(self, service: str) -> bool:
        """API 키 사용 가능 여부 확인"""
        return self.get_api_key(service) is not None
    
    def get_search_provider_config(self) -> Dict[str, Any]:
        """검색 프로바이더 설정 반환"""
        provider = self.get_setting('SEARCH_PROVIDER', 'tavily')
        
        if provider == 'disabled':
            return {
                'provider': 'disabled',
                'api_key': None,
                'is_available': False
            }
        elif provider == 'tavily':
            api_key = self.get_api_key('TAVILY')
            return {
                'provider': 'tavily',
                'api_key': api_key,
                'is_available': api_key is not None
            }
        else:
            return {
                'provider': 'unknown',
                'api_key': None,
                'is_available': False
            }
    
    def get_api_status_summary(self) -> Dict[str, Any]:
        """API 키 상태 요약 반환"""
        available_keys = sum(1 for key in self.api_keys.values() if key is not None)
        total_keys = len(self.api_keys)
        
        return {
            'total_api_keys': total_keys,
            'available_api_keys': available_keys,
            'availability_rate': available_keys / total_keys if total_keys > 0 else 0,
            'missing_keys': [key for key, value in self.api_keys.items() if value is None],
            'available_keys': [key for key, value in self.api_keys.items() if value is not None],
            'search_provider_status': self.get_search_provider_config()
        }
    
    def validate_required_keys(self, required_services: list) -> Dict[str, bool]:
        """필수 서비스들의 API 키 검증"""
        validation_results = {}
        
        for service in required_services:
            validation_results[service] = self.is_api_key_available(service)
        
        return validation_results
    
    def get_fallback_config(self) -> Dict[str, Any]:
        """폴백 설정 반환 (API 키가 없을 때)"""
        return {
            'use_mock_data': True,
            'mock_data_quality': 'basic',
            'fallback_providers': ['heuristic', 'static_mapping'],
            'warnings_enabled': True
        }

# 전역 인스턴스
env_manager = EnvManager()
