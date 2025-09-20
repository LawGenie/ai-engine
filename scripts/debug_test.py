#!/usr/bin/env python3
"""
디버깅용 간단한 테스트 스크립트
"""

import asyncio
import httpx
import json

async def test_requirements_api():
    """요구사항 분석 API 테스트"""
    
    # 테스트 데이터
    test_data = {
        "hs_code": "0901.11.00",
        "product_name": "커피 원두",
        "target_country": "US"
    }
    
    print("🔍 API 테스트 시작...")
    print(f"📋 요청 데이터: {test_data}")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://127.0.0.1:8000/requirements/analyze",
                json=test_data,
                timeout=30.0
            )
            
            print(f"📊 응답 상태: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ API 응답 성공!")
                print(f"📋 인증요건: {len(result.get('requirements', {}).get('certifications', []))}개")
                print(f"📄 필요서류: {len(result.get('requirements', {}).get('documents', []))}개")
                print(f"📚 출처: {len(result.get('sources', []))}개")
                
                # 상세 결과 출력
                print(f"\n📋 상세 결과:")
                print(f"  답변: {result.get('answer', 'N/A')}")
                print(f"  근거: {result.get('reasoning', 'N/A')}")
                
                # 인증요건 상세
                certs = result.get('requirements', {}).get('certifications', [])
                if certs:
                    print(f"\n📋 인증요건 상세:")
                    for cert in certs:
                        print(f"  • {cert.get('name', 'Unknown')} ({cert.get('agency', 'Unknown')})")
                
                # 필요서류 상세
                docs = result.get('requirements', {}).get('documents', [])
                if docs:
                    print(f"\n📄 필요서류 상세:")
                    for doc in docs:
                        print(f"  • {doc.get('name', 'Unknown')}")
                
            else:
                print(f"❌ API 응답 실패: {response.status_code}")
                print(f"오류 내용: {response.text}")
                
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")

if __name__ == "__main__":
    asyncio.run(test_requirements_api())
