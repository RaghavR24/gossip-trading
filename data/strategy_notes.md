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

### 2026-04-04 — Second Cycle

**Market regime:** Iran war week 6, strong March jobs report, rising mortgage rates (6.46%). AG Bondi fired, Zeldin likely replacement. Cabinet anxiety continues.

**Greenland trade:** Bought NO × 8 @ 65c on KXGREENTERRITORY-29 (US acquires Greenland by Jan 2029). Market at 35-36c YES, my estimate 12%. Edge: 23pp. Key evidence:
- Denmark & Greenland firmly oppose: PM said "we choose Denmark"
- Trump pledged at Davos not to use force/tariffs
- No formal negotiations, only vague "framework" talks
- Iran war diverts political capital
- Legal/diplomatic complexity of sovereignty transfer enormous
Risk: Trump unpredictability, long time horizon (3 years). Capital locked for potentially long period.

**Position review:**
- Bondi YES: Still active, closes Apr 5. Will resolve YES. Hold for settlement.
- DeRemer YES: Market flat at 42-44c (our entry 44c). IG investigation ongoing, aides forced out. WashPost says she's "vulnerable." But Trump "wants to avoid massive shake-up." Thesis weakened slightly but still alive. HOLD.

**Markets researched — no trade:**
- **Next AG (KXNEXTAG-29):** Zeldin 55%, Blanche 23%. Zeldin is reported frontrunner but not finalized. Market seems efficient. NOTE: Acting/interim don't count — only Senate-confirmed or recess appointments.
- **OpenAI vs Anthropic IPO (KXOAIANTH-40):** Anthropic at 80% to IPO first. Both targeting Q4 2026. Anthropic has banks/counsel engaged; OpenAI CFO hedging to 2027. My estimate ~70-75% Anthropic. Edge only 5-10pp — below threshold.
- **Netflix Top Show Apr 6 (KXNETFLIXRANKSHOWGLOBAL-26APR06):** XO, Kitty dominates daily chart (#1 with 880 pts vs #2 at 589) but is NOT listed as a market option. If it wins weekly chart, all listed options resolve NO. But edge per contract is thin on the NO side (buying at 91-94c for 6-9c profit).
- **Next Cabinet Departure (KXCABOUT-26APR):** DeRemer 32-34c, Gabbard 23-26c, Hegseth 16-18c, Lutnick 11-12c. Reporting says DeRemer & Lutnick most vulnerable, Trump privately asking about replacing Gabbard. Roughly efficient pricing.
- **2028 Presidential:** Vance 18c, Newsom 18c, Rubio 12c, AOC 5-6c. Too long-dated, didn't find clear edge.

**Process lessons:**
- `kalshi.py scan` is VERY slow (minutes). Use `search` for targeted lookups or direct API calls for bulk queries.
- Most non-sports Kalshi markets have zero liquidity. The active categories are: Elections, Politics, some Entertainment (Netflix).
- Sports markets dominate volume. Avoid unless you have a genuine sports analytics edge.
- The events API with `with_nested_markets` is the fastest way to survey the full market landscape.
- For scanning, filter by OI > 500 and bid/ask spread ≤ 10c to find tradeable markets quickly.

### 2026-04-04 — Third Cycle

**Portfolio status:** $19.58 cash, $10.42 deployed across 2 positions. Total bankroll $30.00.

**Position review:**
- **Bondi Apr 5 (KXBONDIOUT-26APR-APR05):** YES @ 82c × 10. Market still at 81-83c despite confirmed firing Apr 2. Closes tonight. Expected settlement: YES → +$1.80. HOLD.
- **Chavez-DeRemer May 1 (KXDEREMEROUT-26-MAY01):** YES @ 44c × 5. Market at 42-44c, roughly flat. WaPo Apr 3 confirms "vulnerable." IG investigation, aides forced out, Trump "pondering" changes. Estimate 55-60%. HOLD.

**Bondi market still hasn't settled despite early-close condition.** The Apr 5 market has an early_close_condition ("closes early if individual leaves role") and settlement_timer of 1800s, yet it's been 2 days since the firing. Kalshi settlement mechanics may be manual/delayed. Also: the longer-dated Bondi markets (Apr 9: 85-86c, Apr 16: 85-86c, May 1: 93-94c) all show similar discounts. This looks like systematic settlement lag, not genuine uncertainty.

**Cabinet departure pricing update:**
- Lutnick Commerce (16-17c): Vulnerable per WaPo, fallen out of favor with Susie Wiles. Epstein connection + COI. My estimate 20-25%. Edge ~5-8pp — PASS (below threshold).
- Kash Patel FBI (36-39c): "Active discussions" per Atlantic, multiple scandals, class action from fired agents. UP from 26.5% last cycle. My estimate 35-45%. Market roughly efficient now — PASS.
- Gabbard DNI (17-18c): Less concrete evidence. PASS.

**Key news this cycle:**
- Trump imposed 100% tariff on patented pharma products (120-180 day phase-in)
- 50% tariff on steel/aluminum/copper articles
- Supreme Court previously struck down IEEPA tariffs (Feb 2026), currently 10% blanket tariff in effect
- No pharma or CPI/inflation markets found on Kalshi to trade this angle

**No new trades this cycle.** Market scan yielded 26 markets but none with >10pp edge. The cabinet departure cluster remains the most interesting theme but prices have adjusted since Bondi's firing. Waiting for Bondi settlement and monitoring DeRemer/Lutnick news.
