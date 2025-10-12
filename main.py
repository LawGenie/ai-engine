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
from app.routers.requirements_router import router as requirements_router
from app.routers.verification_router import router as verification_router
from app.routers.product_registration_router import router as product_registration_router
from app.routers.keyword_extraction_router import router as keyword_extraction_router
from app.routers.tax_router import router as tax_router
from app.routers.precedents_router import router as precedents_router
from app.routers.hs_tariff_router import router as hs_tariff_router
from app.schemas.common import HealthResponse
from datetime import datetime
import asyncio
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    애플리케이션 생명주기 관리
    - 시작 시: 규제 모니터링 + 판례 분석 서비스 백그라운드 태스크 실행
    - 종료 시: 태스크 정리
    """
    # 시작 시
    print("🚀 AI Engine 시작 중...")
    
    # 1. 판례 분석 서비스 초기화
    from app.routers.precedents_router import initialize_precedents_services
    precedents_ready = initialize_precedents_services()
    if precedents_ready:
        print("✅ 판례 분석 서비스 초기화 완료")
    else:
        print("⚠️ 판례 분석 서비스 초기화 실패 (기능 비활성화)")
    
    # 2. HS Code & Tariff 분석 서비스 초기화
    from app.routers.hs_tariff_router import initialize_hs_tariff_service
    hs_tariff_ready = initialize_hs_tariff_service()
    if hs_tariff_ready:
        print("✅ HS Code & Tariff 분석 서비스 초기화 완료")
    else:
        print("⚠️ HS Code & Tariff 분석 서비스 초기화 실패 (기능 비활성화)")
    
    # 3. 규제 변경 모니터링 시작 (7일 주기)
    from app.services.requirements.regulatory_update_monitor import regulatory_monitor
    monitor_task = asyncio.create_task(regulatory_monitor.start_monitoring())
    print("🔍 규제 변경 모니터링 백그라운드 태스크 시작 (7일 주기)")
    
    yield
    
    # 종료 시
    print("🛑 AI Engine 종료 중...")
    monitor_task.cancel()
    try:
        await monitor_task
    except asyncio.CancelledError:
        print("✅ 모니터링 태스크 종료됨")

app = FastAPI(
    title="LawGenie AI Engine",
    description="AI-powered legal and trade analysis engine for MVP",
    version="1.0.0",
    lifespan=lifespan
)

# CORS 설정 추가 (Frontend 연결)
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(product_router)
app.include_router(chat_router)
app.include_router(requirements_router)
app.include_router(verification_router)
app.include_router(product_registration_router)
app.include_router(keyword_extraction_router)
app.include_router(tax_router)
app.include_router(precedents_router)  # 판례 분석 라우터
app.include_router(hs_tariff_router)   # HS Code & Tariff 분석 라우터

@app.get("/")
async def root():
    return {
        "message": "LawGenie AI Engine is running!",
        "version": "1.0.0",
        "services": ["requirements_analysis", "verification", "product_registration", "keyword_extraction", "chat", "precedents_analysis", "hs_tariff_analysis"]
    }

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """전체 서비스 상태 확인"""
    # 규제 모니터링 상태 추가
    from app.services.requirements.regulatory_update_monitor import regulatory_monitor
    from app.routers.precedents_router import analyzer, cbp_collector, vector_search
    from app.routers.hs_tariff_router import hs_service_ready
    
    monitor_status = regulatory_monitor.get_monitoring_status()
    precedents_ready = analyzer is not None and cbp_collector is not None and vector_search is not None
    
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(),
        services={
            "hs_code_recommendation": "active",
            "tariff_calculation": "active", 
            "requirements_analysis": "active",
            "precedents_analysis": "active" if precedents_ready else "inactive",
            "hs_tariff_analysis": "active" if hs_service_ready else "inactive",
            "detailed_regulations": "active",
            "testing_procedures": "active",
            "penalties": "active",
            "validity": "active",
            "requirements": "active",
            "product_registration": "active",
            "keyword_extraction": "active",
            "chat": "active",
            "regulatory_monitor": "active" if monitor_status['is_active'] else "inactive"
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
