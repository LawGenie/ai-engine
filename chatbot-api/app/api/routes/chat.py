from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from openai import OpenAI

from app.schemas.message import MessageRequest, MessageResponse
from app.services.openai_service import OpenAIService
from app.core.dependencies import get_openai_client

router = APIRouter(prefix="/api", tags=["chat"])

@router.post("/chat")
async def chat(
    req: MessageRequest,
    client: OpenAI = Depends(get_openai_client)
):
    service = OpenAIService(client)
    
    return StreamingResponse(
        service.generate_chat_stream(req.message, req.sender),
        media_type="application/json"
    )

@router.get("/health")
async def health_check():
    return {"status": "healthy", "service": "chatbot-api"}