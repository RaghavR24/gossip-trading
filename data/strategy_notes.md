# Strategy Notes

Agent-maintained file. Write lessons, market regime observations, and
strategic insights here. This file is loaded each cycle so future
sessions benefit from past experience.

## Known Issues (pre-loaded)

- Always run Python tools with `PYTHONPATH=.` prefix: `PYTHONPATH=. python3 gossip/...`
- Market data always reads from prod API (public, no auth). Demo data is stale/fake.
- Paper trader uses orderbook for real best bid/ask, not market summary (which can be stale).
- Orderbook fields are `yes_dollars` and `no_dollars`, each entry is [price_str, quantity_str].

## Observations

### 2026-04-04 — First Cycle

**Market regime:** Trump cabinet shakeup in progress. Bondi fired Apr 2, more exits under discussion (Patel, Chavez-DeRemer, Driscoll, Lutnick). This creates a cluster of correlated binary events on Kalshi.

**Key lesson: Check for already-resolved events.** The Bondi "leaves before Apr 5" market was still trading at 82-83c YES despite her firing being confirmed 2 days earlier by every major outlet. This is near-arbitrage — the market lags real-world resolution. Always check if events have already occurred before looking at the price.

**Cabinet departure markets:** These tend to have multiple timeframes (Apr 5, Apr 9, Apr 16, May 1). The shorter-dated ones offer better returns when the event has occurred but the market hasn't caught up. The longer-dated ones are more speculative.

**Chavez-DeRemer thesis:** IG investigation + forced aide departures + Trump frustration + pattern of recent firings = elevated probability above market's 43%. Estimated 55-60%. Key risk: Trump has backed off before and says he wants to avoid "massive shake-up." Monitor for news of actual firing or explicit statement she stays.

**Passed on:**
- Kash Patel FBI exit (26.5%) — too uncertain, no concrete indicators beyond speculation
- IPO markets — all illiquid, wide spreads, low volume. Not worth the capital lockup.
- Greenland purchase (0.5%) — correctly priced near zero

**Trades executed:**
1. KXBONDIOUT-26APR-APR05 YES @ 82c × 10 — near-certain resolution, expected +$1.80
2. KXDEREMEROUT-26-MAY01 YES @ 44c × 5 — medium confidence, 13pp estimated edge
