#!/usr/bin/env python3
"""
HS코드별 적절한 사이트 매핑 시스템
어떤 물품에 대해 어떤 사이트에서 요구사항을 찾을지 결정
"""

class HSSiteMapper:
    """HS코드별 사이트 매핑 클래스"""
    
    def __init__(self):
        # HS코드별 사이트 매핑
        self.hs_site_mapping = {
            # 전자제품 (84xx, 85xx)
            "8471": {
                "sites": ["FCC", "CBP"],
                "priority": ["FCC", "CBP"],
                "description": "컴퓨터 및 데이터 처리 장치"
            },
            "8517": {
                "sites": ["FCC", "CBP"],
                "priority": ["FCC", "CBP"],
                "description": "전기통신 장치"
            },
            
            # 식품 (09xx, 22xx)
            "0901": {
                "sites": ["FDA", "CBP"],
                "priority": ["FDA", "CBP"],
                "description": "커피, 차, 마테"
            },
            "2208": {
                "sites": ["FDA", "CBP"],
                "priority": ["FDA", "CBP"],
                "description": "알코올 음료"
            },
            
            # 의료용품 (30xx)
            "3004": {
                "sites": ["FDA", "CBP"],
                "priority": ["FDA", "CBP"],
                "description": "의료용품 및 의약품"
            },
            
            # 화학제품 (28xx, 29xx)
            "2800": {
                "sites": ["EPA", "CBP"],
                "priority": ["EPA", "CBP"],
                "description": "화학 원소 및 화합물"
            },
            
            # 섬유제품 (50xx-63xx)
            "6101": {
                "sites": ["CBP"],
                "priority": ["CBP"],
                "description": "의류 및 섬유제품"
            },
            
            # 기계류 (84xx)
            "8401": {
                "sites": ["CBP"],
                "priority": ["CBP"],
                "description": "원자로, 보일러, 기계류"
            }
        }
    
    def get_recommended_sites(self, hs_code: str) -> dict:
        """HS코드에 따른 추천 사이트 반환"""
        hs_prefix = hs_code.split('.')[0]
        
        # 정확한 매칭
        if hs_prefix in self.hs_site_mapping:
            return self.hs_site_mapping[hs_prefix]
        
        # 범위별 매칭
        hs_number = int(hs_prefix)
        
        if 8400 <= hs_number <= 8499 or 8500 <= hs_number <= 8599:
            # 전자제품
            return {
                "sites": ["FCC", "CBP"],
                "priority": ["FCC", "CBP"],
                "description": "전자제품 (범위 매칭)"
            }
        elif 900 <= hs_number <= 999 or 2200 <= hs_number <= 2299:
            # 식품
            return {
                "sites": ["FDA", "CBP"],
                "priority": ["FDA", "CBP"],
                "description": "식품 (범위 매칭)"
            }
        elif 3000 <= hs_number <= 3099:
            # 의료용품
            return {
                "sites": ["FDA", "CBP"],
                "priority": ["FDA", "CBP"],
                "description": "의료용품 (범위 매칭)"
            }
        elif 2800 <= hs_number <= 2999:
            # 화학제품
            return {
                "sites": ["EPA", "CBP"],
                "priority": ["EPA", "CBP"],
                "description": "화학제품 (범위 매칭)"
            }
        else:
            # 기본값 (CBP만)
            return {
                "sites": ["CBP"],
                "priority": ["CBP"],
                "description": "일반 상품 (기본 매칭)"
            }
    
    def should_scrape_site(self, hs_code: str, site_name: str) -> bool:
        """특정 사이트를 스크래핑해야 하는지 판단"""
        recommended = self.get_recommended_sites(hs_code)
        return site_name in recommended["sites"]
    
    def get_scraping_priority(self, hs_code: str) -> list:
        """스크래핑 우선순위 반환"""
        recommended = self.get_recommended_sites(hs_code)
        return recommended["priority"]

def test_hs_mapping():
    """HS코드 매핑 테스트"""
    mapper = HSSiteMapper()
    
    test_codes = [
        "8471.30.01",  # 노트북
        "0901.11.00",  # 커피
        "3004.90.91",  # 의료용 마스크
        "8517.12.00",  # 스마트폰
        "2208.20.00",  # 알코올
        "9999.99.99"   # 알 수 없는 코드
    ]
    
    print("🔍 HS코드별 사이트 매핑 테스트")
    print("=" * 60)
    
    for hs_code in test_codes:
        print(f"\n📦 HS코드: {hs_code}")
        recommended = mapper.get_recommended_sites(hs_code)
        print(f"  📋 추천 사이트: {recommended['sites']}")
        print(f"  🎯 우선순위: {recommended['priority']}")
        print(f"  📝 설명: {recommended['description']}")
        
        # 각 사이트별 스크래핑 여부 확인
        for site in ["FDA", "FCC", "CBP", "EPA"]:
            should_scrape = mapper.should_scrape_site(hs_code, site)
            status = "✅" if should_scrape else "❌"
            print(f"    {status} {site}: {'스크래핑' if should_scrape else '스킵'}")

if __name__ == "__main__":
    test_hs_mapping()
