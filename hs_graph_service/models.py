from pydantic import BaseModel, Field
from typing import List, Optional

class HsCodeSuggestion(BaseModel):
    hs_code: str = Field(..., alias="hsCode")
    description: str
    confidence_score: float = Field(..., alias="confidenceScore")
    reasoning: str
    us_tariff_rate: float = Field(..., alias="usTariffRate")
    
    class Config:
        populate_by_name = True  # snake_case와 camelCase 둘 다 허용

class HsCodeAnalysisRequest(BaseModel):
    product_name: str = Field(..., alias="productName")
    product_description: str = Field(..., alias="productDescription")
    origin_country: Optional[str] = Field(None, alias="originCountry")
    
    class Config:
        populate_by_name = True

class HsCodeAnalysisResponse(BaseModel):
    analysis_session_id: str = Field(..., alias="analysisSessionId")
    suggestions: List[HsCodeSuggestion]
    
    class Config:
        populate_by_name = True
        # 응답 시 camelCase로 변환
        by_alias = True