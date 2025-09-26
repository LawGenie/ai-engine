#!/usr/bin/env python3
"""
HS 코드 기반 스마트 검색 테스트
data.sql의 상품 중 하나를 선택하여 테스트
"""

import asyncio
import json
from pathlib import Path
from dotenv import load_dotenv

# 프로젝트 루트 설정
project_root = Path(__file__).parent
load_dotenv(project_root / ".env")

# 모듈 임포트
import sys
sys.path.append(str(project_root))

from workflows.tools import RequirementsTools

async def test_smart_search():
    """HS 코드 기반 스마트 검색 테스트"""
    
    # 테스트 케이스: 비타민C 세럼 (HS: 3304.99.50.00)
    test_case = {
        "product_name": "Premium Vitamin C Serum",
        "hs_code": "3304.99.50.00",
        "description": "High-concentration Vitamin C serum effective for skin tone improvement and anti-aging. Contains 20% Vitamin C and hyaluronic acid, suitable for all skin types. Volume: 30ml, glass bottle packaging, net weight: 50g."
    }
    
    print("🚀 HS 코드 기반 스마트 검색 테스트 시작")
    print(f"📦 상품: {test_case['product_name']}")
    print(f"🏷️ HS 코드: {test_case['hs_code']}")
    print(f"📝 설명: {test_case['description']}")
    print("=" * 60)
    
    # RequirementsTools 초기화
    tools = RequirementsTools()
    
    try:
        # 스마트 검색 실행
        results = await tools.search_requirements_hybrid(
            hs_code=test_case["hs_code"],
            product_name=test_case["product_name"],
            product_description=test_case["description"]
        )
        
        print("\n🎉 테스트 성공!")
        
        # 결과 요약
        combined_results = results.get("combined_results", {})
        target_agencies = combined_results.get("target_agencies", {})
        
        print(f"\n📊 결과 요약:")
        print(f"  🎯 타겟 기관: {', '.join(target_agencies.get('primary_agencies', []))}")
        print(f"  📊 검색 신뢰도: {target_agencies.get('confidence', 0):.1%}")
        print(f"  🔑 추출된 키워드: {', '.join(combined_results.get('extracted_keywords', [])[:5])}")
        print(f"  📋 총 요구사항: {combined_results.get('total_requirements', 0)}개")
        print(f"  🏆 인증요건: {combined_results.get('total_certifications', 0)}개")
        print(f"  📄 필요서류: {combined_results.get('total_documents', 0)}개")
        
        # 카테고리별 결과
        category_stats = combined_results.get('category_stats', {})
        print(f"\n📈 카테고리별 검색 결과:")
        for category, count in category_stats.items():
            print(f"  {category}: {count}개")
        
        # 웹 검색 결과 상세
        web_results = results.get("web_results", {})
        print(f"\n🔍 웹 검색 결과 상세:")
        for query_key, data in web_results.items():
            if "error" not in data:
                print(f"  {query_key}: {data.get('result_count', 0)}개 결과")
                print(f"    기관: {data.get('agency', 'Unknown')}")
                print(f"    카테고리: {data.get('category', 'Unknown')}")
                print(f"    신뢰도: {data.get('target_confidence', 0):.1%}")
        
        # JSON 결과 저장
        output_file = project_root / "test_smart_search_result.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 결과가 {output_file}에 저장되었습니다.")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_smart_search())
    if success:
        print("\n✅ 테스트 완료!")
    else:
        print("\n❌ 테스트 실패!")
