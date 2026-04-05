# Search Upgrade: Series-Aware Market Discovery

## Problem

The agent can't find series-based markets (weather, gas, CPI) through `search`. These are some of Kalshi's most liquid non-politics markets. The agent has noted this in strategy_notes across 4+ cycles.

Current `search "gas"` flow:
1. Fetch all open **events** (cached, ~5000)
2. Substring match on event `title` and `category`
3. Fetch full details for matches

This misses markets where the **series** title contains the keyword but individual event titles don't match cleanly, or where the event titles use abbreviations/codes.

## Proposed Solution

Add a series index alongside the event index. When the agent searches, match against both.

### New flow for `search "gas"`:

```
1. Check cached event index (already exists, ~5000 events)
2. Check cached series index (NEW, ~200-300 series)
3. Match "gas" against:
   - Event titles (existing)
   - Event categories (existing)  
   - Series titles (NEW)
   - Series tags/category (NEW)
4. For series matches: fetch that series' open markets via /markets?series_ticker=X
5. Deduplicate (events and series can overlap)
6. Return combined results
```

### Implementation

**New cached index** — `_series_index`:
```python
async def _get_series_index(session, max_age=300):
    # Single request: GET /series?limit=500
    # Returns ~200-300 series with title, ticker, category
    # Cache for 5 minutes (same as event index)
```

This is a single API call (not paginated like events). Cheap.

**Modified `search_events()`**:
```python
async def search_events(query: str) -> list[dict]:
    async with aiohttp.ClientSession() as session:
        q = query.lower()
        
        # Existing: match events by title/category
        event_index = await _get_event_index(session)
        event_matches = [e for e in event_index 
                        if q in e.get("title","").lower() 
                        or q in e.get("category","").lower()]
        
        # NEW: match series by title
        series_index = await _get_series_index(session)
        series_matches = [s for s in series_index
                         if q in s.get("title","").lower()
                         or q in s.get("category","").lower()]
        
        # Fetch details for event matches (existing)
        results = []
        for e in event_matches[:15]:
            data = await api_get(session, f"/events/{e['event_ticker']}", 
                               {"with_nested_markets": "true"})
            results.append(format_event(data))
        
        # NEW: Fetch markets for series matches
        seen_tickers = {r["event_ticker"] for r in results}
        for s in series_matches[:5]:
            markets = await api_get(session, "/markets", {
                "series_ticker": s["ticker"],
                "status": "open",
                "limit": 20,
            })
            # Group by event, skip already-seen
            for m in markets.get("markets", []):
                if m.get("event_ticker") not in seen_tickers:
                    results.append(format_market(m, s))
                    seen_tickers.add(m.get("event_ticker"))
        
        return results
```

### What this fixes

| Search query | Before | After |
|---|---|---|
| "gas" | Finds events with "gas" in title | Also finds KXAAAGASW series markets |
| "CPI" | Misses most CPI markets | Finds KXCPIYOY series + all monthly events |
| "weather" | Hits some events | Also finds KXHIGHTDAL, KXHIGHTNYC series |
| "temperature" | Sparse | Finds all temperature series |
| "tariff" | Works (event titles match) | Same + any tariff series |

### Performance

- Series index: 1 API call, cached 5 min. ~200-300 items.
- Per series match: 1 API call for markets. Cap at 5 series = 5 extra calls max.
- Total: 1-6 extra API calls per search. Adds ~2-3 seconds.

### Quick scan page increase

Separate from search, increase `quick_scan` from 5 to 12 pages. The `--limit` flag already caps output at 50 markets, so the LLM sees the same volume — just a more representative sample drawn from the full universe instead of the first 20%.

### No prompt changes needed

The agent already calls:
```
PYTHONPATH=. python3 gossip/kalshi.py search "gas prices"
```

Same interface, better results. The CYCLE_PROMPT doesn't need to explain series vs events.

## Risks

- Series fetch could return stale data if Kalshi updates series list. 5-min cache mitigates.
- Some series have 100+ markets (e.g., daily weather). The `limit: 20` per series keeps this bounded.
- Extra API calls could hit rate limits on very broad searches. The 5-series cap prevents this.

## Effort

~30 lines of code in `kalshi.py`. No other files change.
