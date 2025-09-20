import httpx
import asyncio
from typing import Dict, List, Optional
from app.models.requirement_models import (
    RequirementAnalysisRequest, 
    RequirementAnalysisResponse,
    Requirements,
    Certification,
    Document,
    Labeling,
    Source,
    Metadata
)
from workflows.requirements_workflow import RequirementsWorkflow
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from hs_site_mapping import HSSiteMapper

class RequirementAnalyzer:
    def __init__(self):
        self.hs_mapper = HSSiteMapper()
        self.workflow = RequirementsWorkflow()
        
    async def analyze_requirements(self, request: RequirementAnalysisRequest) -> RequirementAnalysisResponse:
        """HS코드 기반으로 요구사항 분석 수행 (LangGraph 사용)"""

        # HS코드별 추천 사이트 확인
        recommended_sites = self.hs_mapper.get_recommended_sites(request.hs_code)
        print(f"🎯 HS코드 {request.hs_code}에 대한 추천 사이트: {recommended_sites['sites']}")
        print(f"📝 설명: {recommended_sites['description']}")

        # LangGraph 워크플로우 실행
        response = await self.workflow.analyze_requirements(request)
        
        return response