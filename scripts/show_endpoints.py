#!/usr/bin/env python3
import json
import sys
from pathlib import Path

CATALOG = Path(__file__).parent.parent / "endpoints_catalog.json"

def load():
    with open(CATALOG, "r", encoding="utf-8") as f:
        return json.load(f)

def list_all(data):
    for agency, meta in data["agencies"].items():
        print(f"\n[{agency.upper()}] base={meta.get('base_url','')}")
        eps = meta.get("endpoints", {})
        for group, items in eps.items():
            print(f"  - {group}:")
            for name, url in items.items():
                if isinstance(url, dict):
                    print(f"    * {name}:")
                    for k, v in url.items():
                        print(f"        - {k}: {v}")
                else:
                    print(f"    * {name}: {url}")

def search(data, keywords):
    toks = [t.lower() for t in keywords if t.strip()]
    found = []
    for agency, meta in data["agencies"].items():
        eps = meta.get("endpoints", {})
        def walk(prefix, node):
            if isinstance(node, dict):
                for k, v in node.items():
                    walk(prefix + [k], v)
            else:
                path = ".".join(prefix)
                url = str(node)
                hay = f"{agency} {path} {url}".lower()
                if all(tok in hay for tok in toks):
                    found.append((agency, path, url))
        walk([], eps)
    if not found:
        print("No matches.")
        return
    for agency, path, url in found:
        print(f"{agency.upper()} | {path} -> {url}")

if __name__ == "__main__":
    data = load()
    if len(sys.argv) == 1:
        list_all(data)
    else:
        search(data, sys.argv[1:])
