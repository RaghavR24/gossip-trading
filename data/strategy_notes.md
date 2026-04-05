# Strategy Notes

Agent-maintained file. Keep under 80 lines — prune stale observations, keep only lessons that generalize.

## Tool & API Lessons

- Always run Python tools with `PYTHONPATH=.` prefix.
- Prod API only — demo data is stale/fake.
- Orderbook fields are `yes_dollars` and `no_dollars`, each entry is [price_str, quantity_str].
- `search "topic"` now covers both events AND series (gas, CPI, weather, temperature).
- `quick --limit N` shows top N from the full universe — use `--sort volume` or `--sort recent` to explore different slices.
- Most Kalshi markets outside top 10-15 by volume have zero liquidity. Active categories: Politics, some Entertainment, CPI, gas prices.
- Sports markets are efficiently priced — skip them.
- Series-based markets (weather, gas, CPI) need keyword search to find. Series tickers: KXAAAGASW (gas), KXCPIYOY (CPI YoY), KXHIGHTDAL/KXHIGHTNYC (temperature).
- CPI markets: only the nearest month has volume. Reference BLS one-decimal-place 12-month YoY.
- Gas price markets: use AAA daily price. Source: gasprices.aaa.com. Use weekly avg daily change for drift, not single-day change.
- Weather markets: reference NWS Climatological Report. When a weather market crashes intraday, locals likely have real-time obs — don't fade it.

## Trading Lessons

- **Settlement lag is real edge.** Markets can stay open days after events resolve. Check if events already happened before looking at price.
- **Settlement rules are literal.** "Fired" ≠ "departed" if rules require actual vacancy. "Announcements of intent" don't count. Always read rules before trading.
- **Don't extrapolate trends on short horizons.** Gas price deceleration was real — market priced it correctly. A single slow day was signal, not noise. Don't fade momentum shifts in commodity markets on 2-day horizons.
- **Correlated positions = single thesis.** Bondi Apr 5/9/16/May 1 are all the same bet. Don't stack across expiries just because they're different contracts.
- **When revising PASS to TRADE, document what changed.** New evidence, not just another look.
- **Bondi "45-day transition" language** created persistent discount on a resolved event. Rules say "removal" counts — language ambiguity = opportunity.
- **Cabinet departure cluster** is the richest theme when active. Pattern: sequential firings create correlated binary events with staggered expiries.

## Market Regime (update each cycle)

- Iran war week 6+. US/Israel strikes ongoing. Trump gave Apr 6 ultimatum on Strait of Hormuz. Zero tradeable Kalshi markets on Iran.
- Tariffs: 100% pharma (120-180 day phase-in), 50% steel/aluminum/copper (Apr 6). SCOTUS struck down IEEPA tariffs Feb 2026, 10% blanket in effect.
- Cabinet shakeup: Bondi fired Apr 2, DeRemer vulnerable (IG probe), Lutnick falling out of favor. Zeldin frontrunner for AG.
- Kalshi coverage gaps: no Iran, tariff, inflation, or oil markets. Platform dominated by US politics + entertainment.

## Open Position Context

- **KXBONDIOUT-APR09 YES @ 80c x 5**: Bondi confirmed fired Apr 2. Todd Blanche acting AG. Near-arbitrage on settlement lag.
- **KXDEREMEROUT-26-MAY01 YES @ 44c x 2**: IG probe, husband banned from DOL, aides forced out. Soft evidence. Trump says "avoid massive shake-up" — key risk.
