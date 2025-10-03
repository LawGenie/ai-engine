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
    try:
        # 디버깅: 받은 데이터 확인
        logger.info(f"Received request data: {request.dict()}")
        logger.info(f"Product: {request.product_name}")
        
        result = await run_hs_analysis_workflow(
            product_name=request.product_name,
            product_description=request.product_description,
            origin_country=request.origin_country
        )
        
        logger.info(f"Analysis completed: {len(result.suggestions)} suggestions")
        return result
        
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Analysis failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)