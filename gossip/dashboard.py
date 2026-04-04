"""
Gossip Trading — Streamlit dashboard.

Run: streamlit run gossip/dashboard.py

Shows: portfolio, open positions, trade history, news feed, market scanner.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
TRADES_FILE = DATA_DIR / "trades.json"
CYCLE_LOG = DATA_DIR / "cycle_log.json"

st.set_page_config(page_title="Gossip Trading", page_icon="🗞️", layout="wide")

st.title("Gossip Trading")
st.caption("Autonomous prediction market agent — Kalshi")


def load_data():
    if TRADES_FILE.exists():
        try:
            return json.loads(TRADES_FILE.read_text())
        except Exception:
            pass
    return {"bankroll": 30.0, "total_pnl": 0.0, "total_trades": 0, "wins": 0, "losses": 0, "trades": []}


def load_cycles():
    if CYCLE_LOG.exists():
        try:
            return json.loads(CYCLE_LOG.read_text())
        except Exception:
            pass
    return []


data = load_data()
cycles = load_cycles()

# --- Top-level metrics ---

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Bankroll", f"${data['bankroll']:.2f}")
col2.metric("Total P&L", f"${data['total_pnl']:+.2f}")
col3.metric("Trades", data['total_trades'])
col4.metric("Win Rate", f"{data['wins'] / data['total_trades'] * 100:.0f}%" if data['total_trades'] > 0 else "—")
col5.metric("Open", len([t for t in data['trades'] if not t.get('settled') and t.get('action') == 'buy']))

st.divider()

# --- Open positions ---

open_trades = [t for t in data["trades"] if not t.get("settled") and t.get("action") == "buy"]

if open_trades:
    st.subheader("Open Positions")
    for t in open_trades:
        with st.container():
            c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
            c1.write(f"**{t['ticker']}** — {t.get('title', '')[:60]}")
            c2.write(f"{t['side'].upper()} x{t['contracts']}")
            c3.write(f"Entry: ${t['entry_price']:.2f}")
            c4.write(f"Edge: {t['edge']:+.1%}")
            if t.get("reasoning"):
                st.caption(t["reasoning"][:200])
            st.divider()
else:
    st.info("No open positions")

# --- Trade history ---

settled = [t for t in data["trades"] if t.get("settled")]
if settled:
    st.subheader("Trade History")
    for t in reversed(settled[-10:]):
        icon = "✅" if t.get("outcome") == "win" else "❌"
        st.write(f"{icon} **{t['ticker']}** — {t['side'].upper()} x{t['contracts']} @ ${t['entry_price']:.2f} → P&L: ${t.get('pnl', 0):+.2f}")
        if t.get("reasoning"):
            st.caption(t["reasoning"][:150])

# --- Agent cycle log ---

if cycles:
    st.subheader("Agent Cycles")
    for c in reversed(cycles[-5:]):
        status_icon = "🟢" if c.get("status") == "ok" else "🔴"
        ts = c.get("timestamp", "")[:19]
        dur = c.get("duration_s", "?")
        preview = c.get("output_preview", "")[:200]
        st.write(f"{status_icon} **{ts}** — {dur}s")
        if preview:
            st.caption(preview)

# --- Auto-refresh ---
st.button("Refresh")
