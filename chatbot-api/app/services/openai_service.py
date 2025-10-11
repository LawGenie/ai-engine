import json
from typing import Generator
from openai import OpenAI
from app.core.config import settings
from app.schemas.message import MessageResponse

class OpenAIService:
    def __init__(self, client: OpenAI):
        self.client = client
    
    def generate_chat_stream(
        self, 
        user_message: str, 
        sender: str
    ) -> Generator[str, None, None]:
        try:
            messages = [
                {"role": "system", "content": settings.SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ]
            
            response = self.client.chat.completions.create(
                model=settings.MODEL_NAME,
                messages=messages,
                max_tokens=settings.MAX_TOKENS,
                temperature=settings.TEMPERATURE,
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