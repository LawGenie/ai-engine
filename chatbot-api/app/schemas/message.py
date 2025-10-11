from pydantic import BaseModel, Field

class MessageRequest(BaseModel):
    sender: str = Field(..., description="발신자 이름")
    message: str = Field(..., description="메시지 내용")
    
    class Config:
        json_schema_extra = {
            "example": {
                "sender": "user",
                "message": "FDA 식품 수출 절차를 알려주세요."
            }
        }

class MessageResponse(BaseModel):
    sender: str = Field(..., description="발신자 이름")
    message: str = Field(..., description="메시지 내용")
    
    class Config:
        json_schema_extra = {
            "example": {
                "sender": "assistant",
                "message": "FDA 식품 수출 절차는..."
            }
        }