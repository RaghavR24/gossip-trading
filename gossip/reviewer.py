"""
Cycle reviewer — automated trace analysis for the trading agent.

Parses agent_live.jsonl after each cycle, extracts structured events,
checks process compliance, and spawns a Claude review for qualitative analysis.

Usage:
    python3 gossip/reviewer.py                     # review latest cycle
    python3 gossip/reviewer.py --trace path.jsonl   # review specific trace
    python3 gossip/reviewer.py --last 3             # review last 3 cycles
    python3 gossip/reviewer.py --no-llm             # just process checks, skip Claude review
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

PROJECT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_DIR / "data"
TRACE_FILE = DATA_DIR / "agent_live.jsonl"
REVIEWS_DIR = DATA_DIR / "reviews"


@dataclass
class ToolCall:
    name: str
    input: dict
    output: str = ""
    index: int = 0


@dataclass
class CycleTrace:
    session_id: str = ""
    model: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    thinking_blocks: list[str] = field(default_factory=list)
    text_blocks: list[str] = field(default_factory=list)
    duration_s: float = 0
    final_result: str = ""


def parse_trace(path: Path) -> CycleTrace:
    """Parse agent_live.jsonl into structured CycleTrace."""
    trace = CycleTrace()
    pending_tools: dict[str, ToolCall] = {}
    call_index = 0

    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue

            msg_type = msg.get("type")

            if msg_type == "system" and msg.get("subtype") == "init":
                trace.session_id = msg.get("session_id", "")
                trace.model = msg.get("model", "")

            elif msg_type == "assistant":
                content = msg.get("message", {}).get("content", [])
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") == "thinking":
                        text = block.get("thinking", "")
                        if text:
                            trace.thinking_blocks.append(text)
                    elif block.get("type") == "tool_use":
                        tc = ToolCall(
                            name=block.get("name", ""),
                            input=block.get("input", {}),
                            index=call_index,
                        )
                        pending_tools[block["id"]] = tc
                        trace.tool_calls.append(tc)
                        call_index += 1
                    elif block.get("type") == "text":
                        text = block.get("text", "")
                        if text.strip():
                            trace.text_blocks.append(text)

            elif msg_type == "user":
                content = msg.get("message", {}).get("content", [])
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") == "tool_result":
                        tool_id = block.get("tool_use_id", "")
                        if tool_id in pending_tools:
                            output = block.get("content", "")
                            if isinstance(output, str):
                                pending_tools[tool_id].output = output[:2000]

            elif msg_type == "result":
                trace.final_result = msg.get("result", "")

    return trace


# --- Process compliance checks ---

@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""


def check_read_soul(trace: CycleTrace) -> CheckResult:
    for tc in trace.tool_calls:
        if tc.name == "Read" and "SOUL.md" in tc.input.get("file_path", ""):
            return CheckResult("read_soul", True, "Read SOUL.md")
    return CheckResult("read_soul", False, "Did not read SOUL.md")


def check_read_strategy_notes(trace: CycleTrace) -> CheckResult:
    for tc in trace.tool_calls:
        if tc.name == "Read" and "strategy_notes" in tc.input.get("file_path", ""):
            return CheckResult("read_strategy_notes", True)
    return CheckResult("read_strategy_notes", False, "Did not read strategy_notes.md")


def check_portfolio(trace: CycleTrace) -> CheckResult:
    for tc in trace.tool_calls:
        if tc.name == "Bash" and "portfolio" in tc.input.get("command", ""):
            return CheckResult("check_portfolio", True)
    return CheckResult("check_portfolio", False, "Did not check portfolio")


def check_settlements(trace: CycleTrace) -> CheckResult:
    for tc in trace.tool_calls:
        if tc.name == "Bash" and "check-settled" in tc.input.get("command", ""):
            return CheckResult("check_settlements", True)
    return CheckResult("check_settlements", False, "Did not run check-settled")


def check_market_scan(trace: CycleTrace) -> CheckResult:
    scan_calls = [tc for tc in trace.tool_calls
                  if tc.name == "Bash" and "kalshi.py quick" in tc.input.get("command", "")]
    if scan_calls:
        return CheckResult("market_scan", True, f"{len(scan_calls)} scan(s)")
    search_calls = [tc for tc in trace.tool_calls
                    if tc.name == "Bash" and "kalshi.py search" in tc.input.get("command", "")]
    if search_calls:
        return CheckResult("market_scan", True, f"{len(search_calls)} search(es) (no broad scan)")
    return CheckResult("market_scan", False, "No market scanning at all")


def check_news_usage(trace: CycleTrace) -> CheckResult:
    news_calls = [tc for tc in trace.tool_calls
                  if tc.name == "Bash" and "news.py" in tc.input.get("command", "")]
    web_searches = [tc for tc in trace.tool_calls if tc.name == "WebSearch"]
    sources = set()
    for tc in news_calls:
        cmd = tc.input.get("command", "")
        for src in ("twitter", "truthsocial", "reddit", "google", "article"):
            if src in cmd:
                sources.add(src)
    if news_calls:
        return CheckResult("news_usage", True,
                           f"{len(news_calls)} news.py call(s) [{', '.join(sources)}], {len(web_searches)} web search(es)")
    if web_searches:
        return CheckResult("news_usage", False,
                           f"Only WebSearch ({len(web_searches)}x) — no Apify sources (twitter, truthsocial, reddit)")
    return CheckResult("news_usage", False, "No news research at all")


def check_settlement_rules(trace: CycleTrace) -> CheckResult:
    """Check if rules were read before any trade."""
    rules_calls = []
    trade_calls = []
    for tc in trace.tool_calls:
        cmd = tc.input.get("command", "")
        if tc.name == "Bash" and "kalshi.py rules" in cmd:
            rules_calls.append(tc)
        if tc.name == "Bash" and "trader.py trade" in cmd:
            trade_calls.append(tc)

    if not trade_calls:
        return CheckResult("settlement_rules", True, "No trades — N/A")
    if not rules_calls:
        return CheckResult("settlement_rules", False,
                           f"Traded {len(trade_calls)}x WITHOUT reading settlement rules")

    first_trade_idx = min(tc.index for tc in trade_calls)
    rules_before_trade = any(tc.index < first_trade_idx for tc in rules_calls)
    if rules_before_trade:
        return CheckResult("settlement_rules", True,
                           f"Read rules before trading ({len(rules_calls)} rules check(s))")
    return CheckResult("settlement_rules", False, "Read rules AFTER first trade — wrong order")


def check_updated_strategy_notes(trace: CycleTrace) -> CheckResult:
    for tc in trace.tool_calls:
        if tc.name == "Edit" and "strategy_notes" in tc.input.get("file_path", ""):
            return CheckResult("updated_strategy_notes", True)
        if tc.name == "Write" and "strategy_notes" in tc.input.get("file_path", ""):
            return CheckResult("updated_strategy_notes", True)
    return CheckResult("updated_strategy_notes", False, "Did not update strategy_notes.md")


def check_indecision(trace: CycleTrace) -> CheckResult:
    """Flag if agent spent >6 tool calls researching a single market without deciding."""
    ticker_calls: dict[str, int] = {}
    for tc in trace.tool_calls:
        cmd = tc.input.get("command", "")
        if tc.name == "Bash":
            for word in cmd.split():
                if word.startswith("KX") or word.startswith("kx"):
                    ticker_calls[word] = ticker_calls.get(word, 0) + 1

    worst = max(ticker_calls.items(), key=lambda x: x[1]) if ticker_calls else None
    if worst and worst[1] > 6:
        return CheckResult("indecision", False,
                           f"Spent {worst[1]} tool calls on {worst[0]} — possible indecision loop")
    return CheckResult("indecision", True)


def check_position_review(trace: CycleTrace) -> CheckResult:
    """If portfolio shows open positions, did agent research them?"""
    portfolio_output = ""
    for tc in trace.tool_calls:
        if tc.name == "Bash" and "portfolio" in tc.input.get("command", ""):
            portfolio_output = tc.output
            break

    if not portfolio_output or "open_positions" not in portfolio_output:
        return CheckResult("position_review", True, "No open positions")

    try:
        data = json.loads(portfolio_output)
        positions = data.get("open_positions", [])
        if not positions:
            return CheckResult("position_review", True, "No open positions")
    except (json.JSONDecodeError, AttributeError):
        if '"open_positions": []' in portfolio_output:
            return CheckResult("position_review", True, "No open positions")
        return CheckResult("position_review", True, "Could not parse portfolio output")

    prices_checked = any(
        tc.name == "Bash" and "trader.py prices" in tc.input.get("command", "")
        for tc in trace.tool_calls
    )
    if prices_checked:
        return CheckResult("position_review", True, "Checked prices on open positions")
    return CheckResult("position_review", False, "Has open positions but didn't check prices")


ALL_CHECKS = [
    check_read_soul,
    check_read_strategy_notes,
    check_portfolio,
    check_settlements,
    check_market_scan,
    check_news_usage,
    check_settlement_rules,
    check_updated_strategy_notes,
    check_indecision,
    check_position_review,
]


def run_checks(trace: CycleTrace) -> list[CheckResult]:
    return [check(trace) for check in ALL_CHECKS]


# --- Trace summary for LLM review ---

def summarize_trace(trace: CycleTrace) -> str:
    """Create a condensed trace summary for LLM review."""
    lines = []
    lines.append(f"SESSION: {trace.session_id}")
    lines.append(f"MODEL: {trace.model}")
    lines.append(f"TOOL CALLS: {len(trace.tool_calls)}")
    lines.append(f"THINKING BLOCKS: {len(trace.thinking_blocks)}")
    lines.append("")

    lines.append("=== TOOL CALL SEQUENCE ===")
    for tc in trace.tool_calls:
        if tc.name == "Bash":
            cmd = tc.input.get("command", "")[:200]
            output_preview = tc.output[:300] if tc.output else "(no output captured)"
            lines.append(f"[{tc.index}] Bash: {cmd}")
            lines.append(f"    → {output_preview}")
        elif tc.name == "Read":
            path = tc.input.get("file_path", "")
            lines.append(f"[{tc.index}] Read: {path}")
        elif tc.name == "Edit":
            path = tc.input.get("file_path", "")
            lines.append(f"[{tc.index}] Edit: {path}")
        elif tc.name == "WebSearch":
            query = tc.input.get("query", "")
            lines.append(f"[{tc.index}] WebSearch: {query}")
            if tc.output:
                lines.append(f"    → {tc.output[:300]}")
        elif tc.name == "Write":
            path = tc.input.get("file_path", "")
            lines.append(f"[{tc.index}] Write: {path}")
        else:
            lines.append(f"[{tc.index}] {tc.name}: {json.dumps(tc.input)[:150]}")

    lines.append("")
    lines.append("=== AGENT TEXT OUTPUT (decisions/reasoning) ===")
    for i, text in enumerate(trace.text_blocks):
        lines.append(f"--- text block {i} ---")
        lines.append(text[:1000])

    lines.append("")
    lines.append("=== KEY THINKING EXCERPTS ===")
    for i, thinking in enumerate(trace.thinking_blocks[:10]):
        lines.append(f"--- thinking {i} ---")
        lines.append(thinking[:500])

    if trace.final_result:
        lines.append("")
        lines.append("=== FINAL RESULT ===")
        lines.append(trace.final_result[:1000])

    return "\n".join(lines)


# --- LLM review ---

REVIEWER_NOTES = DATA_DIR / "reviewer_notes.md"

REVIEW_PROMPT = """You are reviewing a trading agent's cycle trace. Your job is to identify process problems and propose harness improvements.

The agent operates on Kalshi prediction markets. Each cycle it follows CYCLE_PROMPT: read SOUL.md + strategy_notes.md, check portfolio, scan markets, research, trade if edge found.

## IMPORTANT: Review Constraints

What you CAN critique (process/efficiency):
- Tool call waste (redundant calls, rate limits, retries)
- Skipped mandatory steps (settlement rules before trading, portfolio check, strategy notes update)
- Research depth (shallow analysis, not using available sources)
- Indecision loops (too many calls on one market)
- Tool errors the agent didn't recover from

What you CANNOT critique (trading judgment):
- PASSES are correct by default. The agent is trained to pass unless edge is clear. Do NOT flag a pass as "missed opportunity" unless you have hard evidence (not speculation) that the agent overlooked.
- Settlement caution is ALWAYS correct. If the agent was cautious about settlement criteria, that is learned behavior from past costly mistakes. Never second-guess it.
- Position sizing decisions. The agent uses half-Kelly with risk limits. Don't suggest "should have sized up."
- Do NOT flag mandatory steps as waste. The agent MUST check: SOUL.md, strategy_notes.md, user_rationales.json, portfolio, check-settled. These are required every cycle.

## Agent's Learned Lessons (strategy_notes.md)
{strategy_notes}

## Reviewer Memory (your own past learnings)
{reviewer_notes}

## Recent Past Reviews (don't repeat these observations)
{past_reviews}

## Process Compliance Results
{checks}

## Condensed Trace
{trace_summary}

## Your Review

1. **GOOD** — What did the agent do well? (2-3 bullets)
2. **BAD** — Process mistakes or inefficiencies only. (2-3 bullets, or "None" if clean)
3. **MISSED** — Only if you have HARD evidence from the trace data that the agent overlooked something concrete. Not "could have explored X." Say "None" if nothing clear.
4. **HARNESS PROPOSAL** — The single highest-leverage change to prompt, tool output, or tool code that would fix a recurring problem. Be specific: name the file, describe the change, explain why.
   - Overfitting check: "If this exact market disappeared, would this change still help?"
   - Fix the harness, not the agent.
   - If no clear proposal, say "None — clean cycle."
5. **REVIEWER UPDATE** — One line to add to reviewer_notes.md if you learned something new about this agent's behavior patterns. Say "None" if nothing new.

Keep it concise. The audience is an engineer who reads traces daily."""


def _read_file_safe(path: Path, max_chars: int = 3000) -> str:
    try:
        text = path.read_text()
        return text[:max_chars] if len(text) > max_chars else text
    except FileNotFoundError:
        return "(not yet created)"


def _get_past_reviews(n: int = 3) -> str:
    """Read the last N review summaries to avoid repeating observations."""
    if not REVIEWS_DIR.exists():
        return "(no past reviews)"
    reviews = sorted(REVIEWS_DIR.glob("review_*.md"), reverse=True)
    if not reviews:
        return "(no past reviews)"
    parts = []
    for path in reviews[:n]:
        text = _read_file_safe(path, max_chars=1500)
        parts.append(f"--- {path.name} ---\n{text}")
    return "\n\n".join(parts)


def run_llm_review(trace: CycleTrace, checks: list[CheckResult]) -> str:
    """Spawn Claude to review the cycle trace. Auto-gathers context."""
    checks_text = "\n".join(
        f"{'✓' if c.passed else '✗'} {c.name}: {c.detail}" for c in checks
    )
    trace_summary = summarize_trace(trace)

    strategy_notes = _read_file_safe(DATA_DIR / "strategy_notes.md")
    reviewer_notes = _read_file_safe(REVIEWER_NOTES)
    past_reviews = _get_past_reviews(3)

    prompt = REVIEW_PROMPT.format(
        checks=checks_text,
        trace_summary=trace_summary,
        strategy_notes=strategy_notes,
        reviewer_notes=reviewer_notes,
        past_reviews=past_reviews,
    )

    if len(prompt) > 80000:
        prompt = prompt[:80000] + "\n\n[TRUNCATED]"

    cmd = [
        "claude",
        "--print", "-",
        "--output-format", "text",
        "--max-turns", "1",
    ]

    env = {k: v for k, v in os.environ.items() if k not in {
        "CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT",
    }}

    try:
        result = subprocess.run(
            cmd, input=prompt, capture_output=True, text=True,
            env=env, cwd=str(PROJECT_DIR), timeout=120,
        )
        review_text = result.stdout.strip()
    except Exception as e:
        return f"LLM review failed: {e}"

    _update_reviewer_notes(review_text)
    return review_text


def _update_reviewer_notes(review_text: str) -> None:
    """Extract REVIEWER UPDATE from the review and append to reviewer_notes.md."""
    marker = "REVIEWER UPDATE"
    idx = review_text.find(marker)
    if idx == -1:
        return

    update_line = review_text[idx + len(marker):].strip().lstrip("—:- ").split("\n")[0].strip()
    if not update_line or update_line.lower() == "none":
        return

    existing = _read_file_safe(REVIEWER_NOTES, max_chars=10000)
    if existing == "(not yet created)":
        existing = "# Reviewer Notes\n\nLearnings accumulated across cycle reviews. Read before each review.\n"

    if update_line in existing:
        return

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    REVIEWER_NOTES.write_text(f"{existing.rstrip()}\n- [{ts}] {update_line}\n")


def save_review(review_text: str, checks: list[CheckResult], trace: CycleTrace) -> Path:
    """Save review to data/reviews/ with timestamp."""
    REVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = REVIEWS_DIR / f"review_{ts}.md"

    lines = [f"# Cycle Review — {ts}"]
    lines.append(f"\nSession: {trace.session_id}")
    lines.append(f"Tool calls: {len(trace.tool_calls)}")
    lines.append("")

    lines.append("## Process Checks")
    passed = sum(1 for c in checks if c.passed)
    lines.append(f"{passed}/{len(checks)} passed\n")
    for c in checks:
        lines.append(f"{'✓' if c.passed else '✗'} **{c.name}**: {c.detail}")

    if review_text:
        lines.append("\n## LLM Review")
        lines.append(review_text)

    path.write_text("\n".join(lines))
    return path


def main():
    parser = argparse.ArgumentParser(description="Review agent cycle traces")
    parser.add_argument("--trace", type=str, default=None, help="Path to trace JSONL")
    parser.add_argument("--no-llm", action="store_true", help="Skip LLM review, just run process checks")
    parser.add_argument("--summary", action="store_true", help="Print condensed trace summary")

    args = parser.parse_args()

    trace_path = Path(args.trace) if args.trace else TRACE_FILE
    if not trace_path.exists():
        print(f"No trace file at {trace_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Parsing trace: {trace_path}", file=sys.stderr)
    trace = parse_trace(trace_path)
    print(f"  Session: {trace.session_id}", file=sys.stderr)
    print(f"  Tool calls: {len(trace.tool_calls)}", file=sys.stderr)
    print(f"  Thinking blocks: {len(trace.thinking_blocks)}", file=sys.stderr)
    print(f"  Text blocks: {len(trace.text_blocks)}", file=sys.stderr)

    if args.summary:
        print(summarize_trace(trace))
        return

    # Run process checks
    checks = run_checks(trace)
    passed = sum(1 for c in checks if c.passed)
    print(f"\nProcess checks: {passed}/{len(checks)}", file=sys.stderr)
    for c in checks:
        icon = "✓" if c.passed else "✗"
        print(f"  {icon} {c.name}: {c.detail}", file=sys.stderr)

    review_text = ""
    if not args.no_llm:
        print("\nRunning LLM review...", file=sys.stderr)
        review_text = run_llm_review(trace, checks)

    # Save
    path = save_review(review_text, checks, trace)
    print(f"\nReview saved: {path}", file=sys.stderr)

    # Print full review to stdout
    output = {
        "session_id": trace.session_id,
        "tool_calls": len(trace.tool_calls),
        "checks": {c.name: {"passed": c.passed, "detail": c.detail} for c in checks},
        "checks_passed": f"{passed}/{len(checks)}",
        "review": review_text,
        "review_file": str(path),
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
