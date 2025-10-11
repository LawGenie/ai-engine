#!/usr/bin/env python3
import asyncio
import json
import sys
from pathlib import Path
from urllib.parse import urlencode
import httpx

CATALOG = Path(__file__).parent.parent / "endpoints_catalog.json"

async def head_ok(client: httpx.AsyncClient, url: str) -> tuple[int, str]:
    try:
        r = await client.head(url, timeout=8)
        return r.status_code, ""
    except Exception as e:
        return 0, str(e)

async def get_try(client: httpx.AsyncClient, url: str, params: dict) -> tuple[int, str, int]:
    try:
        r = await client.get(url, params=params, timeout=12)
        return r.status_code, r.headers.get("content-type", ""), len(r.content)
    except Exception as e:
        return 0, str(e), 0

async def test_endpoint(client: httpx.AsyncClient, agency: str, path: list[str], url: str, product: str, hs: str):
    # Heuristic params by agency
    base_params = {}
    upath = ".".join(path)
    if agency == "fda":
        if "food/enforcement" in url:
            base_params = {"search": f"product_description:\"{product}\"", "limit": 5}
        elif "food/event" in url or "cosmetic/event" in url:
            base_params = {"search": f"products.name_brand:\"{product}\"", "limit": 5}
        elif "device/" in url:
            base_params = {"search": f"device_name:{product}", "limit": 5}
        elif "drug/" in url:
            base_params = {"search": f"patient.drug.medicinalproduct:{product}", "limit": 5}
    elif agency == "usda" and "foods/search" in url:
        base_params = {"query": product, "pageSize": 5, "pageNumber": 1}
    elif agency == "epa" and "chemical/search" in url:
        base_params = {"search": product, "limit": 5}
    elif agency == "epa" and "chemname" in url:
        url = url.replace("{query}", product)
    elif agency == "fcc" and "authorization/grants" in url:
        base_params = {"search": f"device_name:{product}", "limit": 5, "format": "json"}
    elif agency == "cbp" and "hs-codes" in url:
        base_params = {"hs_code": hs, "limit": 5, "format": "json"}
    elif agency == "cpsc" and url.endswith("recalls.json"):
        base_params = {"search": product, "limit": 5}

    sc, ct, size = await get_try(client, url, base_params)
    ok = 200 <= sc < 400
    print(f"{agency.upper()} | {upath:35} -> {url}?{urlencode(base_params)} | status={sc} ok={ok} type={ct} size={size}")

async def main(product: str, hs: str):
    with open(CATALOG, "r", encoding="utf-8") as f:
        data = json.load(f)
    async with httpx.AsyncClient(headers={"User-Agent": "LawGenie-Endpoints-Test/1.0", "Accept": "application/json"}) as client:
        for agency, meta in data["agencies"].items():
            eps = meta.get("endpoints", {})
            print(f"\n=== {agency.upper()} ===")
            async def walk(prefix, node):
                if isinstance(node, dict):
                    for k, v in node.items():
                        await walk(prefix + [k], v)
                else:
                    await test_endpoint(client, agency, prefix, str(node), product, hs)
            await walk([], eps)

if __name__ == "__main__":
    # Usage: python scripts/test_endpoints_catalog.py "노트북 컴퓨터" 8471.30.01
    product = sys.argv[1] if len(sys.argv) > 1 else "노트북 컴퓨터"
    hs = sys.argv[2] if len(sys.argv) > 2 else "8471.30.01"
    asyncio.run(main(product, hs))
