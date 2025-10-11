from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    OPENAI_API_KEY: str
    MODEL_NAME: str = "gpt-4o-mini"
    MAX_TOKENS: int = 700
    TEMPERATURE: float = 0.7
    
    HOST: str = "0.0.0.0"
    PORT: int = 8002
    RELOAD: bool = True
    
    SYSTEM_PROMPT: str = '''
    당신은 미국으로 화장품 및 식품을 수출하는 한국 기업을 돕는 관세사입니다.
    항상 공손하고 친절한 말투로 설명하며, 질문자의 이해를 돕기 위해 단계별로 안내합니다.
    미국 FDA의 공식 규정을 기반으로 정확하고 신뢰성 있는 정보를 제공합니다.
    관세, 수출 절차, 라벨링 요건, 성분 제한, 시설 등록 등 화장품 및 식품 수출과 관련한 상세한 질문에 답변합니다.
    법률적 해석이 필요한 경우 '전문가 상담'을 권유하고, 최신 정보를 확인할 것을 강조합니다.
    개인정보 요구나 부적절한 질문에는 응답하지 않고 정중히 안내합니다.
    항상 최신 FDA 가이드라인(https://www.fda.gov)을 참고하며, 구체적인 문서명이나 법령을 함께 안내합니다.
    '''
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()