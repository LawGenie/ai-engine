import json
from pathlib import Path
from typing import Optional


class HTSQueryService:
    def __init__(self, index_dir: str | None = None):
        base = Path(index_dir) if index_dir else Path(__file__).parent / "index_store"
        self._metadata_path = base / "metadata.json"
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

    def get_adjusted_rate(self, hts_number: str) -> Optional[float]:
        rec = self._hts_to_record.get(hts_number)
        if not rec:
            return None
        base_rate = rec.get("final_rate_for_korea", 0.0) or 0.0
        try:
            return float(base_rate) + 15.0
        except Exception:
            return 15.0


