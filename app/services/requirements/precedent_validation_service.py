"""
판례 기반 요구사항 검증 서비스
FAISS DB의 판례와 분석 결과를 비교하여 신뢰도 검증
"""

import asyncio
import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime
from openai import AsyncOpenAI
import os
import sys
from pathlib import Path

# FAISS DB import
project_root = Path(__file__).resolve().parents[3]
precedents_path = project_root / "precedents-analysis"
if str(precedents_path) not in sys.path:
    sys.path.insert(0, str(precedents_path))

from faiss_precedents_db import FAISSPrecedentsDB

@dataclass
class PrecedentValidationResult:
    """판례 검증 결과"""
    validation_score: float  # 0.0 ~ 1.0
    precedents_analyzed: int
    precedents_source: str
    matched_requirements: List[Dict[str, Any]]
    missing_requirements: List[Dict[str, Any]]
    extra_requirements: List[Dict[str, Any]]
    red_flags: List[Dict[str, Any]]
    verdict: Dict[str, Any]

class PrecedentValidationService:
    """판례 기반 검증 서비스"""
    
    def __init__(self):
        try:
            self.faiss_db = FAISSPrecedentsDB()
            print("✅ FAISS DB 초기화 완료")
        except Exception as e:
            print(f"⚠️ FAISS DB 초기화 실패: {e}")
            self.faiss_db = None
        
        try:
            self.openai_client = AsyncOpenAI()
            print("✅ OpenAI 클라이언트 초기화 완료")
        except Exception as e:
            print(f"⚠️ OpenAI 클라이언트 초기화 실패: {e}")
            self.openai_client = None
    
    async def validate_requirements(
        self,
        hs_code: str,
        product_name: str,
        our_requirements: Dict[str, Any],
        precedents: Optional[List[Dict[str, Any]]] = None
    ) -> PrecedentValidationResult:
        """
        판례와 우리 분석 결과를 비교하여 검증
        
        Args:
            hs_code: HS 코드
            product_name: 상품명
            our_requirements: 우리 분석 결과 (certifications, documents 등)
            precedents: 판례 데이터 (없으면 FAISS DB에서 자동 조회)
        
        Returns:
            PrecedentValidationResult: 검증 결과
        """
        print(f"\n🔍 판례 기반 검증 시작 - HS: {hs_code}, 상품: {product_name}")
        
        try:
            # 1. 판례 데이터 가져오기 (FAISS DB에서)
            if precedents is None:
                precedents = await self._get_precedents_from_db(hs_code, product_name)
            
            if not precedents:
                print(f"⚠️ 판례 없음 - 검증 스킵")
                return self._create_empty_result()
            
            print(f"  📊 판례 {len(precedents)}개 분석 중...")
            
            # 2. 판례에서 요구사항 추출 (LLM)
            precedent_requirements = await self._extract_requirements_from_precedents(
                precedents, hs_code, product_name
            )
            
            # 3. 우리 요구사항과 비교
            comparison_result = await self._compare_requirements(
                our_requirements=our_requirements,
                precedent_requirements=precedent_requirements
            )
            
            # 4. 검증 점수 계산
            validation_score = self._calculate_validation_score(
                comparison_result, precedent_requirements
            )
            
            # 5. 누락/추가 요구사항 식별
            missing = self._find_missing_requirements(
                comparison_result, precedent_requirements, precedents
            )
            extra = self._find_extra_requirements(
                our_requirements, comparison_result
            )
            
            # 6. Red Flags (경고) 생성
            red_flags = self._generate_red_flags(missing, extra)
            
            # 7. 최종 판정
            verdict = self._make_verdict(validation_score, red_flags)
            
            result = PrecedentValidationResult(
                validation_score=validation_score,
                precedents_analyzed=len(precedents),
                precedents_source="faiss_db",
                matched_requirements=comparison_result['matched'],
                missing_requirements=missing,
                extra_requirements=extra,
                red_flags=red_flags,
                verdict=verdict
            )
            
            print(f"✅ 판례 검증 완료 - 점수: {validation_score:.2f}, 판정: {verdict['status']}")
            
            return result
            
        except Exception as e:
            print(f"❌ 판례 검증 실패: {e}")
            import traceback
            traceback.print_exc()
            return self._create_empty_result()
    
    async def _get_precedents_from_db(
        self, 
        hs_code: str, 
        product_name: str
    ) -> List[Dict[str, Any]]:
        """FAISS DB에서 판례 가져오기"""
        if not self.faiss_db:
            print("⚠️ FAISS DB 없음")
            return []
        
        try:
            # 1. HS 코드로 직접 검색 (정확 매칭)
            direct_precedents = self.faiss_db.search_by_hs_code(
                hs_code=hs_code,
                n_results=10
            )
            
            # 2. 의미론적 유사 검색 (상품명 기반)
            similar_precedents = self.faiss_db.search_similar_precedents(
                query=f"{product_name} {hs_code}",
                n_results=5
            )
            
            # 3. 병합 (중복 제거)
            all_precedents = direct_precedents + similar_precedents
            seen_ids = set()
            unique_precedents = []
            
            for p in all_precedents:
                if p['precedent_id'] not in seen_ids:
                    seen_ids.add(p['precedent_id'])
                    unique_precedents.append(p)
            
            print(f"  📊 FAISS DB 검색 완료: {len(unique_precedents)}개 판례")
            return unique_precedents
            
        except Exception as e:
            print(f"❌ FAISS DB 검색 실패: {e}")
            return []
    
    async def _extract_requirements_from_precedents(
        self,
        precedents: List[Dict[str, Any]],
        hs_code: str,
        product_name: str
    ) -> Dict[str, Any]:
        """판례에서 요구사항 추출 (LLM 사용)"""
        if not self.openai_client:
            print("⚠️ OpenAI 클라이언트 없음 - 기본 추출 사용")
            return self._extract_requirements_simple(precedents)
        
        try:
            # 판례 텍스트 결합 (상위 5개만)
            precedent_texts = []
            for i, p in enumerate(precedents[:5], 1):
                text = p.get('text', '')[:500]  # 500자까지만
                precedent_texts.append(f"판례 {i}: {text}")
            
            combined_text = "\n\n".join(precedent_texts)
            
            prompt = f"""
다음 CBP 판례들에서 HS 코드 {hs_code} ({product_name}) 제품의 수입 요구사항을 추출하세요.

판례 데이터:
{combined_text}

추출할 항목:
1. 필요한 인증 (예: FDA VCRP 등록, CPSC 인증)
2. 필요한 서류 (예: 성분 안전성 데이터, 라벨 샘플)
3. 규제 요구사항 (예: 라벨링 규정, 성분 제한)

JSON 형식으로 반환:
{{
  "certifications": ["인증명1", "인증명2"],
  "documents": ["서류명1", "서류명2"],
  "regulations": ["규정1", "규정2"]
}}

판례에 명시적으로 언급된 것만 추출하세요.
"""
            
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            result = json.loads(content)
            
            print(f"  ✅ LLM 요구사항 추출 완료: {len(result.get('certifications', []))}개 인증, {len(result.get('documents', []))}개 서류")
            
            return result
            
        except Exception as e:
            print(f"⚠️ LLM 추출 실패: {e} - 기본 추출 사용")
            return self._extract_requirements_simple(precedents)
    
    def _extract_requirements_simple(
        self, 
        precedents: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """간단한 키워드 기반 요구사항 추출"""
        certifications = []
        documents = []
        regulations = []
        
        cert_keywords = ['registration', 'certification', 'approval', 'license', 'permit']
        doc_keywords = ['document', 'report', 'certificate', 'declaration', 'statement']
        reg_keywords = ['regulation', 'requirement', 'standard', 'compliance', 'labeling']
        
        for p in precedents[:10]:  # 상위 10개만
            text = p.get('text', '').lower()
            
            # 인증 추출
            for keyword in cert_keywords:
                if keyword in text:
                    certifications.append(f"{p.get('source', 'CBP')} {keyword}")
            
            # 서류 추출
            for keyword in doc_keywords:
                if keyword in text:
                    documents.append(f"{keyword} required")
            
            # 규정 추출
            for keyword in reg_keywords:
                if keyword in text:
                    regulations.append(f"{keyword} compliance")
        
        # 중복 제거
        return {
            "certifications": list(set(certifications))[:10],
            "documents": list(set(documents))[:10],
            "regulations": list(set(regulations))[:10]
        }
    
    async def _compare_requirements(
        self,
        our_requirements: Dict[str, Any],
        precedent_requirements: Dict[str, Any]
    ) -> Dict[str, Any]:
        """우리 요구사항과 판례 요구사항 비교"""
        matched = []
        
        our_certs = our_requirements.get('certifications', [])
        prec_certs = precedent_requirements.get('certifications', [])
        
        # 인증 요건 비교
        for our_cert in our_certs:
            our_name = our_cert.get('name', '') if isinstance(our_cert, dict) else str(our_cert)
            
            for prec_cert in prec_certs:
                # 간단한 키워드 매칭
                similarity = self._calculate_text_similarity(our_name, prec_cert)
                
                if similarity > 0.5:  # 50% 이상 유사
                    matched.append({
                        "our_requirement": our_name,
                        "precedent_requirement": prec_cert,
                        "similarity_score": similarity,
                        "type": "certification",
                        "status": "matched"
                    })
                    break
        
        # 서류 요건 비교
        our_docs = our_requirements.get('documents', [])
        prec_docs = precedent_requirements.get('documents', [])
        
        for our_doc in our_docs:
            our_name = our_doc.get('name', '') if isinstance(our_doc, dict) else str(our_doc)
            
            for prec_doc in prec_docs:
                similarity = self._calculate_text_similarity(our_name, prec_doc)
                
                if similarity > 0.5:
                    matched.append({
                        "our_requirement": our_name,
                        "precedent_requirement": prec_doc,
                        "similarity_score": similarity,
                        "type": "document",
                        "status": "matched"
                    })
                    break
        
        return {
            "matched": matched,
            "total_our_requirements": len(our_certs) + len(our_docs),
            "total_precedent_requirements": len(prec_certs) + len(prec_docs)
        }
    
    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """간단한 텍스트 유사도 계산 (단어 기반)"""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1 & words2
        union = words1 | words2
        
        return len(intersection) / len(union) if union else 0.0
    
    def _calculate_validation_score(
        self,
        comparison_result: Dict[str, Any],
        precedent_requirements: Dict[str, Any]
    ) -> float:
        """검증 점수 계산 (0.0 - 1.0)"""
        matched_count = len(comparison_result['matched'])
        total_precedent = comparison_result.get('total_precedent_requirements', 1)
        
        if total_precedent == 0:
            return 0.5  # 판례에 요구사항 없으면 중립 점수
        
        # 판례 요구사항 중 몇 개나 우리가 찾았는가?
        coverage_score = matched_count / total_precedent
        
        # 평균 유사도 점수
        if matched_count > 0:
            avg_similarity = sum(
                m['similarity_score'] for m in comparison_result['matched']
            ) / matched_count
        else:
            avg_similarity = 0.0
        
        # 가중 평균 (커버리지 70%, 유사도 30%)
        validation_score = (coverage_score * 0.7) + (avg_similarity * 0.3)
        
        return min(validation_score, 1.0)
    
    def _find_missing_requirements(
        self,
        comparison_result: Dict[str, Any],
        precedent_requirements: Dict[str, Any],
        precedents: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """판례에 있는데 우리가 못 찾은 요구사항"""
        missing = []
        matched_precedent_reqs = [
            m['precedent_requirement'] for m in comparison_result['matched']
        ]
        
        # 판례의 모든 요구사항 확인
        all_precedent_reqs = []
        all_precedent_reqs.extend(precedent_requirements.get('certifications', []))
        all_precedent_reqs.extend(precedent_requirements.get('documents', []))
        all_precedent_reqs.extend(precedent_requirements.get('regulations', []))
        
        for prec_req in all_precedent_reqs:
            if prec_req not in matched_precedent_reqs:
                # 관련 판례 찾기
                related_precedent = next(
                    (p for p in precedents if prec_req.lower() in p.get('text', '').lower()),
                    precedents[0] if precedents else {}
                )
                
                missing.append({
                    "requirement": prec_req,
                    "precedent_id": related_precedent.get('precedent_id', 'unknown'),
                    "precedent_case_type": related_precedent.get('case_type', 'unknown'),
                    "severity": self._assess_severity(prec_req)
                })
        
        return missing[:5]  # 최대 5개만
    
    def _find_extra_requirements(
        self,
        our_requirements: Dict[str, Any],
        comparison_result: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """우리가 추가로 찾은 요구사항 (판례에 없음)"""
        extra = []
        matched_our_reqs = [
            m['our_requirement'] for m in comparison_result['matched']
        ]
        
        # 우리 인증 요건 확인
        our_certs = our_requirements.get('certifications', [])
        for cert in our_certs:
            cert_name = cert.get('name', '') if isinstance(cert, dict) else str(cert)
            if cert_name and cert_name not in matched_our_reqs:
                extra.append({
                    "requirement": cert_name,
                    "type": "certification",
                    "note": "판례에 없는 새로운 요구사항 (최신 규제 가능성)"
                })
        
        # 우리 서류 요건 확인
        our_docs = our_requirements.get('documents', [])
        for doc in our_docs:
            doc_name = doc.get('name', '') if isinstance(doc, dict) else str(doc)
            if doc_name and doc_name not in matched_our_reqs:
                extra.append({
                    "requirement": doc_name,
                    "type": "document",
                    "note": "판례에 없는 새로운 요구사항 (상세 분석)"
                })
        
        return extra[:5]  # 최대 5개만
    
    def _assess_severity(self, requirement: str) -> str:
        """요구사항 심각도 평가"""
        req_lower = requirement.lower()
        
        high_keywords = ['prohibited', 'banned', 'illegal', 'violation', 'penalty']
        medium_keywords = ['required', 'mandatory', 'must', 'certification', 'approval']
        
        if any(keyword in req_lower for keyword in high_keywords):
            return "high"
        elif any(keyword in req_lower for keyword in medium_keywords):
            return "medium"
        else:
            return "low"
    
    def _generate_red_flags(
        self,
        missing: List[Dict[str, Any]],
        extra: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """경고 항목 생성"""
        red_flags = []
        
        # 누락된 요구사항 → Red Flag
        for miss in missing:
            red_flags.append({
                "type": "missing_requirement",
                "severity": miss['severity'],
                "description": f"판례에서 '{miss['requirement']}'가 언급되었으나 분석 결과에 없음",
                "precedent_case_id": miss['precedent_id'],
                "recommendation": f"{miss['requirement']} 추가 확인 필요"
            })
        
        # 추가 요구사항 → 낮은 우선순위 플래그
        for ext in extra[:2]:  # 최대 2개만
            red_flags.append({
                "type": "extra_requirement",
                "severity": "low",
                "description": f"판례에 없는 새로운 요구사항 발견: '{ext['requirement']}'",
                "note": ext['note'],
                "recommendation": "최신 규제 확인 또는 더 상세한 분석 결과"
            })
        
        return red_flags
    
    def _make_verdict(
        self,
        validation_score: float,
        red_flags: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """최종 판정"""
        high_severity_flags = [f for f in red_flags if f.get('severity') == 'high']
        medium_severity_flags = [f for f in red_flags if f.get('severity') == 'medium']
        
        if validation_score >= 0.85 and len(high_severity_flags) == 0:
            return {
                "status": "RELIABLE",
                "confidence": "HIGH",
                "reason": f"판례 일치도 {validation_score:.0%}, 중대 경고 없음",
                "action": "수입 진행 가능"
            }
        elif validation_score >= 0.7 and len(high_severity_flags) <= 1:
            action = "수입 진행 가능"
            if medium_severity_flags:
                action = f"추가 확인 필요: {medium_severity_flags[0]['recommendation']}"
            
            return {
                "status": "NEEDS_REVIEW",
                "confidence": "MEDIUM",
                "reason": f"판례 일치도 {validation_score:.0%}, 경고 {len(red_flags)}건",
                "action": action
            }
        else:
            return {
                "status": "UNRELIABLE",
                "confidence": "LOW",
                "reason": f"판례 일치도 {validation_score:.0%}, 중대 경고 {len(high_severity_flags)}건",
                "action": "전문가 상담 권장"
            }
    
    def _create_empty_result(self) -> PrecedentValidationResult:
        """빈 검증 결과 생성"""
        return PrecedentValidationResult(
            validation_score=0.5,
            precedents_analyzed=0,
            precedents_source="none",
            matched_requirements=[],
            missing_requirements=[],
            extra_requirements=[],
            red_flags=[],
            verdict={
                "status": "NO_PRECEDENTS",
                "confidence": "N/A",
                "reason": "판례 데이터 없음",
                "action": "기본 분석 결과 사용"
            }
        )

# 전역 인스턴스
_precedent_validation_service = None

def get_precedent_validation_service() -> PrecedentValidationService:
    """싱글톤 인스턴스 반환"""
    global _precedent_validation_service
    if _precedent_validation_service is None:
        _precedent_validation_service = PrecedentValidationService()
    return _precedent_validation_service

