import json
import os
from pathlib import Path
from typing import List, Dict, Tuple

# Lightweight FAISS index builder for HTS data
# - Builds the index OUTSIDE of FastAPI main
# - Saves FAISS index and metadata for later loading


def _load_records(json_path: Path) -> List[Dict]:
    with json_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _build_text(record: Dict) -> str:
    parts: List[str] = []
    for key in ("hts_number", "description", "final_rate_display", "chapter", "item_type"):
        value = record.get(key)
        if value:
            parts.append(str(value))
    return " | ".join(parts)


def _hash_embedding(text: str, dim: int = 384) -> List[float]:
    # Very small dependency footprint embedding: character hashing into fixed dims
    # Not SOTA, but sufficient to satisfy a FAISS index structure without extra deps
    vector = [0.0] * dim
    if not text:
        return vector
    # Simple rolling hash per character
    for i, ch in enumerate(text):
        bucket = (ord(ch) + i * 1315423911) % dim
        vector[bucket] += 1.0
    # L2 normalize
    norm = sum(v * v for v in vector) ** 0.5
    if norm > 0:
        vector = [v / norm for v in vector]
    return vector


def build_faiss_index(
    json_path: str = str(Path(__file__).parent / "data" / "hts_complete_data.json"),
    out_dir: str = str(Path(__file__).parent / "index_store"),
    dim: int = 384,
) -> Tuple[str, str]:
    """
    Build a FAISS index and metadata from HTS JSON.

    Returns:
        (index_path, metadata_path)
    """
    try:
        import faiss  # type: ignore
        import numpy as np  # type: ignore
    except Exception as e:
        raise RuntimeError("faiss and numpy are required to build the index") from e

    json_file = Path(json_path)
    if not json_file.exists():
        raise FileNotFoundError(f"JSON not found: {json_file}")

    os.makedirs(out_dir, exist_ok=True)
    index_path = str(Path(out_dir) / "hts_index.faiss")
    metadata_path = str(Path(out_dir) / "metadata.json")

    records = _load_records(json_file)

    # Prepare embeddings and metadata
    embeddings: List[List[float]] = []
    metadata: List[Dict] = []
    for rec in records:
        text = _build_text(rec)
        emb = _hash_embedding(text, dim=dim)
        embeddings.append(emb)
        metadata.append({
            "hts_number": rec.get("hts_number"),
            "final_rate_for_korea": rec.get("final_rate_for_korea", 0.0),
            "description": rec.get("description", ""),
        })

    # Build FAISS index
    vectors = np.array(embeddings, dtype="float32")
    index = faiss.IndexFlatIP(dim)
    # Ensure normalized for inner product similarity
    faiss.normalize_L2(vectors)
    index.add(vectors)

    faiss.write_index(index, index_path)
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False)

    return index_path, metadata_path


if __name__ == "__main__":
    path_idx, path_meta = build_faiss_index()
    print(f"✅ Built FAISS index: {path_idx}")
    print(f"✅ Wrote metadata: {path_meta}")


