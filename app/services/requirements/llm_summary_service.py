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
Provide a comprehensive, actionable analysis in JSON format.

**🚨 CRITICAL - SOURCE URL REQUIREMENTS**:
1. **NEVER** use "ACTUAL_URL_FROM_SOURCES_ABOVE" as-is
2. **ALWAYS** extract real URLs from the ## Available Sources section above
3. Match each requirement/document to its corresponding source URL
4. If no specific URL matches, use the agency's main website:
   - FDA: https://www.fda.gov/
   - USDA: https://www.usda.gov/
   - EPA: https://www.epa.gov/
   - CPSC: https://www.cpsc.gov/
   - CBP: https://www.cbp.gov/
5. Every "source_url" field MUST be a valid HTTP/HTTPS URL

## Response Format (JSON with Bilingual Support):
**CRITICAL INSTRUCTIONS**: 
- Replace "ACTUAL_URL_FROM_SOURCES_ABOVE" with REAL URLs from the sources provided above
- NEVER leave "ACTUAL_URL_FROM_SOURCES_ABOVE" as-is - always use actual URLs
- If no specific URL available, use the agency's main regulation page
- Include ALL fields in the response, especially:
  * execution_checklist (pre_import, during_import, post_import tasks)
  * cost_breakdown (mandatory_costs, optional_costs, hidden_costs)
  * risk_matrix (high_risk, medium_risk items)
  * compliance_score (overall_score with category breakdown)
  * market_access (retailer_requirements, state_regulations)
- Focus on actionable, specific information over generic statements

{{
    "critical_requirements": [
        {{
            "requirement": "Specific requirement description",
            "requirement_ko": "요구사항 한국어 설명",
            "agency": "FDA/USDA/EPA/etc",
            "source_url": "https://www.fda.gov/ (or specific URL from sources)",
            "severity": "mandatory/recommended",
            "penalty_if_violated": "Brief description of consequences",
            "penalty_if_violated_ko": "위반 시 처벌 한국어 설명",
            "effective_date": "YYYY-MM-DD (when this regulation took effect)",
            "last_updated": "YYYY-MM-DD (most recent update)"
        }}
    ],
    "required_documents": [
        {{
            "document": "Document name",
            "document_ko": "문서명 한국어",
            "issuing_authority": "Who issues this",
            "issuing_authority_ko": "발급 기관 한국어",
            "source_url": "https://www.fda.gov/ (or specific URL from sources)",
            "estimated_time": "Processing time",
            "estimated_time_ko": "소요 시간 한국어",
            "notes": "Important details",
            "notes_ko": "주의사항 한국어"
        }}
    ],
    "compliance_steps": [
        {{
            "step": 1,
            "action": "Specific action to take",
            "action_ko": "조치 사항 한국어",
            "responsible_party": "Who should do this",
            "responsible_party_ko": "담당자 한국어",
            "source_url": "https://www.fda.gov/ (or specific URL from sources)",
            "estimated_duration": "Time needed",
            "estimated_duration_ko": "소요 시간 한국어",
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
            "risk_ko": "위험 요소 한국어 설명",
            "likelihood": "high/medium/low",
            "impact": "high/medium/low",
            "mitigation": "How to mitigate this risk",
            "mitigation_ko": "완화 방안 한국어",
            "source_url": "https://..."
        }}
    ],
    "recommendations": [
        {{
            "recommendation": "Actionable recommendation",
            "recommendation_ko": "권장사항 한국어",
            "priority": "high/medium/low",
            "rationale": "Why this is important",
            "rationale_ko": "이유 한국어",
            "source_url": "https://..."
        }}
    ],
    "labeling_requirements": [
        {{
            "element": "Ingredient list/Country of origin/etc",
            "requirement": "Specific requirement",
            "agency": "FDA/FTC/etc",
            "source_url": "https://www.fda.gov/ (or specific URL from sources)",
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
            "source_url": "https://www.fda.gov/ (or specific URL from sources)",
            "alternatives": ["Safe alternatives if available"]
        }}
    ],
    "prior_notifications": [
        {{
            "type": "FDA Prior Notice/EPA notification/etc",
            "required_for": "Product categories",
            "deadline": "When to submit",
            "submission_method": "How to submit",
            "source_url": "https://www.fda.gov/ (or specific URL from sources)",
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
            "source_url": "https://www.fda.gov/ (or specific URL from sources)",
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
            "source_url": "https://www.fda.gov/ (or specific URL from sources)",
            "market_advantage": "Business benefit"
        }}
    ],
    "exemptions": [
        {{
            "exemption_type": "De minimis/Low value/Specific category",
            "condition": "Product value < $800 OR Category XYZ",
            "condition_ko": "조건 한국어 설명",
            "exempted_from": ["FDA Prior Notice", "Specific requirement"],
            "exempted_from_ko": ["FDA 사전 통지", "특정 요건"],
            "limitations": "What is NOT exempted",
            "limitations_ko": "면제되지 않는 사항 한국어",
            "how_to_claim": "Documentation or process needed",
            "how_to_claim_ko": "신청 방법 한국어",
            "source_url": "https://www.fda.gov/ (or specific URL from sources)",
            "notes": "Important caveats",
            "notes_ko": "주의사항 한국어"
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
            "source_url": "https://www.fda.gov/ (or specific URL from sources)",
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
    }},
    "execution_checklist": {{ // ⚠️ REQUIRED - Must include pre/during/post import tasks
        "pre_import": [
            {{
                "task": "Specific pre-import task",
                "task_ko": "수입 전 작업 한국어",
                "deadline": "When to complete",
                "deadline_ko": "완료 시한 한국어",
                "responsible": "Who does this",
                "responsible_ko": "담당자 한국어",
                "priority": "high/medium/low",
                "estimated_hours": 2,
                "dependencies": ["Prerequisite tasks"],
                "success_criteria": "How to verify completion",
                "success_criteria_ko": "완료 확인 방법 한국어",
                "source_url": "ACTUAL_URL_FROM_SOURCES_ABOVE"
            }}
        ],
        "during_import": [
            {{
                "task": "Import process task",
                "task_ko": "수입 과정 작업 한국어",
                "timing": "When during import",
                "timing_ko": "수입 중 시점 한국어",
                "estimated_hours": 4,
                "source_url": "ACTUAL_URL_FROM_SOURCES_ABOVE"
            }}
        ],
        "post_import": [
            {{
                "task": "Post-import compliance task",
                "task_ko": "수입 후 준수 작업 한국어",
                "deadline": "When to complete",
                "estimated_hours": 1,
                "source_url": "ACTUAL_URL_FROM_SOURCES_ABOVE"
            }}
        ]
    }},
    "cost_breakdown": {{ // ⚠️ REQUIRED - Must include mandatory/optional/hidden costs
        "mandatory_costs": {{
            "testing": {{"min": 300, "max": 800, "currency": "USD", "frequency": "per_batch", "source_url": "ACTUAL_URL_FROM_SOURCES_ABOVE"}},
            "certification": {{"min": 500, "max": 1500, "currency": "USD", "frequency": "annual", "source_url": "ACTUAL_URL_FROM_SOURCES_ABOVE"}},
            "prior_notice": {{"min": 0, "max": 0, "currency": "USD", "frequency": "per_shipment", "source_url": "ACTUAL_URL_FROM_SOURCES_ABOVE"}}
        }},
        "optional_costs": {{
            "legal_review": {{"min": 200, "max": 500, "currency": "USD", "frequency": "one_time", "source_url": "ACTUAL_URL_FROM_SOURCES_ABOVE"}},
            "consultation": {{"min": 100, "max": 300, "currency": "USD", "frequency": "as_needed", "source_url": "ACTUAL_URL_FROM_SOURCES_ABOVE"}}
        }},
        "hidden_costs": {{
            "storage_fees": {{"min": 50, "max": 200, "currency": "USD", "frequency": "per_day", "source_url": "ACTUAL_URL_FROM_SOURCES_ABOVE"}},
            "inspection_fees": {{"min": 0, "max": 500, "currency": "USD", "frequency": "if_inspected", "source_url": "ACTUAL_URL_FROM_SOURCES_ABOVE"}}
        }},
        "cost_optimization": [
            {{
                "strategy": "Cost-saving strategy",
                "strategy_ko": "비용 절약 전략 한국어",
                "potential_savings": "Amount saved",
                "potential_savings_ko": "절약 금액 한국어",
                "trade_offs": "What you give up",
                "trade_offs_ko": "대가 한국어",
                "source_url": "ACTUAL_URL_FROM_SOURCES_ABOVE"
            }}
        ]
    }},
    "risk_matrix": {{ // ⚠️ REQUIRED - Must include high/medium risk assessment
        "high_risk": [
            {{
                "risk": "High-impact risk",
                "risk_ko": "고위험 요소 한국어",
                "probability": "high/medium/low",
                "impact": "high/medium/low",
                "detection_method": "How to detect early",
                "detection_method_ko": "조기 감지 방법 한국어",
                "contingency_plan": "What to do if it happens",
                "contingency_plan_ko": "발생시 대응 방안 한국어",
                "source_url": "ACTUAL_URL_FROM_SOURCES_ABOVE"
            }}
        ],
        "medium_risk": [
            {{
                "risk": "Medium-impact risk",
                "risk_ko": "중위험 요소 한국어",
                "probability": "medium",
                "impact": "medium",
                "monitoring_frequency": "How often to check",
                "monitoring_frequency_ko": "확인 주기 한국어",
                "source_url": "ACTUAL_URL_FROM_SOURCES_ABOVE"
            }}
        ]
    }},
    "compliance_score": {{ // ⚠️ REQUIRED - Must calculate overall readiness score
        "overall_score": 85,
        "category_scores": {{
            "documentation": {{"score": 90, "weight": 0.3, "max_score": 100}},
            "testing": {{"score": 80, "weight": 0.25, "max_score": 100}},
            "labeling": {{"score": 85, "weight": 0.2, "max_score": 100}},
            "timeline": {{"score": 90, "weight": 0.15, "max_score": 100}},
            "cost_efficiency": {{"score": 75, "weight": 0.1, "max_score": 100}}
        }},
        "improvement_areas": [
            {{
                "area": "Area needing improvement",
                "area_ko": "개선 영역 한국어",
                "current_gap": "What's missing",
                "current_gap_ko": "부족한 부분 한국어",
                "action_plan": "How to improve",
                "action_plan_ko": "개선 방안 한국어",
                "priority": "high/medium/low",
                "estimated_effort": "hours/days/weeks",
                "source_url": "ACTUAL_URL_FROM_SOURCES_ABOVE"
            }}
        ]
    }},
    "market_access": {{ // ⚠️ REQUIRED - Must include retailer and state requirements
        "retailer_requirements": [
            {{
                "retailer": "Amazon/Walmart/Target/etc",
                "specific_requirements": ["Retailer-specific requirements"],
                "specific_requirements_ko": ["소매업체별 요구사항 한국어"],
                "certifications_needed": ["Additional certifications"],
                "certifications_needed_ko": ["추가 인증 한국어"],
                "compliance_deadline": "When to comply",
                "compliance_deadline_ko": "준수 시한 한국어",
                "source_url": "ACTUAL_URL_FROM_SOURCES_ABOVE"
            }}
        ],
        "state_regulations": [
            {{
                "state": "California/New York/etc",
                "regulation": "State-specific requirement",
                "regulation_ko": "주별 특수 요구사항 한국어",
                "applies_to": "Product categories",
                "applies_to_ko": "적용 상품 카테고리 한국어",
                "penalty": "State-level penalty",
                "penalty_ko": "주별 처벌 한국어",
                "source_url": "ACTUAL_URL_FROM_SOURCES_ABOVE"
            }}
        ]
    }}
}}

## Guidelines (Enhanced Requirements Extraction):
1. **Bilingual Support**: Provide both English and Korean (_ko suffix) for all user-facing text
2. **Citations**: Every claim MUST include a source_url from the provided sources
3. **Specificity**: Use exact numbers, dates, and requirements (not vague terms)
4. **Actionability**: Each step should be clear enough to execute immediately
5. **Prioritization**: Order items by importance/urgency (High/Medium/Low)
6. **Risk Assessment**: Be realistic about potential issues with probability/impact matrix
7. **Cost Accuracy**: Provide ranges based on typical cases, include hidden costs, cite sources
8. **Timeline Realism**: Account for government processing times, identify critical path
9. **Agency Identification**: Clearly identify which agency regulates what
10. **Confidence**: Lower confidence if sources are limited or contradictory
11. **Product-Specific**: Tailor advice to the specific HS code and product category
12. **Execution Focus**: Generate actionable checklists, not just information
13. **Cost Optimization**: Identify money-saving strategies and trade-offs
14. **Risk Management**: Provide early warning systems and contingency plans
15. **Compliance Scoring**: Rate compliance readiness with improvement areas
16. **Market Access**: Include retailer and state-specific requirements
17. **Completeness Check**: Identify gaps and recommend professional consultation
18. **Practical Reality**: Include real-world challenges (storage, inspection, delays)
19. **Exemptions**: Explicitly identify any exemption conditions (de minimis, low value, category exemptions)
20. **Labeling Focus**: Pay special attention to labeling requirements (critical for customs)
21. **Prohibited Substances**: Explicitly identify any banned/restricted ingredients
22. **Prior Notice**: Highlight any pre-arrival notification requirements
23. **Testing**: Specify which tests are mandatory vs recommended
24. **State Laws**: Include California Prop 65 and other major state requirements
25. **Practical Costs**: Include all costs (testing, certification, legal, bonds, insurance)
26. **Customs Reality**: Mention inspection probability and common detention reasons
27. **Updates**: Flag recent regulatory changes that may affect compliance
28. **Dates**: Extract effective_date and last_updated from source data when available
29. **Recency**: Prioritize more recent regulations and flag outdated information

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
                max_tokens=4000  # 확장된 JSON 구조를 위해 증가 (2000 → 4000)
            )
            
            response_time = (datetime.now() - start_time).total_seconds()
            
            # 응답 파싱 (JSON 파싱 에러 방지)
            try:
                content = response.choices[0].message.content
                
                # JSON 파싱 시도
                result = json.loads(content)
                
                # 필수 필드 검증
                required_fields = ["critical_requirements", "required_documents", "compliance_steps"]
                for field in required_fields:
                    if field not in result:
                        print(f"⚠️ 필수 필드 누락: {field} - 빈 배열로 초기화")
                        result[field] = []
                
                # Optional 필드 기본값 설정
                optional_fields = {
                    "execution_checklist": None,
                    "cost_breakdown": None,
                    "risk_matrix": None,
                    "compliance_score": None,
                    "market_access": None
                }
                for field, default_value in optional_fields.items():
                    if field not in result:
                        result[field] = default_value
                
            except json.JSONDecodeError as json_err:
                print(f"❌ JSON 파싱 실패: {json_err}")
                print(f"📄 GPT 응답 내용 (처음 500자): {content[:500] if content else 'None'}")
                
                # JSON 파싱 실패 시에도 부분적으로 복구 시도
                try:
                    # JSON 수정 시도 (마지막 닫는 괄호 추가)
                    if content and not content.strip().endswith('}'):
                        content_fixed = content.strip() + '}'
                        result = json.loads(content_fixed)
                        print(f"✅ JSON 복구 성공")
                    else:
                        return None
                except:
                    # 복구 실패 시 빈 결과 반환
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
