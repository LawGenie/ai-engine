"""
HS 코드 분석 API 테스트 스크립트
"""

import asyncio
import httpx
import json

async def test_hs_code_analysis():
    """HS 코드 분석 API를 테스트합니다."""
    
    # 테스트 데이터
    test_cases = [
        {
            "product_name": "Premium Vitamin C Serum",
            "product_description": "High-concentration Vitamin C serum effective for skin tone improvement and anti-aging. Contains 20% Vitamin C and hyaluronic acid, suitable for all skin types.",
            "origin_country": "KOR"
        },
        {
            "product_name": "Korean Rice Snack",
            "product_description": "Traditional Korean rice snacks made with organic brown rice and seasoned with natural ingredients. Crispy texture with savory taste.",
            "origin_country": "KOR"
        },
        {
            "product_name": "Smartphone Case",
            "product_description": "Protective case for iPhone 15 Pro made of silicone material with shock absorption features.",
            "origin_country": "CHN"
        }
    ]
    
    base_url = "http://127.0.0.1:8001"  # HS 코드 분석 전용 포트
    
    async with httpx.AsyncClient() as client:
        # 헬스 체크
        try:
            health_response = await client.get(f"{base_url}/health")
            print(f"✅ 서비스 상태: {health_response.json()}")
        except Exception as e:
            print(f"❌ 서비스 연결 실패: {e}")
            return
        
        # 각 테스트 케이스 실행
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n🧪 테스트 케이스 {i}: {test_case['product_name']}")
            print("-" * 50)
            
            try:
                response = await client.post(
                    f"{base_url}/api/hs-code/analyze",
                    json=test_case,
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"✅ 분석 성공!")
                    print(f"📋 세션 ID: {result['analysisSessionId']}")
                    print(f"⏰ 타임스탬프: {result['timestamp']}")
                    print(f"✅ 유효성: {result['isValid']}")
                    
                    print(f"\n📊 추천 HS 코드:")
                    for j, suggestion in enumerate(result['suggestions'], 1):
                        print(f"  {j}. {suggestion['hsCode']}")
                        print(f"     설명: {suggestion['description']}")
                        print(f"     신뢰도: {suggestion['confidenceScore']:.2f}")
                        print(f"     관세율: {suggestion['usTariffRate']:.4f}")
                        print(f"     추천 이유: {suggestion['reasoning']}")
                        print()
                else:
                    print(f"❌ API 오류: {response.status_code}")
                    print(f"오류 내용: {response.text}")
                    
            except Exception as e:
                print(f"❌ 요청 실패: {e}")

if __name__ == "__main__":
    print("🚀 HS 코드 분석 API 테스트 시작")
    print("=" * 60)
    asyncio.run(test_hs_code_analysis())
    print("\n✅ 테스트 완료")
