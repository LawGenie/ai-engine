"""
HS 코드 분석을 위한 프롬프트 템플릿
"""

def get_hs_code_analysis_prompt(product_name: str, product_description: str, origin_country: str = None) -> str:
    """
    HS 코드 분석을 위한 프롬프트를 생성합니다.
    """
    origin_info = f"- 원산지: {origin_country}" if origin_country else "- 원산지: 미지정"
    
    prompt = f"""
당신은 미국 HS 코드 분류 전문가입니다. 주어진 제품 정보를 바탕으로 가장 적합한 HS 코드 3개를 추천해주세요.

**제품 정보:**
- 제품명: {product_name}
- 제품 설명: {product_description}
{origin_info}

**분류 기준:**
1. 제품의 본질적 특성 (재질, 용도, 기능)
2. 미국 관세법의 일반 분류 규칙 (GRI 1-6)
3. 가장 구체적인 분류를 우선 선택
4. 용도가 명확한 경우 용도 기준 우선

다음 JSON 형식으로 응답해주세요:

```json
{{
  "suggestions": [
    {{
      "hsCode": "XXXX.XX.XX.XX",
      "description": "미국 관세청 공식 설명",
      "confidenceScore": 0.XX,
      "reasoning": "GRI 규칙 적용 근거 및 추천 이유",
      "usTariffRate": 0.XXXX
    }},
    {{
      "hsCode": "XXXX.XX.XX.XX",
      "description": "미국 관세청 공식 설명",
      "confidenceScore": 0.XX,
      "reasoning": "GRI 규칙 적용 근거 및 추천 이유",
      "usTariffRate": 0.XXXX
    }},
    {{
      "hsCode": "XXXX.XX.XX.XX",
      "description": "미국 관세청 공식 설명",
      "confidenceScore": 0.XX,
      "reasoning": "GRI 규칙 적용 근거 및 추천 이유",
      "usTariffRate": 0.XXXX
    }}
  ]
}}
```

**중요사항:**
- HS 코드는 반드시 10자리 형식 (XXXX.XX.XX.XX)
- 신뢰도는 0.00~1.00 사이의 소수점 둘째 자리
- 가장 적합한 코드를 첫 번째로 배치
- 불확실한 경우 신뢰도를 낮게 설정
- 관세율은 일반 관세율 기준으로 제공
"""
    return prompt
