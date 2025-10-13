"""
채팅 라우터 (통합 레이어)

Original Implementation:
- Location: chatbot-api/
- Files: app/api/routes/chat.py, app/services/openai_service.py, app/schemas/message.py
- Author: JengInu
- Purpose: OpenAI 기반 FDA 수출 관련 챗봇 API

Integration Work:
- Date: 2025-10-13
- Purpose: 메인 AI Engine에 챗봇 기능 통합 (포트 8002 → 8000 통합)
- Changes: OpenAI 채팅 서비스를 app/services/openai_chat_service.py로 통합, 
           Backend API 연결 경로 변경 (8002/api/chat → 8000/chat/api)

Note: 
원본 코드는 chatbot-api/ 디렉토리에 보존되어 있으며,
이 파일은 기존 챗봇 기능과 새로운 OpenAI 스트리밍 API를 모두 제공합니다.
원작자(JengInu)의 기여 이력은 chatbot-api/ 디렉토리의 Git 이력에서 확인 가능합니다.
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import Dict, Any
from app.schemas.product import ChatRequest, ChatResponse
from app.schemas.common import BaseResponse
from app.services.openai_chat_service import OpenAIChatService, MessageRequest

router = APIRouter(prefix="/chat", tags=["chat"])

# OpenAI 채팅 서비스 (chatbot-api 통합)
chat_service = None

def get_chat_service():
    """OpenAI 채팅 서비스 싱글톤"""
    global chat_service
    if chat_service is None:
        try:
            chat_service = OpenAIChatService()
        except ValueError:
            # OPENAI_API_KEY가 없는 경우
            pass
    return chat_service

@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """챗봇 API"""
    try:
        # 사용자 메시지 분석
        intent = analyze_user_intent(request.message)
        
        # 의도별 처리
        if intent == "tariff":
            return await handle_tariff_question(request)
        elif intent == "requirements":
            return await handle_requirements_question(request)
        elif intent == "precedents":
            return await handle_precedents_question(request)
        elif intent == "comprehensive":
            return await handle_comprehensive_question(request)
        else:
            return await handle_general_question(request)
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"챗봇 처리 중 오류가 발생했습니다: {str(e)}")

def analyze_user_intent(message: str) -> str:
    """사용자 의도 분석"""
    message_lower = message.lower()
    
    if any(keyword in message_lower for keyword in ["관세", "tariff", "세금", "세율"]):
        return "tariff"
    elif any(keyword in message_lower for keyword in ["요구사항", "requirements", "서류", "인증"]):
        return "requirements"
    elif any(keyword in message_lower for keyword in ["판례", "precedents", "사례", "경험"]):
        return "precedents"
    elif any(keyword in message_lower for keyword in ["종합", "전체", "모든", "분석"]):
        return "comprehensive"
    else:
        return "general"

async def handle_tariff_question(request: ChatRequest) -> ChatResponse:
    """관세 관련 질문 처리"""
    if not request.product_id:
        return ChatResponse(
            answer="관세 정보를 조회하려면 상품 ID가 필요합니다.",
            sources=[],
            confidence=0.0,
            analysis_type="tariff"
        )
    
    # TODO: 실제 관세 분석 결과 조회
    return ChatResponse(
        answer="해당 상품의 관세율은 5%입니다. 추가적인 관세 정책 정보가 필요하시면 말씀해 주세요.",
        sources=[
            {"title": "관세 계산 결과", "url": "https://example.com", "type": "AI 분석"}
        ],
        confidence=0.85,
        analysis_type="tariff"
    )

async def handle_requirements_question(request: ChatRequest) -> ChatResponse:
    """요구사항 관련 질문 처리"""
    if not request.product_id:
        return ChatResponse(
            answer="요구사항 정보를 조회하려면 상품 ID가 필요합니다.",
            sources=[],
            confidence=0.0,
            analysis_type="requirements"
        )
    
    # TODO: 실제 요구사항 분석 결과 조회
    return ChatResponse(
        answer="해당 상품의 주요 요구사항은 FDA 승인과 원산지 증명서입니다. 자세한 서류 목록을 확인하시겠습니까?",
        sources=[
            {"title": "요구사항 분석 결과", "url": "https://example.com", "type": "AI 분석"}
        ],
        confidence=0.80,
        analysis_type="requirements"
    )

async def handle_precedents_question(request: ChatRequest) -> ChatResponse:
    """판례 관련 질문 처리"""
    if not request.product_id:
        return ChatResponse(
            answer="판례 정보를 조회하려면 상품 ID가 필요합니다.",
            sources=[],
            confidence=0.0,
            analysis_type="precedents"
        )
    
    # TODO: 실제 판례 분석 결과 조회
    return ChatResponse(
        answer="해당 상품의 통관 성공률은 85%입니다. 주요 성공 요인은 정확한 HS코드 분류와 완전한 서류 준비입니다.",
        sources=[
            {"title": "판례 분석 결과", "url": "https://example.com", "type": "AI 분석"}
        ],
        confidence=0.75,
        analysis_type="precedents"
    )

async def handle_comprehensive_question(request: ChatRequest) -> ChatResponse:
    """종합 분석 질문 처리"""
    if not request.product_id:
        return ChatResponse(
            answer="종합 분석을 위해서는 상품 ID가 필요합니다.",
            sources=[],
            confidence=0.0,
            analysis_type="comprehensive"
        )
    
    # TODO: 실제 종합 분석 결과 조회
    return ChatResponse(
        answer="종합 분석 결과: 관세율 5%, 요구사항 3개, 통관 성공률 85%. 전체적으로 수출 가능성이 높은 상품입니다.",
        sources=[
            {"title": "종합 분석 결과", "url": "https://example.com", "type": "AI 분석"}
        ],
        confidence=0.80,
        analysis_type="comprehensive"
    )

async def handle_general_question(request: ChatRequest) -> ChatResponse:
    """일반 질문 처리"""
    return ChatResponse(
        answer="안녕하세요! 관세, 요구사항, 판례 분석에 대해 도움을 드릴 수 있습니다. 구체적인 질문을 해주시면 더 정확한 답변을 드릴 수 있습니다.",
        sources=[],
        confidence=0.5,
        analysis_type="general"
    )

# ==================== OpenAI Chatbot API (통합) ====================

@router.post("/api")
async def chat_with_openai(request: MessageRequest):
    """
    OpenAI 기반 채팅 API (chatbot-api에서 통합)
    
    Backend API의 ChatService가 호출하는 엔드포인트
    URL: POST /chat/api
    """
    service = get_chat_service()
    
    if service is None:
        raise HTTPException(
            status_code=503,
            detail="채팅 서비스를 사용할 수 없습니다. OPENAI_API_KEY를 설정해주세요."
        )
    
    return StreamingResponse(
        service.generate_chat_stream(request.message, request.sender),
        media_type="application/json"
    )
