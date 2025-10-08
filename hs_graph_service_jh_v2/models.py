from pydantic import BaseModel, Field
from typing import List, Optional

class HierarchicalDescription(BaseModel):
    """HS 코드 계층적 설명 (Heading → Subheading → Tertiary)"""
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
    """HS 코드 추천 결과"""
    hs_code: str = Field(..., alias="hsCode", description="HS 코드 (10자리)")
    description: str = Field(..., description="HS 코드 설명")
    confidence_score: float = Field(..., alias="confidenceScore", description="신뢰도 점수 (0-1)")
    reasoning: str = Field(..., description="HS 코드 추천 근거 (LLM 생성)")
    tariff_reasoning: str = Field(..., alias="tariffReasoning", description="관세율 적용 근거")
    us_tariff_rate: float = Field(..., alias="usTariffRate", description="총 관세율 (상호관세 포함)")
    base_tariff_rate: Optional[float] = Field(None, alias="baseTariffRate", description="기본 관세율")
    reciprocal_tariff_rate: Optional[float] = Field(None, alias="reciprocalTariffRate", description="상호관세율")
    usitc_url: str = Field(..., alias="usitcUrl", description="USITC 참조 URL")
    hierarchical_description: Optional[HierarchicalDescription] = Field(None, alias="hierarchicalDescription", description="계층적 설명")
    
    class Config:
        populate_by_name = True  # snake_case와 camelCase 둘 다 허용
        by_alias = True

class HsCodeAnalysisRequest(BaseModel):
    """HS 코드 분석 요청"""
    product_name: str = Field(..., alias="productName", description="제품명")
    product_description: str = Field(..., alias="productDescription", description="제품 상세 설명")
    origin_country: Optional[str] = Field("KOR", alias="originCountry", description="원산지 국가 코드")
    
    class Config:
        populate_by_name = True

class HsCodeAnalysisResponse(BaseModel):
    """HS 코드 분석 응답"""
    analysis_session_id: str = Field(..., alias="analysisSessionId", description="분석 세션 ID")
    suggestions: List[HsCodeSuggestion] = Field(..., description="HS 코드 추천 목록 (최대 3개)")
    
    class Config:
        populate_by_name = True
        by_alias = True  # 응답 시 camelCase로 변환