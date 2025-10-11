from fastapi import FastAPI
import uvicorn

from app.core.config import settings
from app.api.routes import chat

app = FastAPI(
    title="Chatbot API",
    description="FDA 수출 관련 챗봇 API",
    version="1.0.0"
)

# 라우터 등록
app.include_router(chat.router)

@app.get("/")
def read_root():
    return {
        "message": "Chatbot API Server is running",
        "port": settings.PORT,
        "docs": f"http://{settings.HOST}:{settings.PORT}/docs"
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.RELOAD
    )