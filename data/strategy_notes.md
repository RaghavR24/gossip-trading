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

(none yet — first cycle pending)
