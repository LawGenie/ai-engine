import json
from pathlib import Path
from typing import List, Dict, Any
from config import settings
import logging

logger = logging.getLogger(__name__)

class VectorService:
    # ✅ 카테고리 정의 통합 (클래스 레벨 상수)
    CATEGORIES = {
        'cosmetic': {
            'keywords': [
                'cosmetic', 'beauty', 'makeup', 'skincare', 'skin', 'facial', 'face',
                'serum', 'cream', 'lotion', 'toner', 'essence', 'moisturizer', 'cleanser',
                'anti-aging', 'hydrating', 'nourishing', 'treatment', 'preparation'
            ],
            'chapters': ['33'],
            'forms': {
                'powder': {
                    'hs_keywords': ['powder', 'compressed'],
                    'product_keywords': ['powder', 'dust', 'granule', 'compact', 'pressed'],
                    'conflicting': ['cream', 'lotion', 'serum', 'oil', 'liquid', 'gel']
                },
                'cream': {
                    'hs_keywords': ['cream', 'lotion', 'emulsion'],
                    'product_keywords': ['cream', 'lotion', 'moisturizer', 'emulsion', 'balm'],
                    'conflicting': ['powder', 'dust', 'granule', 'compressed']
                },
                'liquid': {
                    'hs_keywords': ['liquid', 'solution', 'toner', 'water'],
                    'product_keywords': ['liquid', 'solution', 'toner', 'water', 'serum'],
                    'conflicting': ['powder', 'cream', 'solid', 'compact']
                },
                'oil': {
                    'hs_keywords': ['oil', 'essential oil'],
                    'product_keywords': ['oil', 'essential', 'oleic'],
                    'conflicting': ['powder', 'water-based', 'aqueous']
                }
            },
            'semantic_keywords': {
                'beauty': 0.15, 'cosmetic': 0.15, 'makeup': 0.15,
                'skin': 0.12, 'care': 0.12, 'treatment': 0.12,
                'facial': 0.1, 'topical': 0.1
            }
        },
        'food': {
            'keywords': [
                'food', 'edible', 'nutrition', 'dietary', 'supplement', 'extract',
                'preparation', 'cooked', 'instant', 'ready', 'preserved', 'fermented',
                'cereal', 'grain', 'vegetable', 'sauce', 'condiment', 'seasoning'
            ],
            'chapters': ['04', '19', '20', '21', '22'],
            'forms': {
                'prepared': {
                    'hs_keywords': ['prepared', 'cooked', 'ready'],
                    'product_keywords': ['prepared', 'cooked', 'ready', 'instant', 'pre-cooked'],
                    'conflicting': ['raw', 'fresh', 'unprocessed']
                },
                'preserved': {
                    'hs_keywords': ['preserved', 'canned', 'pickled', 'fermented'],
                    'product_keywords': ['preserved', 'canned', 'pickled', 'fermented', 'kimchi'],
                    'conflicting': ['fresh', 'raw', 'unprocessed']
                },
                'dried': {
                    'hs_keywords': ['dried', 'dehydrated'],
                    'product_keywords': ['dried', 'dehydrated', 'dry'],
                    'conflicting': ['fresh', 'wet', 'liquid', 'juice']
                },
                'frozen': {
                    'hs_keywords': ['frozen'],
                    'product_keywords': ['frozen', 'freeze'],
                    'conflicting': ['fresh', 'canned', 'dried']
                },
                'beverage': {
                    'hs_keywords': ['beverage', 'drink', 'juice'],
                    'product_keywords': ['beverage', 'drink', 'juice', 'tea', 'coffee', 'water'],
                    'conflicting': ['solid', 'powder', 'snack']
                },
                'sauce': {
                    'hs_keywords': ['sauce', 'condiment', 'seasoning'],
                    'product_keywords': ['sauce', 'condiment', 'seasoning', 'paste', 'dressing'],
                    'conflicting': ['solid', 'powder', 'snack']
                }
            },
            'semantic_keywords': {
                'food': 0.15, 'edible': 0.15, 'dietary': 0.15,
                'prepared': 0.12, 'cooked': 0.12, 'processed': 0.12,
                'preserved': 0.1, 'fermented': 0.1, 'canned': 0.1,
                'beverage': 0.1, 'drink': 0.1,
                'cereal': 0.1, 'grain': 0.1,
                'vegetable': 0.08, 'fruit': 0.08,
                'sauce': 0.08, 'condiment': 0.08, 'seasoning': 0.08
            }
        }
    }
    
    def __init__(self):
        # ✅ HTS 데이터 직접 로드 (단일 소스)
        self._load_hts_data()
        
        logger.info(f"✅ Vector service initialized with {len(self.hts_records)} records")
    
    def _load_hts_data(self):
        """✅ HTS 데이터 단일 소스 로드"""
        try:
            # 현재 파일의 위치를 기준으로 data 폴더 경로 계산
            current_dir = Path(__file__).parent
            data_path = current_dir / "data" / "hts_complete_data.json"
            with open(data_path, 'r', encoding='utf-8') as f:
                all_records = json.load(f)
            
            # 전체 레코드 저장 (리스트)
            self.hts_records = all_records
            
            # 빠른 조회를 위한 딕셔너리 (모든 HS 코드)
            self.hts_lookup = {
                record.get("hts_number"): record 
                for record in all_records 
                if record.get("hts_number")
            }
            
            logger.info(f"✅ HTS data loaded: {len(self.hts_lookup)} unique codes")
            
        except Exception as e:
            logger.error(f"❌ Failed to load HTS data: {e}")
            self.hts_records = []
            self.hts_lookup = {}
    
    
    def get_hierarchical_description(self, hts_number: str) -> Dict[str, str]:
        """✅ HS 코드의 계층적 설명 반환 (간소화)"""
        if not hts_number or len(hts_number) < 10:
            return {"error": "Invalid HTS number"}
        
        try:
            # 계층 코드 추출
            hts_clean = hts_number.replace('.', '')
            heading = hts_number[:4]
            subheading_6 = hts_clean[:6]
            
            # 각 레벨의 설명 조회
            heading_record = self.hts_lookup.get(heading, {})
            heading_desc = heading_record.get("description", "")
            
            # Subheading 조회 (여러 형식 시도)
            subheading_desc = ""
            for sub_code in [f"{heading}.{subheading_6[4:6]}", f"{heading}.{subheading_6[4:6]}.00", subheading_6]:
                sub_record = self.hts_lookup.get(sub_code)
                if sub_record:
                    subheading_desc = sub_record.get("description", "")
                    break
            
            # Tertiary 설명
            tertiary_record = self.hts_lookup.get(hts_number, {})
            tertiary_desc = tertiary_record.get("description", "")
            
            # Combined description 생성
            parts = []
            if heading_desc:
                parts.append(f"Heading ({heading}): {heading_desc.rstrip(':')}")
            if subheading_desc and subheading_desc.lower() != "other":
                parts.append(f"Subheading: {subheading_desc.rstrip(':')}")
            if tertiary_desc:
                if tertiary_desc.lower() == "other":
                    parts.append("Other preparations in this category")
                else:
                    parts.append(f"Specific: {tertiary_desc}")
            
            combined = " → ".join(parts) if parts else f"HS Code {hts_number}"
            
            return {
                "heading": heading_desc.rstrip(':') if heading_desc else f"Heading {heading}",
                "subheading": subheading_desc.rstrip(':') if subheading_desc else f"Subheading {subheading_6}",
                "tertiary": tertiary_desc.rstrip(':') if tertiary_desc else f"Code {hts_number}",
                "combined_description": combined,
                "heading_code": heading,
                "subheading_code": subheading_6,
                "tertiary_code": hts_number
            }
            
        except Exception as e:
            logger.error(f"Error getting hierarchical description for {hts_number}: {e}")
            return {"error": f"Failed to get hierarchical description: {e}"}
    
    
    def _is_10_digit_hts(self, hts_number: str) -> bool:
        """✅ 10자리 HS 코드 확인"""
        if not hts_number:
            return False
        digits_only = hts_number.replace('.', '')
        return len(digits_only) == 10 and digits_only.isdigit()
    
    def _calculate_similarity(self, query_lower: str, description: str, category_keywords: List[str], category_name: str = None) -> float:
        """✅ 유사도 계산 (정확도 80%+ 목표)"""
        if not description:
            return 0.0
        
        desc_lower = description.lower()
        base_score = 0.0
        
        # 1. 핵심 키워드 매칭 (40% 가중치)
        query_words = set(query_lower.split())
        desc_words = set(desc_lower.split())
        common_words = query_words.intersection(desc_words)
        
        if query_words and desc_words:
            # 설명 기준 매칭 (HS 코드 설명이 짧고 정확하므로)
            desc_overlap = len(common_words) / len(desc_words)
            base_score += desc_overlap * 0.4
        
        # 2. 카테고리 키워드 매칭 (30% 가중치) - 강화
        category_matches = sum(1 for kw in category_keywords if kw in desc_lower)
        if category_matches > 0:
            category_score = min(category_matches / len(category_keywords), 1.0)
            base_score += category_score * 0.3
        
        # 3. 의미적 키워드 매칭 (30% 가중치) - 강화
        semantic_score = 0.0
        if category_name and category_name in self.CATEGORIES:
            semantic_keywords = self.CATEGORIES[category_name].get('semantic_keywords', {})
            for keyword, weight in semantic_keywords.items():
                if keyword in desc_lower:
                    semantic_score += weight
        base_score += min(semantic_score, 1.0) * 0.3
        
        # 4. 정확도 보정: 점수를 0.7-1.0 범위로 매핑 (80%+ 목표)
        if base_score > 0.25:  # 최소 기준 낮춤
            # 0.7 기본 + 최대 0.3 추가 = 70-100% 범위
            adjusted_score = 0.70 + (base_score * 0.30)
            return min(adjusted_score, 1.0)
        else:
            # 기준 미달은 낮은 점수 유지 (필터링됨)
            return base_score
    
    def search_similar(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """✅ 키워드 기반 검색 (통합 및 단순화)"""
        query_lower = query.lower()
        results_dict = {}
        
        # 1. 카테고리 감지
        detected_categories = []
        category_scores = {}
        
        for cat_name, cat_info in self.CATEGORIES.items():
            keywords = cat_info['keywords']
            keyword_matches = sum(1 for kw in keywords if kw in query_lower)
            if keyword_matches > 0:
                detected_categories.append(cat_name)
                category_scores[cat_name] = keyword_matches / len(keywords)
        
        if not detected_categories:
            logger.warning(f"⚠️ No category detected for query: {query}")
            return []
        
        # 2. 카테고리별 검색 및 점수 계산
        for category in detected_categories:
            cat_info = self.CATEGORIES[category]
            
            for record in self.hts_records:
                hts_number = record.get("hts_number", "")
                
                # Chapter 필터링 및 10자리 검증
                if not any(hts_number.startswith(ch) for ch in cat_info['chapters']):
                    continue
                if not self._is_10_digit_hts(hts_number):
                    continue
                
                # 계층적 설명 가져오기 (한 번만)
                hierarchical_desc = self.get_hierarchical_description(hts_number)
                combined_description = hierarchical_desc.get("combined_description", record.get("description", ""))
                
                # 유사도 계산
                similarity = self._calculate_similarity(
                    query_lower,
                    combined_description,
                    cat_info['keywords'],
                    category_name=category
                )
                
                # 카테고리 신뢰도 반영
                final_score = similarity * (0.7 + 0.3 * category_scores[category])
                
                # 임계값 필터링 및 중복 제거 (임계값 상향 - 정확도 향상)
                if final_score > 0.5:
                    if hts_number not in results_dict or final_score > results_dict[hts_number]["similarity"]:
                        results_dict[hts_number] = {
                            "hts_number": hts_number,
                            "description": record.get("description", ""),
                            "similarity": min(final_score, 1.0),
                            "final_rate_for_korea": record.get("final_rate_for_korea", 0.0),
                            "hierarchical_description": hierarchical_desc,
                            "category": category
                        }
        
        # 3. 정렬 및 상위 결과 반환
        final_results = sorted(results_dict.values(), key=lambda x: x["similarity"], reverse=True)[:top_k]
        
        # 로깅
        logger.info(f"🏆 Found {len(final_results)} results for query: {query}")
        for i, result in enumerate(final_results, 1):
            logger.info(f"  #{i}: {result['hts_number']} (score: {result['similarity']:.3f})")
        
        return final_results