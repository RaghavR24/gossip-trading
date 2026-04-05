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
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

def log(msg: str) -> None:
    print(msg, file=sys.stderr)

def get_db():
    from gossip.db import GossipDB
    return GossipDB()


# --- State management (all state lives in SQLite) ---

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
    id: int | None = None

@dataclass
class Portfolio:
    bankroll: float = 15.0
    total_pnl: float = 0.0
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    open_positions: list[Trade] = field(default_factory=list)

    @property
    def win_rate(self) -> float:
        if self.total_trades == 0:
            return 0.0
        return self.wins / self.total_trades

    @property
    def deployed_capital(self) -> float:
        return sum(t.cost + t.fee for t in self.open_positions)


def load_portfolio() -> Portfolio:
    db = get_db()
    pdata = db.get_portfolio()
    p = Portfolio(
        bankroll=pdata["bankroll"],
        total_pnl=pdata["total_pnl"],
        total_trades=pdata["total_trades"],
        wins=pdata["wins"],
        losses=pdata["losses"],
    )
    for row in db.get_open_positions():
        sources = row.get("sources", "[]")
        if isinstance(sources, str):
            try:
                sources = json.loads(sources)
            except (json.JSONDecodeError, TypeError):
                sources = []
        p.open_positions.append(Trade(
            id=row["id"],
            timestamp=row["timestamp"],
            ticker=row["ticker"],
            title=row.get("title", ""),
            category=row.get("category", ""),
            side=row["side"],
            action=row.get("action", "buy"),
            contracts=row["contracts"],
            entry_price=row["entry_price"],
            cost=row["cost"],
            fee=row.get("fee", 0),
            estimated_prob=row.get("estimated_prob", 0),
            edge=row.get("edge", 0),
            confidence=row.get("confidence", ""),
            reasoning=row.get("reasoning", ""),
            news_trigger=row.get("news_trigger", ""),
            sources=sources,
            settled=bool(row.get("settled", 0)),
            outcome=row.get("outcome", ""),
            pnl=row.get("pnl", 0),
        ))
    return p


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
        per_contract_fee = kalshi_fee(1, price)
        contracts = max(1, int((bankroll - 0.01) / (price + per_contract_fee)))
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
    from gossip.kalshi import get_market_detail, get_orderbook as fetch_orderbook, kalshi_fee as kfee

    detail = await get_market_detail(ticker)
    market = detail.get("market", {})
    if not market or "error" in detail:
        return {"error": f"Market {ticker} not found"}

    title = market.get("title", "?")
    category = market.get("category", "?")

    # Use orderbook for real best bid/ask, fall back to market summary
    orderbook = detail.get("orderbook", {})
    if not orderbook:
        orderbook = await fetch_orderbook(ticker)

    # Orderbook uses yes_dollars/no_dollars (each entry: [price_str, quantity_str])
    yes_bids = orderbook.get("yes_dollars", orderbook.get("yes", [])) if orderbook else []
    no_bids = orderbook.get("no_dollars", orderbook.get("no", [])) if orderbook else []

    # Market summary prices
    summary_bid = float(market.get("yes_bid_dollars", "0") or "0")
    summary_ask = float(market.get("yes_ask_dollars", "0") or "0")

    # Best bid/ask from orderbook — prices are already in dollars (e.g. "0.47")
    if yes_bids:
        ob_yes_bid = max(float(b[0]) for b in yes_bids)
    else:
        ob_yes_bid = summary_bid

    if no_bids:
        best_no_bid = max(float(b[0]) for b in no_bids)
        ob_yes_ask = round(1.0 - best_no_bid, 4)  # NO bid of 0.53 = YES ask of 0.47
    else:
        ob_yes_ask = summary_ask

    bid = ob_yes_bid if ob_yes_bid > 0 else summary_bid
    ask = ob_yes_ask if ob_yes_ask > 0 else summary_ask

    log(f"TRADE PRICING for {ticker}: yes_bid={bid:.4f} yes_ask={ask:.4f} (summary: bid={summary_bid:.4f} ask={summary_ask:.4f})")

    if side == "yes":
        entry_price = ask
        edge = estimated_prob - ask
    else:
        entry_price = 1.0 - bid
        edge = (1 - estimated_prob) - (1 - bid)

    if entry_price <= 0 or entry_price >= 1:
        return {"error": f"Invalid entry price {entry_price:.4f} for {side} side (bid={bid:.4f} ask={ask:.4f})"}

    cost = entry_price * contracts
    fee = kalshi_fee(contracts, entry_price)

    portfolio = load_portfolio()

    risk = check_risk(portfolio, ticker, cost + fee)
    if not risk["ok"]:
        return {"error": "Risk check failed", "issues": risk["issues"]}

    price_detail = f"yes_bid={bid:.4f} yes_ask={ask:.4f} | entry={entry_price:.4f} ({side})"
    full_reasoning = f"{reasoning}\n[Prices at execution: {price_detail}]"

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
        reasoning=full_reasoning,
        news_trigger=news_trigger,
        sources=sources or [],
    )

    # Live execution if enabled
    live_trading = os.getenv("LIVE_TRADING", "false").lower() == "true"
    order_result = None
    if live_trading:
        from gossip.kalshi import place_order
        price_cents = int(entry_price * 100)
        max_cost_cents = int((cost + fee + 0.05) * 100)
        order_result = await place_order(
            ticker=ticker,
            action="buy",
            side=side,
            count=contracts,
            price_cents=price_cents,
            order_type="limit",
            buy_max_cost=max_cost_cents,
            sell_position_floor=0,
        )
        if "error" in order_result:
            return {"error": f"Live order failed: {order_result}", "mode": "live"}
        log(f"LIVE ORDER placed: {order_result}")

    db = get_db()
    db.insert_trade(
        ticker=ticker, title=title, category=category, side=side,
        contracts=contracts, entry_price=round(entry_price, 4),
        cost=round(cost, 2), fee=round(fee, 4),
        estimated_prob=estimated_prob, edge=round(edge, 4),
        confidence=confidence, reasoning=full_reasoning,
        news_trigger=news_trigger, sources=sources or [],
    )
    portfolio = load_portfolio()

    rules = detail.get("settlement_rules", "")
    return {
        "status": "executed",
        "mode": "live" if live_trading else "paper",
        "order": order_result,
        "ticker": ticker,
        "side": side,
        "contracts": contracts,
        "entry_price": trade.entry_price,
        "cost": trade.cost,
        "fee": trade.fee,
        "edge": trade.edge,
        "yes_bid": bid,
        "yes_ask": ask,
        "summary_bid": summary_bid,
        "summary_ask": summary_ask,
        "bankroll_remaining": portfolio.bankroll,
        "title": title,
        "settlement_rules": rules,
    }


async def exit_position(ticker: str, reasoning: str) -> dict:
    from gossip.kalshi import get_market_detail

    detail = await get_market_detail(ticker)
    market = detail.get("market", {})
    bid = float(market.get("yes_bid_dollars", "0") or "0")
    ask = float(market.get("yes_ask_dollars", "0") or "0")

    db = get_db()
    row = db.conn.execute(
        "SELECT * FROM trades WHERE ticker=? AND settled=0 ORDER BY timestamp DESC LIMIT 1",
        (ticker,),
    ).fetchone()
    if not row:
        return {"error": f"No open position on {ticker}"}

    trade = dict(row)
    side = trade["side"]
    entry_price = trade["entry_price"]
    contracts = trade["contracts"]

    exit_price = bid if side == "yes" else 1.0 - ask
    pnl = round((exit_price - entry_price) * contracts, 2)

    result = db.exit_trade(ticker, exit_price, reasoning)
    if not result:
        return {"error": f"DB exit failed for {ticker}"}

    return {
        "status": "exited",
        "ticker": ticker,
        "pnl": pnl,
        "exit_price": exit_price,
        "bankroll": result["bankroll"],
    }


def settle_market(ticker: str, outcome_yes: bool) -> dict:
    db = get_db()
    result = db.settle_trade(ticker, outcome_yes)
    if not result:
        return {"error": f"No open trade on {ticker}"}
    return {
        "status": "settled",
        "ticker": ticker,
        "outcome": "yes" if outcome_yes else "no",
        "result": result["outcome"],
        "pnl": result["pnl"],
        "bankroll": result["bankroll"],
    }


async def check_settlements() -> list[dict]:
    """Check if any open positions have resolved on Kalshi and auto-settle them."""
    from gossip.kalshi import get_market_detail

    db = get_db()
    open_trades = db.get_open_positions()
    settled = []
    for row in open_trades:
        ticker = row["ticker"]
        detail = await get_market_detail(ticker)
        market = detail.get("market", {})
        result = market.get("result", "")
        status = market.get("status", "")
        if result in ("yes", "no") or status == "settled":
            outcome_yes = result == "yes"
            settle_result = db.settle_trade(ticker, outcome_yes)
            if settle_result:
                settled.append({
                    "ticker": ticker,
                    "result": result,
                    "outcome": settle_result["outcome"],
                    "pnl": settle_result["pnl"],
                })
                log(f"AUTO-SETTLED {ticker}: {settle_result['outcome']} (pnl: {settle_result['pnl']:+.2f})")
    return settled


async def get_position_prices() -> list[dict]:
    """Fetch current prices for all open positions and calculate unrealized P&L."""
    from gossip.kalshi import get_market_detail

    portfolio = load_portfolio()
    positions = []
    for t in portfolio.open_positions:
        if not isinstance(t, Trade):
            continue
        detail = await get_market_detail(t.ticker)
        market = detail.get("market", {})
        bid = float(market.get("yes_bid_dollars", "0") or "0")
        ask = float(market.get("yes_ask_dollars", "0") or "0")
        mid = (bid + ask) / 2 if bid > 0 or ask > 0 else 0

        if t.side == "yes":
            current_value = bid * t.contracts
            mark_price = bid
        else:
            current_value = (1.0 - ask) * t.contracts
            mark_price = 1.0 - ask

        unrealized_pnl = round(current_value - t.cost, 2)
        positions.append({
            "ticker": t.ticker,
            "title": t.title,
            "side": t.side,
            "contracts": t.contracts,
            "entry_price": t.entry_price,
            "mark_price": round(mark_price, 4),
            "mid": round(mid, 4),
            "cost": t.cost,
            "current_value": round(current_value, 2),
            "unrealized_pnl": unrealized_pnl,
            "pnl_pct": round(unrealized_pnl / t.cost * 100, 1) if t.cost > 0 else 0,
            "status": market.get("status", ""),
            "result": market.get("result", ""),
        })
    return positions


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
    sub.add_parser("check-settled", help="Auto-settle resolved markets")
    sub.add_parser("prices", help="Current prices + unrealized P&L for open positions")

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
        db = get_db()
        trades = db.get_trade_history(limit=20)
        print(json.dumps(trades, indent=2))

    elif args.command == "check-settled":
        settled = await check_settlements()
        print(json.dumps({"settled": settled, "count": len(settled)}, indent=2))

    elif args.command == "prices":
        positions = await get_position_prices()
        total_unrealized = sum(p["unrealized_pnl"] for p in positions)
        print(json.dumps({"positions": positions, "total_unrealized_pnl": round(total_unrealized, 2)}, indent=2))

    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())
