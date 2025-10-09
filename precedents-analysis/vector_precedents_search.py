"""
벡터 DB 기반 유사 판례 검색 시스템
FAISS를 사용하여 판례 데이터를 벡터화하고 유사 검색을 수행합니다.
"""

import sys
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging

# 프로젝트 루트를 sys.path에 추가
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from faiss_precedents_db import FAISSPrecedentsDB

logger = logging.getLogger(__name__)

class VectorPrecedentsSearch:
    def __init__(self):
        """벡터 기반 유사 판례 검색기 초기화 (FAISS 사용)"""
        self.faiss_db = None
        self.cbp_collector = None
        
        try:
            self.faiss_db = FAISSPrecedentsDB()
            logger.info("✅ FAISS 벡터 서비스 초기화 완료")
        except Exception as e:
            logger.error(f"❌ FAISS 벡터 서비스 초기화 실패: {e}")
    
    def set_cbp_collector(self, cbp_collector):
        """CBP 데이터 수집기 설정"""
        self.cbp_collector = cbp_collector
        logger.info("✅ CBP 데이터 수집기 설정 완료")
    
    async def find_similar_precedents(
        self, 
        product_description: str, 
        product_name: str = "",
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        상품 설명을 기반으로 유사한 판례를 검색합니다. (FAISS 사용)
        
        Args:
            product_description: 상품 설명
            product_name: 상품명 (선택사항)
            top_k: 반환할 유사 판례 개수
            
        Returns:
            List[Dict]: 유사 판례 데이터 리스트
        """
        if not self.faiss_db:
            logger.warning("FAISS DB가 없어서 유사 판례 검색을 건너뜁니다.")
            return []
        
        try:
            logger.info(f"🔍 FAISS 유사 판례 검색 시작: {product_name}")
            
            # 1. 상품 설명을 기반으로 유사한 판례 검색
            query_text = f"{product_name} {product_description}".strip()
            similar_precedents = self.faiss_db.search_similar_precedents(
                query=query_text,
                n_results=top_k
            )
            
            if not similar_precedents:
                logger.info("유사한 판례를 찾을 수 없습니다.")
                return []
            
            # 2. 결과 포맷팅 (CBP 스크래퍼 형식에 맞춤)
            formatted_precedents = []
            for precedent in similar_precedents:
                formatted_precedents.append({
                    'case_id': precedent['precedent_id'],
                    'title': f"Similar precedent: {precedent['text'][:100]}...",
                    'status': precedent['outcome'],
                    'date': precedent['additional_metadata'].get('date', '2024-01-01'),
                    'description': precedent['text'],
                    'key_factors': precedent['additional_metadata'].get('key_factors', ['Vector Search']),
                    'hs_code': precedent['hs_code'],
                    'source': 'faiss_vector_search',
                    'link': precedent['additional_metadata'].get('link', ''),
                    'case_type': precedent['case_type'],
                    'outcome': precedent['outcome'],
                    'reason': f"Similar precedent found via FAISS vector search",
                    'similarity_score': precedent['similarity_score'],
                    'search_source': 'faiss_vector_search'
                })
            
            logger.info(f"✅ FAISS 유사 판례 검색 완료: {len(formatted_precedents)}개 판례")
            return formatted_precedents
            
        except Exception as e:
            logger.error(f"❌ FAISS 유사 판례 검색 실패: {e}")
            return []
    
    def add_precedent_to_db(self, 
                           precedent_id: str,
                           text: str,
                           hs_code: str,
                           case_type: str = "unknown",
                           outcome: str = "unknown",
                           source: str = "cbp",
                           additional_metadata: Dict[str, Any] = None) -> bool:
        """판례 데이터를 FAISS DB에 추가"""
        if not self.faiss_db:
            return False
        
        return self.faiss_db.add_precedent(
            precedent_id=precedent_id,
            text=text,
            hs_code=hs_code,
            case_type=case_type,
            outcome=outcome,
            source=source,
            additional_metadata=additional_metadata
        )
    
    def search_by_hs_code(self, hs_code: str, n_results: int = 10) -> List[Dict[str, Any]]:
        """특정 HS코드의 판례 검색"""
        if not self.faiss_db:
            return []
        
        return self.faiss_db.search_by_hs_code(hs_code, n_results)
    
    def get_search_stats(self) -> Dict[str, Any]:
        """검색 통계 반환"""
        stats = {
            'faiss_available': self.faiss_db is not None,
            'cbp_collector_available': self.cbp_collector is not None,
            'search_enabled': self.faiss_db is not None
        }
        
        if self.faiss_db:
            collection_stats = self.faiss_db.get_collection_stats()
            stats.update({
                'faiss_stats': collection_stats
            })
        
        if self.cbp_collector:
            cache_stats = self.cbp_collector.get_cache_stats()
            stats.update({
                'cache_stats': cache_stats
            })
        
        return stats
    
    def clear_vector_db(self) -> bool:
        """벡터 DB 초기화"""
        if not self.faiss_db:
            return False
        
        return self.faiss_db.clear_collection()
    
    def get_vector_db_info(self) -> Dict[str, Any]:
        """벡터 DB 정보 반환"""
        if not self.faiss_db:
            return {'error': 'FAISS DB not initialized'}
        
        return {
            'type': 'FAISS',
            'dimension': self.faiss_db.dimension,
            'embedding_model': 'hash_based',
            'persist_directory': self.faiss_db.persist_directory,
            'index_size': self.faiss_db.index.ntotal if self.faiss_db.index else 0
        }