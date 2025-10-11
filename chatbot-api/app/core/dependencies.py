from openai import OpenAI
from app.core.config import settings

def get_openai_client() -> OpenAI:
    return OpenAI(api_key=settings.OPENAI_API_KEY)