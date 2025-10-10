"""
규정 교차 검증 서비스
FDA vs USDA, 연방 vs 주 규정 간 충돌 검사 및 해결 방안 제시
"""

import asyncio
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import json
from datetime import datetime

@dataclass
class RegulationConflict:
    """규정 충돌 정보"""
    conflict_type: str  # "agency_conflict", "federal_state_conflict", "international_conflict"
    conflicting_agencies: List[str]
    conflict_description: str
    severity: str  # "low", "medium", "high", "critical"
    resolution_guidance: str
    affected_requirements: List[str]

@dataclass
class CrossValidationResult:
    """교차 검증 결과"""
    hs_code: str
    product_name: str
    conflicts_found: List[RegulationConflict]
    validation_score: float  # 0.0 ~ 1.0
    recommendations: List[str]
    last_updated: datetime

class CrossValidationService:
    """규정 교차 검증 서비스"""
    
    def __init__(self):
        self.conflict_patterns = self._build_conflict_patterns()
        self.resolution_rules = self._build_resolution_rules()
    
    def _build_conflict_patterns(self) -> Dict[str, Dict[str, Any]]:
        """충돌 패턴 정의"""
        return {
            "organic_certification": {
                "pattern": ["organic", "certified organic", "usda organic"],
                "conflicting_keywords": ["non-organic", "conventional", "synthetic"],
                "agencies": ["FDA", "USDA"],
                "severity": "high"
            },
            "food_additive": {
                "pattern": ["food additive", "preservative", "artificial"],
                "conflicting_keywords": ["natural", "organic", "no additives"],
                "agencies": ["FDA", "USDA"],
                "severity": "medium"
            },
            "pesticide_residue": {
                "pattern": ["pesticide", "residue", "MRL"],
                "conflicting_keywords": ["organic", "pesticide-free", "natural"],
                "agencies": ["FDA", "EPA", "USDA"],
                "severity": "critical"
            },
            "safety_standards": {
                "pattern": ["safety", "hazard", "risk"],
                "conflicting_keywords": ["safe", "non-toxic", "harmless"],
                "agencies": ["CPSC", "FDA", "EPA"],
                "severity": "high"
            },
            "labeling_requirements": {
                "pattern": ["labeling", "disclosure", "declaration"],
                "conflicting_keywords": ["voluntary", "optional", "not required"],
                "agencies": ["FDA", "FTC", "USDA"],
                "severity": "medium"
            }
        }
    
    def _build_resolution_rules(self) -> Dict[str, str]:
        """해결 규칙 정의"""
        return {
            "FDA_USDA_conflict": "USDA 규정이 식품 관련 사항에서 우선 적용됩니다.",
            "FDA_EPA_conflict": "EPA 규정이 환경/화학물질 관련 사항에서 우선 적용됩니다.",
            "CPSC_FDA_conflict": "CPSC 규정이 소비자 안전 관련 사항에서 우선 적용됩니다.",
            "federal_state_conflict": "연방 규정이 주 규정보다 우선 적용됩니다.",
            "international_conflict": "미국 내 규정이 국제 표준보다 우선 적용됩니다."
        }
    
    async def validate_regulations(
        self, 
        hs_code: str, 
        product_name: str,
        fda_results: Dict[str, Any],
        usda_results: Dict[str, Any],
        epa_results: Dict[str, Any],
        cpsc_results: Dict[str, Any],
        fcc_results: Dict[str, Any]
    ) -> CrossValidationResult:
        """규정 교차 검증 수행"""
        
        print(f"🔍 규정 교차 검증 시작 - HS코드: {hs_code}, 상품: {product_name}")
        
        conflicts = []
        
        # 1. 기관 간 충돌 검사
        agency_conflicts = await self._check_agency_conflicts(
            fda_results, usda_results, epa_results, cpsc_results, fcc_results
        )
        conflicts.extend(agency_conflicts)
        
        # 2. 연방 vs 주 규정 충돌 검사
        federal_state_conflicts = await self._check_federal_state_conflicts(
            fda_results, usda_results, epa_results, cpsc_results, fcc_results
        )
        conflicts.extend(federal_state_conflicts)
        
        # 3. 국제 표준 충돌 검사
        international_conflicts = await self._check_international_conflicts(
            fda_results, usda_results, epa_results, cpsc_results, fcc_results
        )
        conflicts.extend(international_conflicts)
        
        # 4. 검증 점수 계산
        validation_score = self._calculate_validation_score(conflicts)
        
        # 5. 권고사항 생성
        recommendations = self._generate_recommendations(conflicts, hs_code)
        
        result = CrossValidationResult(
            hs_code=hs_code,
            product_name=product_name,
            conflicts_found=conflicts,
            validation_score=validation_score,
            recommendations=recommendations,
            last_updated=datetime.now()
        )
        
        print(f"✅ 교차 검증 완료 - 충돌 {len(conflicts)}개 발견, 검증점수: {validation_score:.2f}")
        
        return result
    
    async def _check_agency_conflicts(
        self, 
        fda_results: Dict[str, Any],
        usda_results: Dict[str, Any], 
        epa_results: Dict[str, Any],
        cpsc_results: Dict[str, Any],
        fcc_results: Dict[str, Any]
    ) -> List[RegulationConflict]:
        """기관 간 충돌 검사"""
        conflicts = []
        
        # FDA vs USDA 충돌 검사
        if fda_results and usda_results:
            fda_conflicts = self._extract_conflict_keywords(fda_results)
            usda_conflicts = self._extract_conflict_keywords(usda_results)
            
            for pattern_name, pattern_data in self.conflict_patterns.items():
                fda_matches = self._find_keyword_matches(fda_conflicts, pattern_data["pattern"])
                usda_matches = self._find_keyword_matches(usda_conflicts, pattern_data["conflicting_keywords"])
                
                if fda_matches and usda_matches:
                    conflicts.append(RegulationConflict(
                        conflict_type="agency_conflict",
                        conflicting_agencies=["FDA", "USDA"],
                        conflict_description=f"{pattern_name} 관련 FDA와 USDA 규정 간 충돌 발견",
                        severity=pattern_data["severity"],
                        resolution_guidance=self.resolution_rules.get("FDA_USDA_conflict", "규정 우선순위 확인 필요"),
                        affected_requirements=fda_matches + usda_matches
                    ))
        
        # FDA vs EPA 충돌 검사
        if fda_results and epa_results:
            fda_conflicts = self._extract_conflict_keywords(fda_results)
            epa_conflicts = self._extract_conflict_keywords(epa_results)
            
            for pattern_name, pattern_data in self.conflict_patterns.items():
                fda_matches = self._find_keyword_matches(fda_conflicts, pattern_data["pattern"])
                epa_matches = self._find_keyword_matches(epa_conflicts, pattern_data["conflicting_keywords"])
                
                if fda_matches and epa_matches:
                    conflicts.append(RegulationConflict(
                        conflict_type="agency_conflict",
                        conflicting_agencies=["FDA", "EPA"],
                        conflict_description=f"{pattern_name} 관련 FDA와 EPA 규정 간 충돌 발견",
                        severity=pattern_data["severity"],
                        resolution_guidance=self.resolution_rules.get("FDA_EPA_conflict", "규정 우선순위 확인 필요"),
                        affected_requirements=fda_matches + epa_matches
                    ))
        
        # CPSC vs FDA 충돌 검사
        if cpsc_results and fda_results:
            cpsc_conflicts = self._extract_conflict_keywords(cpsc_results)
            fda_conflicts = self._extract_conflict_keywords(fda_results)
            
            for pattern_name, pattern_data in self.conflict_patterns.items():
                cpsc_matches = self._find_keyword_matches(cpsc_conflicts, pattern_data["pattern"])
                fda_matches = self._find_keyword_matches(fda_conflicts, pattern_data["conflicting_keywords"])
                
                if cpsc_matches and fda_matches:
                    conflicts.append(RegulationConflict(
                        conflict_type="agency_conflict",
                        conflicting_agencies=["CPSC", "FDA"],
                        conflict_description=f"{pattern_name} 관련 CPSC와 FDA 규정 간 충돌 발견",
                        severity=pattern_data["severity"],
                        resolution_guidance=self.resolution_rules.get("CPSC_FDA_conflict", "규정 우선순위 확인 필요"),
                        affected_requirements=cpsc_matches + fda_matches
                    ))
        
        return conflicts
    
    async def _check_federal_state_conflicts(
        self, 
        fda_results: Dict[str, Any],
        usda_results: Dict[str, Any], 
        epa_results: Dict[str, Any],
        cpsc_results: Dict[str, Any],
        fcc_results: Dict[str, Any]
    ) -> List[RegulationConflict]:
        """연방 vs 주 규정 충돌 검사"""
        conflicts = []
        
        # 현재는 연방 규정만 검사하므로 실제 구현에서는 주별 규정 데이터가 필요
        # 예시: 캘리포니아 Prop 65, 뉴욕 주 규정 등
        
        all_results = [fda_results, usda_results, epa_results, cpsc_results, fcc_results]
        for result in all_results:
            if result and "state_regulations" in result:
                state_conflicts = self._extract_conflict_keywords(result["state_regulations"])
                federal_conflicts = self._extract_conflict_keywords(result)
                
                for pattern_name, pattern_data in self.conflict_patterns.items():
                    state_matches = self._find_keyword_matches(state_conflicts, pattern_data["pattern"])
                    federal_matches = self._find_keyword_matches(federal_conflicts, pattern_data["conflicting_keywords"])
                    
                    if state_matches and federal_matches:
                        conflicts.append(RegulationConflict(
                            conflict_type="federal_state_conflict",
                            conflicting_agencies=["Federal", "State"],
                            conflict_description=f"{pattern_name} 관련 연방과 주 규정 간 충돌 발견",
                            severity=pattern_data["severity"],
                            resolution_guidance=self.resolution_rules.get("federal_state_conflict", "연방 규정 우선 적용"),
                            affected_requirements=state_matches + federal_matches
                        ))
        
        return conflicts
    
    async def _check_international_conflicts(
        self, 
        fda_results: Dict[str, Any],
        usda_results: Dict[str, Any], 
        epa_results: Dict[str, Any],
        cpsc_results: Dict[str, Any],
        fcc_results: Dict[str, Any]
    ) -> List[RegulationConflict]:
        """국제 표준 충돌 검사"""
        conflicts = []
        
        # 국제 표준 (Codex, ISO, IEC 등)과의 충돌 검사
        all_results = [fda_results, usda_results, epa_results, cpsc_results, fcc_results]
        for result in all_results:
            if result and "international_standards" in result:
                intl_conflicts = self._extract_conflict_keywords(result["international_standards"])
                us_conflicts = self._extract_conflict_keywords(result)
                
                for pattern_name, pattern_data in self.conflict_patterns.items():
                    intl_matches = self._find_keyword_matches(intl_conflicts, pattern_data["pattern"])
                    us_matches = self._find_keyword_matches(us_conflicts, pattern_data["conflicting_keywords"])
                    
                    if intl_matches and us_matches:
                        conflicts.append(RegulationConflict(
                            conflict_type="international_conflict",
                            conflicting_agencies=["US", "International"],
                            conflict_description=f"{pattern_name} 관련 미국과 국제 표준 간 충돌 발견",
                            severity=pattern_data["severity"],
                            resolution_guidance=self.resolution_rules.get("international_conflict", "미국 규정 우선 적용"),
                            affected_requirements=intl_matches + us_matches
                        ))
        
        return conflicts
    
    def _extract_conflict_keywords(self, results: Dict[str, Any]) -> List[str]:
        """결과에서 충돌 키워드 추출"""
        keywords = []
        
        if not results:
            return keywords
        
        # certifications에서 키워드 추출
        if "certifications" in results:
            for cert in results["certifications"]:
                if "name" in cert:
                    keywords.append(cert["name"].lower())
                if "description" in cert:
                    keywords.extend(cert["description"].lower().split())
        
        # documents에서 키워드 추출
        if "documents" in results:
            for doc in results["documents"]:
                if "name" in doc:
                    keywords.append(doc["name"].lower())
                if "description" in doc:
                    keywords.extend(doc["description"].lower().split())
        
        # detailed_regulations에서 키워드 추출
        if "detailed_regulations" in results:
            for reg in results["detailed_regulations"]:
                if "title" in reg:
                    keywords.append(reg["title"].lower())
                if "content" in reg:
                    keywords.extend(reg["content"].lower().split())
        
        return keywords
    
    def _find_keyword_matches(self, keywords: List[str], patterns: List[str]) -> List[str]:
        """키워드에서 패턴 매칭"""
        matches = []
        for keyword in keywords:
            for pattern in patterns:
                if pattern.lower() in keyword or keyword in pattern.lower():
                    matches.append(keyword)
        return list(set(matches))  # 중복 제거
    
    def _calculate_validation_score(self, conflicts: List[RegulationConflict]) -> float:
        """검증 점수 계산 (0.0 ~ 1.0)"""
        if not conflicts:
            return 1.0
        
        severity_weights = {
            "low": 0.1,
            "medium": 0.3,
            "high": 0.6,
            "critical": 1.0
        }
        
        total_penalty = 0.0
        for conflict in conflicts:
            penalty = severity_weights.get(conflict.severity, 0.5)
            total_penalty += penalty
        
        # 최대 패널티는 2.0으로 제한
        max_penalty = min(total_penalty, 2.0)
        score = max(0.0, 1.0 - (max_penalty / 2.0))
        
        return round(score, 2)
    
    def _generate_recommendations(
        self, 
        conflicts: List[RegulationConflict], 
        hs_code: str
    ) -> List[str]:
        """권고사항 생성"""
        recommendations = []
        
        if not conflicts:
            recommendations.append("규정 간 충돌이 발견되지 않았습니다. 현재 분석된 요구사항을 그대로 따르시면 됩니다.")
            return recommendations
        
        # 충돌별 권고사항
        for conflict in conflicts:
            if conflict.conflict_type == "agency_conflict":
                recommendations.append(
                    f"⚠️ {', '.join(conflict.conflicting_agencies)} 간 규정 충돌 발견: {conflict.conflict_description}. "
                    f"해결 방안: {conflict.resolution_guidance}"
                )
            elif conflict.conflict_type == "federal_state_conflict":
                recommendations.append(
                    f"⚠️ 연방-주 규정 충돌 발견: {conflict.conflict_description}. "
                    f"해결 방안: {conflict.resolution_guidance}"
                )
            elif conflict.conflict_type == "international_conflict":
                recommendations.append(
                    f"⚠️ 국제 표준 충돌 발견: {conflict.conflict_description}. "
                    f"해결 방안: {conflict.resolution_guidance}"
                )
        
        # 일반적인 권고사항
        recommendations.append("📋 충돌 해결을 위해 관련 기관에 직접 문의하시기 바랍니다.")
        recommendations.append("🔍 최신 규정 업데이트를 정기적으로 확인하시기 바랍니다.")
        
        return recommendations
    
    def format_cross_validation_result(self, result: CrossValidationResult) -> Dict[str, Any]:
        """교차 검증 결과를 API 응답 형식으로 변환"""
        return {
            "cross_validation": {
                "hs_code": result.hs_code,
                "product_name": result.product_name,
                "validation_score": result.validation_score,
                "conflicts_count": len(result.conflicts_found),
                "conflicts": [
                    {
                        "type": conflict.conflict_type,
                        "agencies": conflict.conflicting_agencies,
                        "description": conflict.conflict_description,
                        "severity": conflict.severity,
                        "resolution": conflict.resolution_guidance,
                        "affected_requirements": conflict.affected_requirements
                    }
                    for conflict in result.conflicts_found
                ],
                "recommendations": result.recommendations,
                "last_updated": result.last_updated.isoformat(),
                "status": "completed"
            }
        }
