from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

class Source(BaseModel):
    title: str
    url: str
    type: str
    relevance: str = "medium"

class Certification(BaseModel):
    name: str
    required: bool
    description: str
    agency: str
    url: str

class Document(BaseModel):
    name: str
    required: bool
    description: str
    url: str

class Labeling(BaseModel):
    requirement: str
    description: str
    url: str

class Requirements(BaseModel):
    certifications: List[Certification] = []
    documents: List[Document] = []
    labeling: List[Labeling] = []

class Metadata(BaseModel):
    from_cache: bool
    cached_at: Optional[str] = None
    confidence: float
    response_time_ms: int
    last_updated: Optional[str] = None

class RequirementAnalysisResponse(BaseModel):
    answer: str
    reasoning: str
    requirements: Requirements
    sources: List[Source]
    metadata: Metadata
    hs_code_8digit: Optional[str] = None
    hs_code_6digit: Optional[str] = None
    agency_status: Optional[Dict[str, Any]] = None

class RequirementAnalysisRequest(BaseModel):
    hs_code: str
    product_name: str
    product_description: Optional[str] = None
    target_country: str = "US"