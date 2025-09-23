"""
Tavily Search 전용 테스트 스크립트
웹 검색 + 스크래핑만 테스트
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
tavily_key = os.getenv("TAVILY_API_KEY")
print(f"🔑 TAVILY_API_KEY: {'SET' if tavily_key else 'NOT_FOUND'}")

from workflows.tools import RequirementsTools

async def test_tavily_only():
    """Tavily Search 전용 테스트"""
    print("🚀 Tavily Search 전용 테스트 시작")
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
    
    tools = RequirementsTools()
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
            
            # Tavily Search만 실행 (API 제외)
            web_results = {}
            search_queries = {
                f"FDA_8digit": f"site:fda.gov import requirements {product['name']} HS {product['hs_code']}",
                f"USDA_8digit": f"site:usda.gov agricultural import requirements {product['name']} HS {product['hs_code']}",
                f"EPA_8digit": f"site:epa.gov environmental regulations {product['name']} HS {product['hs_code']}",
                f"FCC_8digit": f"site:fcc.gov device authorization requirements {product['name']} HS {product['hs_code']}",
                f"CBP_8digit": f"site:cbp.gov import documentation requirements HS {product['hs_code']} {product['name']}",
                f"CPSC_8digit": f"site:cpsc.gov consumer product safety {product['name']} HS {product['hs_code']}"
            }
            
            # 6자리 HS코드도 추가
            hs_code_6digit = ".".join(product['hs_code'].split(".")[:2]) if "." in product['hs_code'] else product['hs_code']
            search_queries.update({
                f"FDA_6digit": f"site:fda.gov import requirements {product['name']} HS {hs_code_6digit}",
                f"USDA_6digit": f"site:usda.gov agricultural import requirements {product['name']} HS {hs_code_6digit}",
                f"EPA_6digit": f"site:epa.gov environmental regulations {product['name']} HS {hs_code_6digit}",
                f"FCC_6digit": f"site:fcc.gov device authorization requirements {product['name']} HS {hs_code_6digit}",
                f"CBP_6digit": f"site:cbp.gov import documentation requirements HS {hs_code_6digit} {product['name']}",
                f"CPSC_6digit": f"site:cpsc.gov consumer product safety {product['name']} HS {hs_code_6digit}"
            })
            
            for query_key, query in search_queries.items():
                try:
                    search_results = await tools.search_service.search(query, max_results=5)
                    web_results[query_key] = {
                        "query": query,
                        "results": search_results,
                        "urls": [r.get("url") for r in search_results if r.get("url")],
                        "hs_code_type": "8digit" if "8digit" in query_key else "6digit",
                        "agency": query_key.split("_")[0]
                    }
                except Exception as e:
                    web_results[query_key] = {"error": str(e)}
            
            end_time = time.time()
            response_time = int((end_time - start_time) * 1000)
            
            # 결과 분석
            total_urls = sum(len(data.get("urls", [])) for data in web_results.values() if "error" not in data)
            successful_queries = len([data for data in web_results.values() if "error" not in data])
            
            print(f"\n✅ Tavily 검색 완료 ({response_time}ms)")
            print(f"  🔍 성공한 쿼리: {successful_queries}/{len(search_queries)}개")
            print(f"  🔗 총 URL: {total_urls}개")
            
            # 기관별 결과
            agencies_found = set()
            for query_key, data in web_results.items():
                if "error" not in data and data.get("urls"):
                    agency = query_key.split("_")[0]
                    agencies_found.add(agency)
                    print(f"  ✅ {agency}: {len(data.get('urls', []))}개 URL")
            
            print(f"  🏢 발견된 기관: {', '.join(sorted(agencies_found))}")
            
            # 상세 결과 저장
            product_result = {
                "product_name": product["name"],
                "hs_code": product["hs_code"],
                "hs_code_6digit": hs_code_6digit,
                "expected_agencies": product["expected_agencies"],
                "response_time_ms": response_time,
                "tavily_success": total_urls > 0,
                "search_summary": {
                    "total_queries": len(search_queries),
                    "successful_queries": successful_queries,
                    "total_urls": total_urls,
                    "agencies_found": list(agencies_found)
                },
                "web_results": web_results
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
    filename = f"tavily_only_test_results_{timestamp}.json"
    filepath = project_root / filename
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n📁 결과 저장: {filepath}")
    
    # 전체 요약
    print(f"\n📊 전체 Tavily 테스트 요약")
    print("=" * 60)
    successful_tests = len([r for r in results["results"] if "error" not in r])
    print(f"✅ 성공한 테스트: {successful_tests}/{len(test_products)}")
    
    if successful_tests > 0:
        total_urls = sum(r.get("search_summary", {}).get("total_urls", 0) for r in results["results"] if "error" not in r)
        total_queries = sum(r.get("search_summary", {}).get("total_queries", 0) for r in results["results"] if "error" not in r)
        successful_queries = sum(r.get("search_summary", {}).get("successful_queries", 0) for r in results["results"] if "error" not in r)
        
        print(f"🔍 총 쿼리: {total_queries}개")
        print(f"✅ 성공한 쿼리: {successful_queries}개")
        print(f"🔗 총 URL: {total_urls}개")
        
        # 기관별 통계
        all_agencies = set()
        for r in results["results"]:
            if "error" not in r:
                all_agencies.update(r.get("search_summary", {}).get("agencies_found", []))
        
        print(f"🏢 발견된 기관: {', '.join(sorted(all_agencies))}")
    
    print(f"\n🎉 Tavily Search 전용 테스트 완료!")

if __name__ == "__main__":
    asyncio.run(test_tavily_only())
