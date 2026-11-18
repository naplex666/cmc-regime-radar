#!/usr/bin/env python3
"""Regime Radar CLI — CoinMarketCap market-regime verdict from live keyless data.

Reads the CoinMarketCap keyless public API (no API key, no account):
    https://pro-api.coinmarketcap.com/public-api

Endpoints used (all GET, keyless):
    /v3/fear-and-greed/latest
    /v1/altcoin-season-index/latest
    /v3/index/cmc100-latest
    /v3/index/cmc20-latest
    /v1/global-metrics/quotes/latest
    /v1/cryptocurrency/listings/latest?limit=100&convert=USD

Usage:
    python3 regime.py            # human-readable verdict
    python3 regime.py --json     # machine-readable JSON (for agents / scripts)
    python3 regime.py --no-cache # ignore the 5-minute disk cache

The anonymous keyless pool is shared per IP and tight (error 1022 after
~10 rapid calls), so results are cached for 5 minutes in
data/.regime-cache.json (gitignored) and calls are spaced 1s apart with
2 retries and exponential backoff on 429 / 1022.

VERDICT RULES v1 — keep in sync with index.html:
    Fear & Greed: <=24 Extreme Fear, <=44 Fear, <=55 Neutral,
                  <=74 Greed, else Extreme Greed.
    Altcoin Season index: >=75 Altcoin Season, <=25 Bitcoin Season,
                          else Neutral.
    Regime line: "{F&G label} · {Alt/BTC season label} · CMC100 {up/down} {x}%
                  in 24h · BTC dominance {x}%"
Not financial advice.
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://pro-api.coinmarketcap.com/public-api"
CACHE_FILE = Path(__file__).resolve().parent / "data" / ".regime-cache.json"
CACHE_TTL_S = 300  # 5 minutes — Fear & Greed updates daily, indices every 5 min
SLEEP_BETWEEN_CALLS_S = 1.0
MAX_RETRIES = 2

ENDPOINTS = {
    "fear_greed": "/v3/fear-and-greed/latest",
    "altcoin_season": "/v1/altcoin-season-index/latest",
    "cmc100": "/v3/index/cmc100-latest",
    "cmc20": "/v3/index/cmc20-latest",
    "global_metrics": "/v1/global-metrics/quotes/latest",
    "listings": "/v1/cryptocurrency/listings/latest?limit=100&convert=USD",
}


# ---------------------------------------------------------------- verdict logic
def fear_greed_label(value):
    if value is None:
        return "Unknown"
    if value <= 24:
        return "Extreme Fear"
    if value <= 44:
        return "Fear"
    if value <= 55:
        return "Neutral"
    if value <= 74:
        return "Greed"
    return "Extreme Greed"


def season_label(index):
    if index is None:
        return "Unknown"
    if index >= 75:
        return "Altcoin Season"
    if index <= 25:
        return "Bitcoin Season"
    return "Neutral"


def takeaway(fg_value, fg_label, season, btc_dom, cmc100_chg):
    """One plain-English sentence. Branches mirror index.html exactly."""
    if fg_label == "Extreme Fear" and btc_dom is not None and btc_dom > 58:
        return ("Risk-off: capital is hiding in BTC. New money usually waits "
                "for Fear to lift before rotating to alts.")
    if fg_label in ("Extreme Fear", "Fear") and season == "Altcoin Season":
        return ("Fearful market, but alts are still outperforming BTC — "
                "nervous rotation, not a broad exit.")
    if fg_label in ("Greed", "Extreme Greed") and season == "Altcoin Season":
        return ("Risk-on and alts leading: the classic late-cycle alt rotation. "
                "Watch for Fear & Greed rolling over first.")
    if fg_label in ("Greed", "Extreme Greed") and season == "Bitcoin Season":
        return ("Greedy but BTC-led: strength is concentrated in Bitcoin, "
                "alts are lagging the move.")
    if fg_label == "Neutral" and season == "Neutral":
        return ("No strong regime: sentiment and rotation are both flat. "
                "Wait for Fear & Greed or the Altcoin Season index to break out.")
    if cmc100_chg is not None and cmc100_chg < -2:
        return ("Broad market down over 24h while sentiment is shaky — "
                "defensive positioning is dominating.")
    return ("Mixed signals: check the five numbers above rather than any "
            "single indicator.")


def build_verdict(d):
    fg = (d.get("fear_greed") or {}).get("value")
    fg_label = fear_greed_label(fg)
    season_idx = (d.get("altcoin_season") or {}).get("altcoin_index")
    season = season_label(season_idx)
    cmc100 = d.get("cmc100") or {}
    cmc100_chg = cmc100.get("value_24h_percentage_change")
    gm = d.get("global_metrics") or {}
    btc_dom = gm.get("btc_dominance")

    direction = "flat"
    if cmc100_chg is not None:
        direction = "up" if cmc100_chg > 0 else ("down" if cmc100_chg < 0 else "flat")
    chg_txt = f"{abs(cmc100_chg):.2f}%" if cmc100_chg is not None else "n/a"
    dom_txt = f"{btc_dom:.1f}%" if btc_dom is not None else "n/a"

    line = (f"{fg_label} · {season} · CMC100 {direction} {chg_txt} in 24h "
            f"· BTC dominance {dom_txt}")
    return {
        "regime_line": line,
        "fear_greed_label": fg_label,
        "season_label": season,
        "takeaway": takeaway(fg, fg_label, season, btc_dom, cmc100_chg),
    }


# ---------------------------------------------------------------- fetching
def _get(path, retries=MAX_RETRIES):
    """One GET against the keyless API. Returns parsed JSON or raises."""
    url = BASE + path
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            try:
                payload = json.loads(e.read().decode("utf-8"))
            except Exception:
                payload = {}
            code = (payload.get("status") or {}).get("error_code")
            if e.code in (429, 1022) or code in (429, 1022, "429", "1022"):
                if attempt < retries:
                    time.sleep(2 ** attempt * 5)
                    continue
                raise RuntimeError(
                    "Anonymous keyless limit reached (error 1022 / HTTP 429). "
                    "Wait a few minutes and retry, or use a free CMC API key.")
            raise RuntimeError(f"HTTP {e.code} on {path}: "
                               f"{(payload.get('status') or {}).get('error_message') or e}")
        except urllib.error.URLError as e:
            if attempt < retries:
                time.sleep(2 ** attempt * 5)
                continue
            raise RuntimeError(f"Network error on {path}: {e}")
        status = payload.get("status") or {}
        if str(status.get("error_code")) not in ("0", "None"):
            raise RuntimeError(f"CMC error on {path}: "
                               f"{status.get('error_message') or status}")
        return payload.get("data")
    raise RuntimeError(f"Failed to fetch {path}")


def fetch_all():
    """Fetch the six keyless endpoints, spaced out. Returns raw dict."""
    out = {}
    for key, path in ENDPOINTS.items():
        out[key] = _get(path)
        time.sleep(SLEEP_BETWEEN_CALLS_S)
    return out


def normalise(raw):
    """Flatten raw API responses into the shared snapshot shape."""
    gm = raw.get("global_metrics") or {}
    quote = (gm.get("quote") or {}).get("USD") or {}
    listings = []
    for c in raw.get("listings") or []:
        q = (c.get("quote") or {}).get("USD") or {}
        listings.append({
            "id": c.get("id"),
            "name": c.get("name"),
            "symbol": c.get("symbol"),
            "cmc_rank": c.get("cmc_rank"),
            "price_usd": q.get("price"),
            "percent_change_24h": q.get("percent_change_24h"),
            "percent_change_7d": q.get("percent_change_7d"),
            "percent_change_30d": q.get("percent_change_30d"),
            "market_cap_usd": q.get("market_cap"),
            "volume_24h_usd": q.get("volume_24h"),
        })
    return {
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": "CoinMarketCap keyless public API",
        "fear_greed": raw.get("fear_greed"),
        "altcoin_season": raw.get("altcoin_season"),
        "cmc100": raw.get("cmc100"),
        "cmc20": raw.get("cmc20"),
        "global_metrics": {
            "total_market_cap_usd": quote.get("total_market_cap"),
            "total_market_cap_24h_pct": quote.get("total_market_cap_yesterday_percentage_change"),
            "total_volume_24h_usd": quote.get("total_volume_24h"),
            "btc_dominance": gm.get("btc_dominance"),
            "eth_dominance": gm.get("eth_dominance"),
            "active_cryptocurrencies": gm.get("active_cryptocurrencies"),
            "total_cryptocurrencies": gm.get("total_cryptocurrencies"),
            "defi_market_cap_usd": quote.get("defi_market_cap"),
            "stablecoin_market_cap_usd": quote.get("stablecoin_market_cap"),
        },
        "listings_top": listings,
    }


def load_data(use_cache=True):
    if use_cache and CACHE_FILE.exists():
        try:
            cached = json.loads(CACHE_FILE.read_text())
            age = time.time() - cached.get("_cached_at", 0)
            if age < CACHE_TTL_S:
                return cached["data"], True
        except Exception:
            pass
    raw = fetch_all()
    data = normalise(raw)
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(json.dumps({"_cached_at": time.time(), "data": data}))
    except Exception:
        pass  # cache is a nicety, never fatal
    return data, False


# ---------------------------------------------------------------- output
def fmt_usd(n):
    if n is None:
        return "n/a"
    if n >= 1e12:
        return f"${n / 1e12:.3f}T"
    if n >= 1e9:
        return f"${n / 1e9:.2f}B"
    if n >= 1e6:
        return f"${n / 1e6:.2f}M"
    return f"${n:,.2f}"


def fmt_pct(n):
    return "n/a" if n is None else f"{n:+.2f}%"


def print_human(data, verdict, from_cache):
    fg = data.get("fear_greed") or {}
    season = data.get("altcoin_season") or {}
    c100 = data.get("cmc100") or {}
    c20 = data.get("cmc20") or {}
    gm = data.get("global_metrics") or {}
    listings = data.get("listings_top") or []

    print("Regime Radar — CoinMarketCap market regime"
          + (" (cached, <5 min old)" if from_cache else " (live)"))
    print(f"Fetched: {data.get('fetched_at')} UTC")
    print()
    print(f"Regime: {verdict['regime_line']}")
    print(f"Takeaway: {verdict['takeaway']}")
    print("Not financial advice.")
    print()
    print(f"  Fear & Greed:   {fg.get('value')} ({fg.get('value_classification')})")
    print(f"  Altcoin Season: {season.get('altcoin_index')} "
          f"(yearly {season.get('yearly_low')}–{season.get('yearly_high')})")
    print(f"  CMC100:         {c100.get('value')} ({fmt_pct(c100.get('value_24h_percentage_change'))} 24h)")
    print(f"  CMC20:          {c20.get('value')} ({fmt_pct(c20.get('value_24h_percentage_change'))} 24h)")
    print(f"  Total mcap:     {fmt_usd(gm.get('total_market_cap_usd'))} "
          f"({fmt_pct(gm.get('total_market_cap_24h_pct'))} 24h)")
    print(f"  BTC dominance:  {gm.get('btc_dominance')}")
    print(f"  ETH dominance:  {gm.get('eth_dominance')}")
    print(f"  24h volume:     {fmt_usd(gm.get('total_volume_24h_usd'))}")
    print()
    print("Top 10 by market cap:")
    print(f"  {'#':>3} {'Symbol':<8} {'Price':>14} {'24h':>8} {'7d':>8} {'30d':>8}  Market cap")
    for c in listings[:10]:
        print(f"  {c.get('cmc_rank') or '':>3} {c.get('symbol') or '':<8} "
              f"${(c.get('price_usd') or 0):>13,.2f} "
              f"{fmt_pct(c.get('percent_change_24h')):>8} "
              f"{fmt_pct(c.get('percent_change_7d')):>8} "
              f"{fmt_pct(c.get('percent_change_30d')):>8}  "
              f"{fmt_usd(c.get('market_cap_usd'))}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Regime Radar — CMC market-regime verdict.")
    ap.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    ap.add_argument("--no-cache", action="store_true", help="Ignore the 5-minute cache")
    args = ap.parse_args(argv)
    try:
        data, from_cache = load_data(use_cache=not args.no_cache)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    verdict = build_verdict(data)
    if args.json:
        print(json.dumps({**verdict, "data": data}, indent=2))
    else:
        print_human(data, verdict, from_cache)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
