from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from models import HsCodeAnalysisRequest, HsCodeAnalysisResponse
from workflow import run_hs_analysis_workflow
from config import settings
import logging
import asyncio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 상수 정의
ANALYSIS_TIMEOUT = 90.0  # 분석 타임아웃 (초)
API_VERSION = "1.0.0"

app = FastAPI(
    title="HS Code Graph Analysis Service",
    description="LangGraph + Vector Search + LLM for HS Code Analysis",
    version=API_VERSION
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    """헬스 체크 엔드포인트"""
    return {
        "status": "healthy",
        "service": "hs-graph-analysis",
        "version": API_VERSION
    }

@app.post("/api/hs-code/analyze-graph", response_model=HsCodeAnalysisResponse)
async def analyze_hs_code_graph(request: HsCodeAnalysisRequest):
    """HS 코드 분석 API"""
    try:
        logger.info(f"📥 Received request: {request.product_name}")
        
        # 타임아웃 설정
        result = await asyncio.wait_for(
            run_hs_analysis_workflow(
                product_name=request.product_name,
                product_description=request.product_description,
                origin_country=request.origin_country or "KOR"
            ),
            timeout=ANALYSIS_TIMEOUT
        )
        
        logger.info(f"✅ Analysis completed: {len(result.suggestions)} suggestions")
        return result
        
    except asyncio.TimeoutError:
        logger.error(f"⏰ Analysis timed out after {ANALYSIS_TIMEOUT} seconds")
        raise HTTPException(
            status_code=408, 
            detail=f"분석 시간이 초과되었습니다 ({ANALYSIS_TIMEOUT}초). 제품 설명을 더 간단하게 입력해주세요."
        )
    except ValueError as e:
        logger.error(f"❌ Validation error: {str(e)}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Analysis failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"분석 중 오류가 발생했습니다: {str(e)}")

if __name__ == "__main__":
    print("=" * 80)
    print("⚠️ 주의: 이 파일은 더 이상 직접 실행할 필요가 없습니다!")
    print("=" * 80)
    print("")
    print("📌 HS Code & Tariff 분석 기능이 메인 AI Engine에 통합되었습니다.")
    print("")
    print("✅ 올바른 실행 방법:")
    print("   cd ai-engine")
    print("   python -m uvicorn main:app --reload --port 8000")
    print("")
    print("✅ 사용 가능한 엔드포인트:")
    print("   POST http://localhost:8000/hs-tariff/analyze")
    print("   GET  http://localhost:8000/hs-tariff/health")
    print("   GET  http://localhost:8000/hs-tariff/test")
    print("")
    print("📖 자세한 내용: ai-engine/PRECEDENTS_INTEGRATION.md")
    print("=" * 80)
    print("")
    print("🚀 테스트 목적으로 이 서버를 단독 실행하시겠습니까?")
    
    import uvicorn
    uvicorn.run(
        app, 
        host=settings.fastapi_host, 
        port=settings.fastapi_port,
        log_level="info"
    )