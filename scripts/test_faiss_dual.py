import os
import sys
from pathlib import Path

# Ensure project root on sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tax_via_hs.index_builder import build_faiss_index
from tax_via_hs.query_service import HTSQueryService


def ensure_index():
    base = PROJECT_ROOT / "tax_via_hs" / "index_store"
    if not (base / "hts_index.faiss").exists() or not (base / "metadata.json").exists():
        print("Index not found. Building now...")
        build_faiss_index()
    else:
        print("Index exists. Skipping build.")


def run_examples():
    # Example A: final_rate_for_korea == 0.0 → adjusted == 15.0
    hts_zero = os.environ.get("TEST_HTS_ZERO", "0101.21.00.10")
    # Example B: final_rate_for_korea > 0.0 → adjusted != 15.0 (e.g., 6.0 + 15.0 = 21.0)
    hts_nonzero = os.environ.get("TEST_HTS_NONZERO", "1701.91.44.00")

    service = HTSQueryService()

    val_zero = service.get_adjusted_rate(hts_zero)
    val_nonzero = service.get_adjusted_rate(hts_nonzero)

    print({"hts_number": hts_zero, "adjusted_final_rate_for_korea": val_zero})
    print({"hts_number": hts_nonzero, "adjusted_final_rate_for_korea": val_nonzero})

    # Simple expectations in output (not raising unless None)
    if val_zero is None:
        print("Warning: zero-rate example not found")
    if val_nonzero is None:
        print("Warning: non-zero example not found")


if __name__ == "__main__":
    ensure_index()
    run_examples()


