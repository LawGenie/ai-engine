import json
import faiss
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional
from config import settings
import logging

logger = logging.getLogger(__name__)

class VectorService:
    def __init__(self):
        self.index_path = Path(settings.vector_index_path) / "hts_index.faiss"
        self.metadata_path = Path(settings.vector_index_path) / "metadata.json"
        
        # FAISS 인덱스 로드
        self.index = faiss.read_index(str(self.index_path))
        
        # 메타데이터 로드
        with open(self.metadata_path, 'r', encoding='utf-8') as f:
            self.metadata = json.load(f)
        
        # HTS 번호로 빠른 조회를 위한 딕셔너리
        self.hts_lookup = {
            record.get("hts_number"): record
            for record in self.metadata
            if record.get("hts_number")
        }
        
        # 전체 HTS 데이터 로드 (계층적 설명을 위해)
        self._load_full_hts_data()
        
        logger.info(f"Vector service initialized with {len(self.metadata)} records")
        logger.info(f"HTS lookup dictionary has {len(self.hts_lookup)} entries")
    
    def _load_full_hts_data(self):
        """전체 HTS 데이터를 로드하여 계층적 설명 조회 가능하게 함"""
        try:
            full_data_path = Path(settings.vector_index_path).parent / "data" / "hts_complete_data.json"
            with open(full_data_path, 'r', encoding='utf-8') as f:
                self.full_hts_data = json.load(f)
            
            # 계층별 조회를 위한 딕셔너리 구성
            self.full_hts_lookup = {}
            
            for record in self.full_hts_data:
                hts_number = record.get("hts_number", "")
                if hts_number:
                    self.full_hts_lookup[hts_number] = record
            
            logger.info(f"Full HTS data loaded: {len(self.full_hts_data)} records")
            
        except Exception as e:
            logger.error(f"Failed to load full HTS data: {e}")
            self.full_hts_data = []
            self.full_hts_lookup = {}
    
    
    def get_hierarchical_description(self, hts_number: str) -> Dict[str, str]:
        """HS 코드의 계층적 설명 반환 (Heading-Subheading-Tertiary Subheading)"""
        if not hts_number or len(hts_number) < 10:
            return {"error": "Invalid HTS number"}
        
        try:
            # 10자리 HS 코드에서 계층 추출
            heading = hts_number[:4]  # 4자리 (예: 3304)
            
            # 8자리 subheading 찾기 (점 제거)
            hts_clean = hts_number.replace('.', '')
            subheading_8 = hts_clean[:6]  # 6자리 (예: 330499)
            
            # Heading 설명 (4자리)
            heading_desc = ""
            if heading in self.full_hts_lookup:
                heading_desc = self.full_hts_lookup[heading].get("description", "")
            
            # Subheading 설명 (6자리) - 다양한 형태로 시도
            subheading_desc = ""
            possible_subheadings = [
                f"{heading}.{subheading_8[4:6]}",  # 3304.99
                f"{heading}.{subheading_8[4:6]}.00",  # 3304.99.00
                subheading_8,  # 330499
            ]
            
            for sub_code in possible_subheadings:
                if sub_code in self.full_hts_lookup:
                    subheading_desc = self.full_hts_lookup[sub_code].get("description", "")
                    break
            
            # Tertiary Subheading 설명 (10자리 - 현재 코드)
            tertiary_desc = ""
            if hts_number in self.full_hts_lookup:
                tertiary_desc = self.full_hts_lookup[hts_number].get("description", "")
            elif hts_number in self.hts_lookup:
                tertiary_desc = self.hts_lookup[hts_number].get("description", "")
            
            # 계층적 설명 조합 - 의미있는 설명들만 연결
            combined_descriptions = []
            
            if heading_desc and heading_desc.strip():
                combined_descriptions.append(f"Heading ({heading}): {heading_desc.rstrip(':')}")
            
            if subheading_desc and subheading_desc.strip() and subheading_desc.lower() != "other":
                combined_descriptions.append(f"Subheading: {subheading_desc.rstrip(':')}")
            
            if tertiary_desc and tertiary_desc.strip():
                if tertiary_desc.lower() == "other" and len(combined_descriptions) > 0:
                    # "Other"인 경우 상위 설명과 조합
                    combined_descriptions.append("Other preparations in this category")
                else:
                    combined_descriptions.append(f"Specific: {tertiary_desc}")
            
            # 최종 조합된 설명
            final_description = " → ".join(combined_descriptions) if combined_descriptions else f"HS Code {hts_number}"
            
            return {
                "heading": f"{heading_desc.rstrip(':')}" if heading_desc else f"Heading {heading}",
                "subheading": f"{subheading_desc.rstrip(':')}" if subheading_desc else f"Subheading {subheading_8}",
                "tertiary": f"{tertiary_desc.rstrip(':')}" if tertiary_desc else f"Code {hts_number}",
                "combined_description": final_description,
                "heading_code": heading,
                "subheading_code": subheading_8,
                "tertiary_code": hts_number
            }
            
        except Exception as e:
            logger.error(f"Error getting hierarchical description for {hts_number}: {e}")
            return {"error": f"Failed to get hierarchical description: {e}"}
    
    def _hash_embedding(self, text: str, dim: int = 384) -> List[float]:
        """개선된 해시 임베딩 - 의미적 유사성 강화"""
        vector = [0.0] * dim
        if not text:
            return vector
        
        # 텍스트 전처리 - 의미적 토큰 추출
        processed_text = self._preprocess_for_embedding(text)
        
        # 단어 단위 해싱 (기존 문자 단위보다 의미적)
        words = processed_text.split()
        for word_idx, word in enumerate(words):
            word_hash = hash(word.lower()) % dim
            # 단어 위치와 빈도 고려
            position_weight = 1.0 / (word_idx + 1)  # 앞쪽 단어에 더 높은 가중치
            vector[word_hash] += position_weight
            
            # 문자 단위도 보조적으로 사용 (기존 방식)
            for char_idx, ch in enumerate(word):
                bucket = (ord(ch) + char_idx * 1315423911 + word_idx * 7919) % dim
                vector[bucket] += 0.3  # 낮은 가중치
        
        # L2 정규화
        norm = sum(v * v for v in vector) ** 0.5
        if norm > 0:
            vector = [v / norm for v in vector]
        
        return vector
    
    def _preprocess_for_embedding(self, text: str) -> str:
        """임베딩을 위한 텍스트 전처리 (간소화)"""
        import re
        
        # 소문자 변환
        text = text.lower()
        
        # 특수문자 제거
        text = re.sub(r'[^\w\s]', ' ', text)
        
        # 연속 공백 제거
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def _is_10_digit_hts(self, hts_number: str) -> bool:
        """10자리 HS 코드인지 확인 (XXXX.XX.XX.XX 형태)"""
        if not hts_number:
            return False
        
        # 점을 제거하고 숫자만 확인
        digits_only = hts_number.replace('.', '')
        
        # 정확히 10자리 숫자인지 확인
        if len(digits_only) == 10 and digits_only.isdigit():
            return True
        
        # XXXX.XX.XX.XX 형태인지 확인
        parts = hts_number.split('.')
        if len(parts) == 4:
            try:
                # 각 부분이 올바른 길이의 숫자인지 확인
                return (len(parts[0]) == 4 and parts[0].isdigit() and
                        len(parts[1]) == 2 and parts[1].isdigit() and
                        len(parts[2]) == 2 and parts[2].isdigit() and
                        len(parts[3]) == 2 and parts[3].isdigit())
            except:
                return False
        
        return False
    
    
    
    def _calculate_combined_similarity(self, query_lower: str, combined_description: str, category_keywords: List[str]) -> float:
        """Combined description과 쿼리 간의 유사도 계산 (범용적 접근)"""
        if not combined_description:
            return 0.0
        
        desc_lower = combined_description.lower()
        score = 0.0
        
        # 1. 직접 키워드 매칭 (쿼리의 단어들이 설명에 포함되는지)
        query_words = set(query_lower.split())
        desc_words = set(desc_lower.split())
        
        # 공통 단어 비율
        common_words = query_words.intersection(desc_words)
        if query_words:
            word_overlap_score = len(common_words) / len(query_words)
            score += word_overlap_score * 0.4
        
        # 2. 카테고리 키워드 매칭
        category_matches = sum(1 for kw in category_keywords if kw in desc_lower)
        if category_matches > 0:
            category_score = min(category_matches / len(category_keywords), 0.5)
            score += category_score * 0.3
        
        # 3. 의미적 키워드 매칭 (화장품/식품 공통)
        semantic_keywords = {
            'preparation': 0.2, 'preparations': 0.2,
            'beauty': 0.15, 'cosmetic': 0.15, 'makeup': 0.15,
            'food': 0.15, 'edible': 0.15, 'dietary': 0.15,
            'skin': 0.1, 'care': 0.1, 'treatment': 0.1,
            'other': 0.05  # 일반적인 "Other" 카테고리
        }
        
        for keyword, weight in semantic_keywords.items():
            if keyword in desc_lower:
                score += weight
        
        # 4. 제품 형태/특성 매칭
        product_forms = {
            'serum': ['serum', 'essence', 'treatment', 'concentrate'],
            'cream': ['cream', 'moisturizer', 'lotion', 'emulsion'],
            'oil': ['oil', 'essential', 'extract'],
            'powder': ['powder', 'dust', 'granule'],
            'liquid': ['liquid', 'solution', 'suspension']
        }
        
        for form_type, form_keywords in product_forms.items():
            if form_type in query_lower:
                form_matches = sum(1 for kw in form_keywords if kw in desc_lower)
                if form_matches > 0:
                    score += min(form_matches * 0.1, 0.2)
        
        return min(score, 1.0)
    
    def _extract_tariff_rate(self, record: Dict[str, Any]) -> float:
        """레코드에서 관세율 추출 (퍼센트 단위로 반환)"""
        rate = record.get("final_rate_for_korea", 0.0)
        
        # None이나 빈 값 처리
        if rate is None or rate == "":
            return 0.0
        
        try:
            rate_float = float(rate)
            # 이미 퍼센트 형식이면 그대로 반환
            return rate_float
        except (ValueError, TypeError):
            logger.warning(f"Invalid tariff rate: {rate}")
            return 0.0
    
    def get_tariff_rate(self, hts_number: str) -> float:
        """HTS 코드의 최종 관세율 반환 (퍼센트 단위)"""
        # 빠른 조회
        record = self.hts_lookup.get(hts_number)
        
        if record:
            tariff_rate = self._extract_tariff_rate(record)
            logger.info(f"Found tariff for {hts_number}: {tariff_rate}%")
            return tariff_rate
        
        # 못 찾은 경우
        logger.warning(f"HTS number not found: {hts_number}")
        return 0.0
    
    def _direct_keyword_search(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        """다중 카테고리 키워드 기반 직접 검색 - 의미적 매칭 강화"""
        query_lower = query.lower()
        results = []
        
        # 1. 간소화된 카테고리별 키워드 정의 (범용적 접근)
        categories = {
            'cosmetic': {
                'keywords': [
                    'cosmetic', 'beauty', 'makeup', 'skincare', 'skin', 'facial', 'face',
                    'serum', 'cream', 'lotion', 'toner', 'essence', 'moisturizer', 'cleanser',
                    'anti-aging', 'hydrating', 'nourishing', 'treatment', 'preparation'
                ],
                'chapters': ['33']  # Chapter 33: Essential oils and cosmetic preparations
            },
            'food': {
                'keywords': [
                    'food', 'edible', 'nutrition', 'dietary', 'supplement', 'extract',
                    'preparation', 'cooked', 'instant', 'ready', 'preserved', 'fermented',
                    'cereal', 'grain', 'vegetable', 'sauce', 'condiment', 'seasoning'
                ],
                'chapters': ['04', '19', '20', '21', '22']  # Food-related chapters
            }
        }
        
        # 2. 쿼리에서 카테고리 감지 (다중 카테고리 지원)
        detected_categories = []
        category_scores = {}
        
        for cat_name, cat_info in categories.items():
            keyword_matches = sum(1 for kw in cat_info['keywords'] if kw in query_lower)
            if keyword_matches > 0:
                detected_categories.append(cat_name)
                category_scores[cat_name] = keyword_matches / len(cat_info['keywords'])
        
        # 3. 감지된 카테고리별 검색
        for category in detected_categories:
            cat_info = categories[category]
            
            for record in self.metadata:
                hts_number = record.get("hts_number", "")
                description = record.get("description", "").lower()
                
                # 해당 Chapter에 속하는지 확인
                if any(hts_number.startswith(ch) for ch in cat_info['chapters']):
                    # 10자리 HS 코드만 처리 (XXXX.XX.XX.XX 형태)
                    if not self._is_10_digit_hts(hts_number):
                        continue
                    
                    # Combined description 가져오기
                    hierarchical_desc = self.get_hierarchical_description(hts_number)
                    combined_description = hierarchical_desc.get("combined_description", description)
                    
                    # Combined description과 쿼리 간의 유사도 계산 (단순화)
                    similarity_score = self._calculate_combined_similarity(query_lower, combined_description, cat_info['keywords'])
                    
                    # 카테고리 신뢰도 반영
                    final_score = similarity_score * (0.7 + 0.3 * category_scores[category])
                    
                    if final_score > 0.2:
                        logger.info(f"Combined similarity for {hts_number}: {final_score:.3f} ('{combined_description[:80]}...')")
                        
                        # 중복 제거 (더 높은 점수만 유지)
                        existing = next((r for r in results if r["hts_number"] == hts_number), None)
                        if existing:
                            if final_score > existing["similarity"]:
                                existing["similarity"] = min(final_score, 1.0)
                                existing["category"] = category
                        else:
                            results.append({
                                "hts_number": hts_number,
                                "description": record.get("description", ""),
                                "similarity": min(final_score, 1.0),
                                "final_rate_for_korea": record.get("final_rate_for_korea", 0.0),
                                "category": category
                            })
        
        # 4. 점수 순으로 정렬
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]
    
    def _vector_search_fallback(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        """개선된 벡터 검색 - 의미적 확장 쿼리 활용"""
        # 1. 의미적 확장 쿼리 생성
        expanded_query = self._expand_query_semantically(query)
        
        # 2. 확장된 쿼리로 임베딩 생성
        query_embedding = self._hash_embedding(expanded_query)
        query_vector = np.array([query_embedding], dtype="float32")
        faiss.normalize_L2(query_vector)
        
        # 3. 더 넓은 범위에서 검색
        search_k = min(top_k * 8, len(self.metadata))
        scores, indices = self.index.search(query_vector, search_k)
        
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self.metadata):
                continue
                
            record = self.metadata[idx]
            hts_number = record.get("hts_number", "")
            
            # 10자리 HS 코드만 처리
            if not self._is_10_digit_hts(hts_number):
                continue
            
            # 4. 의미적 유사성 점수 계산
            semantic_score = self._calculate_semantic_similarity(query, record.get("description", ""))
            
            # 5. 벡터 점수와 의미적 점수 조합
            combined_score = 0.4 * float(score) + 0.6 * semantic_score
            
            results.append({
                "hts_number": hts_number,
                "description": record.get("description", ""),
                "similarity": combined_score,
                "final_rate_for_korea": record.get("final_rate_for_korea", 0.0),
                "category": "vector_search"
            })
        
        return results
    
    def _expand_query_semantically(self, query: str) -> str:
        """쿼리를 의미적으로 확장 (간소화)"""
        query_lower = query.lower()
        
        # 핵심 동의어만 추가
        if 'serum' in query_lower:
            return f"{query} essence treatment"
        elif 'cream' in query_lower:
            return f"{query} lotion moisturizer"
        elif 'perfume' in query_lower:
            return f"{query} fragrance"
        elif 'food' in query_lower:
            return f"{query} edible"
        
        return query
    
    def _calculate_semantic_similarity(self, query: str, description: str) -> float:
        """의미적 유사성 계산 (간소화)"""
        if not description:
            return 0.0
        
        query_words = set(query.lower().split())
        desc_words = set(description.lower().split())
        
        # 단어 중복도 (Jaccard similarity)
        intersection = query_words.intersection(desc_words)
        union = query_words.union(desc_words)
        
        return len(intersection) / len(union) if union else 0.0
    
    def _combine_results(self, direct_results: List[Dict], vector_results: List[Dict]) -> List[Dict]:
        """결과 통합 및 중복 제거"""
        seen_codes = set()
        combined = []
        
        # 직접 검색 결과 우선 (33류)
        for result in direct_results:
            hts_code = result["hts_number"]
            if hts_code not in seen_codes:
                seen_codes.add(hts_code)
                combined.append(result)
        
        # 벡터 검색 결과 보완 (중복 제거)
        for result in vector_results:
            hts_code = result["hts_number"]
            if hts_code not in seen_codes:
                seen_codes.add(hts_code)
                combined.append(result)
        
        return combined
    
    def search_similar(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """Combined description 기반 검색 (간소화)"""
        # 1단계: 키워드 기반 직접 검색 (주요 방법)
        direct_results = self._direct_keyword_search(query, top_k * 2)
        
        # 2단계: 벡터 검색으로 보완 (필요시)
        if len(direct_results) < top_k:
            vector_results = self._vector_search_fallback(query, top_k)
            combined_results = self._combine_results(direct_results, vector_results)
        else:
            combined_results = direct_results
        
        # 3단계: 계층적 설명 추가 및 최종 정렬
        final_results = []
        for result in combined_results[:top_k]:
            hierarchical_desc = self.get_hierarchical_description(result["hts_number"])
            
            final_results.append({
                "hts_number": result["hts_number"],
                "description": result["description"],
                "similarity": result["similarity"],
                "final_rate_for_korea": result.get("final_rate_for_korea", 0.0),
                "hierarchical_description": hierarchical_desc
            })
        
        # 간소화된 로깅
        logger.info(f"🏆 Final results: {len(final_results)} HS codes")
        for i, result in enumerate(final_results, 1):
            logger.info(f"  #{i}: {result['hts_number']} (score: {result['similarity']:.3f})")
        
        return final_results
    
    
    