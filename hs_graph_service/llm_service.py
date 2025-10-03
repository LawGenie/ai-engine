from openai import OpenAI
from typing import List, Dict, Any
from config import settings
import json
import logging

logger = logging.getLogger(__name__)

class LLMService:
    def __init__(self):
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = settings.graph_model
    
    async def generate_reasoning(self, 
                               product_name: str, 
                               product_description: str,
                               candidates: List[Dict[str, Any]],
                               origin_country: str = "KOR") -> Dict[str, str]:
        """후보별 추천 이유 생성 (HS 분류 규칙 기반, 한국어 번역 포함)"""
        
        if not candidates:
            return {}
        
        # 후보 정보 준비 - Combined description 사용
        from vector_service import VectorService
        vector_service = VectorService()
        
        candidate_list = []
        for c in candidates:
            # Combined description 가져오기
            hierarchical_desc = vector_service.get_hierarchical_description(c["hts_number"])
            combined_description = hierarchical_desc.get("combined_description", c["description"])
            
            candidate_list.append({
                "hsCode": c["hts_number"],
                "hsDescription": c["description"],  # 원본 설명도 유지
                "hierarchicalDescription": combined_description,  # Combined description 추가
                "confidenceScore": c["similarity"]
            })
        
        # 한국어 전용 프롬프트 - 자연스러운 한국어 생성
        prompt = f"""당신은 미국 HS 코드 분류 전문가로서 국제무역 규정과 관세 분류에 대한 깊은 지식을 가지고 있습니다.

분류 시 고려사항:
1. 제품의 재질과 제조 공정 (무엇으로 만들어졌는가?)
2. 주요 용도와 기능 (어떻게 사용되는가?)
3. HS 코드 계층구조: 류(Chapter) → 호(Heading) → 소호(Subheading)
4. 일반해석규칙(GIR) 적용
5. 원산지국({origin_country})의 관세 최적화 고려
6. 특별 무역협정 (한국 제품의 경우 한미FTA)

분류할 제품:
- 제품명: {product_name}
- 제품 설명: {product_description}
- 원산지: {origin_country}

후보 HS 코드들 (벡터 유사도 순):
{json.dumps(candidate_list, indent=2)}

각 후보 코드에 대해 다음 4단계로 논리적 설명을 제공하세요:

1. 제품 분석: 이 제품이 무엇이며 핵심 특징은 무엇인가
2. 분류 근거: 재질/용도/기능을 바탕으로 왜 이 HS 코드가 적용되는가
3. 구별 요소: 다른 유사 코드들과 비교했을 때 이 코드가 더 적합한 이유
4. 신뢰도 평가: 얼마나 확실한지와 그 이유

JSON 배열로 출력 (한국어 추천근거만):
[
  {{
    "hsCode": "코드",
    "reasoning": "논리적 4단계 설명 (4-5 문장). 제품의 구체적 특징과 성분을 언급하고, 왜 이 코드가 다른 코드보다 적합한지 명확한 근거 제시. 예: '이 크림은 히알루론산 성분으로 보습이 주목적입니다', '립스틱과 달리 피부에 흡수되는 형태입니다' 등 구체적 비교 포함"
  }}
]

중요사항:
1. 자연스러운 한국어로 작성 (번역체 금지)
2. 구체적 제품 특성(성분, 형태, 기능)을 근거로 사용
3. 유사 코드와 비교하여 차이점 명시 (예: "립스틱 코드와 달리", "세정제와 다르게")
4. 분류 결정에 영향을 준 구체적 요소 언급
5. 모호한 표현 금지 - 구체적 근거 기반 서술
6. 각 HS 코드별로 고유한 구별 요소 제시
7. JSON 배열만 출력, 추가 설명 금지"""

        try:
            # 타임아웃과 함께 LLM 호출 (더 긴 응답을 위해 max_tokens 증가)
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=1500,  # 이중 언어 응답을 위해 증가
                timeout=30.0  # 30초 타임아웃
            )
            
            text = response.choices[0].message.content or "[]"
            logger.info(f"🤖 LLM raw response: {text[:200]}...")
            
            # JSON 추출
            start = text.find("[")
            end = text.rfind("]") + 1
            
            if start != -1 and end != -1:
                json_str = text[start:end]
                reasoning_list = json.loads(json_str)
                
                # 한국어 추천근거 직접 반환
                return {
                    item.get("hsCode", ""): item.get("reasoning", "")
                    for item in reasoning_list
                    if isinstance(item, dict)
                }
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON parsing failed: {e}")
            logger.error(f"Raw response: {text}")
        except Exception as e:
            logger.error(f"❌ LLM reasoning generation failed: {e}")
        
        # 폴백: 자연스러운 한국어 기본 설명
        return {
            c["hts_number"]: f"이 제품은 {product_name}로 분석됩니다. {c['description'][:30]}... 분류에 가장 적합한 것으로 판단됩니다. 제품의 특성과 용도를 고려할 때 이 HS 코드가 적절합니다. 다른 유사 코드들보다 제품 특징과 잘 맞아 신뢰할 수 있는 분류입니다."
            for c in candidates
        }