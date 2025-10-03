from fastapi import FastAPI
from dotenv import load_dotenv
import os

# .env 파일 로딩 (ai-engine 디렉토리에서)
import os
from pathlib import Path

# ai-engine 디렉토리의 .env 파일 찾기
current_dir = Path(__file__).parent
env_path = current_dir / ".env"
print(f"🔍 .env 파일 경로: {env_path}")
print(f"📁 .env 파일 존재: {env_path.exists()}")

if env_path.exists():
    load_dotenv(env_path)
    print(f"✅ .env 파일 로딩 성공")
else:
    print(f"❌ ai-engine/.env 파일을 찾을 수 없습니다")
    # 프로젝트 루트에서도 시도
    project_root = current_dir.parent
    root_env_path = project_root / ".env"
    print(f"🔄 프로젝트 루트 .env 시도: {root_env_path}")
    if root_env_path.exists():
        load_dotenv(root_env_path)
        print(f"✅ 프로젝트 루트 .env 파일 로딩 성공")
    else:
        print(f"❌ 프로젝트 루트 .env 파일도 없습니다")
        # 현재 디렉토리에서도 시도
        load_dotenv()
        print(f"🔄 현재 디렉토리에서 .env 로딩 시도")

# API 키 확인
api_key = os.getenv('TAVILY_API_KEY')
if api_key:
    print(f"🔑 TAVILY_API_KEY: {api_key[:10]}...")
else:
    print(f"❌ TAVILY_API_KEY를 찾을 수 없습니다")

from app.routers.product_router import router as product_router
from app.routers.chat_router import router as chat_router
from app.routers.requirements.requirement_router import router as requirement_router
from app.routers.tax_router import router as tax_router
from app.routers.testing_procedures_router import router as testing_procedures_router
from app.routers.detailed_regulations_router import router as detailed_regulations_router
from app.routers.penalties_router import router as penalties_router
from app.routers.validity_router import router as validity_router
from app.schemas.common import HealthResponse
from datetime import datetime

app = FastAPI(
    title="LawGenie AI Engine",
    description="AI-powered legal and trade analysis engine for MVP",
    version="1.0.0"
)

# 라우터 등록
app.include_router(product_router)
app.include_router(chat_router)
app.include_router(requirement_router)
app.include_router(tax_router)
app.include_router(testing_procedures_router)
app.include_router(detailed_regulations_router)
app.include_router(penalties_router)
app.include_router(validity_router)

@app.get("/")
async def root():
    return {
        "message": "LawGenie AI Engine is running!",
        "version": "1.0.0",
        "services": ["hs_code_recommendation", "tariff_calculation", "requirements_analysis", "precedents_analysis", "detailed_regulations", "chat"]
    }

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """전체 서비스 상태 확인"""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(),
        services={
            "hs_code_recommendation": "active",
            "tariff_calculation": "active", 
            "requirements_analysis": "active",
            "precedents_analysis": "active",
            "detailed_regulations": "active",
            "chat": "active"
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
