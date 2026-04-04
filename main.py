"""
Gossip Trading — autonomous agent loop.

Spawns Claude Code as a subprocess to reason about markets + news and trade.
All state lives in files (data/trades.json), not in conversation context.

Usage:
    python3 main.py                    # run one cycle
    python3 main.py --loop             # continuous loop (default 15min interval)
    python3 main.py --loop --interval 300   # 5 min interval
    python3 main.py --prompt "check positions"  # custom prompt
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

DATA_DIR = Path(__file__).resolve().parent / "data"
SESSION_FILE = DATA_DIR / "session_id.txt"
CYCLE_LOG = DATA_DIR / "cycle_log.json"

AGENT_PROMPT = """You are Gossip Trading, an autonomous prediction market agent. You research news and trade Kalshi prediction markets when you find mispriced opportunities.

YOUR TOOLS (run as shell commands from the gossip-trading directory):

Market Data:
  python3 gossip/kalshi.py scan                                    → list active markets (sorted by volume)
  python3 gossip/kalshi.py scan --categories "Economics,Politics"   → filtered scan
  python3 gossip/kalshi.py market TICKER                           → market details + orderbook
  python3 gossip/kalshi.py orderbook TICKER                        → full orderbook
  python3 gossip/kalshi.py search "bitcoin"                        → search events by keyword

News Intelligence:
  python3 gossip/news.py --keywords "bitcoin,tariff"               → Google News scrape
  python3 gossip/news.py --source twitter --keywords "crypto"      → Twitter/X scrape
  python3 gossip/news.py --trending                                → trending news scan
  python3 gossip/news.py --urls "url1,url2"                        → extract article text

Trading:
  python3 gossip/trader.py portfolio                               → current positions + P&L
  python3 gossip/trader.py trade TICKER --side yes --estimate 0.72 --confidence high --reasoning "..."
  python3 gossip/trader.py trade TICKER --side no --contracts 3 --estimate 0.30 --confidence medium --reasoning "..."
  python3 gossip/trader.py exit TICKER --reasoning "..."
  python3 gossip/trader.py settle TICKER --outcome yes
  python3 gossip/trader.py size TICKER --estimate 0.72             → dry-run sizing calc
  python3 gossip/trader.py history                                 → recent trades

YOUR JOB EACH CYCLE:

1. CHECK PORTFOLIO — Run `python3 gossip/trader.py portfolio` to see current state.

2. CHECK POSITIONS — For each open position:
   - Scrape latest news relevant to that market
   - Has the thesis changed? If invalidated, exit the position.
   - Has edge shrunk below 5pp? Consider taking profit.

3. SCAN MARKETS — Run `python3 gossip/kalshi.py scan` to see high-volume markets.

4. SCRAPE NEWS — Run `python3 gossip/news.py --keywords "..."` with keywords derived from
   the most interesting markets. Focus on markets where news could create edge.

5. ANALYZE — For each market where news seems relevant:
   - Think carefully about the base rate and what the news actually implies
   - Estimate the TRUE probability (not what the market says, what YOU think)
   - Compare to market price
   - Only trade if edge > 10 percentage points AND you can articulate WHY the market is wrong

6. TRADE — Use `python3 gossip/trader.py trade ...` with:
   - Your probability estimate (--estimate)
   - Your confidence level (--confidence high/medium/low)
   - Clear reasoning (--reasoning "...")
   - Kelly sizing is automatic if you omit --contracts

SELF-DISCOVERY:
- You decide what markets are interesting. The scan shows everything — YOU pick what to research.
- You decide what to search for. Pick keywords based on the markets you see, not hardcoded lists.
- You can scrape ANY news source, follow links, dig into articles for primary data.
- If you discover an opportunity type the system wasn't designed for, trade it anyway.
- Explore different market categories — crypto, politics, economics, weather, companies, world events.
- Look for non-obvious connections: a news event might affect a market in a different category.

RULES:
- Think like a quant. Be specific about probabilities. Don't round to convenient numbers.
- Only trade when you have a clear, articulable edge. "This seems underpriced" is NOT enough.
- Read primary sources when possible — actual articles, not just headlines.
- Consider the time to expiry. Markets closing in 2 days vs 30 days need different analysis.
- Don't trade on noise. If the news is ambiguous, pass.
- Log everything. Every decision should have reasoning.
- Risk guardrails: max 5 concurrent positions, max 30% bankroll per position. Within those bounds, size optimally.
"""

def load_session_id() -> str | None:
    if SESSION_FILE.exists():
        sid = SESSION_FILE.read_text().strip()
        return sid if sid else None
    return None

def save_session_id(sid: str) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SESSION_FILE.write_text(sid)

def log_cycle(result: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    entries = []
    if CYCLE_LOG.exists():
        try:
            entries = json.loads(CYCLE_LOG.read_text())
        except Exception:
            pass
    entries.append(result)
    # keep last 100 cycles
    CYCLE_LOG.write_text(json.dumps(entries[-100:], indent=2))


def run_agent_cycle(session_id: str | None, prompt: str, timeout: int = 600) -> dict:
    """Spawn Claude Code as a subprocess and capture output."""
    cmd = [
        "claude",
        "--print", "-",
        "--output-format", "stream-json",
        "--verbose",
        "--max-turns", "50",
    ]
    if session_id:
        cmd.extend(["--resume", session_id])

    # Strip Claude Code nesting guards (Paperclip pattern)
    env = {k: v for k, v in os.environ.items() if k not in {
        "CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT",
    }}

    start = time.time()
    try:
        result = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            cwd=str(Path(__file__).resolve().parent),
        )
    except subprocess.TimeoutExpired:
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "timeout",
            "duration_s": timeout,
            "session_id": session_id,
        }

    duration = round(time.time() - start, 1)
    new_session_id = session_id
    agent_output = ""

    # Parse stream-json for session_id and output
    for line in result.stdout.strip().split("\n"):
        if not line.strip():
            continue
        try:
            msg = json.loads(line)
            if msg.get("type") == "system" and "session_id" in msg:
                new_session_id = msg["session_id"]
            if msg.get("type") == "result":
                agent_output = msg.get("result", "")
            if msg.get("type") == "assistant" and msg.get("message"):
                content = msg["message"].get("content", [])
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        agent_output += block.get("text", "") + "\n"
        except json.JSONDecodeError:
            continue

    cycle_result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "ok" if result.returncode == 0 else "error",
        "duration_s": duration,
        "session_id": new_session_id,
        "output_preview": agent_output[:500] if agent_output else result.stderr[:500],
    }

    if new_session_id and new_session_id != session_id:
        save_session_id(new_session_id)

    return cycle_result


def main():
    parser = argparse.ArgumentParser(description="Gossip Trading agent loop")
    parser.add_argument("--loop", action="store_true", help="Run continuously")
    parser.add_argument("--interval", type=int, default=None, help="Cycle interval in seconds")
    parser.add_argument("--prompt", type=str, default=None, help="Custom prompt (overrides default)")
    parser.add_argument("--fresh", action="store_true", help="Start fresh session (ignore saved session)")
    parser.add_argument("--dry-run", action="store_true", help="Print prompt and exit")
    parser.add_argument("--timeout", type=int, default=600, help="Agent timeout per cycle in seconds")

    args = parser.parse_args()

    interval = args.interval or int(os.getenv("CYCLE_INTERVAL", "900"))
    prompt = args.prompt or AGENT_PROMPT

    if args.dry_run:
        print(prompt)
        return

    session_id = None if args.fresh else load_session_id()

    print(f"[Gossip Trading] Starting agent", file=sys.stderr)
    print(f"  Session: {'resuming ' + session_id[:12] + '...' if session_id else 'new'}", file=sys.stderr)
    print(f"  Mode: {'loop (' + str(interval) + 's)' if args.loop else 'single cycle'}", file=sys.stderr)
    print(f"  Demo: {os.getenv('KALSHI_USE_DEMO', 'false')}", file=sys.stderr)

    while True:
        cycle_start = datetime.now(timezone.utc)
        print(f"\n[{cycle_start.strftime('%H:%M:%S')}] Starting cycle...", file=sys.stderr)

        result = run_agent_cycle(session_id, prompt, timeout=args.timeout)
        session_id = result.get("session_id")
        log_cycle(result)

        print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] Cycle done: {result['status']} ({result['duration_s']}s)", file=sys.stderr)
        if result.get("output_preview"):
            print(f"  Output: {result['output_preview'][:200]}", file=sys.stderr)

        if not args.loop:
            print(json.dumps(result, indent=2))
            break

        print(f"  Sleeping {interval}s until next cycle...", file=sys.stderr)
        time.sleep(interval)


if __name__ == "__main__":
    main()
