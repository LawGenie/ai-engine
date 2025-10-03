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
                               candidates: List[Dict[str, Any]]) -> Dict[str, str]:
        """후보별 추천 이유 생성"""
        
        if not candidates:
            return {}
        
        # 후보 정보 준비
        candidate_list = [
            {
                "hsCode": c["hts_number"],
                "hsDescription": c["description"],
                "confidenceScore": c["similarity"]
            }
            for c in candidates
        ]
        
        prompt = f"""You are an expert in U.S. HS code classification.
Given the product and candidate HS codes (retrieved via vector search), produce a concise justification (≤2 sentences) per candidate.

Product:
- Name: {product_name}
- Description: {product_description}

Candidates:
{json.dumps(candidate_list, indent=2)}

Output strictly as JSON array with this schema:
[
  {{"hsCode": "string", "reasoning": "string"}}
]
No extra text outside JSON."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=1000
            )
            
            text = response.choices[0].message.content or "[]"
            
            # JSON 추출
            start = text.find("[")
            end = text.rfind("]") + 1
            
            if start != -1 and end != -1:
                json_str = text[start:end]
                reasoning_list = json.loads(json_str)
                
                # 딕셔너리로 변환
                return {
                    item.get("hsCode", ""): item.get("reasoning", "")
                    for item in reasoning_list
                    if isinstance(item, dict)
                }
            
        except Exception as e:
            logger.error(f"LLM reasoning generation failed: {e}")
        
        # 폴백: 기본 이유
        return {
            c["hts_number"]: "Selected based on vector similarity between product description and HTS description."
            for c in candidates
        }