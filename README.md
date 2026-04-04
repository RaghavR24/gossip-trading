# Gossip Trading

Autonomous prediction market trading agent for [Kalshi](https://kalshi.com). Built for the Entrepreneur First Hackathon.

The agent scrapes news, scans Kalshi markets, estimates probabilities using LLM reasoning, and paper trades when it finds mispriced markets. The "gossip" is the news — the agent listens to the world's gossip and trades before the crowd catches up.

## Architecture

**Claude Code IS the agent.** No API calls to Anthropic. We spawn the `claude` CLI as a subprocess (Paperclip pattern), which means zero LLM cost on a Claude Max subscription. The Python modules are CLI tools that Claude Code invokes.

```
┌─────────────────────────────────────────────────┐
│           CLAUDE CODE (the brain)                │
│  • Reads SOUL.md for personality/strategy        │
│  • Scans markets (gossip/kalshi.py)              │
│  • Scrapes news (gossip/news.py + web search)    │
│  • Reasons about probability (native LLM)        │
│  • Trades (gossip/trader.py)                     │
│  • Writes strategy_notes.md for memory           │
└─────────────────────────────────────────────────┘
         │              │               │
    ┌────▼────┐   ┌─────▼─────┐   ┌────▼────┐
    │ Kalshi  │   │   News    │   │ Trader  │
    │  API    │   │  (Apify)  │   │ (Paper) │
    └─────────┘   └───────────┘   └─────────┘
         │              │               │
         └──────────────┼───────────────┘
                   ┌────▼────┐
                   │ SQLite  │  ← data/gossip.db
                   └─────────┘
                        │
                   ┌────▼────┐
                   │ Next.js │  ← web/ (dashboard)
                   └─────────┘
```

## Quick Start

```bash
# 1. Install Python deps
pip install -r requirements.txt

# 2. Set up env
cp .env.example .env
# Fill in: KALSHI_API_KEY_ID, KALSHI_PRIVATE_KEY_PATH, APIFY_API_TOKEN

# 3. Run one agent cycle
python3 main.py

# 4. Run continuous loop (15 min default)
python3 main.py --loop

# 5. Submit a trading thesis
python3 main.py --rationale "I think tariffs on China will escalate"

# 6. Start the dashboard
cd web && npm install && npm run dev
# Open http://localhost:3000
```

## Project Structure

```
gossip-trading/
├── SOUL.md              ← Agent personality, strategy, risk rules
├── SPEC.md              ← Full technical spec
├── main.py              ← Agent orchestrator (spawns Claude Code subprocess)
├── requirements.txt
├── .env                 ← API keys (gitignored)
├── gossip/
│   ├── kalshi.py        ← Kalshi API client (scan, search, market, orderbook, auth)
│   ├── news.py          ← Apify news scraping (Google, Twitter, web, articles)
│   ├── trader.py        ← Paper/live trading, Kelly sizing, portfolio management
│   ├── db.py            ← SQLite persistence (trades, news, snapshots, agent logs)
│   └── dashboard.py     ← Streamlit dashboard (legacy, replaced by web/)
├── web/                 ← Next.js + Tailwind TypeScript dashboard
│   ├── src/app/
│   │   ├── page.tsx     ← Main dashboard (positions, live stream, news, agent log)
│   │   └── api/         ← REST endpoints reading from SQLite
│   └── src/lib/db.ts    ← SQLite connection for Next.js
├── data/
│   ├── gossip.db        ← SQLite database (source of truth)
│   ├── trades.json      ← Trade log (secondary, used by agent)
│   ├── strategy_notes.md ← Agent-maintained memory across sessions
│   └── user_rationales.json ← User-submitted theses queue
└── references/          ← (gitignored) cloned repos for reference
```

## How It Works

### Agent Loop (`main.py`)

1. Spawns `claude --print --dangerously-skip-permissions` as a subprocess
2. Pipes CYCLE_PROMPT: "Read SOUL.md, check portfolio, scan markets, research, trade"
3. Claude Code runs tools (Bash, WebSearch, WebFetch, Read, Write)
4. Agent uses Python CLI tools for market data and trading
5. Output streams to `data/agent_live.jsonl` for the dashboard
6. Cycle ends, results logged to SQLite

### Key Design Decisions

- **Fresh sessions each cycle** — no context bloat. State lives in files (SQLite + JSON + strategy_notes.md). Each cycle starts clean and reads its state.
- **SOUL.md** — persistent personality document every agent session reads. Ensures consistent strategy and risk discipline across sessions.
- **strategy_notes.md** — agent-maintained memory. Writes lessons learned, reads them next cycle.
- **User rationales** — users submit theses ("I think X"), agent researches and trades accordingly.
- **Orderbook pricing** — uses real orderbook (yes_dollars/no_dollars) not stale market summary.
- **Always prod API** — demo API has fake/stale data. We always read from prod.

### Dashboard (`web/`)

Next.js app that reads from SQLite. Features:
- Real-time portfolio metrics (bankroll, P&L, trades, win rate)
- Live agent stream (text, tool calls, tool results as they happen)
- Thesis input — submit a thesis for the agent to research
- Custom command input — send any instruction to the agent
- Loop interval control (1m/5m/10m/15m/30m)
- Open positions, trade history, news feed, agent log tabs

## Tech Stack

- **Python 3.11+** — agent tools, Kalshi API, Apify, trading logic
- **Claude Code CLI** — LLM brain (zero cost on Max subscription)
- **Apify** — news scraping (Google News, Twitter, web search, article extraction)
- **Kalshi REST API** — prediction market data and trading
- **SQLite** — persistence (WAL mode, zero config)
- **Next.js + Tailwind** — real-time dashboard
- **better-sqlite3** — SQLite from Node.js

## Configuration

### Environment Variables (.env)

| Variable | Required | Description |
|----------|----------|-------------|
| `KALSHI_API_KEY_ID` | Yes | Kalshi API key ID |
| `KALSHI_PRIVATE_KEY_PATH` | Yes | Path to RSA private key PEM |
| `APIFY_API_TOKEN` | Yes | Apify API token for news scraping |
| `BANKROLL` | No | Starting paper bankroll (default $30) |
| `MIN_EDGE` | No | Minimum edge to trade (default 10pp) |
| `MAX_POSITION_PCT` | No | Max bankroll per position (default 30%) |
| `CYCLE_INTERVAL` | No | Loop interval in seconds (default 900) |

### Risk Guardrails

These are circuit breakers the agent cannot override:
- Max 30% of bankroll on any single position
- Max 5 concurrent positions
- Minimum 10pp edge to enter
- Half-Kelly sizing (never full Kelly)
