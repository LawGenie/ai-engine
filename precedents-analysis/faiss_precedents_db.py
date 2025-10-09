import faiss
import numpy as np
import sqlite3
import json
import os
import logging
from typing import List, Dict, Any, Optional
import hashlib
import pickle

logger = logging.getLogger(__name__)

class FAISSPrecedentsDB:
    def __init__(self, 
                 persist_directory: str = "./faiss_precedents_db",
                 dimension: int = 256):
        """
        FAISS 기반 판례 벡터 DB 초기화 (tax_via_hs와 완전 별개)
        간단한 해시 기반 임베딩 사용
        """
        self.persist_directory = persist_directory
        self.dimension = dimension
        os.makedirs(persist_directory, exist_ok=True)
        
        logger.info(f"✅ FAISS 벡터 DB 초기화 완료 (차원: {dimension})")
        
        # FAISS 인덱스 초기화
        try:
            self.index_path = os.path.join(persist_directory, "precedents_index.faiss")
            self.metadata_path = os.path.join(persist_directory, "precedents_metadata.db")
            
            # 기존 인덱스 로드 또는 새로 생성
            if os.path.exists(self.index_path):
                self.index = faiss.read_index(self.index_path)
                logger.info("✅ 기존 FAISS 인덱스 로드 완료")
            else:
                # Inner Product 사용 (코사인 유사도와 유사)
                self.index = faiss.IndexFlatIP(dimension)
                logger.info("✅ 새로운 FAISS 인덱스 생성 완료")
            
            # 메타데이터 DB 초기화
            self._init_metadata_db()
            
        except Exception as e:
            logger.error(f"❌ FAISS 인덱스 초기화 실패: {e}")
            self.index = None
    
    def _text_to_embedding(self, text: str) -> np.ndarray:
        """텍스트를 간단한 해시 기반 임베딩으로 변환"""
        try:
            # 텍스트를 해시화하고 고정 길이 벡터로 변환
            text_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()
            
            # 해시를 256차원 벡터로 변환
            embedding = np.zeros(self.dimension, dtype=np.float32)
            
            # 해시 문자열을 8바이트씩 나누어 벡터에 분산
            for i in range(0, len(text_hash), 8):
                chunk = text_hash[i:i+8]
                value = int(chunk, 16) / (16**8)  # 0-1 정규화
                embedding[i//8 % self.dimension] = value
            
            # 정규화
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = embedding / norm
            
            return embedding.reshape(1, -1)
            
        except Exception as e:
            logger.error(f"❌ 임베딩 생성 실패: {e}")
            return np.random.random((1, self.dimension)).astype(np.float32)
    
    def _init_metadata_db(self):
        """메타데이터 SQLite DB 초기화"""
        try:
            conn = sqlite3.connect(self.metadata_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS precedents_metadata (
                    id INTEGER PRIMARY KEY,
                    precedent_id TEXT UNIQUE,
                    text TEXT,
                    hs_code TEXT,
                    case_type TEXT,
                    outcome TEXT,
                    source TEXT,
                    additional_metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            conn.close()
            logger.info("✅ 메타데이터 DB 초기화 완료")
            
        except Exception as e:
            logger.error(f"❌ 메타데이터 DB 초기화 실패: {e}")
    
    def add_precedent(self, 
                     precedent_id: str, 
                     text: str, 
                     hs_code: str,
                     case_type: str = "unknown",
                     outcome: str = "unknown",
                     source: str = "cbp",
                     additional_metadata: Dict[str, Any] = None) -> bool:
        """
        판례 데이터를 FAISS 인덱스와 메타데이터 DB에 추가
        """
        if not self.index:
            logger.error("FAISS 인덱스가 초기화되지 않았습니다.")
            return False
        
        try:
            # 텍스트 임베딩 생성 (해시 기반)
            embedding = self._text_to_embedding(text)
            
            # 정규화 (Inner Product를 위해)
            faiss.normalize_L2(embedding)
            
            # FAISS 인덱스에 추가
            self.index.add(embedding)
            
            # 메타데이터를 SQLite에 저장
            conn = sqlite3.connect(self.metadata_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO precedents_metadata 
                (precedent_id, text, hs_code, case_type, outcome, source, additional_metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                precedent_id,
                text,
                hs_code,
                case_type,
                outcome,
                source,
                json.dumps(additional_metadata) if additional_metadata else None
            ))
            
            conn.commit()
            conn.close()
            
            # 인덱스 저장
            self._save_index()
            
            logger.info(f"✅ 판례 데이터 추가 완료: {precedent_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 판례 데이터 추가 실패: {e}")
            return False
    
    def search_similar_precedents(self, 
                                 query: str, 
                                 n_results: int = 5,
                                 filter_metadata: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        쿼리 텍스트로 유사한 판례 검색
        """
        if not self.index or self.index.ntotal == 0:
            logger.warning("검색할 데이터가 없습니다.")
            return []
        
        try:
            # 쿼리 임베딩 생성 (해시 기반)
            query_embedding = self._text_to_embedding(query)
            faiss.normalize_L2(query_embedding)
            
            # FAISS 검색
            scores, indices = self.index.search(query_embedding, n_results)
            
            # 메타데이터 조회
            results = []
            conn = sqlite3.connect(self.metadata_path)
            cursor = conn.cursor()
            
            for score, idx in zip(scores[0], indices[0]):
                if idx >= 0:  # 유효한 인덱스
                    cursor.execute('''
                        SELECT precedent_id, text, hs_code, case_type, outcome, source, additional_metadata
                        FROM precedents_metadata 
                        WHERE id = ?
                    ''', (int(idx),))
                    
                    row = cursor.fetchone()
                    if row:
                        precedent_id, text, hs_code, case_type, outcome, source, additional_metadata = row
                        
                        # 메타데이터 필터링
                        if filter_metadata:
                            if filter_metadata.get('hs_code') and hs_code != filter_metadata['hs_code']:
                                continue
                            if filter_metadata.get('case_type') and case_type != filter_metadata['case_type']:
                                continue
                        
                        additional_meta = json.loads(additional_metadata) if additional_metadata else {}
                        
                        results.append({
                            'precedent_id': precedent_id,
                            'text': text,
                            'hs_code': hs_code,
                            'case_type': case_type,
                            'outcome': outcome,
                            'source': source,
                            'additional_metadata': additional_meta,
                            'similarity_score': float(score),
                            'faiss_index': int(idx)
                        })
            
            conn.close()
            
            logger.info(f"✅ FAISS 검색 완료: {len(results)}개 결과")
            return results
            
        except Exception as e:
            logger.error(f"❌ FAISS 검색 실패: {e}")
            return []
    
    def search_by_hs_code(self, hs_code: str, n_results: int = 10) -> List[Dict[str, Any]]:
        """
        특정 HS 코드의 판례 검색
        """
        try:
            conn = sqlite3.connect(self.metadata_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT precedent_id, text, hs_code, case_type, outcome, source, additional_metadata
                FROM precedents_metadata 
                WHERE hs_code = ?
                ORDER BY created_at DESC
                LIMIT ?
            ''', (hs_code, n_results))
            
            results = []
            for row in cursor.fetchall():
                precedent_id, text, hs_code, case_type, outcome, source, additional_metadata = row
                additional_meta = json.loads(additional_metadata) if additional_metadata else {}
                
                results.append({
                    'precedent_id': precedent_id,
                    'text': text,
                    'hs_code': hs_code,
                    'case_type': case_type,
                    'outcome': outcome,
                    'source': source,
                    'additional_metadata': additional_meta,
                    'similarity_score': 1.0,  # HS 코드 직접 매치
                    'search_type': 'hs_code_direct'
                })
            
            conn.close()
            logger.info(f"✅ HS 코드 검색 완료: {hs_code} -> {len(results)}개 결과")
            return results
            
        except Exception as e:
            logger.error(f"❌ HS 코드 검색 실패: {e}")
            return []
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """
        컬렉션 통계 반환
        """
        try:
            stats = {
                'total_precedents': 0,
                'faiss_index_size': 0,
                'embedding_dimension': self.dimension,
                'embedding_model': 'hash_based'
            }
            
            if self.index:
                stats['faiss_index_size'] = self.index.ntotal
            
            # 메타데이터 DB 통계
            conn = sqlite3.connect(self.metadata_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) FROM precedents_metadata')
            stats['total_precedents'] = cursor.fetchone()[0]
            
            cursor.execute('SELECT hs_code, COUNT(*) FROM precedents_metadata GROUP BY hs_code')
            hs_code_stats = {row[0]: row[1] for row in cursor.fetchall()}
            stats['hs_code_distribution'] = hs_code_stats
            
            cursor.execute('SELECT source, COUNT(*) FROM precedents_metadata GROUP BY source')
            source_stats = {row[0]: row[1] for row in cursor.fetchall()}
            stats['source_distribution'] = source_stats
            
            conn.close()
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ 통계 조회 실패: {e}")
            return {'error': str(e)}
    
    def clear_collection(self) -> bool:
        """
        모든 데이터 삭제
        """
        try:
            # FAISS 인덱스 재생성
            if self.index:
                self.index = faiss.IndexFlatIP(self.dimension)
                self._save_index()
            
            # 메타데이터 DB 초기화
            conn = sqlite3.connect(self.metadata_path)
            cursor = conn.cursor()
            cursor.execute('DELETE FROM precedents_metadata')
            conn.commit()
            conn.close()
            
            logger.info("✅ 컬렉션 초기화 완료")
            return True
            
        except Exception as e:
            logger.error(f"❌ 컬렉션 초기화 실패: {e}")
            return False
    
    def _save_index(self):
        """FAISS 인덱스를 디스크에 저장"""
        try:
            if self.index:
                faiss.write_index(self.index, self.index_path)
                logger.debug("FAISS 인덱스 저장 완료")
        except Exception as e:
            logger.error(f"❌ FAISS 인덱스 저장 실패: {e}")
    
    def __del__(self):
        """소멸자에서 인덱스 저장"""
        try:
            self._save_index()
        except:
            pass
