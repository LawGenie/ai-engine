"""
에러 처리 및 복구 서비스
워크플로우 단계별 에러 처리 및 폴백 메커니즘
"""

import asyncio
import logging
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime
from enum import Enum
import traceback

class ErrorSeverity(Enum):
    """에러 심각도"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class ErrorRecoveryStrategy(Enum):
    """에러 복구 전략"""
    IGNORE = "ignore"
    RETRY = "retry"
    FALLBACK = "fallback"
    SKIP = "skip"
    FAIL = "fail"

class WorkflowError(Exception):
    """워크플로우 에러"""
    def __init__(self, message: str, severity: ErrorSeverity = ErrorSeverity.MEDIUM, 
                 recovery_strategy: ErrorRecoveryStrategy = ErrorRecoveryStrategy.FALLBACK,
                 context: Dict[str, Any] = None):
        super().__init__(message)
        self.severity = severity
        self.recovery_strategy = recovery_strategy
        self.context = context or {}
        self.timestamp = datetime.now()

class ErrorHandler:
    """에러 처리기"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.error_history: List[Dict[str, Any]] = []
        self.retry_config = {
            'max_retries': 3,
            'retry_delay': 1.0,
            'backoff_factor': 2.0
        }
    
    def handle_error(self, error: Exception, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """에러 처리 메인 메서드"""
        error_info = {
            'error_type': type(error).__name__,
            'error_message': str(error),
            'timestamp': datetime.now().isoformat(),
            'context': context or {},
            'severity': ErrorSeverity.MEDIUM.value,
            'recovery_strategy': ErrorRecoveryStrategy.FALLBACK.value,
            'traceback': traceback.format_exc()
        }
        
        # 에러 타입별 처리
        if isinstance(error, WorkflowError):
            error_info['severity'] = error.severity.value
            error_info['recovery_strategy'] = error.recovery_strategy.value
            error_info['context'].update(error.context)
        
        # 에러 로깅
        self._log_error(error_info)
        
        # 에러 히스토리에 추가
        self.error_history.append(error_info)
        
        # 복구 전략 실행
        return self._execute_recovery_strategy(error_info)
    
    def _log_error(self, error_info: Dict[str, Any]):
        """에러 로깅"""
        severity = error_info['severity']
        message = f"❌ {error_info['error_type']}: {error_info['error_message']}"
        
        if severity == ErrorSeverity.CRITICAL.value:
            self.logger.critical(message)
        elif severity == ErrorSeverity.HIGH.value:
            self.logger.error(message)
        elif severity == ErrorSeverity.MEDIUM.value:
            self.logger.warning(message)
        else:
            self.logger.info(message)
    
    def _execute_recovery_strategy(self, error_info: Dict[str, Any]) -> Dict[str, Any]:
        """복구 전략 실행"""
        strategy = error_info['recovery_strategy']
        
        if strategy == ErrorRecoveryStrategy.IGNORE.value:
            return self._handle_ignore(error_info)
        elif strategy == ErrorRecoveryStrategy.RETRY.value:
            return self._handle_retry(error_info)
        elif strategy == ErrorRecoveryStrategy.FALLBACK.value:
            return self._handle_fallback(error_info)
        elif strategy == ErrorRecoveryStrategy.SKIP.value:
            return self._handle_skip(error_info)
        elif strategy == ErrorRecoveryStrategy.FAIL.value:
            return self._handle_fail(error_info)
        else:
            return self._handle_fallback(error_info)  # 기본값
    
    def _handle_ignore(self, error_info: Dict[str, Any]) -> Dict[str, Any]:
        """에러 무시"""
        return {
            'status': 'ignored',
            'error_handled': True,
            'continue_workflow': True,
            'message': '에러가 무시되었습니다'
        }
    
    def _handle_retry(self, error_info: Dict[str, Any]) -> Dict[str, Any]:
        """재시도"""
        return {
            'status': 'retry_required',
            'error_handled': True,
            'continue_workflow': False,
            'retry_count': error_info.get('retry_count', 0) + 1,
            'message': '재시도가 필요합니다'
        }
    
    def _handle_fallback(self, error_info: Dict[str, Any]) -> Dict[str, Any]:
        """폴백 처리"""
        return {
            'status': 'fallback',
            'error_handled': True,
            'continue_workflow': True,
            'fallback_data': self._get_fallback_data(error_info),
            'message': '폴백 데이터로 처리되었습니다'
        }
    
    def _handle_skip(self, error_info: Dict[str, Any]) -> Dict[str, Any]:
        """단계 건너뛰기"""
        return {
            'status': 'skipped',
            'error_handled': True,
            'continue_workflow': True,
            'message': '단계가 건너뛰어졌습니다'
        }
    
    def _handle_fail(self, error_info: Dict[str, Any]) -> Dict[str, Any]:
        """워크플로우 실패"""
        return {
            'status': 'failed',
            'error_handled': True,
            'continue_workflow': False,
            'message': '워크플로우가 실패했습니다'
        }
    
    def _get_fallback_data(self, error_info: Dict[str, Any]) -> Dict[str, Any]:
        """폴백 데이터 생성"""
        context = error_info.get('context', {})
        
        # 컨텍스트에 따라 다른 폴백 데이터 제공
        if 'step' in context:
            step = context['step']
            
            if step == 'keyword_extraction':
                return {
                    'keywords': ['default', 'fallback'],
                    'confidence': 0.1,
                    'method': 'fallback'
                }
            elif step == 'search':
                return {
                    'results': [],
                    'total_count': 0,
                    'source': 'fallback',
                    'message': '검색 실패 - 기본 정보 제공'
                }
            elif step == 'scraping':
                return {
                    'certifications': [],
                    'documents': [],
                    'sources': [],
                    'status': 'fallback'
                }
            elif step == 'llm_summary':
                return {
                    'critical_requirements': ['기본 요구사항 확인 필요'],
                    'required_documents': ['기본 서류 확인 필요'],
                    'confidence_score': 0.1
                }
        
        # 기본 폴백 데이터
        return {
            'status': 'fallback',
            'message': '기본 데이터로 처리됨',
            'confidence': 0.1
        }
    
    async def retry_with_backoff(self, func: Callable, *args, **kwargs) -> Any:
        """백오프를 사용한 재시도"""
        last_exception = None
        
        for attempt in range(self.retry_config['max_retries']):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                
                if attempt < self.retry_config['max_retries'] - 1:
                    delay = self.retry_config['retry_delay'] * (self.retry_config['backoff_factor'] ** attempt)
                    self.logger.warning(f"재시도 {attempt + 1}/{self.retry_config['max_retries']} - {delay}초 후 재시도")
                    await asyncio.sleep(delay)
                else:
                    self.logger.error(f"최대 재시도 횟수 초과: {str(e)}")
        
        raise last_exception
    
    def get_error_summary(self) -> Dict[str, Any]:
        """에러 요약 정보"""
        if not self.error_history:
            return {
                'total_errors': 0,
                'error_types': {},
                'severity_distribution': {},
                'recovery_strategies': {}
            }
        
        error_types = {}
        severity_dist = {}
        recovery_strategies = {}
        
        for error in self.error_history:
            # 에러 타입별 카운트
            error_type = error['error_type']
            error_types[error_type] = error_types.get(error_type, 0) + 1
            
            # 심각도별 분포
            severity = error['severity']
            severity_dist[severity] = severity_dist.get(severity, 0) + 1
            
            # 복구 전략별 분포
            strategy = error['recovery_strategy']
            recovery_strategies[strategy] = recovery_strategies.get(strategy, 0) + 1
        
        return {
            'total_errors': len(self.error_history),
            'error_types': error_types,
            'severity_distribution': severity_dist,
            'recovery_strategies': recovery_strategies,
            'last_error': self.error_history[-1] if self.error_history else None
        }
    
    def clear_error_history(self):
        """에러 히스토리 초기화"""
        self.error_history.clear()
        self.logger.info("에러 히스토리가 초기화되었습니다")

# 전역 에러 핸들러 인스턴스
error_handler = ErrorHandler()
