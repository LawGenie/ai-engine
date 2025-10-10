"""
LLM 요약 서비스
GPT를 사용한 규정 문서 요약 및 구조화
"""

import asyncio
import json
import hashlib
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import aiohttp
from openai import AsyncOpenAI

@dataclass
class SummaryResult:
    """요약 결과"""
    hs_code: str
    product_name: str
    critical_requirements: List[str]
    required_documents: List[str]
    compliance_steps: List[str]
    estimated_costs: Dict[str, str]
    timeline: str
    risk_factors: List[str]
    recommendations: List[str]
    model_used: str
    tokens_used: int
    cost: float
    confidence_score: float

class LlmSummaryService:
    """LLM 요약 서비스"""
    
    def __init__(self, backend_api_url: str = "http://localhost:8081"):
        self.backend_api_url = backend_api_url
        self.openai_client = AsyncOpenAI()
        self.cache_ttl = 86400  # 24시간
        
        # GPT 프롬프트 템플릿 (Citations 포함)
        self.summary_prompt_template = """
You are an expert US import compliance analyst. Analyze the import regulations for product "{product_name}" (HS Code: {hs_code}) based on the following official sources.

## Available Sources (with URLs):
{documents}

## Your Task:
Provide a comprehensive, actionable analysis in JSON format. **IMPORTANT**: For each requirement, document, or recommendation, include the source URL(s) that support it.

## Response Format (JSON):
{{
    "critical_requirements": [
        {{
            "requirement": "Specific requirement description",
            "agency": "FDA/USDA/EPA/etc",
            "source_url": "https://...",
            "severity": "mandatory/recommended",
            "penalty_if_violated": "Brief description of consequences",
            "effective_date": "YYYY-MM-DD (when this regulation took effect)",
            "last_updated": "YYYY-MM-DD (most recent update)"
        }}
    ],
    "required_documents": [
        {{
            "document": "Document name",
            "issuing_authority": "Who issues this",
            "source_url": "https://...",
            "estimated_time": "Processing time",
            "notes": "Important details"
        }}
    ],
    "compliance_steps": [
        {{
            "step": 1,
            "action": "Specific action to take",
            "responsible_party": "Who should do this",
            "source_url": "https://...",
            "estimated_duration": "Time needed",
            "dependencies": ["Previous steps if any"]
        }}
    ],
    "estimated_costs": {{
        "certification": {{"min": 500, "max": 1000, "currency": "USD", "source_url": "https://..."}},
        "testing": {{"min": 300, "max": 800, "currency": "USD", "source_url": "https://..."}},
        "legal_review": {{"min": 200, "max": 500, "currency": "USD", "source_url": "https://..."}},
        "total": {{"min": 1000, "max": 2300, "currency": "USD"}},
        "notes": "Cost estimates based on typical cases"
    }},
    "timeline": {{
        "minimum_days": 30,
        "typical_days": 45,
        "maximum_days": 60,
        "critical_path": ["Step 1", "Step 2", "Step 3"],
        "source_url": "https://..."
    }},
    "risk_factors": [
        {{
            "risk": "Specific risk description",
            "likelihood": "high/medium/low",
            "impact": "high/medium/low",
            "mitigation": "How to mitigate this risk",
            "source_url": "https://..."
        }}
    ],
    "recommendations": [
        {{
            "recommendation": "Actionable recommendation",
            "priority": "high/medium/low",
            "rationale": "Why this is important",
            "source_url": "https://..."
        }}
    ],
    "labeling_requirements": [
        {{
            "element": "Ingredient list/Country of origin/etc",
            "requirement": "Specific requirement",
            "agency": "FDA/FTC/etc",
            "source_url": "https://...",
            "format": "Required format",
            "placement": "Where on package",
            "language": "English/Bilingual",
            "penalties": "Consequences if non-compliant"
        }}
    ],
    "prohibited_restricted_substances": [
        {{
            "substance": "Chemical name",
            "status": "prohibited/restricted",
            "max_concentration": "If restricted",
            "agency": "Regulating agency",
            "source_url": "https://...",
            "alternatives": ["Safe alternatives if available"]
        }}
    ],
    "prior_notifications": [
        {{
            "type": "FDA Prior Notice/EPA notification/etc",
            "required_for": "Product categories",
            "deadline": "When to submit",
            "submission_method": "How to submit",
            "source_url": "https://...",
            "processing_time": "Expected time",
            "consequences_if_missed": "What happens"
        }}
    ],
    "testing_requirements": [
        {{
            "test": "Test name",
            "required_by": "Agency",
            "frequency": "How often",
            "accredited_labs": ["Lab names"],
            "cost_per_test": {{"min": 200, "max": 500, "currency": "USD"}},
            "turnaround_time": "Days",
            "source_url": "https://...",
            "pass_criteria": "Acceptance criteria"
        }}
    ],
    "third_party_certifications": [
        {{
            "certification": "Certification name",
            "type": "mandatory/voluntary",
            "purpose": "What it certifies",
            "cost_range": {{"min": 1000, "max": 5000, "currency": "USD"}},
            "validity": "Duration",
            "recognized_bodies": ["Certifying organizations"],
            "source_url": "https://...",
            "market_advantage": "Business benefit"
        }}
    ],
    "customs_clearance": {{
        "entry_filing": {{
            "deadline": "15 days after arrival",
            "required_forms": ["Form names"],
            "source_url": "https://..."
        }},
        "bonds_required": {{
            "type": "Single/Continuous",
            "amount": "Dollar amount",
            "source_url": "https://..."
        }},
        "inspection_probability": "high/medium/low with factors"
    }},
    "state_requirements": [
        {{
            "state": "California/New York/etc",
            "requirement": "Specific state requirement",
            "applies_to": "Product categories",
            "source_url": "https://...",
            "penalty": "State-level penalties"
        }}
    ],
    "key_agencies": [
        {{
            "agency": "FDA/USDA/EPA/etc",
            "role": "What they regulate",
            "contact": "Contact information if available",
            "website": "Official website URL"
        }}
    ],
    "regulatory_updates": {{
        "recent_changes": [
            {{
                "date": "YYYY-MM-DD",
                "agency": "Agency name",
                "change": "What changed",
                "impact": "How it affects this product",
                "effective_date": "When it takes effect",
                "source_url": "https://..."
            }}
        ],
        "pending_legislation": "Any upcoming changes to watch"
    }},
    "confidence_score": 0.85,
    "analysis_notes": "Any important caveats or additional context",
    "data_completeness": {{
        "sources_found": 5,
        "sources_expected": 8,
        "missing_areas": ["Areas where data is lacking"],
        "recommendation": "Consult customs broker/attorney if needed"
    }}
}}

## Guidelines:
1. **Citations**: Every claim MUST include a source_url from the provided sources
2. **Specificity**: Use exact numbers, dates, and requirements (not vague terms)
3. **Actionability**: Each step should be clear enough to execute immediately
4. **Prioritization**: Order items by importance/urgency
5. **Risk Assessment**: Be realistic about potential issues
6. **Cost Accuracy**: Provide ranges based on typical cases, cite sources
7. **Timeline Realism**: Account for government processing times
8. **Agency Identification**: Clearly identify which agency regulates what
9. **Confidence**: Lower confidence if sources are limited or contradictory
10. **Product-Specific**: Tailor advice to the specific HS code and product category
11. **Labeling Focus**: Pay special attention to labeling requirements (critical for customs)
12. **Prohibited Substances**: Explicitly identify any banned/restricted ingredients
13. **Prior Notice**: Highlight any pre-arrival notification requirements
14. **Testing**: Specify which tests are mandatory vs recommended
15. **State Laws**: Include California Prop 65 and other major state requirements
16. **Practical Costs**: Include all costs (testing, certification, legal, bonds, insurance)
17. **Customs Reality**: Mention inspection probability and common detention reasons
18. **Market Access**: Note retailer-specific requirements (Amazon, Walmart, etc)
19. **Updates**: Flag recent regulatory changes that may affect compliance
20. **Completeness**: Indicate data gaps and recommend professional consultation when needed
21. **Dates**: Extract effective_date and last_updated from source data when available (FDA uses report_date, recall_initiation_date)
22. **Recency**: Prioritize more recent regulations and flag outdated information

## Important:
- If information is missing from sources, indicate "Not found in provided sources"
- Do not make up URLs - only use URLs from the provided sources
- If multiple sources conflict, note the discrepancy
- Focus on US import requirements only
- Prioritize official government sources over general information

## JSON Formatting Rules (CRITICAL):
- **Escape Special Characters**: All quotes, newlines, and backslashes in strings MUST be properly escaped
- **No Line Breaks in Strings**: Keep all text in single lines within JSON strings (no \\n unless escaped)
- **Short Text**: Keep requirement/recommendation texts under 200 characters each
- **Valid Strings**: Ensure all strings are properly closed with double quotes
- **Test Your JSON**: The output must be valid JSON parseable by standard parsers

Return ONLY valid, parseable JSON. No markdown, no comments, no additional text.
"""
    
    async def summarize_regulations(
        self, 
        hs_code: str, 
        product_name: str,
        raw_documents: List[Dict[str, Any]]
    ) -> SummaryResult:
        """규정 문서 요약"""
        
        print(f"🤖 LLM 요약 시작 - HS코드: {hs_code}, 상품: {product_name}")
        
        # 문서 해시 생성 (캐시 키용)
        documents_hash = self._generate_documents_hash(raw_documents)
        
        # 캐시 확인
        cached_result = await self._get_from_cache(hs_code, product_name, documents_hash)
        if cached_result:
            print(f"✅ LLM 캐시에서 조회")
            return cached_result
        
        # 문서 내용 추출 및 정리
        document_texts = self._extract_document_texts(raw_documents)
        
        if not document_texts:
            print(f"⚠️ 요약할 문서 내용이 없음")
            return self._create_empty_summary(hs_code, product_name)
        
        # GPT 요약 실행
        summary_data = await self._call_gpt_summary(hs_code, product_name, document_texts)
        
        if not summary_data:
            print(f"❌ GPT 요약 실패")
            return self._create_empty_summary(hs_code, product_name)
        
        # 결과 객체 생성
        result = SummaryResult(
            hs_code=hs_code,
            product_name=product_name,
            critical_requirements=summary_data.get("critical_requirements", []),
            required_documents=summary_data.get("required_documents", []),
            compliance_steps=summary_data.get("compliance_steps", []),
            estimated_costs=summary_data.get("estimated_costs", {}),
            timeline=summary_data.get("timeline", "정보 없음"),
            risk_factors=summary_data.get("risk_factors", []),
            recommendations=summary_data.get("recommendations", []),
            model_used="gpt-4o-mini",
            tokens_used=summary_data.get("tokens_used", 0),
            cost=summary_data.get("cost", 0.0),
            confidence_score=summary_data.get("confidence_score", 0.0)
        )
        
        # 캐시에 저장
        await self._save_to_cache(result, documents_hash)
        
        print(f"✅ LLM 요약 완료 - 신뢰도: {result.confidence_score:.2f}")
        return result
    
    def _extract_document_texts(self, raw_documents: List[Dict[str, Any]]) -> List[str]:
        """문서에서 텍스트 추출"""
        texts = []
        
        for doc in raw_documents:
            # 다양한 필드에서 텍스트 추출
            text_fields = ["content", "summary", "description", "text", "body"]
            
            for field in text_fields:
                if field in doc and doc[field]:
                    text = str(doc[field])
                    if len(text) > 50:  # 의미있는 길이의 텍스트만
                        texts.append(text[:2000])  # 최대 2000자로 제한
                        break
            
            # 제목도 포함
            if "title" in doc and doc["title"]:
                texts.append(f"제목: {doc['title']}")
        
        # 중복 제거 및 길이 제한
        unique_texts = list(set(texts))
        return unique_texts[:10]  # 최대 10개 문서만 처리
    
    async def _call_gpt_summary(
        self, 
        hs_code: str, 
        product_name: str, 
        document_texts: List[str]
    ) -> Optional[Dict[str, Any]]:
        """GPT 요약 호출"""
        try:
            # 문서 내용 결합
            combined_text = "\n\n".join(document_texts)
            
            # 프롬프트 생성
            prompt = self.summary_prompt_template.format(
                hs_code=hs_code,
                product_name=product_name,
                documents=combined_text
            )
            
            # 토큰 수 추정
            estimated_tokens = len(prompt.split()) * 1.3  # 대략적인 추정
            
            # GPT 호출
            start_time = datetime.now()
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                response_format={"type": "json_object"},
                max_tokens=2000
            )
            
            response_time = (datetime.now() - start_time).total_seconds()
            
            # 응답 파싱 (JSON 파싱 에러 방지)
            try:
                content = response.choices[0].message.content
                result = json.loads(content)
            except json.JSONDecodeError as json_err:
                print(f"❌ JSON 파싱 실패: {json_err}")
                print(f"📄 GPT 응답 내용 (처음 500자): {content[:500] if content else 'None'}")
                # JSON 파싱 실패 시 빈 결과 반환
                return None
            
            # 메타데이터 추가
            result["tokens_used"] = response.usage.total_tokens
            result["cost"] = self._calculate_cost(response.usage.total_tokens)
            result["response_time"] = response_time
            
            print(f"✅ GPT 요약 완료 - 토큰: {result['tokens_used']}, 비용: ${result['cost']:.4f}")
            
            return result
            
        except json.JSONDecodeError as json_err:
            print(f"❌ GPT 요약 실패 (JSON 파싱): {json_err}")
            return None
        except Exception as e:
            print(f"❌ GPT 요약 실패: {e}")
            return None
    
    def _calculate_cost(self, tokens: int) -> float:
        """토큰 비용 계산 (GPT-4o-mini 기준)"""
        # GPT-4o-mini 비용: $0.00015/1K input tokens, $0.0006/1K output tokens
        # 대략적인 계산 (입력:출력 = 3:1 비율 가정)
        input_tokens = int(tokens * 0.75)
        output_tokens = int(tokens * 0.25)
        
        input_cost = (input_tokens / 1000) * 0.00015
        output_cost = (output_tokens / 1000) * 0.0006
        
        return input_cost + output_cost
    
    def _generate_documents_hash(self, documents: List[Dict[str, Any]]) -> str:
        """문서 해시 생성"""
        # 문서 내용을 문자열로 변환
        doc_strings = []
        for doc in documents:
            doc_str = f"{doc.get('title', '')}_{doc.get('content', '')}_{doc.get('summary', '')}"
            doc_strings.append(doc_str)
        
        # 해시 생성
        combined = "|".join(doc_strings)
        return hashlib.md5(combined.encode()).hexdigest()
    
    async def _get_from_cache(
        self, 
        hs_code: str, 
        product_name: str, 
        documents_hash: str
    ) -> Optional[SummaryResult]:
        """캐시에서 요약 결과 조회"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.backend_api_url}/api/llm-summary-cache/search"
                params = {
                    "hs_code": hs_code,
                    "product_name": product_name,
                    "documents_hash": documents_hash
                }
                
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data:
                            return self._parse_cached_result(data)
        except Exception as e:
            print(f"⚠️ LLM 캐시 조회 실패: {e}")
        
        return None
    
    async def _save_to_cache(self, result: SummaryResult, documents_hash: str):
        """요약 결과를 캐시에 저장"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.backend_api_url}/api/llm-summary-cache"
                data = {
                    "hsCode": result.hs_code,
                    "productName": result.product_name,
                    "rawDocumentsHash": documents_hash,
                    "summaryResult": json.dumps({
                        "critical_requirements": result.critical_requirements,
                        "required_documents": result.required_documents,
                        "compliance_steps": result.compliance_steps,
                        "estimated_costs": result.estimated_costs,
                        "timeline": result.timeline,
                        "risk_factors": result.risk_factors,
                        "recommendations": result.recommendations,
                        "confidence_score": result.confidence_score
                    }),
                    "modelUsed": result.model_used,
                    "tokensUsed": result.tokens_used,
                    "cost": result.cost,
                    "expiresAt": (datetime.now() + timedelta(seconds=self.cache_ttl)).isoformat()
                }
                
                async with session.post(url, json=data) as response:
                    if response.status in [200, 201]:
                        print(f"✅ LLM 캐시 저장 완료")
                    else:
                        print(f"❌ LLM 캐시 저장 실패: {response.status}")
                        
        except Exception as e:
            print(f"❌ LLM 캐시 저장 오류: {e}")
    
    def _parse_cached_result(self, data: Dict[str, Any]) -> SummaryResult:
        """캐시된 결과 파싱"""
        summary_data = json.loads(data["summaryResult"])
        
        return SummaryResult(
            hs_code=data["hsCode"],
            product_name=data["productName"],
            critical_requirements=summary_data.get("critical_requirements", []),
            required_documents=summary_data.get("required_documents", []),
            compliance_steps=summary_data.get("compliance_steps", []),
            estimated_costs=summary_data.get("estimated_costs", {}),
            timeline=summary_data.get("timeline", "정보 없음"),
            risk_factors=summary_data.get("risk_factors", []),
            recommendations=summary_data.get("recommendations", []),
            model_used=data["modelUsed"],
            tokens_used=data["tokensUsed"],
            cost=float(data["cost"]),
            confidence_score=summary_data.get("confidence_score", 0.0)
        )
    
    def _create_empty_summary(self, hs_code: str, product_name: str) -> SummaryResult:
        """빈 요약 결과 생성"""
        return SummaryResult(
            hs_code=hs_code,
            product_name=product_name,
            critical_requirements=["문서 분석 실패 - 수동 검토 필요"],
            required_documents=["기본 수입 서류 확인 필요"],
            compliance_steps=["1단계: 관련 기관 문의", "2단계: 요구사항 확인"],
            estimated_costs={"total": "비용 산정 불가"},
            timeline="소요 시간 산정 불가",
            risk_factors=["요구사항 불명확"],
            recommendations=["전문가 상담 권장"],
            model_used="none",
            tokens_used=0,
            cost=0.0,
            confidence_score=0.0
        )
    
    async def get_summary_statistics(self) -> Dict[str, Any]:
        """요약 통계 조회"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.backend_api_url}/api/llm-summary-cache/statistics"
                
                async with session.get(url) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        return {"error": f"통계 조회 실패: {response.status}"}
                        
        except Exception as e:
            return {"error": f"통계 조회 오류: {e}"}
    
    def format_summary_result(self, result: SummaryResult) -> Dict[str, Any]:
        """요약 결과를 API 응답 형식으로 변환"""
        return {
            "llm_summary": {
                "hs_code": result.hs_code,
                "product_name": result.product_name,
                "critical_requirements": result.critical_requirements,
                "required_documents": result.required_documents,
                "compliance_steps": result.compliance_steps,
                "estimated_costs": result.estimated_costs,
                "timeline": result.timeline,
                "risk_factors": result.risk_factors,
                "recommendations": result.recommendations,
                "model_used": result.model_used,
                "tokens_used": result.tokens_used,
                "cost": result.cost,
                "confidence_score": result.confidence_score,
                "status": "completed"
            }
        }
