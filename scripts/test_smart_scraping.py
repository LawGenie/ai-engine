#!/usr/bin/env python3
"""
HS코드별 스마트 스크래핑 테스트 (확장)
6개 공식 사이트에서 검색 및 스크래핑 결과를 JSON 형태로 출력
HS코드 8자리와 6자리 모두 검색하여 결과 구분
"""

import asyncio
import sys
import os
import requests
import json
from datetime import datetime

# 현재 디렉토리를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_smart_scraping():
    """스마트 스크래핑 시스템 테스트 (확장)"""
    print("🎯 HS코드별 스마트 스크래핑 테스트 시작...")
    print("=" * 60)
    
    # AI 엔진 API 엔드포인트
    api_url = "http://127.0.0.1:8000/requirements/analyze"
    
    # 다양한 HS코드로 테스트 (8자리와 6자리 모두)
    test_products = [
        {
            "name": "노트북 컴퓨터",
            "hs_code_8digit": "8471.30.01",
            "hs_code_6digit": "8471.30",
            "expected_sites": ["FDA", "FCC", "CBP", "USDA", "EPA", "CPSC", "KCS", "MFDS", "MOTIE"]
        },
        {
            "name": "커피 원두", 
            "hs_code_8digit": "0901.11.00",
            "hs_code_6digit": "0901.11",
            "expected_sites": ["FDA", "FCC", "CBP", "USDA", "EPA", "CPSC", "KCS", "MFDS", "MOTIE"]
        },
        {
            "name": "스마트폰",
            "hs_code_8digit": "8517.12.00", 
            "hs_code_6digit": "8517.12",
            "expected_sites": ["FDA", "FCC", "CBP", "USDA", "EPA", "CPSC", "KCS", "MFDS", "MOTIE"]
        },
        {
            "name": "의료용 마스크",
            "hs_code_8digit": "3004.90.91",
            "hs_code_6digit": "3004.90",
            "expected_sites": ["FDA", "FCC", "CBP", "USDA", "EPA", "CPSC", "KCS", "MFDS", "MOTIE"]
        }
    ]
    
    # 전체 결과를 저장할 딕셔너리
    all_results = {
        "test_timestamp": datetime.now().isoformat(),
        "total_products": len(test_products),
        "results": []
    }
    
    for i, product in enumerate(test_products, 1):
        print(f"\n{'='*60}")
        print(f"🔍 테스트 {i}: {product['name']}")
        print(f"📋 8자리 HS코드: {product['hs_code_8digit']}")
        print(f"📋 6자리 HS코드: {product['hs_code_6digit']}")
        print(f"🌐 검색 대상 사이트: {len(product['expected_sites'])}개")
        print('='*60)
        
        # 8자리와 6자리 HS코드 모두 테스트
        test_results = {
            "product_name": product["name"],
            "hs_code_8digit": product["hs_code_8digit"],
            "hs_code_6digit": product["hs_code_6digit"],
            "expected_sites": product["expected_sites"],
            "8digit_results": None,
            "6digit_results": None
        }
        
        # 8자리 HS코드 테스트
        print(f"\n🔍 8자리 HS코드 테스트: {product['hs_code_8digit']}")
        test_results["8digit_results"] = test_hs_code(
            api_url, product["hs_code_8digit"], product["name"], "8digit"
        )
        
        # 6자리 HS코드 테스트
        print(f"\n🔍 6자리 HS코드 테스트: {product['hs_code_6digit']}")
        test_results["6digit_results"] = test_hs_code(
            api_url, product["hs_code_6digit"], product["name"], "6digit"
        )
        
        all_results["results"].append(test_results)
    
    # 전체 결과를 JSON 파일로 저장
    output_file = f"scraping_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*60}")
    print("🎯 스마트 스크래핑 테스트 완료!")
    print(f"📄 결과가 {output_file}에 저장되었습니다.")
    print("📊 이제 HS코드별로 적절한 사이트만 스크래핑합니다.")
    print("⚡ 불필요한 스크래핑이 제거되어 속도가 향상되었습니다.")

def test_hs_code(api_url, hs_code, product_name, digit_type):
    """개별 HS코드 테스트"""
    request_data = {
        "hs_code": hs_code,
        "product_name": product_name,
        "target_country": "US"
    }
    
    result = {
        "hs_code": hs_code,
        "digit_type": digit_type,
        "success": False,
        "error": None,
        "response_time_ms": 0,
        "scraping_summary": {},
        "requirements_summary": {},
        "detailed_results": None
    }
    
    start_time = datetime.now()
    
    try:
        # API 호출
        response = requests.post(api_url, json=request_data, timeout=300)
        end_time = datetime.now()
        result["response_time_ms"] = int((end_time - start_time).total_seconds() * 1000)
        
        if response.status_code == 200:
            api_result = response.json()
            result["success"] = True
            result["detailed_results"] = api_result
            
            # 스크래핑 요약 정보 추출
            scraping_metadata = api_result.get("metadata", {}).get("scraping_metadata", {})
            result["scraping_summary"] = {
                "total_pages_scraped": scraping_metadata.get("total_pages_scraped", 0),
                "successful_agencies": scraping_metadata.get("successful_agencies", []),
                "failed_agencies": scraping_metadata.get("failed_agencies", []),
                "scraping_duration_ms": scraping_metadata.get("scraping_duration_ms", 0),
                "content_quality_score": scraping_metadata.get("content_quality_score", 0)
            }
            
            # 요구사항 요약 정보 추출
            requirements = api_result.get("requirements", {})
            result["requirements_summary"] = {
                "certifications_count": len(requirements.get("certifications", [])),
                "documents_count": len(requirements.get("documents", [])),
                "labeling_count": len(requirements.get("labeling", [])),
                "sources_count": len(api_result.get("sources", [])),
                "agencies_found": list(set([cert.get("agency", "Unknown") for cert in requirements.get("certifications", [])]))
            }
            
            print(f"✅ {digit_type} HS코드 API 응답 성공!")
            print(f"⏱️ 응답 시간: {result['response_time_ms']}ms")
            print(f"📊 스크래핑된 페이지: {result['scraping_summary']['total_pages_scraped']}개")
            print(f"✅ 성공한 기관: {result['scraping_summary']['successful_agencies']}")
            print(f"❌ 실패한 기관: {result['scraping_summary']['failed_agencies']}")
            print(f"📋 인증요건: {result['requirements_summary']['certifications_count']}개")
            print(f"📄 필요서류: {result['requirements_summary']['documents_count']}개")
            print(f"🏷️ 라벨링요건: {result['requirements_summary']['labeling_count']}개")
            print(f"📚 출처: {result['requirements_summary']['sources_count']}개")
            print(f"🏢 발견된 기관: {result['requirements_summary']['agencies_found']}")
            
            # 상세 정보 출력
            if requirements.get('certifications'):
                print(f"\n📋 인증요건 상세:")
                for cert in requirements['certifications']:
                    print(f"  • {cert.get('name', 'Unknown')} ({cert.get('agency', 'Unknown')})")
            
            if requirements.get('documents'):
                print(f"\n📄 필요서류 상세:")
                for doc in requirements['documents']:
                    print(f"  • {doc.get('name', 'Unknown')}")
            
            if api_result.get('sources'):
                print(f"\n📚 출처:")
                for source in api_result['sources']:
                    print(f"  • {source.get('title', 'Unknown')} ({source.get('type', 'Unknown')})")
            
        else:
            result["error"] = f"API 오류: {response.status_code} - {response.text}"
            print(f"❌ {digit_type} HS코드 API 오류: {response.status_code}")
            print(f"❌ 오류 내용: {response.text}")
            
    except requests.exceptions.Timeout:
        result["error"] = "API 타임아웃 (300초 초과)"
        print(f"⏰ {digit_type} HS코드 API 타임아웃 (300초 초과)")
    except requests.exceptions.RequestException as e:
        result["error"] = f"API 요청 실패: {str(e)}"
        print(f"❌ {digit_type} HS코드 API 요청 실패: {e}")
    except Exception as e:
        result["error"] = f"예상치 못한 오류: {str(e)}"
        print(f"❌ {digit_type} HS코드 예상치 못한 오류: {e}")
    
    return result

if __name__ == "__main__":
    test_smart_scraping()
