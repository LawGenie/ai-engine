"""
병렬 처리 최적화 서비스
비동기 병렬 처리, 배치 처리, 리소스 관리 등을 포함
"""

import asyncio
import time
from typing import Dict, List, Any, Optional, Callable, Union, Tuple
from dataclasses import dataclass
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import logging
from enum import Enum

class ProcessingMode(Enum):
    """처리 모드"""
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    BATCH = "batch"
    STREAM = "stream"

@dataclass
class ProcessingTask:
    """처리 작업"""
    id: str
    func: Callable
    args: tuple = ()
    kwargs: dict = None
    priority: int = 0
    timeout: float = None
    retry_count: int = 0
    max_retries: int = 3
    
    def __post_init__(self):
        if self.kwargs is None:
            self.kwargs = {}

@dataclass
class ProcessingResult:
    """처리 결과"""
    task_id: str
    success: bool
    result: Any = None
    error: str = None
    processing_time: float = 0
    retry_count: int = 0

class ParallelProcessor:
    """병렬 처리기"""
    
    def __init__(
        self,
        max_workers: int = 10,
        max_concurrent_tasks: int = 20,
        default_timeout: float = 30.0,
        enable_metrics: bool = True
    ):
        self.logger = logging.getLogger(__name__)
        
        # 처리 설정
        self.max_workers = max_workers
        self.max_concurrent_tasks = max_concurrent_tasks
        self.default_timeout = default_timeout
        self.enable_metrics = enable_metrics
        
        # 실행기들
        self.thread_executor = ThreadPoolExecutor(max_workers=max_workers)
        self.process_executor = ProcessPoolExecutor(max_workers=max_workers)
        
        # 동시성 제어
        self.semaphore = asyncio.Semaphore(max_concurrent_tasks)
        
        # 메트릭
        self.metrics = {
            'total_tasks': 0,
            'completed_tasks': 0,
            'failed_tasks': 0,
            'total_processing_time': 0.0,
            'average_processing_time': 0.0,
            'concurrent_peak': 0,
            'current_concurrent': 0
        }
        
        # 작업 큐
        self.task_queue = asyncio.Queue()
        self.results = {}
        
        self.logger.info(f"✅ 병렬 처리기 초기화 완료")
        self.logger.info(f"   최대 워커: {max_workers}")
        self.logger.info(f"   최대 동시 작업: {max_concurrent_tasks}")
        self.logger.info(f"   기본 타임아웃: {default_timeout}초")
    
    async def process_parallel(
        self,
        tasks: List[ProcessingTask],
        mode: ProcessingMode = ProcessingMode.PARALLEL,
        timeout: float = None
    ) -> List[ProcessingResult]:
        """병렬 처리 실행"""
        
        timeout = timeout or self.default_timeout
        self.logger.info(f"🚀 병렬 처리 시작 - 모드: {mode.value}, 작업 수: {len(tasks)}")
        
        start_time = time.time()
        
        try:
            if mode == ProcessingMode.SEQUENTIAL:
                results = await self._process_sequential(tasks, timeout)
            elif mode == ProcessingMode.PARALLEL:
                results = await self._process_parallel(tasks, timeout)
            elif mode == ProcessingMode.BATCH:
                results = await self._process_batch(tasks, timeout)
            elif mode == ProcessingMode.STREAM:
                results = await self._process_stream(tasks, timeout)
            else:
                raise ValueError(f"지원하지 않는 처리 모드: {mode}")
            
            # 메트릭 업데이트
            processing_time = time.time() - start_time
            self._update_metrics(results, processing_time)
            
            self.logger.info(f"✅ 병렬 처리 완료 - 소요시간: {processing_time:.2f}초")
            return results
            
        except Exception as e:
            self.logger.error(f"❌ 병렬 처리 실패: {e}")
            raise
    
    async def _process_sequential(self, tasks: List[ProcessingTask], timeout: float) -> List[ProcessingResult]:
        """순차 처리"""
        results = []
        
        for task in tasks:
            try:
                result = await self._execute_task(task, timeout)
                results.append(result)
            except Exception as e:
                self.logger.error(f"❌ 작업 실패: {task.id}, 에러: {e}")
                results.append(ProcessingResult(
                    task_id=task.id,
                    success=False,
                    error=str(e)
                ))
        
        return results
    
    async def _process_parallel(self, tasks: List[ProcessingTask], timeout: float) -> List[ProcessingResult]:
        """병렬 처리"""
        # 모든 작업을 동시에 실행
        coroutines = []
        for task in tasks:
            coro = self._execute_task_with_semaphore(task, timeout)
            coroutines.append(coro)
        
        # 모든 작업 완료 대기
        results = await asyncio.gather(*coroutines, return_exceptions=True)
        
        # 예외 처리
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(ProcessingResult(
                    task_id=tasks[i].id,
                    success=False,
                    error=str(result)
                ))
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def _process_batch(self, tasks: List[ProcessingTask], timeout: float) -> List[ProcessingResult]:
        """배치 처리"""
        batch_size = min(len(tasks), self.max_concurrent_tasks)
        results = []
        
        for i in range(0, len(tasks), batch_size):
            batch = tasks[i:i + batch_size]
            batch_results = await self._process_parallel(batch, timeout)
            results.extend(batch_results)
            
            # 배치 간 짧은 대기 (리소스 부하 방지)
            if i + batch_size < len(tasks):
                await asyncio.sleep(0.1)
        
        return results
    
    async def _process_stream(self, tasks: List[ProcessingTask], timeout: float) -> List[ProcessingResult]:
        """스트림 처리 (결과를 실시간으로 반환)"""
        results = []
        
        # 모든 작업을 동시에 시작하되, 완료되는 대로 결과 수집
        pending_tasks = {}
        
        for task in tasks:
            future = asyncio.create_task(
                self._execute_task_with_semaphore(task, timeout)
            )
            pending_tasks[future] = task
        
        # 완료되는 대로 결과 처리
        while pending_tasks:
            done, pending = await asyncio.wait(
                pending_tasks.keys(),
                return_when=asyncio.FIRST_COMPLETED
            )
            
            for future in done:
                task = pending_tasks[future]
                try:
                    result = await future
                    results.append(result)
                except Exception as e:
                    results.append(ProcessingResult(
                        task_id=task.id,
                        success=False,
                        error=str(e)
                    ))
                
                del pending_tasks[future]
        
        return results
    
    async def _execute_task_with_semaphore(self, task: ProcessingTask, timeout: float) -> ProcessingResult:
        """세마포어를 사용한 작업 실행"""
        async with self.semaphore:
            return await self._execute_task(task, timeout)
    
    async def _execute_task(self, task: ProcessingTask, timeout: float) -> ProcessingResult:
        """작업 실행"""
        start_time = time.time()
        task_id = task.id
        
        self.logger.debug(f"🔄 작업 시작: {task_id}")
        
        try:
            # 타임아웃 설정
            task_timeout = task.timeout or timeout
            
            # 함수 실행
            if asyncio.iscoroutinefunction(task.func):
                # 비동기 함수
                result = await asyncio.wait_for(
                    task.func(*task.args, **task.kwargs),
                    timeout=task_timeout
                )
            else:
                # 동기 함수 (스레드풀에서 실행)
                result = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(
                        self.thread_executor,
                        lambda: task.func(*task.args, **task.kwargs)
                    ),
                    timeout=task_timeout
                )
            
            processing_time = time.time() - start_time
            
            self.logger.debug(f"✅ 작업 완료: {task_id}, 소요시간: {processing_time:.2f}초")
            
            return ProcessingResult(
                task_id=task_id,
                success=True,
                result=result,
                processing_time=processing_time,
                retry_count=task.retry_count
            )
            
        except asyncio.TimeoutError:
            processing_time = time.time() - start_time
            error_msg = f"작업 타임아웃: {task_id} ({task_timeout}초 초과)"
            
            self.logger.warning(f"⏰ {error_msg}")
            
            return ProcessingResult(
                task_id=task_id,
                success=False,
                error=error_msg,
                processing_time=processing_time,
                retry_count=task.retry_count
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = f"작업 실행 실패: {task_id}, 에러: {str(e)}"
            
            self.logger.error(f"❌ {error_msg}")
            
            return ProcessingResult(
                task_id=task_id,
                success=False,
                error=error_msg,
                processing_time=processing_time,
                retry_count=task.retry_count
            )
    
    async def process_with_retry(
        self,
        tasks: List[ProcessingTask],
        max_retries: int = 3,
        retry_delay: float = 1.0,
        backoff_factor: float = 2.0
    ) -> List[ProcessingResult]:
        """재시도가 포함된 처리"""
        
        self.logger.info(f"🔄 재시도 처리 시작 - 최대 재시도: {max_retries}")
        
        all_results = []
        retry_tasks = []
        
        # 첫 번째 시도
        results = await self.process_parallel(tasks)
        
        for result in results:
            if result.success:
                all_results.append(result)
            else:
                # 실패한 작업을 재시도 큐에 추가
                task = next((t for t in tasks if t.id == result.task_id), None)
                if task and task.retry_count < max_retries:
                    task.retry_count += 1
                    retry_tasks.append(task)
        
        # 재시도 실행
        current_delay = retry_delay
        for attempt in range(max_retries):
            if not retry_tasks:
                break
            
            self.logger.info(f"🔄 재시도 {attempt + 1}/{max_retries} - {len(retry_tasks)}개 작업")
            
            # 재시도 전 대기
            if attempt > 0:
                await asyncio.sleep(current_delay)
                current_delay *= backoff_factor
            
            # 재시도 실행
            retry_results = await self.process_parallel(retry_tasks)
            
            # 재시도 큐 업데이트
            next_retry_tasks = []
            for result in retry_results:
                if result.success:
                    all_results.append(result)
                else:
                    task = next((t for t in retry_tasks if t.id == result.task_id), None)
                    if task and task.retry_count < max_retries:
                        task.retry_count += 1
                        next_retry_tasks.append(task)
            
            retry_tasks = next_retry_tasks
        
        # 최종 실패한 작업들 추가
        for task in retry_tasks:
            all_results.append(ProcessingResult(
                task_id=task.id,
                success=False,
                error=f"최대 재시도 횟수 초과: {max_retries}",
                retry_count=task.retry_count
            ))
        
        self.logger.info(f"✅ 재시도 처리 완료 - 성공: {len([r for r in all_results if r.success])}/{len(all_results)}")
        
        return all_results
    
    def _update_metrics(self, results: List[ProcessingResult], total_time: float):
        """메트릭 업데이트"""
        if not self.enable_metrics:
            return
        
        self.metrics['total_tasks'] += len(results)
        self.metrics['completed_tasks'] += len([r for r in results if r.success])
        self.metrics['failed_tasks'] += len([r for r in results if not r.success])
        self.metrics['total_processing_time'] += total_time
        
        if self.metrics['total_tasks'] > 0:
            self.metrics['average_processing_time'] = (
                self.metrics['total_processing_time'] / self.metrics['total_tasks']
            )
        
        # 동시성 메트릭
        current_concurrent = len([r for r in results if r.success])
        self.metrics['current_concurrent'] = current_concurrent
        if current_concurrent > self.metrics['concurrent_peak']:
            self.metrics['concurrent_peak'] = current_concurrent
    
    def get_metrics(self) -> Dict[str, Any]:
        """메트릭 반환"""
        if not self.enable_metrics:
            return {}
        
        return {
            'total_tasks': self.metrics['total_tasks'],
            'completed_tasks': self.metrics['completed_tasks'],
            'failed_tasks': self.metrics['failed_tasks'],
            'success_rate': (
                self.metrics['completed_tasks'] / self.metrics['total_tasks'] * 100
                if self.metrics['total_tasks'] > 0 else 0
            ),
            'average_processing_time': round(self.metrics['average_processing_time'], 3),
            'total_processing_time': round(self.metrics['total_processing_time'], 3),
            'concurrent_peak': self.metrics['concurrent_peak'],
            'current_concurrent': self.metrics['current_concurrent'],
            'max_workers': self.max_workers,
            'max_concurrent_tasks': self.max_concurrent_tasks,
            'timestamp': datetime.now().isoformat()
        }
    
    async def cleanup(self):
        """리소스 정리"""
        self.logger.info("🧹 병렬 처리기 리소스 정리 시작")
        
        # 실행기 종료
        self.thread_executor.shutdown(wait=True)
        self.process_executor.shutdown(wait=True)
        
        self.logger.info("✅ 병렬 처리기 리소스 정리 완료")

# 전역 병렬 처리기 인스턴스
parallel_processor = ParallelProcessor()
