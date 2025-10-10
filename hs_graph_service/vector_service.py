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
        
        logger.info(f"Vector service initialized with {len(self.metadata)} records")
        logger.info(f"HTS lookup dictionary has {len(self.hts_lookup)} entries")
    
    def _hash_embedding(self, text: str, dim: int = 384) -> List[float]:
        """기존 index_builder와 동일한 해시 임베딩"""
        vector = [0.0] * dim
        if not text:
            return vector
        
        for i, ch in enumerate(text):
            bucket = (ord(ch) + i * 1315423911) % dim
            vector[bucket] += 1.0
        
        # L2 정규화
        norm = sum(v * v for v in vector) ** 0.5
        if norm > 0:
            vector = [v / norm for v in vector]
        
        return vector
    
    def search_similar(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """벡터 유사도 검색으로 Top-K 후보 반환"""
        query_embedding = self._hash_embedding(query)
        query_vector = np.array([query_embedding], dtype="float32")
        
        # 정규화 (IndexFlatIP 사용)
        faiss.normalize_L2(query_vector)
        
        # 검색
        scores, indices = self.index.search(query_vector, top_k)
        
        results = []
        for i, (score, idx) in enumerate(zip(scores[0], indices[0])):
            if idx < 0 or idx >= len(self.metadata):
                continue
                
            record = self.metadata[idx]
            hts_number = record.get("hts_number", "")
            
            # 관세율 추출 및 정규화
            tariff_rate = self._extract_tariff_rate(record)
            
            results.append({
                "hts_number": hts_number,
                "description": record.get("description", ""),
                "similarity": float(score),
                "final_rate_for_korea": tariff_rate
            })
            
            logger.info(
                f"Rank {i+1}: HTS {hts_number}, "
                f"Similarity: {score:.4f}, "
                f"Tariff: {tariff_rate}%"
            )
        
        return results
    
    def _extract_tariff_rate(self, record: Dict[str, Any]) -> float:
        """레코드에서 관세율 추출 (퍼센트 단위로 반환)"""
        rate = record.get("final_rate_for_korea", 0.0)
        
        # None이나 빈 값 처리
        if rate is None or rate == "":
            return 0.0
        
        try:
            rate_float = float(rate)
            # 이미 퍼센트 형식이면 그대로 반환
            # (build_index.py에서 어떻게 저장했는지에 따라 다름)
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