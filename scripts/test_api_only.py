"""
API 전용 테스트 스크립트
FDA, USDA, EPA, FCC, CBP, CPSC API만 테스트
"""

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
import sys
import os
from dotenv import load_dotenv

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

# .env 파일 로드
env_path = project_root / ".env"
if env_path.exists():
    load_dotenv(env_path)
    print(f"✅ .env 파일 로딩 성공: {env_path}")
else:
    print(f"⚠️ .env 파일 없음: {env_path}")

# API 키 확인
data_gov_key = os.getenv("API_DATA_GOV")
print(f"🔑 API_DATA_GOV: {'SET' if data_gov_key else 'NOT_FOUND'}")

from app.services.requirements.data_gov_api import DataGovAPIService

async def test_api_only():
    """API 전용 테스트"""
    print("🚀 API 전용 테스트 시작")
    print("=" * 60)
    
    # 테스트 제품들
    test_products = [
        {
            "name": "노트북 컴퓨터",
            "hs_code": "8471.30.01",
            "expected_agencies": ["FDA", "FCC", "CBP", "EPA", "CPSC"]
        },
        {
            "name": "커피 원두",
            "hs_code": "0901.21.00",
            "expected_agencies": ["FDA", "USDA", "CBP"]
        },
        {
            "name": "비타민C 세럼",
            "hs_code": "3304.99.50.00",
            "expected_agencies": ["FDA", "CBP"]
        }
    ]
    
    api_service = DataGovAPIService()
    results = {
        "test_timestamp": datetime.now().isoformat(),
        "total_products": len(test_products),
        "results": []
    }
    
    for i, product in enumerate(test_products, 1):
        print(f"\n📦 테스트 {i}/{len(test_products)}: {product['name']}")
        print(f"  📋 HS코드: {product['hs_code']}")
        print(f"  🏢 예상 기관: {', '.join(product['expected_agencies'])}")
        print("-" * 40)
        
        try:
            start_time = time.time()
            
            # API 검색 실행
            api_results = await api_service.search_requirements_by_hs_code(
                product["hs_code"], 
                product["name"]
            )
            
            end_time = time.time()
            response_time = int((end_time - start_time) * 1000)
            
            # 결과 분석
            total_requirements = api_results.get("total_requirements", 0)
            total_certifications = api_results.get("total_certifications", 0)
            total_documents = api_results.get("total_documents", 0)
            
            print(f"\n✅ API 검색 완료 ({response_time}ms)")
            print(f"  📋 총 요구사항: {total_requirements}개")
            print(f"  🏆 인증요건: {total_certifications}개")
            print(f"  📄 필요서류: {total_documents}개")
            
            # 기관별 결과 분석
            agencies = api_results.get("agencies", {})
            successful_agencies = []
            failed_agencies = []
            
            for agency, data in agencies.items():
                if data.get("status") == "success":
                    successful_agencies.append(agency)
                    print(f"  ✅ {agency}: 성공")
                else:
                    failed_agencies.append(agency)
                    print(f"  ❌ {agency}: {data.get('status', 'unknown')}")
            
            print(f"  🏢 성공한 기관: {', '.join(successful_agencies)}")
            if failed_agencies:
                print(f"  ❌ 실패한 기관: {', '.join(failed_agencies)}")
            
            # 상세 결과 저장
            product_result = {
                "product_name": product["name"],
                "hs_code": product["hs_code"],
                "expected_agencies": product["expected_agencies"],
                "response_time_ms": response_time,
                "api_success": total_requirements > 0,
                "requirements_summary": {
                    "total_requirements": total_requirements,
                    "total_certifications": total_certifications,
                    "total_documents": total_documents,
                    "successful_agencies": successful_agencies,
                    "failed_agencies": failed_agencies
                },
                "api_results": api_results
            }
            
            results["results"].append(product_result)
            
        except Exception as e:
            print(f"❌ 테스트 실패: {e}")
            results["results"].append({
                "product_name": product["name"],
                "hs_code": product["hs_code"],
                "error": str(e),
                "response_time_ms": 0
            })
    
    # 결과 저장
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"api_only_test_results_{timestamp}.json"
    filepath = project_root / filename
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n📁 결과 저장: {filepath}")
    
    # 전체 요약
    print(f"\n📊 전체 API 테스트 요약")
    print("=" * 60)
    successful_tests = len([r for r in results["results"] if "error" not in r])
    print(f"✅ 성공한 테스트: {successful_tests}/{len(test_products)}")
    
    if successful_tests > 0:
        total_requirements = sum(r.get("requirements_summary", {}).get("total_requirements", 0) for r in results["results"] if "error" not in r)
        total_certifications = sum(r.get("requirements_summary", {}).get("total_certifications", 0) for r in results["results"] if "error" not in r)
        total_documents = sum(r.get("requirements_summary", {}).get("total_documents", 0) for r in results["results"] if "error" not in r)
        
        print(f"📋 총 요구사항: {total_requirements}개")
        print(f"🏆 총 인증요건: {total_certifications}개")
        print(f"📄 총 필요서류: {total_documents}개")
        
        # 기관별 통계
        all_successful_agencies = set()
        all_failed_agencies = set()
        for r in results["results"]:
            if "error" not in r:
                all_successful_agencies.update(r.get("requirements_summary", {}).get("successful_agencies", []))
                all_failed_agencies.update(r.get("requirements_summary", {}).get("failed_agencies", []))
        
        print(f"✅ 성공한 기관: {', '.join(sorted(all_successful_agencies))}")
        if all_failed_agencies:
            print(f"❌ 실패한 기관: {', '.join(sorted(all_failed_agencies))}")
    
    print(f"\n🎉 API 전용 테스트 완료!")

if __name__ == "__main__":
    asyncio.run(test_api_only())
