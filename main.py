"""
Gossip Trading — agent orchestrator.

Spawns Claude Code as a subprocess. The agent reads SOUL.md for personality,
uses tools directly (web search, Apify, Kalshi API), and persists state to SQLite.

Usage:
    python3 main.py                         # single research + trade cycle
    python3 main.py --loop                  # continuous loop
    python3 main.py --loop --interval 300   # 5 min interval
    python3 main.py --rationale "I think tariffs will escalate next week"
    python3 main.py --prompt "check my positions and update strategy notes"
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

PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR = PROJECT_DIR / "data"
SESSION_FILE = DATA_DIR / "session_id.txt"

# The agent prompt: agentic, not scripted. Agent uses its own tools.
CYCLE_PROMPT = """Read SOUL.md for your identity and strategy principles.
Read data/strategy_notes.md for lessons from past sessions.
Check data/user_rationales.json for any pending user theses to research.

Then run a full trading cycle:

1. HOUSEKEEPING:
   `PYTHONPATH=. python3 gossip/trader.py check-settled` — auto-settle any resolved markets.
   `PYTHONPATH=. python3 gossip/trader.py portfolio` — check bankroll and open positions.
   If you have open positions, also run:
   `PYTHONPATH=. python3 gossip/trader.py prices` — current prices + unrealized P&L.
   For each open position: verify thesis still holds (web search the event, not just the price). EXIT if thesis is dead, HOLD if edge remains, consider SELL if price moved 15c+ toward your target.
   `PYTHONPATH=. python3 gossip/trader.py exit TICKER --reasoning "..."`

2. MARKET DISCOVERY — you have several tools, use whichever combination fits:
   Scanning:
   - `PYTHONPATH=. python3 gossip/kalshi.py quick --limit 40` — broad overview (default: mixed sort). Note: output shows top N of thousands — use --limit, --sort, --exclude, --categories, or search to explore further.
   - `PYTHONPATH=. python3 gossip/kalshi.py quick --sort volume --limit 30` — most liquid markets
   - `PYTHONPATH=. python3 gossip/kalshi.py quick --sort recent --limit 30` — newest/soonest-closing markets (often mispriced)
   - Filter by category: `--categories Politics,Economics` (include only) or `--exclude Sports,Entertainment` (skip these)
   - Available categories: Sports, Crypto, Financials, Entertainment, Economics, Climate and Weather, Mentions, Science and Technology, Politics, Elections, Companies, World
   Searching:
   - `PYTHONPATH=. python3 gossip/kalshi.py search "topic"` — search all open events + series by keyword
   News & social intelligence (via Apify — these give you data WebSearch can't):
   - `PYTHONPATH=. python3 gossip/news.py --source twitter --keywords "topic"` — real tweets with like/retweet counts, sorted by engagement. See what insiders and journalists are actually saying, not just what Google indexes.
   - `PYTHONPATH=. python3 gossip/news.py --source truthsocial` — Trump's Truth Social posts. Direct signal for executive action, tariff, and cabinet markets.
   - `PYTHONPATH=. python3 gossip/news.py --source reddit` — hot posts from r/wallstreetbets, r/politics, r/news, r/economics. Retail sentiment and breaking stories.
   - `PYTHONPATH=. python3 gossip/news.py --source google --keywords "topic"` — Google News results with URLs for deeper reading.
   - `PYTHONPATH=. python3 gossip/news.py --source article --urls "url1,url2"` — extract full article text (3000 chars) from URLs you found.
   - Web search (your built-in tool) — fast for general queries, but gives you snippets only.
   When to use what:
   - WebSearch: quick fact-checking, general background. Fast but shallow.
   - Twitter via news.py: engagement signals, leak chatter, journalist scoops. The delta over WebSearch is seeing WHO is saying it and how many people are amplifying it.
   - Truth Social: Trump posts move markets directly. Check before any executive action / tariff / cabinet market.
   - Reddit: retail sentiment gauge, sometimes surfaces stories before mainstream media.
   - Article extraction: when a web search snippet is ambiguous — get the full 3000 chars to confirm.
   Common patterns that work well:
   - Check Truth Social + Twitter first for political markets, then search Kalshi for related markets
   - Use `quick --sort recent` to spot new markets before they're efficiently priced
   - When you already know a topic is hot, go straight to `search` instead of scanning
   - Skip sports, entertainment, and markets with spread > 15c

3. RESEARCH — pick 3-5 promising markets:
   - Use web search for general background, then news.py for the unique signals:
     Twitter engagement levels tell you if a story has real momentum or is noise.
     Truth Social posts are leading indicators for executive actions.
     Full article text (via --source article) resolves ambiguous snippets.
   - Estimate the true probability based on evidence
   - When a market has related contracts (e.g. different timeframes or outcomes), compare them — pick the one where your edge is best supported by the evidence you actually have

4. BEFORE TRADING — read settlement rules and verify:
   `PYTHONPATH=. python3 gossip/kalshi.py rules TICKER`
   This is non-negotiable. Kalshi rules define exactly what triggers settlement — it's often stricter than you'd assume.
   Common traps:
   - "Must have actual departure date" — being fired/announced isn't enough, they must vacate the role
   - "Announcements of intent to depart are not sufficient" — the event must actually happen
   - "Sources from [specific list]" — only certain outlets count for resolution
   - Time windows: "before May 1" means the event must occur in that window, not just be announced
   If you can't explain how the rules map to your evidence, you don't have a trade.

5. TRADE if you find edge > 10pp with clear reasoning:
   Before executing, answer: "Evidence: [hard/soft/speculation]. Weakest assumption: [X]. Settlement criteria met: [yes/pending/no]."
   If settlement criteria are not yet met, discount your estimate accordingly.
   If the evidence is speculation, PASS unless edge is overwhelming (>25pp).
   If you can't name what would make you wrong, PASS.
   `PYTHONPATH=. python3 gossip/trader.py trade TICKER --side yes/no --estimate 0.XX --confidence high/medium --reasoning "..."`

6. Update data/strategy_notes.md with what you learned this cycle. Keep it under 80 lines — prune stale price observations and resolved-market notes. Only keep lessons that generalize to future trades.

EXECUTION DISCIPLINE:
- FAST PATH: If you find near-arbitrage, breaking news to buy on, OR breaking news that invalidates an open position — act immediately. Don't finish the full scan before exiting a position that's about to collapse.
- Be decisive. Research → conclude → act. Don't loop endlessly.
- For each market: reach a YES/NO/PASS decision within 2-3 tool calls.
- Evaluate 3-5 markets per cycle, trade the best 1-2. Don't try to cover everything.
- If you can't find edge after 5 minutes on a market, pass and move on.
- Write your conclusion even when you pass — future cycles benefit from it.
"""


def build_rationale_prompt(rationale: str) -> str:
    return f"""Read SOUL.md for your identity and strategy principles.

A user has submitted this thesis for you to research and potentially trade on:

USER THESIS: {rationale}

Your job:
1. Check portfolio: `PYTHONPATH=. python3 gossip/trader.py portfolio`
2. Research this thesis thoroughly using web search and news scraping.
3. Find evidence for AND against.
4. Search for relevant Kalshi markets: `PYTHONPATH=. python3 gossip/kalshi.py search "relevant keywords"`
5. If you find a market, READ THE SETTLEMENT RULES first: `PYTHONPATH=. python3 gossip/kalshi.py rules TICKER`
6. Estimate the probability. Before trading, answer: "Evidence: [hard/soft/speculation]. Settlement criteria met: [yes/pending/no]."
7. If you find edge based on this thesis, trade it. If the thesis doesn't hold up, explain why and pass.
8. Update data/user_rationales.json with your findings.
9. Update data/strategy_notes.md if you learned something new.
"""


LIVE_LOG = DATA_DIR / "agent_live.jsonl"
LIVE_STATUS = DATA_DIR / "agent_status.json"


def write_status(status: str, **extra) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LIVE_STATUS.write_text(json.dumps({"status": status, "timestamp": _now(), **extra}))


def run_agent(prompt: str, timeout: int = 600) -> dict:
    """Spawn Claude Code as a subprocess. Stream output to live log file."""
    cmd = [
        "claude",
        "--print", "-",
        "--output-format", "stream-json",
        "--verbose",
        "--max-turns", "80",
        "--dangerously-skip-permissions",
    ]

    env = {k: v for k, v in os.environ.items() if k not in {
        "CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT",
    }}
    env["PYTHONPATH"] = str(PROJECT_DIR)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    # Clear live log for this cycle
    LIVE_LOG.write_text("")
    write_status("running")

    start = time.time()
    session_id = None
    agent_output = ""

    try:
        proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, env=env, cwd=str(PROJECT_DIR),
        )
        # Send prompt and close stdin
        proc.stdin.write(prompt)
        proc.stdin.close()

        # Watchdog thread kills the process if timeout is exceeded
        import threading
        def _watchdog():
            deadline = start + timeout
            while proc.poll() is None:
                if time.time() > deadline:
                    proc.kill()
                    break
                time.sleep(5)
        wd = threading.Thread(target=_watchdog, daemon=True)
        wd.start()

        # Stream stdout line by line to live log
        with open(LIVE_LOG, "a") as logf:
            for line in proc.stdout:
                line = line.strip()
                if not line:
                    continue
                logf.write(line + "\n")
                logf.flush()

                try:
                    msg = json.loads(line)
                    if msg.get("type") == "system" and "session_id" in msg:
                        session_id = msg["session_id"]
                    if msg.get("type") == "result":
                        agent_output = msg.get("result", "")
                    if msg.get("type") == "assistant" and msg.get("message"):
                        for block in msg["message"].get("content", []):
                            if isinstance(block, dict) and block.get("type") == "text":
                                text = block.get("text", "")
                                agent_output += text + "\n"
                                write_status("running", last_text=text[:200])
                    if msg.get("type") == "assistant" and msg.get("message"):
                        for block in msg["message"].get("content", []):
                            if isinstance(block, dict) and block.get("type") == "tool_use":
                                tool = block.get("name", "")
                                write_status("running", tool=tool)
                except json.JSONDecodeError:
                    continue

        proc.wait()

        if proc.returncode == -9:
            write_status("timeout")
            return {"status": "timeout", "duration_s": timeout, "timestamp": _now()}

    except Exception as e:
        write_status("error", error=str(e))
        return {"status": "error", "duration_s": round(time.time() - start, 1), "timestamp": _now(), "error": str(e)}

    duration = round(time.time() - start, 1)

    cycle_result = {
        "timestamp": _now(),
        "status": "ok" if proc.returncode == 0 else "error",
        "duration_s": duration,
        "session_id": session_id,
        "output": agent_output[:2000] if agent_output else "",
    }

    write_status("idle", last_cycle=duration)

    # Log to DB
    try:
        from gossip.db import GossipDB
        db = GossipDB()
        db.log_cycle(
            session_id=session_id or "",
            duration_s=duration,
            status=cycle_result["status"],
            output_summary=agent_output[:1000] if agent_output else "",
        )
    except Exception:
        pass

    return cycle_result


def submit_rationale(thesis: str) -> None:
    """Add a user rationale to the queue."""
    rationale_file = DATA_DIR / "user_rationales.json"
    data = {"rationales": []}
    if rationale_file.exists():
        try:
            data = json.loads(rationale_file.read_text())
        except Exception:
            pass

    data["rationales"].append({
        "id": len(data["rationales"]) + 1,
        "timestamp": _now(),
        "thesis": thesis,
        "status": "pending",
        "agent_response": None,
    })
    rationale_file.write_text(json.dumps(data, indent=2))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser(description="Gossip Trading agent")
    parser.add_argument("--loop", action="store_true", help="Run continuously")
    parser.add_argument("--interval", type=int, default=None, help="Cycle interval in seconds")
    parser.add_argument("--prompt", type=str, default=None, help="Custom prompt")
    parser.add_argument("--rationale", type=str, default=None, help="Submit a trading thesis")
    parser.add_argument("--timeout", type=int, default=1200, help="Agent timeout per cycle (default 20min)")
    parser.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()
    interval = args.interval or int(os.getenv("CYCLE_INTERVAL", "900"))

    if args.rationale:
        submit_rationale(args.rationale)
        prompt = build_rationale_prompt(args.rationale)
    else:
        prompt = args.prompt or CYCLE_PROMPT

    if args.dry_run:
        print(prompt)
        return

    print(f"[Gossip Trading] Starting agent", file=sys.stderr)
    print(f"  Mode: {'loop (' + str(interval) + 's)' if args.loop else 'single cycle'}", file=sys.stderr)

    while True:
        ts = datetime.now(timezone.utc).strftime('%H:%M:%S')
        print(f"\n[{ts}] Starting cycle...", file=sys.stderr)

        result = run_agent(prompt, timeout=args.timeout)

        print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] Done: {result['status']} ({result['duration_s']}s)", file=sys.stderr)
        if result.get("output"):
            print(result["output"][:500], file=sys.stderr)

        if not args.loop:
            print(json.dumps(result, indent=2))
            break

        print(f"  Next cycle in {interval}s...", file=sys.stderr)
        time.sleep(interval)


if __name__ == "__main__":
    main()
