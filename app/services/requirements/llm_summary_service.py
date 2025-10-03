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
        
        # GPT 프롬프트 템플릿
        self.summary_prompt_template = """
HS코드 {hs_code}에 해당하는 상품 "{product_name}"의 미국 수입 규정을 분석하여 다음 형식으로 요약해주세요:

다음 문서들을 분석:
{documents}

응답 형식 (JSON):
{{
    "critical_requirements": ["필수 요구사항 1", "필수 요구사항 2"],
    "required_documents": ["필수 서류 1", "필수 서류 2"],
    "compliance_steps": ["1단계: ...", "2단계: ..."],
    "estimated_costs": {{
        "certification": "예상 비용",
        "testing": "예상 비용",
        "legal_review": "예상 비용",
        "total": "총 예상 비용"
    }},
    "timeline": "예상 소요 시간",
    "risk_factors": ["위험 요소 1", "위험 요소 2"],
    "recommendations": ["권고사항 1", "권고사항 2"],
    "confidence_score": 0.85
}}

중요 사항:
- critical_requirements: 반드시 준수해야 하는 요구사항 (최대 5개)
- required_documents: 제출해야 하는 서류 (최대 8개)
- compliance_steps: 단계별 준수 절차 (최대 6단계)
- estimated_costs: 구체적인 비용 범위 제시 (예: "$500-1,000")
- timeline: 실제적인 소요 시간 (예: "4-6주")
- risk_factors: 수입 실패 위험 요소
- recommendations: 실행 가능한 권고사항
- confidence_score: 0.0-1.0 사이의 신뢰도

JSON 형식으로만 응답하세요.
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
            
            # 응답 파싱
            result = json.loads(response.choices[0].message.content)
            
            # 메타데이터 추가
            result["tokens_used"] = response.usage.total_tokens
            result["cost"] = self._calculate_cost(response.usage.total_tokens)
            result["response_time"] = response_time
            
            print(f"✅ GPT 요약 완료 - 토큰: {result['tokens_used']}, 비용: ${result['cost']:.4f}")
            
            return result
            
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
