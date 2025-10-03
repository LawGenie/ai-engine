from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class HierarchicalDescription(BaseModel):
    heading: str
    subheading: str
    tertiary: str
    combined_description: str = Field(..., alias="combinedDescription")
    heading_code: str = Field(..., alias="headingCode")
    subheading_code: str = Field(..., alias="subheadingCode")
    tertiary_code: str = Field(..., alias="tertiaryCode")
    
    class Config:
        populate_by_name = True
        by_alias = True

class HsCodeSuggestion(BaseModel):
    hs_code: str = Field(..., alias="hsCode")
    description: str
    confidence_score: float = Field(..., alias="confidenceScore")
    reasoning: str
    us_tariff_rate: float = Field(..., alias="usTariffRate")
    usitc_url: str = Field(..., alias="usitcUrl")
    hierarchical_description: Optional[HierarchicalDescription] = Field(None, alias="hierarchicalDescription")
    
    class Config:
        populate_by_name = True  # snake_case와 camelCase 둘 다 허용
        by_alias = True

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