import openai
import json
import logging
from typing import List, Dict, Any
import os
from datetime import datetime
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

logger = logging.getLogger(__name__)

class PrecedentsAnalyzer:
    def __init__(self):
        # OpenAI API 키 설정 (.env 파일에서 가져오기)
        self.api_key = os.getenv('OPENAI_API_KEY')
        if not self.api_key or self.api_key == 'your-actual-openai-api-key-here':
            logger.error("OPENAI_API_KEY가 설정되지 않았습니다.")
            logger.error("다음 방법 중 하나로 설정해주세요:")
            logger.error("1. .env 파일에 OPENAI_API_KEY=your-key-here 추가")
            logger.error("2. 환경변수로 export OPENAI_API_KEY='your-key-here'")
            raise ValueError("OpenAI API key not configured")
        
        openai.api_key = self.api_key
        self.model = "gpt-4o-mini"
    
    async def analyze_precedents(self, product_data: Dict[str, Any], cbp_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        GPT-4o-mini를 사용하여 판례 분석을 수행합니다.
        """
        try:
            logger.info("AI 분석 시작")
            
            # 1. 프롬프트 생성
            prompt = self._create_analysis_prompt(product_data, cbp_data)
            
            # 2. GPT-4o-mini API 호출
            response = await openai.ChatCompletion.acreate(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "당신은 미국 수입 규제 전문가입니다. 주어진 상품 정보와 판례 데이터를 바탕으로 상세한 분석을 제공해주세요."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                temperature=0.3,
                max_tokens=2000
            )
            
            # 3. 응답 파싱
            analysis_text = response.choices[0].message.content
            analysis_result = self._parse_analysis_response(analysis_text)
            
            logger.info("AI 분석 완료")
            return analysis_result
            
        except Exception as e:
            logger.error(f"AI 분석 실패: {str(e)}")
            # 실패 시 기본값 반환
            return self._get_default_analysis()
    
    def _create_analysis_prompt(self, product_data: Dict[str, Any], cbp_data: List[Dict[str, Any]]) -> str:
        """
        분석을 위한 프롬프트를 생성합니다.
        """
        prompt = f"""
다음 상품 정보와 관련 판례 데이터를 분석하여 JSON 형태로 결과를 제공해주세요.

## 상품 정보
- 상품명: {product_data.get('product_name', 'N/A')}
- 설명: {product_data.get('description', 'N/A')}
- HS코드: {product_data.get('hs_code', 'N/A')}
- 원산지: {product_data.get('origin_country', 'N/A')}
- 가격: ${product_data.get('price', 0)}
- FOB 가격: ${product_data.get('fob_price', 0)}

## 관련 판례 데이터
{json.dumps(cbp_data, ensure_ascii=False, indent=2)}

## 분석 요청사항
다음 JSON 형태로 분석 결과를 제공해주세요:

{{
    "success_cases": ["성공 사례 1", "성공 사례 2"],
    "failure_cases": ["실패 사례 1", "실패 사례 2"],
    "actionable_insights": ["실행 가능한 인사이트 1", "실행 가능한 인사이트 2"],
    "risk_factors": ["위험 요소 1", "위험 요소 2"],
    "recommended_action": "권장 조치",
    "confidence_score": 0.85,
    "is_valid": true
}}

분석 시 다음 사항을 고려해주세요:
1. 상품의 HS코드와 관련된 규제 요구사항
2. 원산지별 특별 규정
3. 유사한 상품의 성공/실패 패턴
4. FDA, CBP 규정 준수 요구사항
5. 실무적으로 실행 가능한 조치사항
"""
        return prompt
    
    def _parse_analysis_response(self, response_text: str) -> Dict[str, Any]:
        """
        GPT 응답을 파싱하여 구조화된 데이터로 변환합니다.
        """
        try:
            # JSON 부분만 추출
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start != -1 and json_end != -1:
                json_str = response_text[json_start:json_end]
                analysis_data = json.loads(json_str)
                
                # 필수 필드 검증 및 기본값 설정
                return {
                    "success_cases": analysis_data.get("success_cases", []),
                    "failure_cases": analysis_data.get("failure_cases", []),
                    "actionable_insights": analysis_data.get("actionable_insights", []),
                    "risk_factors": analysis_data.get("risk_factors", []),
                    "recommended_action": analysis_data.get("recommended_action", "추가 분석 필요"),
                    "confidence_score": float(analysis_data.get("confidence_score", 0.5)),
                    "is_valid": bool(analysis_data.get("is_valid", True))
                }
            else:
                logger.warning("JSON 파싱 실패, 기본값 반환")
                return self._get_default_analysis()
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON 파싱 오류: {str(e)}")
            return self._get_default_analysis()
    
    def _get_default_analysis(self) -> Dict[str, Any]:
        """
        분석 실패 시 반환할 기본값입니다.
        """
        return {
            "success_cases": ["분석을 위해 추가 데이터가 필요합니다"],
            "failure_cases": ["일반적인 수입 거부 사유를 확인하세요"],
            "actionable_insights": ["FDA 인증서 준비", "HS코드 정확성 확인"],
            "risk_factors": ["규제 변경 가능성", "문서 부족"],
            "recommended_action": "전문가 상담 권장",
            "confidence_score": 0.3,
            "is_valid": False
        }
