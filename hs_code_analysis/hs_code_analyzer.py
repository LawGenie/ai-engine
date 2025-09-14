"""
HS 코드 분석 서비스
GPT-4o-mini를 사용하여 제품 정보를 바탕으로 HS 코드를 추천합니다.
"""

from openai import OpenAI
import json
import logging
from typing import List, Dict, Any, Optional
import os
from datetime import datetime
from dotenv import load_dotenv
from prompts import get_hs_code_analysis_prompt

# .env 파일 로드
load_dotenv()

logger = logging.getLogger(__name__)

class HsCodeAnalyzer:
    def __init__(self):
        # OpenAI API 키 설정
        self.api_key = os.getenv('OPENAI_API_KEY')
        if not self.api_key or self.api_key == 'your-actual-openai-api-key-here':
            logger.error("OPENAI_API_KEY가 설정되지 않았습니다.")
            raise ValueError("OpenAI API key not configured")
        
        self.client = OpenAI(api_key=self.api_key)
        self.model = "gpt-4o-mini"
    
    async def analyze_hs_code(
        self, 
        product_name: str, 
        product_description: str, 
        origin_country: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        제품 정보를 바탕으로 HS 코드 3개를 추천합니다.
        
        Args:
            product_name: 제품명
            product_description: 제품 설명
            origin_country: 원산지 (선택사항)
            
        Returns:
            Dict: HS 코드 추천 결과
        """
        # 분석 시작 시간 기록
        start_time = datetime.now()
        start_timestamp = start_time.isoformat()
        
        try:
            logger.info(f"HS 코드 분석 시작 - 제품명: {product_name} (시작시간: {start_timestamp})")
            
            # 1. 프롬프트 생성
            prompt = get_hs_code_analysis_prompt(product_name, product_description, origin_country)
            
            # 2. GPT-4o-mini API 호출
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "당신은 미국 HS 코드 분류 전문가입니다. 정확하고 신뢰할 수 있는 HS 코드 분류를 제공해주세요."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                temperature=0.1,  # 일관된 결과를 위해 낮은 temperature
                max_tokens=2000
            )
            
            # 분석 완료 시간 기록
            end_time = datetime.now()
            end_timestamp = end_time.isoformat()
            processing_time_ms = (end_time - start_time).total_seconds() * 1000
            
            # 3. 응답 파싱
            analysis_text = response.choices[0].message.content
            logger.info(f"GPT 응답: {analysis_text[:500]}...")  # 디버깅용 로그
            analysis_result = self._parse_analysis_response(analysis_text, start_time, end_time)
            
            logger.info(f"HS 코드 분석 완료 - 제품명: {product_name} (완료시간: {end_timestamp}, 소요시간: {processing_time_ms:.2f}ms)")
            return analysis_result
            
        except Exception as e:
            logger.error(f"HS 코드 분석 실패: {str(e)}")
            # 실패 시 기본값 반환
            return self._get_default_analysis()
    
    def _parse_analysis_response(self, response_text: str, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
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
                suggestions = analysis_data.get("suggestions", [])
                
                # 각 제안에 대해 검증
                validated_suggestions = []
                for suggestion in suggestions:
                    validated_suggestion = {
                        "hsCode": suggestion.get("hsCode", ""),
                        "description": suggestion.get("description", ""),
                        "confidenceScore": float(suggestion.get("confidenceScore", 0.5)),
                        "reasoning": suggestion.get("reasoning", ""),
                        "usTariffRate": float(suggestion.get("usTariffRate", 0.0))
                    }
                    validated_suggestions.append(validated_suggestion)
                
                # 시간 정보 계산
                start_timestamp = start_time.isoformat()
                end_timestamp = end_time.isoformat()
                processing_time_ms = (end_time - start_time).total_seconds() * 1000
                
                logger.info(f"시간 정보 추가 - startTime: {start_timestamp}, endTime: {end_timestamp}, processingTimeMs: {processing_time_ms}")
                
                result = {
                    "suggestions": validated_suggestions,
                    "analysisSessionId": self._generate_session_id(),
                    "timestamp": end_timestamp,
                    "startTime": start_timestamp,
                    "endTime": end_timestamp,
                    "processingTimeMs": round(processing_time_ms, 2),
                    "isValid": True
                }
                
                logger.info(f"최종 응답 키: {list(result.keys())}")
                return result
            else:
                logger.warning("JSON 파싱 실패, 기본값 반환")
                return self._get_default_analysis()
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON 파싱 오류: {str(e)}")
            logger.error(f"파싱 시도한 문자열: {json_str[:1000]}...")
            return self._get_default_analysis()
    
    def _get_default_analysis(self) -> Dict[str, Any]:
        """
        분석 실패 시 반환할 기본값입니다.
        """
        current_time = datetime.now()
        return {
            "suggestions": [
                {
                    "hsCode": "9999.99.99.99",
                    "description": "분석을 위해 추가 정보가 필요합니다",
                    "confidenceScore": 0.1,
                    "reasoning": "제품 정보가 부족하여 정확한 분류가 어렵습니다",
                    "usTariffRate": 0.0
                }
            ],
            "analysisSessionId": self._generate_session_id(),
            "timestamp": current_time.isoformat(),
            "startTime": current_time.isoformat(),
            "endTime": current_time.isoformat(),
            "processingTimeMs": 0.0,
            "isValid": False
        }
    
    def _generate_session_id(self) -> str:
        """
        분석 세션 ID를 생성합니다.
        """
        return f"hs_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash(datetime.now().isoformat()) % 10000}"
