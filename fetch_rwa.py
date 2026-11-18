#!/usr/bin/env python3
"""Fetch optional RWA (Real World Assets) data for Regime Radar.

Uses the KEYED CoinMarketCap Pro API — a free Basic key is enough for the
endpoints used here. The key is read ONLY from the CMC_PRO_API_KEY
environment variable; it is never read from a file and never written anywhere.

    export CMC_PRO_API_KEY="your-free-key"   # get one at pro.coinmarketcap.com
    python3 fetch_rwa.py                     # writes data/rwa.json

Endpoints used (all GET, keyed, Basic tier and up):
    /v5/real-world-assets/assets/list?limit=20&sort=tokenized_market_cap&sort_dir=desc
    /v5/real-world-assets/issuers/list?limit=10

Without a key this script exits with a clear message and writes nothing —
no fake data is ever generated. data/rwa.json is gitignored; the dashboard
shows its locked state when the file is absent.
"""

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://pro-api.coinmarketcap.com"
OUT = Path(__file__).resolve().parent / "data" / "rwa.json"


def _get(path, key):
    url = BASE + path
    req = urllib.request.Request(url, headers={
        "Accept": "application/json",
        "X-CMC_PRO_API_KEY": key,
    })
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            payload = json.loads(e.read().decode("utf-8"))
        except Exception:
            payload = {}
        msg = (payload.get("status") or {}).get("error_message") or f"HTTP {e.code}"
        raise RuntimeError(f"{path}: {msg}")
    status = payload.get("status") or {}
    if str(status.get("error_code")) not in ("0", "None"):
        raise RuntimeError(f"{path}: {status.get('error_message') or status}")
    return payload.get("data")


def main():
    key = os.environ.get("CMC_PRO_API_KEY", "").strip()
    if not key:
        print("No CMC_PRO_API_KEY in the environment — nothing fetched.", file=sys.stderr)
        print("Get a free key at https://pro.coinmarketcap.com/login, then:", file=sys.stderr)
        print("  export CMC_PRO_API_KEY=\"your-key\" && python3 fetch_rwa.py", file=sys.stderr)
        return 2
    try:
        assets = _get("/v5/real-world-assets/assets/list"
                      "?limit=20&sort=tokenized_market_cap&sort_dir=desc", key)
        issuers = _get("/v5/real-world-assets/issuers/list?limit=10", key)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "fetched_at": __import__("time").strftime("%Y-%m-%dT%H:%M:%SZ",
                                                  __import__("time").gmtime()),
        "source": "CoinMarketCap Pro API (keyed, free Basic tier)",
        "assets": assets,
        "issuers": issuers,
    }, indent=2))
    n_assets = len(assets) if isinstance(assets, list) else 0
    n_issuers = len(issuers) if isinstance(issuers, list) else 0
    print(f"Wrote {OUT} ({n_assets} assets, {n_issuers} issuers).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
