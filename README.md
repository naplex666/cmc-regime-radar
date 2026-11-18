# Regime Radar — CoinMarketCap Market Regime Dashboard

**Is the market fearful or greedy — and is the money in BTC or in alts?**
One verdict, built from five numbers only CoinMarketCap can give you in one
call each. Built for the **Build with CMC: API Hackathon Round 2 (Plushie)**
on DoraHacks, **Data and Visualisation** track.

- Hackathon: 18 Nov – **9 Dec 2026, submissions close Wed 9 Dec 23:59 UTC
  (= Thu 10 Dec 06:59 WIB)**. Judging 10–25 Dec 2026, results 30 Dec 2026.
- Solo or teams up to 4. No entry fee. No upfront KYC found.
- Prizes (non-cash, cannot be exchanged for cash): Top 3 = 1-year CMC Pro
  API grants (1st Professional, 2nd Growth, 3rd Startup); Top 10 =
  exclusive CMC Plushie; Top 30 = exclusive CMC Keyboard; every
  participant = free Startup tier for the event.
- Judging /100: Does it work 30 · Usefulness 25 · Interesting use of the
  API 20 · Code quality and documentation 15 · Presentation 10.
- Submission requires: public GitHub repo + working demo (deployed link or
  screen recording) + **demo video (required)** + X post with
  **#BuildwithCMC** + endpoints named explicitly + visible evidence of a
  real API call.

> **Demo video: still to be recorded.** The dashboard and CLI below are
> working; the video will be recorded once the repo is public.

## What it is

- **Regime verdict** — one plain-English line computed from Fear & Greed,
  Altcoin Season, CMC100/CMC20 24h change, BTC dominance and total market
  cap 24h change, plus a one-sentence takeaway. Example from live data on
  18 Nov 2026: *“Extreme Fear · Neutral · CMC100 down 0.14% in 24h · BTC
  dominance 59.1%”* — “Risk-off: capital is hiding in BTC.”
- **Market snapshot** — BTC/ETH price, total market cap, BTC/ETH dominance,
  24h volume, DeFi and stablecoin market cap.
- **Top-100 screener** — rank, price, 24h/7d/30d %, market cap; sortable
  columns, text filter, gainers/losers toggle.
- **RWA watch** — tokenised real-world assets (stocks, commodities,
  treasuries, funds). Locked until a free CMC API key is added; see below.
- **`regime.py`** — the same verdict as a CLI / agent tool: human-readable
  text, or `--json` for machine use. Python 3 stdlib only, no pip packages.

No API key is needed for the core dashboard. Not financial advice.

## Run it

```bash
# Dashboard — open index.html, or serve it:
python3 -m http.server 8000        # then http://localhost:8000/

# CLI verdict (live, 6 keyless calls, 5-minute disk cache):
python3 regime.py
python3 regime.py --json           # machine-readable, for agents

# RWA section (optional, needs a free key — no card):
export CMC_PRO_API_KEY="your-free-key"   # from pro.coinmarketcap.com/login
python3 fetch_rwa.py               # writes data/rwa.json, dashboard picks it up
```

## Endpoints used (named explicitly)

Keyless public API — base `https://pro-api.coinmarketcap.com/public-api`,
no auth header, no account:

| Endpoint | Used for |
|---|---|
| `GET /v3/fear-and-greed/latest` | Fear & Greed value (13, Extreme Fear on 18 Nov) |
| `GET /v1/altcoin-season-index/latest` | Altcoin Season index (52 on 18 Nov) |
| `GET /v3/index/cmc100-latest` | CMC100 value + 24h change (125.33, −0.14%) |
| `GET /v3/index/cmc20-latest` | CMC20 value + 24h change (130.92, −0.11%) |
| `GET /v1/global-metrics/quotes/latest` | Total mcap ($2.188T), BTC dominance (59.1%), volume |
| `GET /v1/cryptocurrency/listings/latest?limit=100&convert=USD` | Top-100 screener |

Keyed Pro API — base `https://pro-api.coinmarketcap.com`, header
`X-CMC_PRO_API_KEY`, free Basic tier and up (via `fetch_rwa.py` only):

| Endpoint | Used for |
|---|---|
| `GET /v5/real-world-assets/assets/list` | Tokenised RWA list by market cap |
| `GET /v5/real-world-assets/issuers/list` | RWA issuers |
| `GET /v5/real-world-assets/map`, `GET /v5/real-world-assets/quotes/latest` | Documented for follow-up use |

Verdict rules (identical in `index.html` and `regime.py`, “VERDICT RULES v1”):
Fear & Greed ≤24 Extreme Fear, ≤44 Fear, ≤55 Neutral, ≤74 Greed, else
Extreme Greed. Altcoin Season ≥75 Altcoin Season, ≤25 Bitcoin Season, else
Neutral. Regime line: “{F&G} · {Season} · CMC100 {up/down} {x}% in 24h ·
BTC dominance {x}%”.

## What the API made possible — and where it got in the way

- **Made possible:** the four proprietary indices (Fear & Greed, Altcoin
  Season, CMC100, CMC20) are single keyless calls. Without them this
  verdict would be a modelling task to invent and defend; with them it is
  four numbers plus dominance.
- **Anonymous limit is tight:** the keyless pool is shared per IP. After
  ~10 rapid calls it returns error `1022` (“reached the limit for
  anonymous access”). The dashboard therefore fetches once per load (6
  calls, sequential, 400 ms apart, in-memory cache) and falls back to the
  bundled real snapshot in `data/snapshot.json` (captured live 18 Nov
  2026 03:09 UTC) with a visible “showing snapshot” banner. `regime.py`
  caches for 5 minutes on disk.
- **Trending is keyed:** `/v1/cryptocurrency/trending/latest` returns
  error `1005` (“An API Key is required”) on the keyless path, so the
  screener ranks by market cap instead of trending. A free key unlocks it.
- **RWA is keyed:** all `/v5/real-world-assets/*` endpoints need
  `X-CMC_PRO_API_KEY`. The free Basic tier covers map/info/list/quotes;
  market-pairs needs Growth+. The RWA section is therefore an honest
  locked state until a key is added — it never shows fake data.
- **No key is ever committed:** keys come only from the
  `CMC_PRO_API_KEY` environment variable; `.gitignore` blocks `.env`,
  key files, `data/rwa.json` and the CLI cache.

## Files

| File | What it is |
|---|---|
| `index.html` | The whole dashboard — no framework, no build step |
| `regime.py` | CLI / agent tool, stdlib only (`--json` for agents) |
| `fetch_rwa.py` | Optional RWA fetcher, stdlib only, env key only |
| `data/snapshot.json` | Real live snapshot, 18 Nov 2026 03:09 UTC (offline fallback) |
| `data/rwa.json` | Created by `fetch_rwa.py` when a key is present (gitignored) |

## Evidence of a real API call

Live keyless call, 18 Nov 2026 03:09 UTC:

```bash
curl "https://pro-api.coinmarketcap.com/public-api/v3/fear-and-greed/latest"
# {"data":{"value":13,"update_time":"2026-11-18T03:08:10.071Z",
#  "value_classification":"Extreme fear"},"status":{"timestamp":"2026-11-18T03:09:23.683Z",
#  "error_code":"0","error_message":"","elapsed":3,"credit_count":1}}
```

`regime.py` output (live run, 18 Nov 2026 03:13 UTC): Fear & Greed 13
Extreme Fear, Altcoin Season 52, CMC100 125.33 (−0.33%), CMC20 131.06
(−0.01%), BTC $64,446.55, ETH $1,807.92, total market cap $2.189T, BTC
dominance 59.2%. Second run served the same numbers from the 5-minute
disk cache with zero API calls.
