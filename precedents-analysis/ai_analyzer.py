from openai import OpenAI
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
        
        self.client = OpenAI(api_key=self.api_key)
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
            response = self.client.chat.completions.create(
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
        # 판례를 성공/실패로 명확하게 분류
        success_precedents = []
        failure_precedents = []
        unknown_precedents = []
        
        for case in cbp_data:
            case_id = case.get('case_id', 'N/A')
            description = case.get('description', case.get('title', 'N/A'))
            link = case.get('link', '')
            
            # 링크가 있으면 포함
            if link:
                case_info = f"{case_id}: {description} | Link: {link}"
            else:
                case_info = f"{case_id}: {description}"
            
            status = case.get('status', 'UNKNOWN').upper()
            outcome = case.get('outcome', 'UNKNOWN').upper()
            
            # DENIED, REJECTED, EXCLUDED 등은 실패 사례 (더 느슨한 기준)
            if any(keyword in status for keyword in ['DENIED', 'REJECTED', 'EXCLUDED', 'REFUSED', 'PROHIBITED', 'NOT CLASSIFIED']) or \
               any(keyword in outcome for keyword in ['DENIED', 'REJECTED', 'EXCLUDED', 'REFUSED', 'PROHIBITED', 'NOT CLASSIFIED']) or \
               any(keyword in case_info.lower() for keyword in ['excluded', 'denied', 'rejected', 'not classifiable']):
                failure_precedents.append(case_info)
            # APPROVED, ACCEPTED, PERMITTED 등은 성공 사례 (더 느슨한 기준)
            elif any(keyword in status for keyword in ['APPROVED', 'ACCEPTED', 'PERMITTED', 'ALLOWED', 'GRANTED', 'CLASSIFIED']) or \
                 any(keyword in outcome for keyword in ['APPROVED', 'ACCEPTED', 'PERMITTED', 'ALLOWED', 'GRANTED', 'CLASSIFIED']) or \
                 any(keyword in case_info.lower() for keyword in ['approved', 'classified', 'permitted', 'allowed']):
                success_precedents.append(case_info)
            # REVIEW 상태는 검토 사례로 분류
            elif status == 'REVIEW' or outcome == 'REVIEW':
                unknown_precedents.append(case_info)
            else:
                # 기타 사례도 검토 사례로 분류
                unknown_precedents.append(case_info)
        
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

### ✅ 승인된 사례 (성공)
{chr(10).join(f"- {case}" for case in success_precedents) if success_precedents else "- 없음"}

### ❌ 거부된 사례 (실패)
{chr(10).join(f"- {case}" for case in failure_precedents) if failure_precedents else "- 없음"}

### 🔍 검토 필요 사례
{chr(10).join(f"- {case}" for case in unknown_precedents) if unknown_precedents else "- 없음"}

## 분석 요청사항
위의 판례 데이터를 바탕으로 다음 JSON 형태로 분석 결과를 제공해주세요:

{{
    "success_cases": ["승인된 사례를 여기에 그대로 나열"],
    "failure_cases": ["거부된 사례를 여기에 그대로 나열"],
    "review_cases": ["검토 필요 사례를 여기에 그대로 나열"],
    "actionable_insights": ["실행 가능한 인사이트 1", "실행 가능한 인사이트 2"],
    "risk_factors": ["위험 요소 1", "위험 요소 2"],
    "recommended_action": "권장 조치",
    "confidence_score": 0.85,
    "is_valid": true
}}

**중요**: 
- success_cases는 위의 "승인된 사례" 목록을 그대로 사용하세요 (없으면 빈 배열 [])
- failure_cases는 위의 "거부된 사례" 목록을 그대로 사용하세요 (없으면 빈 배열 [])
- 판례에서 "excluded" 또는 "denied"가 포함되면 무조건 failure_cases에 포함하세요
- actionable_insights와 risk_factors는 판례 내용을 분석하여 작성하세요
- **절대로 가짜 사례나 존재하지 않는 CBP 번호를 생성하지 마세요!**
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
                    "review_cases": analysis_data.get("review_cases", []),
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
        분석 실패 시 반환할 기본값입니다. 가짜 사례는 생성하지 않습니다.
        """
        return {
            "success_cases": [],  # 빈 배열 - 가짜 사례 생성 안 함
            "failure_cases": [],  # 빈 배열 - 가짜 사례 생성 안 함
            "review_cases": [],   # 빈 배열 - 가짜 사례 생성 안 함
            "actionable_insights": ["추가 데이터 수집 필요", "전문가 상담 권장"],
            "risk_factors": ["데이터 부족으로 인한 분석 제한"],
            "recommended_action": "실제 CBP 판례 데이터 수집 후 재분석 필요",
            "confidence_score": 0.1,
            "is_valid": False
        }
