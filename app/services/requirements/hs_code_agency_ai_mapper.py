"""
HS 코드 → 기관 매핑 AI 생성기
GPT를 사용하여 HS 코드에 적합한 규제 기관을 자동으로 추천
"""

import json
import asyncio
from typing import Dict, List, Any, Optional
from openai import AsyncOpenAI
import os


class HsCodeAgencyAiMapper:
    """HS 코드 기반 기관 매핑 AI 생성기"""
    
    def __init__(self):
        self.openai_client = AsyncOpenAI()
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        
        # 매핑 생성 프롬프트
        self.mapping_prompt = """
You are an expert in US import regulations and HS code classification.

Given an HS code and product information, identify which US government agencies regulate this product for import.

## HS Code: {hs_code}
## Product Name: {product_name}
## Product Category: {product_category}

## Available US Agencies:
- **FDA** (Food and Drug Administration): Food, drugs, cosmetics, medical devices, dietary supplements
- **USDA** (US Department of Agriculture): Agricultural products, meat, poultry, plants
- **EPA** (Environmental Protection Agency): Chemicals, pesticides, hazardous materials
- **FCC** (Federal Communications Commission): Electronic devices with radio/wireless, telecommunications
- **CPSC** (Consumer Product Safety Commission): Consumer products, toys, children's products
- **CBP** (Customs and Border Protection): All imports (general customs)
- **DOT** (Department of Transportation): Vehicles, hazardous materials transport
- **TTB** (Alcohol and Tobacco Tax and Trade Bureau): Alcohol, tobacco products

## Your Task:
Analyze the HS code and product to determine:
1. **Primary agencies** (directly regulate this product)
2. **Secondary agencies** (may have additional requirements)
3. **Search keywords** (for finding regulations)
4. **Key requirements** (typical requirements for this product)
5. **Confidence score** (0.0-1.0)

## Response Format (JSON):
{{
    "hs_code": "{hs_code}",
    "product_category": "Identified category",
    "primary_agencies": ["FDA", "CPSC"],
    "secondary_agencies": ["FTC"],
    "search_keywords": ["cosmetic", "skincare", "serum", "ingredient"],
    "key_requirements": [
        "Cosmetic registration (VCRP)",
        "Ingredient safety compliance",
        "Labeling requirements (INCI names)",
        "Consumer safety standards"
    ],
    "confidence_score": 0.9,
    "reasoning": "Brief explanation of why these agencies were selected",
    "hs_code_description": "What this HS code typically covers"
}}

## Guidelines:
1. Be specific - only include agencies that actually regulate this product type
2. Primary agencies = direct regulatory authority
3. Secondary agencies = may have labeling/marketing requirements
4. Include practical search keywords for finding regulations
5. List concrete requirements, not vague statements
6. Confidence score based on:
   - 0.9-1.0: Very clear (e.g., food → FDA)
   - 0.7-0.9: Clear with some variation
   - 0.5-0.7: Multiple possible interpretations
   - <0.5: Unclear or unusual HS code

Return ONLY valid JSON, no additional text.
"""
    
    async def generate_mapping(
        self, 
        hs_code: str, 
        product_name: str = "",
        product_category: str = ""
    ) -> Dict[str, Any]:
        """
        AI를 사용하여 HS 코드 → 기관 매핑 생성
        
        Args:
            hs_code: HS 코드 (예: "330499")
            product_name: 제품명 (선택)
            product_category: 제품 카테고리 (선택)
        
        Returns:
            {
                "hs_code": str,
                "product_category": str,
                "primary_agencies": List[str],
                "secondary_agencies": List[str],
                "search_keywords": List[str],
                "key_requirements": List[str],
                "confidence_score": float,
                "reasoning": str
            }
        """
        print(f"🤖 AI 기관 매핑 생성 시작 - HS: {hs_code}, 제품: {product_name}")
        
        try:
            # 프롬프트 생성
            prompt = self.mapping_prompt.format(
                hs_code=hs_code,
                product_name=product_name or "Unknown",
                product_category=product_category or "Unknown"
            )
            
            # GPT 호출
            response = await self.openai_client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert in US import regulations and HS code classification."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1,  # 일관성을 위해 낮은 temperature
                response_format={"type": "json_object"},
                max_tokens=1000
            )
            
            # 응답 파싱
            result = json.loads(response.choices[0].message.content)
            
            # 토큰 사용량 로깅
            tokens_used = response.usage.total_tokens
            cost = self._calculate_cost(tokens_used)
            
            print(f"✅ AI 기관 매핑 생성 완료")
            print(f"  - Primary: {result.get('primary_agencies', [])}")
            print(f"  - Secondary: {result.get('secondary_agencies', [])}")
            print(f"  - Confidence: {result.get('confidence_score', 0):.2f}")
            print(f"  - Tokens: {tokens_used}, Cost: ${cost:.4f}")
            
            # 메타데이터 추가
            result["tokens_used"] = tokens_used
            result["cost"] = cost
            result["model"] = self.model
            
            return result
            
        except Exception as e:
            print(f"❌ AI 기관 매핑 생성 실패: {e}")
            return self._get_default_mapping(hs_code, product_name, product_category)
    
    def _calculate_cost(self, tokens: int) -> float:
        """토큰 비용 계산 (GPT-4o-mini 기준)"""
        # GPT-4o-mini: $0.00015/1K input, $0.0006/1K output
        # 대략 입력:출력 = 3:1
        input_tokens = int(tokens * 0.75)
        output_tokens = int(tokens * 0.25)
        
        input_cost = (input_tokens / 1000) * 0.00015
        output_cost = (output_tokens / 1000) * 0.0006
        
        return input_cost + output_cost
    
    def _get_default_mapping(
        self, 
        hs_code: str, 
        product_name: str,
        product_category: str
    ) -> Dict[str, Any]:
        """AI 실패 시 기본 매핑 반환"""
        # HS 코드 첫 2자리로 대략적인 카테고리 판단
        hs_2digit = hs_code[:2] if len(hs_code) >= 2 else "00"
        
        # 기본 매핑 (휴리스틱)
        basic_mappings = {
            "33": {"primary": ["FDA"], "category": "Cosmetics"},  # 화장품
            "21": {"primary": ["FDA", "USDA"], "category": "Food"},  # 식품
            "84": {"primary": ["FCC", "CPSC"], "category": "Electronics"},  # 전자기기
            "85": {"primary": ["FCC", "CPSC"], "category": "Electronics"},  # 전기기기
            "95": {"primary": ["CPSC"], "category": "Toys"},  # 장난감
        }
        
        mapping = basic_mappings.get(hs_2digit, {
            "primary": ["FDA", "USDA", "EPA", "FCC", "CPSC"],
            "category": "General"
        })
        
        return {
            "hs_code": hs_code,
            "product_category": mapping["category"],
            "primary_agencies": mapping["primary"],
            "secondary_agencies": ["CBP"],
            "search_keywords": [product_name.lower()] if product_name else [],
            "key_requirements": ["Import compliance check required"],
            "confidence_score": 0.3,  # 낮은 신뢰도
            "reasoning": "AI mapping failed, using basic heuristic",
            "tokens_used": 0,
            "cost": 0.0,
            "model": "fallback"
        }
    
    async def batch_generate_mappings(
        self, 
        hs_codes: List[str],
        products: Optional[List[Dict[str, str]]] = None
    ) -> List[Dict[str, Any]]:
        """
        여러 HS 코드에 대해 배치로 매핑 생성
        
        Args:
            hs_codes: HS 코드 리스트
            products: [{"hs_code": "...", "name": "...", "category": "..."}]
        
        Returns:
            매핑 결과 리스트
        """
        print(f"🔄 배치 매핑 생성 시작 - {len(hs_codes)}개 HS 코드")
        
        tasks = []
        for i, hs_code in enumerate(hs_codes):
            product_name = ""
            product_category = ""
            
            if products and i < len(products):
                product_name = products[i].get("name", "")
                product_category = products[i].get("category", "")
            
            task = self.generate_mapping(hs_code, product_name, product_category)
            tasks.append(task)
        
        # 병렬 실행 (최대 5개씩)
        results = []
        for i in range(0, len(tasks), 5):
            batch = tasks[i:i+5]
            batch_results = await asyncio.gather(*batch)
            results.extend(batch_results)
            
            # API 레이트 리밋 방지
            if i + 5 < len(tasks):
                await asyncio.sleep(1)
        
        print(f"✅ 배치 매핑 생성 완료 - {len(results)}개")
        return results


# 싱글톤 인스턴스
_mapper_instance = None


def get_hs_code_mapper() -> HsCodeAgencyAiMapper:
    """HsCodeAgencyAiMapper 싱글톤 인스턴스 반환"""
    global _mapper_instance
    
    if _mapper_instance is None:
        _mapper_instance = HsCodeAgencyAiMapper()
    
    return _mapper_instance


# 테스트용 메인
if __name__ == "__main__":
    async def test():
        mapper = HsCodeAgencyAiMapper()
        
        # 단일 매핑 테스트
        test_cases = [
            {"hs_code": "330499", "name": "vitamin c serum", "category": "cosmetics"},
            {"hs_code": "8471", "name": "laptop computer", "category": "electronics"},
            {"hs_code": "2106", "name": "ginseng extract", "category": "dietary supplement"},
        ]
        
        for case in test_cases:
            print(f"\n{'='*80}")
            result = await mapper.generate_mapping(
                case["hs_code"],
                case["name"],
                case["category"]
            )
            
            print(f"\n결과:")
            print(json.dumps(result, indent=2, ensure_ascii=False))
    
    asyncio.run(test())

