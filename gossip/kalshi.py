"""
Kalshi API client — market scanning, orderbook, search, and authenticated trading.

CLI tool invoked by Claude Code agent:
    python3 gossip/kalshi.py scan [--categories "Economics,Politics"] [--days 14]
    python3 gossip/kalshi.py market TICKER
    python3 gossip/kalshi.py orderbook TICKER
    python3 gossip/kalshi.py search "bitcoin"
    python3 gossip/kalshi.py events TICKER
    python3 gossip/kalshi.py order TICKER --action buy --side yes --count 3 --price 55
    python3 gossip/kalshi.py positions
    python3 gossip/kalshi.py balance

All output is JSON to stdout. Logs go to stderr.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
import math
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

import aiohttp
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

PROD_BASE = "https://api.elections.kalshi.com/trade-api/v2"
DEMO_BASE = "https://demo-api.kalshi.co/trade-api/v2"

def get_base_url() -> str:
    """Always prod. Demo API has stale/fake data and is useless."""
    return PROD_BASE

def log(msg: str) -> None:
    print(msg, file=sys.stderr)

# --- Auth ---

_cached_private_key = None

def load_private_key():
    global _cached_private_key
    if _cached_private_key is not None:
        return _cached_private_key
    key_path = os.getenv("KALSHI_PRIVATE_KEY_PATH", "")
    key_raw = os.getenv("KALSHI_PRIVATE_KEY", "")
    if key_path:
        key_raw = Path(key_path).read_text()
    if not key_raw:
        return None
    _cached_private_key = serialization.load_pem_private_key(key_raw.encode(), password=None)
    return _cached_private_key

def build_auth_headers(method: str, path: str) -> dict:
    api_key = os.getenv("KALSHI_API_KEY_ID", "")
    pk = load_private_key()
    if not api_key or not pk:
        return {}

    timestamp = str(int(time.time() * 1000))
    message = f"{timestamp}{method.upper()}{path}"
    signature = pk.sign(
        message.encode(),
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=32,
        ),
        hashes.SHA256(),
    )
    import base64
    return {
        "KALSHI-ACCESS-KEY": api_key,
        "KALSHI-ACCESS-SIGNATURE": base64.b64encode(signature).decode(),
        "KALSHI-ACCESS-TIMESTAMP": timestamp,
    }

# --- API helpers ---

SKIP_SERIES = {"KXMVESPORTS", "KXMVE"}  # only skip pure noise; agent decides what's interesting

MAX_RETRIES = 3
BASE_DELAY = 1.0

async def api_get(session: aiohttp.ClientSession, path: str, params: dict | None = None, auth: bool = False) -> dict:
    base = get_base_url()
    url = f"{base}{path}"
    headers = {"Accept-Encoding": "gzip", "Content-Type": "application/json"}
    if auth:
        headers.update(build_auth_headers("GET", f"/trade-api/v2{path}"))

    for attempt in range(MAX_RETRIES + 1):
        try:
            async with session.get(url, params=params, headers=headers) as resp:
                text = await resp.text()
                if resp.status == 429 and attempt < MAX_RETRIES:
                    delay = BASE_DELAY * (2 ** attempt)
                    log(f"Rate limited, retrying in {delay:.0f}s...")
                    await asyncio.sleep(delay)
                    continue
                if resp.status >= 400:
                    return {"error": f"HTTP {resp.status}", "body": text[:200]}
                return json.loads(text) if text else {}
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            if attempt < MAX_RETRIES:
                await asyncio.sleep(BASE_DELAY * (2 ** attempt))
                continue
            return {"error": str(e)}
    return {"error": "max retries exceeded"}

async def api_post(session: aiohttp.ClientSession, path: str, body: dict) -> dict:
    url = f"{get_base_url()}{path}"
    headers = {"Content-Type": "application/json"}
    headers.update(build_auth_headers("POST", f"/trade-api/v2{path}"))

    for attempt in range(MAX_RETRIES + 1):
        try:
            async with session.post(url, json=body, headers=headers) as resp:
                text = await resp.text()
                if resp.status == 429 and attempt < MAX_RETRIES:
                    await asyncio.sleep(BASE_DELAY * (2 ** attempt))
                    continue
                if resp.status >= 400:
                    return {"error": f"HTTP {resp.status}", "body": text[:500]}
                return json.loads(text) if text else {}
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            if attempt < MAX_RETRIES:
                await asyncio.sleep(BASE_DELAY * (2 ** attempt))
                continue
            return {"error": str(e)}
    return {"error": "max retries exceeded"}

async def api_delete(session: aiohttp.ClientSession, path: str, body: dict | None = None) -> dict:
    url = f"{get_base_url()}{path}"
    headers = {"Content-Type": "application/json"}
    headers.update(build_auth_headers("DELETE", f"/trade-api/v2{path}"))

    async with session.delete(url, json=body, headers=headers) as resp:
        text = await resp.text()
        if resp.status >= 400:
            return {"error": f"HTTP {resp.status}", "body": text[:500]}
        return json.loads(text) if text else {}

# --- Market scanning ---

@dataclass
class Market:
    ticker: str
    event_ticker: str
    series_ticker: str
    title: str
    category: str
    rules: str
    close_time: str
    days_to_close: float
    yes_bid: float
    yes_ask: float
    mid: float
    spread_cents: float
    volume: float
    open_interest: float
    implied_prob: float

def parse_market(m: dict, category: str = "") -> Market | None:
    ticker = m.get("ticker", "")
    for skip in SKIP_SERIES:
        if ticker.startswith(skip):
            return None

    close_str = m.get("close_time", "")
    if not close_str:
        return None
    try:
        close_dt = datetime.fromisoformat(close_str.replace("Z", "+00:00"))
    except ValueError:
        return None

    now = datetime.now(timezone.utc)
    days = (close_dt - now).total_seconds() / 86400
    if days < 0:
        return None

    bid = float(m.get("yes_bid_dollars", "0") or "0")
    ask = float(m.get("yes_ask_dollars", "0") or "0")
    vol = float(m.get("volume_fp", "0") or "0")
    oi = float(m.get("open_interest_fp", "0") or "0")

    if bid == 0 and ask == 0:
        return None

    mid = (bid + ask) / 2
    spread = (ask - bid) * 100

    cat = category or m.get("category", "")

    return Market(
        ticker=ticker,
        event_ticker=m.get("event_ticker", ""),
        series_ticker=m.get("series_ticker", ""),
        title=m.get("title", ""),
        category=cat,
        rules=m.get("rules_primary", ""),
        close_time=close_str[:16],
        days_to_close=round(days, 2),
        yes_bid=bid,
        yes_ask=ask,
        mid=round(mid, 4),
        spread_cents=round(spread, 1),
        volume=vol,
        open_interest=oi,
        implied_prob=round(mid, 4),
    )

async def scan_markets(
    categories: set[str] | None = None,
    max_days: int = 30,
    min_oi: float = 50,
    max_series: int = 100,
) -> list[Market]:
    async with aiohttp.ClientSession() as session:
        data = await api_get(session, "/series", {"limit": 500})
        all_series = data.get("series", [])

        interesting = []
        for s in all_series:
            ticker = s.get("ticker", "")
            if any(ticker.startswith(skip) for skip in SKIP_SERIES):
                continue
            if categories:
                cat = s.get("category", "")
                if cat and cat not in categories:
                    continue
            interesting.append(s)

        interesting = interesting[:max_series]
        log(f"Scanning {len(interesting)} series...")

        markets: list[Market] = []
        for i, s in enumerate(interesting):
            mdata = await api_get(session, "/markets", {
                "series_ticker": s["ticker"],
                "status": "open",
                "limit": 200,
            })
            for m in mdata.get("markets", []):
                parsed = parse_market(m, s.get("category", ""))
                if parsed and parsed.days_to_close <= max_days and parsed.open_interest >= min_oi:
                    markets.append(parsed)

            if (i + 1) % 50 == 0:
                log(f"  checked {i+1}/{len(interesting)}...")
                await asyncio.sleep(0.3)

        markets.sort(key=lambda m: m.volume, reverse=True)
        return markets

async def get_market_detail(ticker: str) -> dict:
    async with aiohttp.ClientSession() as session:
        data = await api_get(session, f"/markets/{ticker}")
        market = data.get("market", data)
        ob = await api_get(session, f"/markets/{ticker}/orderbook")
        orderbook = ob.get("orderbook_fp", ob.get("orderbook", {}))

        rules_primary = market.get("rules_primary", "")
        rules_secondary = market.get("rules_secondary", "")
        rules = rules_primary
        if rules_secondary:
            rules = f"{rules_primary}\n\nIMPORTANT DETAILS: {rules_secondary}"
        result: dict = {
            "summary": {
                "ticker": ticker,
                "title": market.get("title", ""),
                "category": market.get("category", ""),
                "status": market.get("status", ""),
                "result": market.get("result", ""),
                "yes_bid": market.get("yes_bid_dollars") or market.get("yes_bid", 0),
                "yes_ask": market.get("yes_ask_dollars") or market.get("yes_ask", 0),
                "volume": market.get("volume", 0),
                "open_interest": market.get("open_interest", 0),
                "close_time": (market.get("close_time") or "")[:16],
                "expiration_time": (market.get("expiration_time") or "")[:16],
            },
            "settlement_rules": rules,
            "orderbook": orderbook,
            "market": market,
        }

        event_ticker = market.get("event_ticker")
        if event_ticker:
            sibling_data = await api_get(session, "/markets", {
                "event_ticker": event_ticker, "limit": 200,
            })
            siblings = [
                {"ticker": m["ticker"], "subtitle": m.get("subtitle", m.get("yes_sub_title", "")),
                 "yes_ask": m.get("yes_ask"), "no_ask": m.get("no_ask"),
                 "volume": m.get("volume"), "status": m.get("status")}
                for m in sibling_data.get("markets", [])
                if m["ticker"] != ticker
            ]
            if siblings:
                result["related_contracts"] = siblings
        return result

async def get_orderbook(ticker: str) -> dict:
    async with aiohttp.ClientSession() as session:
        data = await api_get(session, f"/markets/{ticker}/orderbook")
        return data.get("orderbook_fp", data.get("orderbook", data))

_event_index: list[dict] | None = None
_event_index_ts: float = 0

async def _get_event_index(session: aiohttp.ClientSession, max_age: float = 300) -> list[dict]:
    """Lightweight index of all open events (no nested markets). Cached for max_age seconds."""
    global _event_index, _event_index_ts
    if _event_index is not None and (time.time() - _event_index_ts) < max_age:
        return _event_index
    events = []
    cursor = ""
    for _ in range(30):
        params = {"limit": 200, "with_nested_markets": "false", "status": "open"}
        if cursor:
            params["cursor"] = cursor
        data = await api_get(session, "/events", params)
        events.extend(data.get("events", []))
        cursor = data.get("cursor", "")
        if not cursor:
            break
    _event_index = events
    _event_index_ts = time.time()
    return events

_series_index: list[dict] | None = None
_series_index_ts: float = 0

async def _get_series_index(session: aiohttp.ClientSession, max_age: float = 300) -> list[dict]:
    """Index of all series. Single API call, cached for max_age seconds."""
    global _series_index, _series_index_ts
    if _series_index is not None and (time.time() - _series_index_ts) < max_age:
        return _series_index
    data = await api_get(session, "/series", {"limit": 500})
    _series_index = data.get("series", [])
    _series_index_ts = time.time()
    return _series_index

async def search_events(query: str) -> list[dict]:
    async with aiohttp.ClientSession() as session:
        q = query.lower()

        # Match events by title/category
        event_index = await _get_event_index(session)
        event_matches = [
            e["event_ticker"] for e in event_index
            if q in e.get("title", "").lower() or q in e.get("category", "").lower()
        ][:15]

        results = []
        seen_event_tickers = set()
        for ticker in event_matches:
            data = await api_get(session, f"/events/{ticker}", {"with_nested_markets": "true"})
            e = data.get("event", data)
            seen_event_tickers.add(e.get("event_ticker", ""))
            results.append({
                "event_ticker": e.get("event_ticker", ""),
                "title": e.get("title", ""),
                "category": e.get("category", ""),
                "source": "event",
                "markets": [
                    {
                        "ticker": m.get("ticker", ""),
                        "title": m.get("yes_sub_title", m.get("title", "")),
                        "yes_bid": m.get("yes_bid", 0),
                        "yes_ask": m.get("yes_ask", 0),
                        "volume": m.get("volume", 0),
                    }
                    for m in e.get("markets", [])[:10]
                ],
            })

        # Match series by title/category
        series_index = await _get_series_index(session)
        series_matches = [
            s for s in series_index
            if q in s.get("title", "").lower() or q in s.get("category", "").lower()
        ][:5]

        for s in series_matches:
            mdata = await api_get(session, "/markets", {
                "series_ticker": s["ticker"],
                "status": "open",
                "limit": 20,
            })
            markets = mdata.get("markets", [])
            # Group markets by event to avoid duplicates
            by_event: dict[str, list] = {}
            for m in markets:
                et = m.get("event_ticker", "")
                if et not in seen_event_tickers:
                    by_event.setdefault(et, []).append(m)

            for et, event_markets in list(by_event.items())[:5]:
                seen_event_tickers.add(et)
                results.append({
                    "event_ticker": et,
                    "title": s.get("title", ""),
                    "category": s.get("category", ""),
                    "source": "series",
                    "series_ticker": s["ticker"],
                    "markets": [
                        {
                            "ticker": m.get("ticker", ""),
                            "title": m.get("yes_sub_title", m.get("title", "")),
                            "yes_bid": m.get("yes_bid", 0),
                            "yes_ask": m.get("yes_ask", 0),
                            "volume": m.get("volume", 0),
                        }
                        for m in event_markets[:10]
                    ],
                })

        return results

async def quick_scan(categories: set[str] | None = None, max_days: int = 30, min_volume: float = 0, sort: str = "mixed") -> list[dict]:
    """Scan all open events with nested markets. Paginates up to 6000 events (~10-15s)."""
    async with aiohttp.ClientSession() as session:
        all_markets = []
        cursor = ""
        for page in range(30):
            params = {"limit": 200, "with_nested_markets": "true", "status": "open"}
            if cursor:
                params["cursor"] = cursor
            data = await api_get(session, "/events", params)
            events = data.get("events", [])
            cursor = data.get("cursor", "")

            for e in events:
                cat = e.get("category", "")
                if categories and cat not in categories:
                    continue
                for m in e.get("markets", []):
                    parsed = parse_market(m, cat)
                    if parsed and parsed.days_to_close <= max_days and parsed.volume >= min_volume:
                        all_markets.append(parsed)

            if not cursor:
                break
            if (page + 1) % 10 == 0:
                log(f"  scanned {page + 1} pages...")

        if sort == "volume":
            all_markets.sort(key=lambda m: m.volume, reverse=True)
        elif sort == "recent":
            all_markets.sort(key=lambda m: m.days_to_close)
        elif sort == "mixed":
            by_vol = sorted(all_markets, key=lambda m: m.volume, reverse=True)
            by_recent = sorted(all_markets, key=lambda m: m.days_to_close)
            seen = set()
            merged = []
            for m in by_vol:
                if m.ticker not in seen:
                    seen.add(m.ticker)
                    merged.append(m)
                if len(merged) >= len(all_markets):
                    break
            for m in by_recent:
                if m.ticker not in seen:
                    seen.add(m.ticker)
                    merged.append(m)
            all_markets = merged

        log(f"Quick scan: {len(all_markets)} markets found (sort={sort})")
        return all_markets


async def get_event_markets(event_ticker: str) -> list[dict]:
    async with aiohttp.ClientSession() as session:
        data = await api_get(session, "/markets", {
            "event_ticker": event_ticker,
            "limit": 200,
        })
        return data.get("markets", [])

# --- Authenticated endpoints ---

async def place_order(
    ticker: str, action: str, side: str, count: int,
    price_cents: int | None = None, order_type: str = "market",
    buy_max_cost: int | None = None,
    sell_position_floor: int | None = None,
    expiration_ts: int | None = None,
    client_order_id: str | None = None,
) -> dict:
    import uuid
    body: dict = {
        "ticker": ticker,
        "action": action,
        "side": side,
        "type": order_type,
        "count": count,
        "client_order_id": client_order_id or str(uuid.uuid4()),
    }
    if price_cents is not None:
        body["yes_price"] = price_cents
    if buy_max_cost is not None:
        body["buy_max_cost"] = buy_max_cost
    if sell_position_floor is not None:
        body["sell_position_floor"] = sell_position_floor
    if expiration_ts is not None:
        body["expiration_ts"] = expiration_ts
    async with aiohttp.ClientSession() as session:
        return await api_post(session, "/portfolio/orders", body)

async def get_positions() -> dict:
    async with aiohttp.ClientSession() as session:
        return await api_get(session, "/portfolio/positions", {"limit": 200}, auth=True)

async def get_balance() -> dict:
    async with aiohttp.ClientSession() as session:
        return await api_get(session, "/portfolio/balance", auth=True)

async def cancel_order(order_id: str) -> dict:
    async with aiohttp.ClientSession() as session:
        return await api_delete(session, f"/portfolio/orders/{order_id}")

# --- Fee calculation ---

def kalshi_fee(contracts: int, price: float) -> float:
    return math.ceil(0.07 * contracts * price * (1 - price)) / 100

# --- CLI ---

async def main():
    parser = argparse.ArgumentParser(description="Kalshi API client")
    sub = parser.add_subparsers(dest="command")

    scan_p = sub.add_parser("scan", help="Scan active markets (slow, per-series)")
    scan_p.add_argument("--categories", type=str, default=None)
    scan_p.add_argument("--days", type=int, default=30)
    scan_p.add_argument("--min-oi", type=float, default=50)
    scan_p.add_argument("--limit", type=int, default=50)

    quick_p = sub.add_parser("quick", help="Fast scan via events endpoint (~10s)")
    quick_p.add_argument("--categories", type=str, default=None)
    quick_p.add_argument("--days", type=int, default=30)
    quick_p.add_argument("--min-volume", type=float, default=0)
    quick_p.add_argument("--sort", choices=["volume", "recent", "mixed"], default="mixed")
    quick_p.add_argument("--limit", type=int, default=50)

    market_p = sub.add_parser("market", help="Get market details")
    market_p.add_argument("ticker")

    ob_p = sub.add_parser("orderbook", help="Get orderbook")
    ob_p.add_argument("ticker")

    rules_p = sub.add_parser("rules", help="Get settlement rules for a market")
    rules_p.add_argument("ticker")

    search_p = sub.add_parser("search", help="Search events")
    search_p.add_argument("query")

    events_p = sub.add_parser("events", help="Get event markets")
    events_p.add_argument("event_ticker")

    order_p = sub.add_parser("order", help="Place order (authenticated)")
    order_p.add_argument("ticker")
    order_p.add_argument("--action", choices=["buy", "sell"], required=True)
    order_p.add_argument("--side", choices=["yes", "no"], required=True)
    order_p.add_argument("--count", type=int, required=True)
    order_p.add_argument("--price", type=int, default=None, help="Price in cents (1-99)")
    order_p.add_argument("--type", dest="order_type", choices=["market", "limit"], default="market")

    sub.add_parser("positions", help="Get positions (authenticated)")
    sub.add_parser("balance", help="Get balance (authenticated)")

    cancel_p = sub.add_parser("cancel", help="Cancel order")
    cancel_p.add_argument("order_id")

    args = parser.parse_args()

    if args.command == "scan":
        cats = set(args.categories.split(",")) if args.categories else None
        markets = await scan_markets(categories=cats, max_days=args.days, min_oi=args.min_oi)
        results = [asdict(m) for m in markets[:args.limit]]

        # persist snapshots to DB
        if results:
            try:
                import sys as _sys
                _sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
                from gossip.db import GossipDB
                db = GossipDB()
                db.insert_market_snapshots(results)
            except Exception as e:
                log(f"DB snapshot write failed: {e}")

        print(json.dumps(results, indent=2))

    elif args.command == "quick":
        cats = set(args.categories.split(",")) if args.categories else None
        markets = await quick_scan(categories=cats, max_days=args.days, min_volume=args.min_volume, sort=args.sort)
        results = [asdict(m) for m in markets[:args.limit]]

        if results:
            try:
                import sys as _sys
                _sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
                from gossip.db import GossipDB
                db = GossipDB()
                db.insert_market_snapshots(results)
            except Exception as e:
                log(f"DB snapshot write failed: {e}")

        output = {
            "_meta": {
                "showing": len(results),
                "total_found": len(markets),
                "sort": args.sort,
                "hint": f"Showing top {len(results)} of {len(markets)} markets (sorted by {args.sort}). Use --limit N for more, --sort volume/recent/mixed to change ranking, or `search \"keyword\"` to find specific topics.",
            },
            "markets": results,
        }
        print(json.dumps(output, indent=2))

    elif args.command == "market":
        result = await get_market_detail(args.ticker)
        print(json.dumps(result, indent=2))

    elif args.command == "rules":
        result = await get_market_detail(args.ticker)
        rules = result.get("settlement_rules", "")
        summary = result.get("summary", {})
        print(json.dumps({
            "ticker": summary.get("ticker", args.ticker),
            "title": summary.get("title", ""),
            "close_time": summary.get("close_time", ""),
            "expiration_time": summary.get("expiration_time", ""),
            "settlement_rules": rules,
        }, indent=2))

    elif args.command == "orderbook":
        result = await get_orderbook(args.ticker)
        print(json.dumps(result, indent=2))

    elif args.command == "search":
        results = await search_events(args.query)
        total_markets = sum(len(r.get("markets", [])) for r in results)
        output = {
            "_meta": {
                "events_matched": len(results),
                "total_markets": total_markets,
                "hint": f"Found {len(results)} events with {total_markets} markets matching \"{args.query}\". Use `market TICKER` to get full details + settlement rules for a specific market.",
            },
            "events": results,
        }
        print(json.dumps(output, indent=2))

    elif args.command == "events":
        results = await get_event_markets(args.event_ticker)
        print(json.dumps(results, indent=2))

    elif args.command == "order":
        result = await place_order(
            ticker=args.ticker,
            action=args.action,
            side=args.side,
            count=args.count,
            price_cents=args.price,
            order_type=args.order_type,
        )
        print(json.dumps(result, indent=2))

    elif args.command == "positions":
        result = await get_positions()
        print(json.dumps(result, indent=2))

    elif args.command == "balance":
        result = await get_balance()
        print(json.dumps(result, indent=2))

    elif args.command == "cancel":
        result = await cancel_order(args.order_id)
        print(json.dumps(result, indent=2))

    else:
        parser.print_help()

if __name__ == "__main__":
    asyncio.run(main())
