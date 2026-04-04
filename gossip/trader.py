"""
Trading engine — paper + live execution, Kelly sizing, portfolio management.

CLI tool invoked by Claude Code agent:
    python3 gossip/trader.py portfolio
    python3 gossip/trader.py trade TICKER --side yes --contracts 3 --estimate 0.72 --confidence high --reasoning "..."
    python3 gossip/trader.py exit TICKER --reasoning "..."
    python3 gossip/trader.py settle TICKER --outcome yes
    python3 gossip/trader.py history
    python3 gossip/trader.py size TICKER --estimate 0.72  (dry-run: shows recommended size)

All output is JSON to stdout.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
TRADES_FILE = DATA_DIR / "trades.json"
PORTFOLIO_FILE = DATA_DIR / "portfolio.json"

def log(msg: str) -> None:
    print(msg, file=sys.stderr)

def get_db():
    from gossip.db import GossipDB
    return GossipDB()


# --- State management ---

@dataclass
class Trade:
    timestamp: str
    ticker: str
    title: str
    category: str
    side: str  # "yes" or "no"
    action: str  # "buy" or "sell"
    contracts: int
    entry_price: float
    cost: float
    fee: float
    estimated_prob: float
    edge: float
    confidence: str
    reasoning: str
    news_trigger: str = ""
    sources: list[str] = field(default_factory=list)
    settled: bool = False
    outcome: str = ""  # "win", "loss", ""
    pnl: float = 0.0
    exit_reasoning: str = ""

@dataclass
class Portfolio:
    bankroll: float = 30.0
    total_pnl: float = 0.0
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    trades: list[Trade] = field(default_factory=list)

    @property
    def open_positions(self) -> list[Trade]:
        return [t for t in self.trades if not t.settled and t.action == "buy"]

    @property
    def win_rate(self) -> float:
        if self.total_trades == 0:
            return 0.0
        return self.wins / self.total_trades

    @property
    def deployed_capital(self) -> float:
        return sum(t.cost + t.fee for t in self.open_positions)


def load_portfolio() -> Portfolio:
    if not TRADES_FILE.exists():
        return Portfolio(bankroll=float(os.getenv("BANKROLL", "30.0")))

    try:
        data = json.loads(TRADES_FILE.read_text())
        p = Portfolio()
        p.bankroll = data.get("bankroll", float(os.getenv("BANKROLL", "30.0")))
        p.total_pnl = data.get("total_pnl", 0.0)
        p.total_trades = data.get("total_trades", 0)
        p.wins = data.get("wins", 0)
        p.losses = data.get("losses", 0)
        for t in data.get("trades", []):
            p.trades.append(Trade(**t))
        return p
    except Exception as e:
        log(f"Error loading portfolio: {e}")
        return Portfolio(bankroll=float(os.getenv("BANKROLL", "30.0")))


def save_portfolio(p: Portfolio) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        "bankroll": round(p.bankroll, 2),
        "total_pnl": round(p.total_pnl, 2),
        "total_trades": p.total_trades,
        "wins": p.wins,
        "losses": p.losses,
        "trades": [asdict(t) for t in p.trades],
    }
    TRADES_FILE.write_text(json.dumps(data, indent=2))


# --- Sizing ---

def kalshi_fee(contracts: int, price: float) -> float:
    return math.ceil(0.07 * contracts * price * (1 - price)) / 100


def kelly_size(
    estimated_prob: float,
    market_price: float,
    bankroll: float,
    side: str = "yes",
    kelly_fraction: float = 0.5,
    max_position_pct: float = 0.30,
) -> dict:
    """Half-Kelly position sizing."""
    if side == "yes":
        p = estimated_prob
        price = market_price
    else:
        p = 1 - estimated_prob
        price = 1 - market_price

    if price <= 0 or price >= 1 or p <= price:
        return {"contracts": 0, "edge": 0, "reason": "no edge"}

    edge = p - price
    # Kelly: f* = (p * b - q) / b where b = (1-price)/price, q = 1-p
    b = (1 - price) / price
    q = 1 - p
    kelly_f = (p * b - q) / b
    adjusted_f = kelly_f * kelly_fraction

    max_bet = bankroll * max_position_pct
    bet_size = min(bankroll * adjusted_f, max_bet)

    contracts = max(1, int(bet_size / price))
    cost = contracts * price
    fee = kalshi_fee(contracts, price)

    if cost + fee > bankroll:
        contracts = max(1, int((bankroll - 0.01) / (price + kalshi_fee(1, price) / 1)))
        cost = contracts * price
        fee = kalshi_fee(contracts, price)

    return {
        "contracts": contracts,
        "edge": round(edge, 4),
        "kelly_f": round(kelly_f, 4),
        "adjusted_f": round(adjusted_f, 4),
        "bet_size": round(bet_size, 2),
        "cost": round(cost, 2),
        "fee": round(fee, 4),
        "total_cost": round(cost + fee, 2),
        "expected_value": round(contracts * edge, 2),
    }


# --- Risk checks ---

def check_risk(portfolio: Portfolio, ticker: str, cost: float) -> dict:
    """Run risk checks before a trade."""
    issues = []
    max_pos_pct = float(os.getenv("MAX_POSITION_PCT", "0.30"))
    min_edge = float(os.getenv("MIN_EDGE", "0.10"))

    if cost > portfolio.bankroll * max_pos_pct:
        issues.append(f"Position size ${cost:.2f} exceeds {max_pos_pct:.0%} of bankroll ${portfolio.bankroll:.2f}")

    if cost > portfolio.bankroll:
        issues.append(f"Insufficient bankroll: need ${cost:.2f}, have ${portfolio.bankroll:.2f}")

    if len(portfolio.open_positions) >= 5:
        issues.append(f"Max 5 concurrent positions reached ({len(portfolio.open_positions)} open)")

    existing = [t for t in portfolio.open_positions if t.ticker == ticker]
    if existing:
        issues.append(f"Already have open position on {ticker}")

    return {"ok": len(issues) == 0, "issues": issues}


# --- Trade execution ---

async def execute_trade(
    ticker: str,
    side: str,
    contracts: int,
    estimated_prob: float,
    confidence: str,
    reasoning: str,
    news_trigger: str = "",
    sources: list[str] | None = None,
) -> dict:
    from gossip.kalshi import get_market_detail, kalshi_fee as kfee

    detail = await get_market_detail(ticker)
    market = detail.get("market", {})
    if not market or "error" in detail:
        return {"error": f"Market {ticker} not found"}

    title = market.get("title", "?")
    category = market.get("category", "?")
    bid = float(market.get("yes_bid_dollars", "0") or "0")
    ask = float(market.get("yes_ask_dollars", "0") or "0")

    if side == "yes":
        entry_price = ask
        edge = estimated_prob - ask
    else:
        entry_price = 1.0 - bid
        edge = (1 - estimated_prob) - (1 - bid)

    cost = entry_price * contracts
    fee = kalshi_fee(contracts, entry_price)

    portfolio = load_portfolio()

    risk = check_risk(portfolio, ticker, cost + fee)
    if not risk["ok"]:
        return {"error": "Risk check failed", "issues": risk["issues"]}

    trade = Trade(
        timestamp=datetime.now(timezone.utc).isoformat(),
        ticker=ticker,
        title=title,
        category=category,
        side=side,
        action="buy",
        contracts=contracts,
        entry_price=round(entry_price, 4),
        cost=round(cost, 2),
        fee=round(fee, 4),
        estimated_prob=estimated_prob,
        edge=round(edge, 4),
        confidence=confidence,
        reasoning=reasoning,
        news_trigger=news_trigger,
        sources=sources or [],
    )

    portfolio.trades.append(trade)
    portfolio.bankroll = round(portfolio.bankroll - cost - fee, 2)
    portfolio.total_trades += 1
    save_portfolio(portfolio)

    try:
        db = get_db()
        db.insert_trade(
            ticker=ticker, title=title, category=category, side=side,
            contracts=contracts, entry_price=round(entry_price, 4),
            cost=round(cost, 2), fee=round(fee, 4),
            estimated_prob=estimated_prob, edge=round(edge, 4),
            confidence=confidence, reasoning=reasoning,
            news_trigger=news_trigger, sources=sources or [],
        )
    except Exception as e:
        log(f"DB write failed (trade still recorded in JSON): {e}")

    return {
        "status": "executed",
        "ticker": ticker,
        "side": side,
        "contracts": contracts,
        "entry_price": trade.entry_price,
        "cost": trade.cost,
        "fee": trade.fee,
        "edge": trade.edge,
        "bankroll_remaining": portfolio.bankroll,
        "title": title,
    }


async def exit_position(ticker: str, reasoning: str) -> dict:
    from gossip.kalshi import get_market_detail

    portfolio = load_portfolio()
    open_trade = None
    for t in reversed(portfolio.trades):
        if t.ticker == ticker and not t.settled:
            open_trade = t
            break

    if not open_trade:
        return {"error": f"No open position on {ticker}"}

    detail = await get_market_detail(ticker)
    market = detail.get("market", {})
    bid = float(market.get("yes_bid_dollars", "0") or "0")
    ask = float(market.get("yes_ask_dollars", "0") or "0")

    if open_trade.side == "yes":
        exit_price = bid
    else:
        exit_price = 1.0 - ask

    pnl = round((exit_price - open_trade.entry_price) * open_trade.contracts, 2)

    open_trade.settled = True
    open_trade.outcome = "win" if pnl > 0 else "loss"
    open_trade.pnl = pnl
    open_trade.exit_reasoning = reasoning

    portfolio.bankroll = round(portfolio.bankroll + (exit_price * open_trade.contracts), 2)
    portfolio.total_pnl = round(portfolio.total_pnl + pnl, 2)
    if pnl > 0:
        portfolio.wins += 1
    else:
        portfolio.losses += 1

    save_portfolio(portfolio)

    return {
        "status": "exited",
        "ticker": ticker,
        "pnl": pnl,
        "exit_price": exit_price,
        "bankroll": portfolio.bankroll,
    }


def settle_market(ticker: str, outcome_yes: bool) -> dict:
    portfolio = load_portfolio()

    for t in reversed(portfolio.trades):
        if t.ticker == ticker and not t.settled:
            t.settled = True
            won = (t.side == "yes" and outcome_yes) or (t.side == "no" and not outcome_yes)
            if won:
                t.outcome = "win"
                t.pnl = round((1.0 - t.entry_price) * t.contracts, 2)
                portfolio.wins += 1
            else:
                t.outcome = "loss"
                t.pnl = round(-t.entry_price * t.contracts, 2)
                portfolio.losses += 1

            portfolio.total_pnl = round(portfolio.total_pnl + t.pnl, 2)
            portfolio.bankroll = round(portfolio.bankroll + t.entry_price * t.contracts + t.pnl, 2)
            save_portfolio(portfolio)

            return {
                "status": "settled",
                "ticker": ticker,
                "outcome": "yes" if outcome_yes else "no",
                "result": t.outcome,
                "pnl": t.pnl,
                "bankroll": portfolio.bankroll,
            }

    return {"error": f"No open trade on {ticker}"}


# --- CLI ---

async def main():
    parser = argparse.ArgumentParser(description="Gossip Trading engine")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("portfolio", help="Show portfolio")

    trade_p = sub.add_parser("trade", help="Execute paper trade")
    trade_p.add_argument("ticker")
    trade_p.add_argument("--side", choices=["yes", "no"], required=True)
    trade_p.add_argument("--contracts", type=int, default=None)
    trade_p.add_argument("--estimate", type=float, required=True)
    trade_p.add_argument("--confidence", choices=["low", "medium", "high"], default="medium")
    trade_p.add_argument("--reasoning", type=str, required=True)
    trade_p.add_argument("--news", type=str, default="")
    trade_p.add_argument("--sources", type=str, default="")

    exit_p = sub.add_parser("exit", help="Exit position")
    exit_p.add_argument("ticker")
    exit_p.add_argument("--reasoning", type=str, required=True)

    settle_p = sub.add_parser("settle", help="Settle resolved market")
    settle_p.add_argument("ticker")
    settle_p.add_argument("--outcome", choices=["yes", "no"], required=True)

    size_p = sub.add_parser("size", help="Calculate position size (dry run)")
    size_p.add_argument("ticker")
    size_p.add_argument("--estimate", type=float, required=True)
    size_p.add_argument("--side", choices=["yes", "no"], default="yes")

    sub.add_parser("history", help="Trade history")

    args = parser.parse_args()

    if args.command == "portfolio":
        p = load_portfolio()
        result = {
            "bankroll": p.bankroll,
            "total_pnl": p.total_pnl,
            "total_trades": p.total_trades,
            "wins": p.wins,
            "losses": p.losses,
            "win_rate": round(p.win_rate, 3),
            "deployed_capital": round(p.deployed_capital, 2),
            "open_positions": [
                {
                    "ticker": t.ticker,
                    "title": t.title,
                    "side": t.side,
                    "contracts": t.contracts,
                    "entry_price": t.entry_price,
                    "edge": t.edge,
                    "confidence": t.confidence,
                    "reasoning": t.reasoning[:200],
                }
                for t in p.open_positions
            ],
        }
        print(json.dumps(result, indent=2))

    elif args.command == "trade":
        if args.contracts is None:
            from gossip.kalshi import get_market_detail
            detail = await get_market_detail(args.ticker)
            market = detail.get("market", {})
            bid = float(market.get("yes_bid_dollars", "0") or "0")
            ask = float(market.get("yes_ask_dollars", "0") or "0")
            market_price = ask if args.side == "yes" else (1 - bid)
            p = load_portfolio()
            sizing = kelly_size(args.estimate, market_price, p.bankroll, args.side)
            contracts = sizing["contracts"]
        else:
            contracts = args.contracts

        sources = [s.strip() for s in args.sources.split(",") if s.strip()] if args.sources else []
        result = await execute_trade(
            ticker=args.ticker,
            side=args.side,
            contracts=contracts,
            estimated_prob=args.estimate,
            confidence=args.confidence,
            reasoning=args.reasoning,
            news_trigger=args.news,
            sources=sources,
        )
        print(json.dumps(result, indent=2))

    elif args.command == "exit":
        result = await exit_position(args.ticker, args.reasoning)
        print(json.dumps(result, indent=2))

    elif args.command == "settle":
        result = settle_market(args.ticker, args.outcome == "yes")
        print(json.dumps(result, indent=2))

    elif args.command == "size":
        from gossip.kalshi import get_market_detail
        detail = await get_market_detail(args.ticker)
        market = detail.get("market", {})
        bid = float(market.get("yes_bid_dollars", "0") or "0")
        ask = float(market.get("yes_ask_dollars", "0") or "0")
        market_price = ask if args.side == "yes" else (1 - bid)
        p = load_portfolio()
        result = kelly_size(args.estimate, market_price, p.bankroll, args.side)
        result["ticker"] = args.ticker
        result["market_price"] = market_price
        result["estimated_prob"] = args.estimate
        result["bankroll"] = p.bankroll
        print(json.dumps(result, indent=2))

    elif args.command == "history":
        p = load_portfolio()
        trades = [asdict(t) for t in p.trades[-20:]]
        print(json.dumps(trades, indent=2))

    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())
