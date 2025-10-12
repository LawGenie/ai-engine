#!/usr/bin/env python3
"""
요건 분석 시스템 검증 스크립트
Phase 1-4, 확장 필드, 링크 교체 모두 확인
"""

import asyncio
import json
from workflows.unified_workflow import unified_workflow

async def test_requirements_analysis():
    """화장품 샘플로 요건 분석 테스트"""
    
    print("=" * 60)
    print("🧪 요건 분석 시스템 검증 시작")
    print("=" * 60)
    
    # 테스트 데이터
    test_request = {
        "hs_code": "3304.99.50.00",
        "product_name": "Test Vitamin C Serum",
        "product_description": "Premium anti-aging serum with 20% Vitamin C",
        "target_country": "US",
        "is_new_product": True,
        "force_refresh": True
    }
    
    print(f"\n📦 테스트 상품: {test_request['product_name']}")
    print(f"📋 HS 코드: {test_request['hs_code']}")
    
    try:
        # 워크플로우 실행
        print("\n🚀 워크플로우 실행 중...")
        result = await unified_workflow.run_workflow(test_request)
        
        # 결과 검증
        print("\n" + "=" * 60)
        print("✅ 검증 결과")
        print("=" * 60)
        
        # 1. Phase 1-4 확인
        phase_checks = {
            "phase_1_detailed_regulations": result.get("detailed_regulations"),
            "phase_2_testing_procedures": result.get("testing_procedures"),
            "phase_3_penalties": result.get("penalties"),
            "phase_4_validity": result.get("validity"),
            "cross_validation": result.get("cross_validation")
        }
        
        print("\n📊 Phase 1-4 상태:")
        for phase_name, phase_data in phase_checks.items():
            if phase_data and phase_data != "null":
                sources_count = len(phase_data.get("sources", [])) if isinstance(phase_data, dict) else 0
                print(f"  ✅ {phase_name}: 정상 ({sources_count}개 출처)")
            else:
                print(f"  ❌ {phase_name}: NULL 또는 누락")
        
        # 2. 확장 필드 확인
        llm_summary = result.get("llm_summary", {})
        extended_fields = {
            "execution_checklist": llm_summary.get("execution_checklist"),
            "cost_breakdown": llm_summary.get("cost_breakdown"),
            "risk_matrix": llm_summary.get("risk_matrix"),
            "compliance_score": llm_summary.get("compliance_score"),
            "market_access": llm_summary.get("market_access")
        }
        
        print("\n📋 확장 필드 상태:")
        for field_name, field_data in extended_fields.items():
            if field_data and field_data != "null":
                print(f"  ✅ {field_name}: 정상")
            else:
                print(f"  ❌ {field_name}: NULL 또는 누락")
        
        # 3. 링크 검증
        print("\n🔗 링크 검증:")
        placeholder_found = False
        
        def check_urls(obj, path=""):
            nonlocal placeholder_found
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if key == "source_url" and isinstance(value, str):
                        if "ACTUAL_URL" in value or value == "https://...":
                            print(f"  ❌ 플레이스홀더 발견: {path}.{key} = {value}")
                            placeholder_found = True
                    else:
                        check_urls(value, f"{path}.{key}")
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    check_urls(item, f"{path}[{i}]")
        
        check_urls(result)
        
        if not placeholder_found:
            print("  ✅ 모든 링크가 실제 URL로 교체됨")
        
        # 4. 판례 검증 확인
        print("\n🔍 판례 검증 확인:")
        precedent_val = result.get("precedent_validation")
        if precedent_val and precedent_val != "null":
            val_score = precedent_val.get("validation_score", 0)
            precedents_count = precedent_val.get("precedents_analyzed", 0)
            verdict = precedent_val.get("verdict", {}).get("status", "N/A")
            print(f"  ✅ 판례 검증: {precedents_count}개 판례 분석")
            print(f"  📊 검증 점수: {val_score:.2f}")
            print(f"  ⚖️ 판정: {verdict}")
            print(f"  🎯 일치: {len(precedent_val.get('matched_requirements', []))}개")
            print(f"  ⚠️ 누락: {len(precedent_val.get('missing_requirements', []))}개")
            print(f"  📋 추가: {len(precedent_val.get('extra_requirements', []))}개")
            print(f"  🚨 Red Flags: {len(precedent_val.get('red_flags', []))}개")
        else:
            print("  ⚠️ 판례 검증 결과 없음 (FAISS DB 데이터 확인 필요)")
        
        # 5. 한글 번역 확인
        print("\n🇰🇷 한글 번역 확인:")
        korean_fields = 0
        korean_found = 0
        
        def check_korean(obj):
            nonlocal korean_fields, korean_found
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if key.endswith("_ko"):
                        korean_fields += 1
                        if value and value != "":
                            korean_found += 1
                    else:
                        check_korean(value)
            elif isinstance(obj, list):
                for item in obj:
                    check_korean(item)
        
        check_korean(llm_summary)
        
        if korean_fields > 0:
            coverage = (korean_found / korean_fields) * 100
            print(f"  📊 한글 필드: {korean_found}/{korean_fields} ({coverage:.1f}%)")
            if coverage >= 80:
                print(f"  ✅ 한글 번역 양호")
            else:
                print(f"  ⚠️ 한글 번역 부족 ({coverage:.1f}% < 80%)")
        else:
            print("  ⚠️ 한글 필드를 찾을 수 없음")
        
        # 5. 전체 요약
        print("\n" + "=" * 60)
        print("📊 전체 요약")
        print("=" * 60)
        
        phase_ok = all(v for v in phase_checks.values())
        extended_ok = all(v for v in extended_fields.values())
        links_ok = not placeholder_found
        korean_ok = korean_fields > 0 and (korean_found / korean_fields) >= 0.8
        precedent_ok = precedent_val is not None and precedent_val.get("precedents_analyzed", 0) > 0
        
        print(f"\n  Phase 1-4: {'✅ 통과' if phase_ok else '❌ 실패'}")
        print(f"  확장 필드: {'✅ 통과' if extended_ok else '❌ 실패'}")
        print(f"  링크 교체: {'✅ 통과' if links_ok else '❌ 실패'}")
        print(f"  한글 번역: {'✅ 통과' if korean_ok else '❌ 실패'}")
        print(f"  판례 검증: {'✅ 통과' if precedent_ok else '⚠️ 판례 없음 (선택)'}")
        
        all_passed = phase_ok and extended_ok and links_ok and korean_ok
        # 판례 검증은 선택사항 (FAISS DB 데이터에 따라 다름)
        
        print("\n" + "=" * 60)
        if all_passed:
            print("🎉 모든 검증 통과!")
        else:
            print("⚠️ 일부 검증 실패 - 수정 필요")
        print("=" * 60)
        
        # 결과 파일 저장
        output_file = "test_requirements_result.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"\n💾 전체 결과 저장: {output_file}")
        
        return all_passed
        
    except Exception as e:
        print(f"\n❌ 테스트 실행 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("\n🧪 요건 분석 시스템 검증 스크립트")
    print("=" * 60)
    
    # 실행
    success = asyncio.run(test_requirements_analysis())
    
    # 종료 코드
    exit(0 if success else 1)

