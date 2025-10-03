from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from models import HsCodeAnalysisRequest, HsCodeAnalysisResponse
from workflow import run_hs_analysis_workflow
from config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="HS Code Graph Analysis Service",
    description="LangGraph + Vector Search + LLM for HS Code Analysis",
    version="1.0.0"
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
    return {
        "status": "healthy",
        "service": "hs-graph-analysis",
        "version": "1.0.0"
    }

@app.post("/api/hs-code/analyze-graph", response_model=HsCodeAnalysisResponse)
async def analyze_hs_code_graph(request: HsCodeAnalysisRequest):
    import asyncio
    
    try:
        # 디버깅: 받은 데이터 확인
        logger.info(f"📥 Received request: {request.product_name}")
        
        # 타임아웃 설정 (90초)
        result = await asyncio.wait_for(
            run_hs_analysis_workflow(
                product_name=request.product_name,
                product_description=request.product_description,
                origin_country=request.origin_country or "KOR"
            ),
            timeout=90.0  # 90초 타임아웃
        )
        
        logger.info(f"✅ Analysis completed: {len(result.suggestions)} suggestions")
        return result
        
    except asyncio.TimeoutError:
        logger.error("⏰ Analysis timed out after 90 seconds")
        raise HTTPException(
            status_code=408, 
            detail="분석 시간이 초과되었습니다. 제품 설명을 더 간단하게 입력해주세요."
        )
    except ValueError as e:
        logger.error(f"❌ Validation error: {str(e)}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Analysis failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"분석 중 오류가 발생했습니다: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)