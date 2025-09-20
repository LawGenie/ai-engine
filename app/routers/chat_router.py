from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from app.schemas.product import ChatRequest, ChatResponse
from app.schemas.common import BaseResponse

router = APIRouter(prefix="/chat", tags=["chat"])

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
