"""
신뢰도 계산 서비스
가중치 기반 신뢰도 계산 및 5단계 등급 변환
"""

from typing import Dict, List, Any, Tuple
from enum import Enum


class ConfidenceLevel(Enum):
    """신뢰도 등급"""
    HIGH = "상"           # 0.8-1.0
    MEDIUM_HIGH = "중상"  # 0.6-0.8
    MEDIUM = "중"         # 0.4-0.6
    MEDIUM_LOW = "중하"   # 0.2-0.4
    LOW = "하"            # 0.0-0.2


class ConfidenceCalculator:
    """신뢰도 계산기"""
    
    def __init__(self):
        # 가중치 설정
        self.weights = {
            "source_quality": 0.30,      # 출처 품질 (공식 API vs 웹 스크래핑)
            "data_completeness": 0.25,   # 데이터 완전성
            "agency_match": 0.20,        # 기관 매칭 정확도
            "recency": 0.15,             # 최신성
            "consistency": 0.10          # 일관성 (출처 간 일치도)
        }
    
    def calculate_confidence(
        self,
        sources: List[Dict[str, Any]],
        requirements: List[Dict[str, Any]],
        target_agencies: List[str],
        hs_code_mapping_confidence: float = 0.5
    ) -> Dict[str, Any]:
        """
        종합 신뢰도 계산
        
        Args:
            sources: 출처 리스트 (citations)
            requirements: 요건 리스트
            target_agencies: 타겟 기관 리스트
            hs_code_mapping_confidence: HS 코드 매핑 신뢰도
        
        Returns:
            {
                "score": 0.75,
                "level": "중상",
                "level_enum": "MEDIUM_HIGH",
                "breakdown": {
                    "source_quality": 0.8,
                    "data_completeness": 0.7,
                    "agency_match": 0.75,
                    "recency": 0.6,
                    "consistency": 0.8
                },
                "factors": ["High quality sources", "Good data coverage"],
                "warnings": ["Some data may be outdated"]
            }
        """
        
        # 1. 출처 품질 점수
        source_quality = self._calculate_source_quality(sources)
        
        # 2. 데이터 완전성 점수
        data_completeness = self._calculate_data_completeness(requirements, sources)
        
        # 3. 기관 매칭 점수
        agency_match = self._calculate_agency_match(sources, target_agencies)
        
        # 4. 최신성 점수
        recency = self._calculate_recency(requirements)
        
        # 5. 일관성 점수
        consistency = self._calculate_consistency(requirements)
        
        # 가중 평균 계산
        weighted_score = (
            source_quality * self.weights["source_quality"] +
            data_completeness * self.weights["data_completeness"] +
            agency_match * self.weights["agency_match"] +
            recency * self.weights["recency"] +
            consistency * self.weights["consistency"]
        )
        
        # HS 코드 매핑 신뢰도 반영 (보정)
        final_score = weighted_score * (0.7 + 0.3 * hs_code_mapping_confidence)
        final_score = min(1.0, max(0.0, final_score))  # 0-1 범위로 제한
        
        # 등급 변환
        level, level_enum = self._score_to_level(final_score)
        
        # 요인 및 경고 생성
        factors = self._generate_factors(source_quality, data_completeness, agency_match, recency, consistency)
        warnings = self._generate_warnings(source_quality, data_completeness, agency_match, recency, consistency)
        
        return {
            "score": round(final_score, 2),
            "level": level,
            "level_enum": level_enum.name,
            "breakdown": {
                "source_quality": round(source_quality, 2),
                "data_completeness": round(data_completeness, 2),
                "agency_match": round(agency_match, 2),
                "recency": round(recency, 2),
                "consistency": round(consistency, 2)
            },
            "factors": factors,
            "warnings": warnings
        }
    
    def _calculate_source_quality(self, sources: List[Dict[str, Any]]) -> float:
        """출처 품질 점수 계산"""
        if not sources:
            return 0.0
        
        quality_scores = []
        for source in sources:
            url = source.get("url", "")
            agency = source.get("agency", "")
            
            # 공식 API 출처 (가장 높음)
            if "api.fda.gov" in url or "api.census.gov" in url or "api.nal.usda.gov" in url:
                quality_scores.append(1.0)
            # 공식 .gov 사이트
            elif ".gov" in url:
                quality_scores.append(0.8)
            # 기타
            else:
                quality_scores.append(0.5)
        
        return sum(quality_scores) / len(quality_scores)
    
    def _calculate_data_completeness(self, requirements: List[Dict[str, Any]], sources: List[Dict[str, Any]]) -> float:
        """데이터 완전성 점수 계산"""
        score = 0.0
        
        # 요건 개수 (많을수록 좋음, 최대 20개)
        req_count = len(requirements)
        score += min(1.0, req_count / 20) * 0.5
        
        # 출처 개수 (많을수록 좋음, 최대 10개)
        source_count = len(sources)
        score += min(1.0, source_count / 10) * 0.5
        
        return min(1.0, score)
    
    def _calculate_agency_match(self, sources: List[Dict[str, Any]], target_agencies: List[str]) -> float:
        """기관 매칭 점수 계산"""
        if not target_agencies or not sources:
            return 0.5  # 중립
        
        # 출처에 포함된 기관
        source_agencies = set(s.get("agency", "").upper() for s in sources)
        target_agencies_set = set(a.upper() for a in target_agencies)
        
        # 교집합 비율
        if not target_agencies_set:
            return 0.5
        
        matched = len(source_agencies & target_agencies_set)
        total = len(target_agencies_set)
        
        return matched / total if total > 0 else 0.5
    
    def _calculate_recency(self, requirements: List[Dict[str, Any]]) -> float:
        """최신성 점수 계산"""
        if not requirements:
            return 0.5
        
        from datetime import datetime, timedelta
        
        recent_count = 0
        dated_count = 0
        
        for req in requirements:
            effective_date = req.get("effective_date", "")
            if effective_date:
                try:
                    date = datetime.fromisoformat(effective_date.replace("Z", "+00:00"))
                    dated_count += 1
                    
                    # 3년 이내면 최신
                    if datetime.now() - date < timedelta(days=365 * 3):
                        recent_count += 1
                except:
                    pass
        
        if dated_count == 0:
            return 0.5  # 날짜 정보 없음
        
        return recent_count / dated_count
    
    def _calculate_consistency(self, requirements: List[Dict[str, Any]]) -> float:
        """일관성 점수 계산"""
        if len(requirements) < 2:
            return 1.0  # 단일 요건은 일관성 문제 없음
        
        # 간단한 휴리스틱: 같은 기관에서 온 요건이 많을수록 일관성 높음
        agencies = [r.get("agency", "") for r in requirements]
        if not agencies:
            return 0.5
        
        # 가장 많이 나온 기관의 비율
        from collections import Counter
        most_common_count = Counter(agencies).most_common(1)[0][1]
        
        return min(1.0, most_common_count / len(agencies) * 1.5)
    
    def _score_to_level(self, score: float) -> Tuple[str, ConfidenceLevel]:
        """점수를 5단계 등급으로 변환"""
        if score >= 0.8:
            return "상", ConfidenceLevel.HIGH
        elif score >= 0.6:
            return "중상", ConfidenceLevel.MEDIUM_HIGH
        elif score >= 0.4:
            return "중", ConfidenceLevel.MEDIUM
        elif score >= 0.2:
            return "중하", ConfidenceLevel.MEDIUM_LOW
        else:
            return "하", ConfidenceLevel.LOW
    
    def _generate_factors(self, source_quality, data_completeness, agency_match, recency, consistency) -> List[str]:
        """긍정적 요인 생성"""
        factors = []
        
        if source_quality >= 0.8:
            factors.append("고품질 공식 출처 사용")
        if data_completeness >= 0.7:
            factors.append("충분한 데이터 확보")
        if agency_match >= 0.7:
            factors.append("타겟 기관 정확히 매칭")
        if recency >= 0.7:
            factors.append("최신 규정 정보")
        if consistency >= 0.8:
            factors.append("출처 간 일관성 높음")
        
        return factors if factors else ["기본 분석 완료"]
    
    def _generate_warnings(self, source_quality, data_completeness, agency_match, recency, consistency) -> List[str]:
        """경고 사항 생성"""
        warnings = []
        
        if source_quality < 0.5:
            warnings.append("출처 품질 낮음 - 추가 확인 필요")
        if data_completeness < 0.4:
            warnings.append("데이터 부족 - 전문가 상담 권장")
        if agency_match < 0.5:
            warnings.append("기관 매칭 불확실 - 추가 조사 필요")
        if recency < 0.5:
            warnings.append("일부 정보가 오래됨 - 최신 규정 확인 필요")
        if consistency < 0.5:
            warnings.append("출처 간 불일치 - 신중한 검토 필요")
        
        return warnings


# 싱글톤 인스턴스
_calculator_instance = None


def get_confidence_calculator() -> ConfidenceCalculator:
    """ConfidenceCalculator 싱글톤 인스턴스 반환"""
    global _calculator_instance
    
    if _calculator_instance is None:
        _calculator_instance = ConfidenceCalculator()
    
    return _calculator_instance


# 테스트용 메인
if __name__ == "__main__":
    calculator = ConfidenceCalculator()
    
    # 테스트 데이터
    sources = [
        {"agency": "FDA", "url": "https://api.fda.gov/..."},
        {"agency": "USDA", "url": "https://api.nal.usda.gov/..."},
    ]
    
    requirements = [
        {"agency": "FDA", "effective_date": "2023-01-15"},
        {"agency": "FDA", "effective_date": "2024-06-01"},
        {"agency": "USDA", "effective_date": "2022-03-10"},
    ]
    
    target_agencies = ["FDA", "USDA"]
    
    result = calculator.calculate_confidence(sources, requirements, target_agencies, 0.9)
    
    print(f"\n신뢰도 분석 결과:")
    print(f"  점수: {result['score']}")
    print(f"  등급: {result['level']} ({result['level_enum']})")
    print(f"\n세부 점수:")
    for key, value in result['breakdown'].items():
        print(f"  - {key}: {value}")
    print(f"\n긍정 요인:")
    for factor in result['factors']:
        print(f"  ✅ {factor}")
    print(f"\n경고 사항:")
    for warning in result['warnings']:
        print(f"  ⚠️ {warning}")

