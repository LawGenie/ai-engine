#!/usr/bin/env python3
"""
AI Engine API 테스트 스크립트
"""

import requests
import json
import time
import asyncio
from cbp_scraper import CBPDataCollector

# AI Engine URL
AI_ENGINE_URL = "http://localhost:8000"

def test_health():
    """헬스체크 테스트"""
    print("🔍 헬스체크 테스트...")
    try:
        response = requests.get(f"{AI_ENGINE_URL}/health", timeout=10)
        if response.status_code == 200:
            print("✅ 헬스체크 성공")
            print(f"응답: {response.json()}")
            return True
        else:
            print(f"❌ 헬스체크 실패: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 헬스체크 오류: {e}")
        return False

async def test_cbp_data():
    """CBP 데이터 수집 테스트"""
    print("\n🔍 CBP 데이터 수집 테스트...")
    try:
        collector = CBPDataCollector()
        hs_code = "3304.99.50.00"  # 화장품 HS코드
        
        data = await collector.get_precedents_by_hs_code(hs_code)
        print(f"✅ CBP 데이터 수집 성공: {len(data)}개 사례")
        
        if data:
            print("📋 샘플 데이터:")
            for i, case in enumerate(data[:2], 1):
                print(f"  {i}. {case.get('title', 'N/A')} - {case.get('status', 'N/A')}")
        
        return True
    except Exception as e:
        print(f"❌ CBP 데이터 수집 실패: {e}")
        return False

def test_precedents_analysis():
    """판례 분석 테스트"""
    print("\n🔍 판례 분석 테스트...")
    try:
        test_data = {
            "product_id": "TEST-001",
            "product_name": "Premium Vitamin C Serum",
            "description": "High-concentration Vitamin C serum for anti-aging",
            "hs_code": "3304.99.50.00",
            "origin_country": "KOR",
            "price": 29.99,
            "fob_price": 25.00
        }
        
        print("📤 분석 요청 전송 중...")
        response = requests.post(
            f"{AI_ENGINE_URL}/analyze-precedents",
            json=test_data,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            print("✅ 판례 분석 성공")
            print(f"📊 신뢰도 점수: {result.get('confidence_score', 'N/A')}")
            print(f"✅ 성공 사례: {len(result.get('success_cases', []))}개")
            print(f"❌ 실패 사례: {len(result.get('failure_cases', []))}개")
            print(f"💡 인사이트: {len(result.get('actionable_insights', []))}개")
            print(f"⚠️ 위험 요소: {len(result.get('risk_factors', []))}개")
            print(f"🎯 권장 조치: {result.get('recommended_action', 'N/A')}")
            return True
        else:
            print(f"❌ 판례 분석 실패: {response.status_code}")
            print(f"오류: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 판례 분석 오류: {e}")
        return False

def test_cbp_endpoint():
    """CBP 테스트 엔드포인트"""
    print("\n🔍 CBP 테스트 엔드포인트...")
    try:
        hs_code = "3304.99.50.00"
        response = requests.get(f"{AI_ENGINE_URL}/test-cbp/{hs_code}", timeout=15)
        
        if response.status_code == 200:
            result = response.json()
            print("✅ CBP 테스트 엔드포인트 성공")
            print(f"📊 데이터 개수: {result.get('data_count', 0)}")
            print(f"📋 HS코드: {result.get('hs_code', 'N/A')}")
            return True
        else:
            print(f"❌ CBP 테스트 엔드포인트 실패: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ CBP 테스트 엔드포인트 오류: {e}")
        return False

async def main():
    """메인 테스트 함수"""
    print("🧪 AI Engine API 테스트 시작\n")
    
    # 1. 헬스체크 테스트
    health_ok = test_health()
    if not health_ok:
        print("❌ 서버가 실행되지 않았습니다. 먼저 서버를 시작해주세요.")
        return
    
    # 2. CBP 데이터 수집 테스트
    cbp_ok = await test_cbp_data()
    
    # 3. CBP 테스트 엔드포인트
    endpoint_ok = test_cbp_endpoint()
    
    # 4. 판례 분석 테스트
    analysis_ok = test_precedents_analysis()
    
    # 결과 요약
    print("\n📊 테스트 결과 요약:")
    print(f"헬스체크: {'✅' if health_ok else '❌'}")
    print(f"CBP 데이터 수집: {'✅' if cbp_ok else '❌'}")
    print(f"CBP 엔드포인트: {'✅' if endpoint_ok else '❌'}")
    print(f"판례 분석: {'✅' if analysis_ok else '❌'}")
    
    if all([health_ok, cbp_ok, endpoint_ok, analysis_ok]):
        print("\n🎉 모든 테스트 통과!")
    else:
        print("\n⚠️ 일부 테스트 실패. 로그를 확인해주세요.")

if __name__ == "__main__":
    asyncio.run(main())
