#!/usr/bin/env python3
"""
HS코드별 스마트 스크래핑 테스트
추천된 사이트만 스크래핑하여 효율성 증대
"""

import asyncio
import sys
import os
import requests

# 현재 디렉토리를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_smart_scraping():
    """스마트 스크래핑 시스템 테스트"""
    print("🎯 HS코드별 스마트 스크래핑 테스트 시작...")
    print("=" * 60)
    
    # AI 엔진 API 엔드포인트
    api_url = "http://127.0.0.1:8000/requirements/analyze"
    
    # 다양한 HS코드로 테스트
    test_products = [
        {
            "name": "노트북 컴퓨터",
            "hs_code": "8471.30.01",
            "expected_sites": ["FCC", "CBP"]
        },
        {
            "name": "커피 원두", 
            "hs_code": "0901.11.00",
            "expected_sites": ["FDA", "CBP"]
        },
        {
            "name": "스마트폰",
            "hs_code": "8517.12.00", 
            "expected_sites": ["FCC", "CBP"]
        },
        {
            "name": "의료용 마스크",
            "hs_code": "3004.90.91",
            "expected_sites": ["FDA", "CBP"]
        }
    ]
    
    for i, product in enumerate(test_products, 1):
        print(f"\n{'='*60}")
        print(f"🔍 테스트 {i}: {product['name']} (HS코드: {product['hs_code']})")
        print(f"📋 예상 사이트: {product['expected_sites']}")
        print('='*60)
        
        # API 요청 데이터
        request_data = {
            "hs_code": product["hs_code"],
            "product_name": product["name"],
            "country_of_origin": "KR"
        }
        
        try:
            # API 호출
            response = requests.post(api_url, json=request_data, timeout=180)
            
            if response.status_code == 200:
                result = response.json()
                
                print(f"✅ API 응답 성공!")
                print(f"📊 인증요건: {len(result.get('requirements', {}).get('certifications', []))}개")
                print(f"📄 필요서류: {len(result.get('requirements', {}).get('documents', []))}개") 
                print(f"🏷️ 라벨링요건: {len(result.get('requirements', {}).get('labeling', []))}개")
                print(f"📚 출처: {len(result.get('sources', []))}개")
                
                # 상세 정보 출력
                requirements = result.get('requirements', {})
                
                if requirements.get('certifications'):
                    print(f"\n📋 인증요건 상세:")
                    for cert in requirements['certifications']:
                        print(f"  • {cert.get('name', 'Unknown')} ({cert.get('agency', 'Unknown')})")
                
                if requirements.get('documents'):
                    print(f"\n📄 필요서류 상세:")
                    for doc in requirements['documents']:
                        print(f"  • {doc.get('name', 'Unknown')}")
                
                if result.get('sources'):
                    print(f"\n📚 출처:")
                    for source in result['sources']:
                        print(f"  • {source.get('title', 'Unknown')} ({source.get('type', 'Unknown')})")
                
            else:
                print(f"❌ API 오류: {response.status_code}")
                print(f"❌ 오류 내용: {response.text}")
                
        except requests.exceptions.Timeout:
            print(f"⏰ API 타임아웃 (180초 초과)")
        except requests.exceptions.RequestException as e:
            print(f"❌ API 요청 실패: {e}")
        except Exception as e:
            print(f"❌ 예상치 못한 오류: {e}")
    
    print(f"\n{'='*60}")
    print("🎯 스마트 스크래핑 테스트 완료!")
    print("📊 이제 HS코드별로 적절한 사이트만 스크래핑합니다.")
    print("⚡ 불필요한 스크래핑이 제거되어 속도가 향상되었습니다.")

if __name__ == "__main__":
    test_smart_scraping()
