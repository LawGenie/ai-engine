"""
개선사항 테스트 스크립트
누락된 모듈, 환경변수 관리, 에러 처리, 캐싱, 병렬 처리 등을 테스트
"""

import asyncio
import os
import sys
from datetime import datetime

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

async def test_improvements():
    """개선사항 테스트"""
    print("🧪 요건 파트 개선사항 테스트 시작")
    print("=" * 60)
    
    try:
        # 1. 환경변수 관리 테스트
        print("\n1️⃣ 환경변수 관리 테스트")
        from app.services.requirements.env_manager import env_manager
        
        api_status = env_manager.get_api_status_summary()
        print(f"✅ 환경변수 관리자 초기화 완료")
        print(f"   사용 가능한 API 키: {api_status['available_api_keys']}/{api_status['total_api_keys']}")
        
        # 2. 에러 처리 테스트
        print("\n2️⃣ 에러 처리 테스트")
        from app.services.requirements.error_handler import error_handler, WorkflowError, ErrorSeverity
        
        # 테스트 에러 생성
        test_error = WorkflowError("테스트 에러", ErrorSeverity.MEDIUM)
        error_result = error_handler.handle_error(test_error, {'test': True})
        print(f"✅ 에러 처리 테스트 완료: {error_result['status']}")
        
        # 3. Data.gov API 서비스 테스트
        print("\n3️⃣ Data.gov API 서비스 테스트")
        from app.services.requirements.data_gov_api import DataGovAPIService
        
        data_gov_service = DataGovAPIService()
        print(f"✅ Data.gov API 서비스 초기화 완료")
        
        # 4. 향상된 캐싱 서비스 테스트
        print("\n4️⃣ 향상된 캐싱 서비스 테스트")
        from app.services.requirements.enhanced_cache_service import enhanced_cache
        
        # 캐시 테스트
        test_key = "test_key"
        test_value = {"test": "data", "timestamp": datetime.now().isoformat()}
        
        await enhanced_cache.set(test_key, test_value, ttl=60)
        cached_value = await enhanced_cache.get(test_key)
        
        if cached_value == test_value:
            print(f"✅ 캐싱 서비스 테스트 성공")
        else:
            print(f"❌ 캐싱 서비스 테스트 실패")
        
        # 5. 병렬 처리 테스트
        print("\n5️⃣ 병렬 처리 테스트")
        from app.services.requirements.parallel_processor import parallel_processor, ProcessingTask, ProcessingMode
        
        # 간단한 테스트 작업들
        async def test_task(task_id: str, delay: float = 0.1):
            await asyncio.sleep(delay)
            return f"Task {task_id} completed"
        
        tasks = [
            ProcessingTask(id=f"task_{i}", func=test_task, args=(f"task_{i}", 0.1))
            for i in range(5)
        ]
        
        results = await parallel_processor.process_parallel(tasks, ProcessingMode.PARALLEL)
        successful_tasks = len([r for r in results if r.success])
        
        print(f"✅ 병렬 처리 테스트 완료: {successful_tasks}/{len(tasks)}개 작업 성공")
        
        # 6. 통합 워크플로우 테스트
        print("\n6️⃣ 통합 워크플로우 테스트")
        from workflows.unified_workflow import unified_workflow
        
        workflow_status = unified_workflow.get_workflow_status()
        print(f"✅ 통합 워크플로우 초기화 완료")
        print(f"   워크플로우 타입: {workflow_status['workflow_type']}")
        print(f"   노드 수: {workflow_status['nodes_count']}")
        
        # 7. 요구사항 분석 테스트 (간단한 버전)
        print("\n7️⃣ 요구사항 분석 테스트")
        try:
            result = await unified_workflow.analyze_requirements(
                hs_code="3304",
                product_name="Test Product",
                product_description="Test Description"
            )
            
            if result.get('status') == 'completed':
                print(f"✅ 요구사항 분석 테스트 성공")
                print(f"   처리 시간: {result.get('processing_time_ms', 0)}ms")
            else:
                print(f"⚠️ 요구사항 분석 테스트 부분 성공: {result.get('status', 'unknown')}")
                
        except Exception as e:
            print(f"⚠️ 요구사항 분석 테스트 실패: {e}")
        
        # 8. 메트릭 요약
        print("\n8️⃣ 메트릭 요약")
        cache_metrics = enhanced_cache.get_metrics()
        parallel_metrics = parallel_processor.get_metrics()
        error_summary = error_handler.get_error_summary()
        
        print(f"📊 캐시 메트릭:")
        print(f"   히트율: {cache_metrics.get('hit_rate', 0)}%")
        print(f"   총 요청: {cache_metrics.get('total_requests', 0)}")
        
        print(f"📊 병렬 처리 메트릭:")
        print(f"   성공률: {parallel_metrics.get('success_rate', 0)}%")
        print(f"   평균 처리시간: {parallel_metrics.get('average_processing_time', 0)}초")
        
        print(f"📊 에러 요약:")
        print(f"   총 에러: {error_summary.get('total_errors', 0)}")
        
        print("\n🎉 모든 테스트 완료!")
        
    except Exception as e:
        print(f"\n❌ 테스트 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()

async def main():
    """메인 함수"""
    print("🚀 LawGenie 요건 파트 개선사항 테스트")
    print(f"시작 시간: {datetime.now().isoformat()}")
    print("=" * 60)
    
    await test_improvements()
    
    print("\n" + "=" * 60)
    print(f"완료 시간: {datetime.now().isoformat()}")
    print("테스트 종료")

if __name__ == "__main__":
    asyncio.run(main())
