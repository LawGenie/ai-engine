"""
OpenAI 채팅 서비스 (통합 모듈)

Original Implementation:
- Location: chatbot-api/app/services/
- Files: openai_service.py, message.py (schemas), dependencies.py, config.py
- Author: JengInu
- Purpose: OpenAI GPT 기반 스트리밍 채팅 응답 생성

Integration Work:
- Date: 2025-10-13
- Purpose: chatbot-api 서비스를 메인 AI Engine으로 통합
- Changes: 
  * 독립 실행 서버(포트 8002) → 메인 AI Engine(포트 8000)의 모듈로 통합
  * 환경변수 기반 OpenAI 클라이언트 초기화
  * Pydantic 모델을 로컬로 정의하여 의존성 제거
  * 시스템 프롬프트: FDA 수출 관련 관세사 역할

Note:
원본 코드는 chatbot-api/ 디렉토리에 보존되어 있습니다.
이 모듈은 OpenAI API를 사용하여 스트리밍 방식으로 채팅 응답을 생성합니다.
원작자(JengInu)의 기여 이력은 chatbot-api/ 디렉토리의 Git 이력에서 확인 가능합니다.
"""
import json
import os
from typing import Generator
from openai import OpenAI
from pydantic import BaseModel, Field

# OpenAI 클라이언트
_openai_client = None

def get_openai_client() -> OpenAI:
    """OpenAI 클라이언트 싱글톤"""
    global _openai_client
    if _openai_client is None:
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다")
        _openai_client = OpenAI(api_key=api_key)
    return _openai_client

# 시스템 프롬프트
SYSTEM_PROMPT = '''
당신은 미국으로 화장품 및 식품을 수출하는 한국 기업을 돕는 관세사입니다.
항상 공손하고 친절한 말투로 설명하며, 질문자의 이해를 돕기 위해 단계별로 안내합니다.
미국 FDA의 공식 규정을 기반으로 정확하고 신뢰성 있는 정보를 제공합니다.
관세, 수출 절차, 라벨링 요건, 성분 제한, 시설 등록 등 화장품 및 식품 수출과 관련한 상세한 질문에 답변합니다.
법률적 해석이 필요한 경우 '전문가 상담'을 권유하고, 최신 정보를 확인할 것을 강조합니다.
개인정보 요구나 부적절한 질문에는 응답하지 않고 정중히 안내합니다.
항상 최신 FDA 가이드라인(https://www.fda.gov)을 참고하며, 구체적인 문서명이나 법령을 함께 안내합니다.
'''

class MessageRequest(BaseModel):
    """채팅 메시지 요청"""
    sender: str = Field(..., description="발신자 이름")
    message: str = Field(..., description="메시지 내용")

class MessageResponse(BaseModel):
    """채팅 메시지 응답"""
    sender: str = Field(..., description="발신자 이름")
    message: str = Field(..., description="메시지 내용")

class OpenAIChatService:
    """OpenAI 기반 채팅 서비스"""
    
    def __init__(self, model_name: str = "gpt-4o-mini", max_tokens: int = 700, temperature: float = 0.7):
        self.client = get_openai_client()
        self.model_name = model_name
        self.max_tokens = max_tokens
        self.temperature = temperature
    
    def generate_chat_stream(
        self, 
        user_message: str, 
        sender: str
    ) -> Generator[str, None, None]:
        """스트리밍 방식으로 채팅 응답 생성"""
        try:
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ]
            
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                stream=True,
            )
            
            for chunk in response:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    
                    payload = MessageResponse(
                        sender=sender,
                        message=content
                    )
                    yield json.dumps(
                        payload.model_dump(), 
                        ensure_ascii=False
                    ) + "\n"
                    
        except Exception as e:
            error_payload = MessageResponse(
                sender="system",
                message=f"오류가 발생했습니다: {str(e)}"
            )
            yield json.dumps(
                error_payload.model_dump(), 
                ensure_ascii=False
            ) + "\n"

