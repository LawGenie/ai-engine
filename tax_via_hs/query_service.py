import json
from pathlib import Path
from typing import Optional, List, Dict, Tuple

try:
    import faiss  # type: ignore
    import numpy as np  # type: ignore
except Exception:  # pragma: no cover - optional at runtime, required in server
    faiss = None
    np = None


class HTSQueryService:
    def __init__(self, index_dir: str | None = None):
        base = Path(index_dir) if index_dir else Path(__file__).parent / "index_store"
        self._metadata_path = base / "metadata.json"
        self._index_path = base / "hts_index.faiss"
        if not self._metadata_path.exists():
            raise FileNotFoundError(
                f"metadata.json not found at {self._metadata_path}. Build the index first."
            )
        with self._metadata_path.open("r", encoding="utf-8") as f:
            self._metadata = json.load(f)

        # Build a direct lookup map for exact hts_number queries
        self._hts_to_record = {}
        for rec in self._metadata:
            hts = rec.get("hts_number")
            if hts:
                self._hts_to_record[hts] = rec

        # Lazy-loaded FAISS index
        self._faiss_index = None
        self._dim: int = 384

    def get_adjusted_rate(self, hts_number: str) -> Optional[float]:
        """
        한국에서 미국으로 수출할 때 적용되는 실제 관세율을 반환합니다.
        KORUS FTA가 적용된 최종 관세율입니다.
        """
        rec = self._hts_to_record.get(hts_number)
        if not rec:
            return None
        
        # final_rate_for_korea는 이미 KORUS FTA가 반영된 최종 관세율
        final_rate = rec.get("final_rate_for_korea", 0.0)
        
        try:
            return float(final_rate)  # ✅ 15% 더하지 않음!
        except (ValueError, TypeError):
            # 숫자로 변환 불가능한 경우 0% 반환
            return 0.0
    
    def get_tariff_info(self, hts_number: str) -> Optional[Dict]:
        """
        HTS 코드에 대한 상세 관세 정보를 반환합니다.
        """
        rec = self._hts_to_record.get(hts_number)
        if not rec:
            return None
        
        return {
            "hts_number": rec.get("hts_number"),
            "description": rec.get("description"),
            "general_rate": rec.get("general_rate"),  # 일반 국가 관세율
            "korea_specific_rate": rec.get("korea_specific_rate"),  # 한국 특별 관세율
            "final_rate_for_korea": rec.get("final_rate_for_korea"),  # 한국 최종 관세율
            "has_korea_benefit": rec.get("has_korea_benefit", False),  # FTA 혜택 여부
            "unit_of_quantity": rec.get("unit_of_quantity"),
            "chapter": rec.get("chapter"),
        }

    def calculate_import_cost(self, hts_number: str, product_value: float) -> Optional[Dict]:
        """
        제품 가격을 기준으로 총 수입 비용을 계산합니다.
        
        Args:
            hts_number: HTS 코드
            product_value: 제품 가격 (USD)
            
        Returns:
            Dict with breakdown of costs or None if HTS not found
        """
        tariff_rate = self.get_adjusted_rate(hts_number)
        if tariff_rate is None:
            return None
        
        tariff_info = self.get_tariff_info(hts_number)
        if not tariff_info:
            return None
        
        # 관세 계산
        tariff_amount = product_value * (tariff_rate / 100.0)
        total_cost = product_value + tariff_amount
        
        # KORUS FTA 절약액 계산
        general_rate_str = tariff_info.get("general_rate", "0%")
        try:
            if general_rate_str.upper() in ["FREE", "무관세", "N/A"]:
                general_rate = 0.0
            else:
                general_rate = float(general_rate_str.replace("%", "").strip())
        except:
            general_rate = 0.0
        
        general_tariff = product_value * (general_rate / 100.0)
        savings = general_tariff - tariff_amount
        
        return {
            "hts_number": hts_number,
            "description": tariff_info.get("description"),
            "product_value": product_value,
            "tariff_rate": tariff_rate,
            "tariff_amount": round(tariff_amount, 2),
            "total_cost": round(total_cost, 2),
            "general_rate": general_rate,
            "korus_fta_savings": round(savings, 2) if savings > 0 else 0.0,
            "has_korea_benefit": tariff_info.get("has_korea_benefit", False),
        }

    def _ensure_index(self) -> None:
        if self._faiss_index is not None:
            return
        if faiss is None or np is None:
            raise RuntimeError("faiss and numpy are required to use similarity search")
        if not self._index_path.exists():
            raise FileNotFoundError(f"FAISS index not found at {self._index_path}")
        self._faiss_index = faiss.read_index(str(self._index_path))

    def _hash_embedding(self, text: str, dim: int = 384) -> List[float]:
        vector = [0.0] * dim
        if not text:
            return vector
        for i, ch in enumerate(text):
            bucket = (ord(ch) + i * 1315423911) % dim
            vector[bucket] += 1.0
        # L2 normalize
        norm = sum(v * v for v in vector) ** 0.5
        if norm > 0:
            vector = [v / norm for v in vector]
        return vector

    def search_by_description(self, description: str, top_k: int = 3) -> List[Dict]:
        """Return top_k metadata records most similar to description."""
        self._ensure_index()
        assert self._faiss_index is not None
        if np is None:
            raise RuntimeError("numpy is required for similarity search")

        query_vec = np.array([self._hash_embedding(description, dim=self._dim)], dtype="float32")
        # Ensure normalized to match IndexFlatIP
        faiss.normalize_L2(query_vec)
        scores, ids = self._faiss_index.search(query_vec, top_k)
        results: List[Dict] = []
        if ids.size == 0:
            return results
        for idx, score in zip(ids[0], scores[0]):
            if idx < 0:
                continue
            if idx >= len(self._metadata):
                continue
            rec = dict(self._metadata[int(idx)])
            rec["similarity"] = float(score)
            results.append(rec)
        return results


# 사용 예시
if __name__ == "__main__":
    service = HTSQueryService()
    
    # 예시 1: 관세율만 조회
    rate = service.get_adjusted_rate("8541.10.00")
    print(f"관세율: {rate}%")
    
    # 예시 2: 상세 정보 조회
    info = service.get_tariff_info("8541.10.00")
    print(f"상세 정보: {info}")
    
    # 예시 3: 수입 비용 계산
    cost = service.calculate_import_cost("8541.10.00", 10000)
    print(f"수입 비용: {cost}")