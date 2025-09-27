from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from tax_via_hs.query_service import HTSQueryService


router = APIRouter(prefix="/tax", tags=["tax"])


@router.get("/adjusted-rate")
def get_adjusted_rate(hts_number: str = Query(..., description="HTS number, e.g., 0101.21.00.10")):
    try:
        service = HTSQueryService()
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))

    value: Optional[float] = service.get_adjusted_rate(hts_number)
    if value is None:
        raise HTTPException(status_code=404, detail="hts_number not found")
    return {"hts_number": hts_number, "adjusted_final_rate_for_korea": value}


