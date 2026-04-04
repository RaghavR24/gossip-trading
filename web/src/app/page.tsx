"use client";

import { useEffect, useState, useCallback } from "react";

interface Portfolio {
  bankroll: number;
  total_pnl: number;
  total_trades: number;
  wins: number;
  losses: number;
  open_positions: Trade[];
  total_news: number;
  total_snapshots: number;
  total_cycles: number;
}

interface Trade {
  id: number;
  timestamp: string;
  ticker: string;
  title: string;
  side: string;
  contracts: number;
  entry_price: number;
  edge: number;
  confidence: string;
  reasoning: string;
  settled: number;
  outcome: string;
  pnl: number;
}

interface NewsArticle {
  id: number;
  timestamp: string;
  source: string;
  keyword: string;
  title: string;
  url: string;
  snippet: string;
}

interface AgentCycle {
  id: number;
  timestamp: string;
  duration_s: number;
  status: string;
  output_summary: string;
}

type Tab = "positions" | "trades" | "news" | "agent";

export default function Dashboard() {
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [news, setNews] = useState<NewsArticle[]>([]);
  const [cycles, setCycles] = useState<AgentCycle[]>([]);
  const [tab, setTab] = useState<Tab>("positions");
  const [rationale, setRationale] = useState("");
  const [customPrompt, setCustomPrompt] = useState("");
  const [agentStatus, setAgentStatus] = useState("");
  const [loopInterval, setLoopInterval] = useState(900);

  const fetchAll = useCallback(async () => {
    try {
      const [p, t, n, a] = await Promise.all([
        fetch("/api/portfolio").then((r) => r.json()),
        fetch("/api/trades").then((r) => r.json()),
        fetch("/api/news").then((r) => r.json()),
        fetch("/api/agent").then((r) => r.json()),
      ]);
      setPortfolio(p);
      setTrades(t);
      setNews(n);
      setCycles(a);
    } catch {
      // DB might not exist yet
    }
  }, []);

  useEffect(() => {
    fetchAll();
    const id = setInterval(fetchAll, 5000);
    return () => clearInterval(id);
  }, [fetchAll]);

  const runCycle = async (prompt?: string) => {
    setAgentStatus("Starting cycle...");
    const res = await fetch("/api/agent", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "run_cycle", prompt }),
    });
    const data = await res.json();
    setAgentStatus(data.message || data.status);
  };

  const startLoop = async () => {
    setAgentStatus(`Starting loop (${loopInterval}s interval)...`);
    const res = await fetch("/api/agent", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "start_loop", interval: loopInterval }),
    });
    const data = await res.json();
    setAgentStatus(`Loop started: ${data.interval}s interval`);
  };

  const submitRationale = async () => {
    if (!rationale.trim()) return;
    setAgentStatus("Submitting thesis...");
    const res = await fetch("/api/agent", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "submit_rationale", rationale }),
    });
    const data = await res.json();
    setAgentStatus(data.message || data.status);
    setRationale("");
  };

  const winRate =
    portfolio && portfolio.total_trades > 0
      ? ((portfolio.wins / portfolio.total_trades) * 100).toFixed(0)
      : "—";

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 p-6">
      <div className="max-w-7xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">
              Gossip Trading
            </h1>
            <p className="text-zinc-500 text-sm mt-1">
              Autonomous prediction market agent
            </p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => runCycle()}
              className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 rounded-lg text-sm font-medium transition"
            >
              Run Cycle
            </button>
            <button
              onClick={startLoop}
              className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 rounded-lg text-sm font-medium transition"
            >
              Start Loop
            </button>
            <button
              onClick={fetchAll}
              className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 rounded-lg text-sm font-medium transition"
            >
              Refresh
            </button>
          </div>
        </div>

        {agentStatus && (
          <div className="mb-4 px-4 py-2 bg-zinc-900 border border-zinc-800 rounded-lg text-sm text-zinc-400">
            {agentStatus}
          </div>
        )}

        {portfolio && (
          <div className="grid grid-cols-2 md:grid-cols-6 gap-4 mb-8">
            <MetricCard label="Bankroll" value={`$${portfolio.bankroll.toFixed(2)}`} />
            <MetricCard
              label="P&L"
              value={`$${portfolio.total_pnl >= 0 ? "+" : ""}${portfolio.total_pnl.toFixed(2)}`}
              color={portfolio.total_pnl >= 0 ? "text-emerald-400" : "text-red-400"}
            />
            <MetricCard label="Trades" value={String(portfolio.total_trades)} />
            <MetricCard label="Win Rate" value={`${winRate}%`} />
            <MetricCard label="Open" value={String(portfolio.open_positions.length)} />
            <MetricCard label="Cycles" value={String(portfolio.total_cycles)} />
          </div>
        )}

        {/* Thesis input */}
        <div className="mb-6 p-4 bg-zinc-900 border border-zinc-800 rounded-lg">
          <label className="text-sm text-zinc-400 mb-2 block">
            Submit a thesis for the agent to research & trade
          </label>
          <div className="flex gap-2">
            <input
              type="text"
              value={rationale}
              onChange={(e) => setRationale(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && submitRationale()}
              placeholder='"I think tariffs on China will escalate before April 15"'
              className="flex-1 bg-zinc-800 border border-zinc-700 rounded-lg px-4 py-2 text-sm focus:outline-none focus:border-emerald-500"
            />
            <button
              onClick={submitRationale}
              className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 rounded-lg text-sm font-medium transition whitespace-nowrap"
            >
              Research & Trade
            </button>
          </div>
        </div>

        {/* Command input */}
        <div className="mb-6 p-4 bg-zinc-900 border border-zinc-800 rounded-lg">
          <label className="text-sm text-zinc-400 mb-2 block">
            Send a command to the agent
          </label>
          <div className="flex gap-2">
            <input
              type="text"
              value={customPrompt}
              onChange={(e) => setCustomPrompt(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  runCycle(customPrompt);
                  setCustomPrompt("");
                }
              }}
              placeholder='"Check my BTC positions" or "Scan crypto markets only"'
              className="flex-1 bg-zinc-800 border border-zinc-700 rounded-lg px-4 py-2 text-sm focus:outline-none focus:border-zinc-500"
            />
            <button
              onClick={() => { runCycle(customPrompt); setCustomPrompt(""); }}
              className="px-4 py-2 bg-zinc-700 hover:bg-zinc-600 rounded-lg text-sm font-medium transition"
            >
              Send
            </button>
          </div>
        </div>

        {/* Loop interval */}
        <div className="mb-8 flex items-center gap-4">
          <span className="text-sm text-zinc-500">Loop interval:</span>
          {[60, 300, 600, 900, 1800].map((s) => (
            <button
              key={s}
              onClick={() => setLoopInterval(s)}
              className={`px-3 py-1 rounded text-sm ${
                loopInterval === s
                  ? "bg-emerald-600 text-white"
                  : "bg-zinc-800 text-zinc-400 hover:bg-zinc-700"
              }`}
            >
              {s >= 60 ? `${s / 60}m` : `${s}s`}
            </button>
          ))}
        </div>

        {/* Tabs */}
        <div className="flex gap-1 mb-6 border-b border-zinc-800">
          {([
            ["positions", "Positions"],
            ["trades", "Trade History"],
            ["news", "News Feed"],
            ["agent", "Agent Log"],
          ] as [Tab, string][]).map(([key, label]) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition ${
                tab === key
                  ? "border-emerald-500 text-emerald-400"
                  : "border-transparent text-zinc-500 hover:text-zinc-300"
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Positions */}
        {tab === "positions" && (
          <div className="space-y-3">
            {portfolio?.open_positions.length === 0 && (
              <p className="text-zinc-500 text-sm">No open positions</p>
            )}
            {portfolio?.open_positions.map((t) => (
              <div key={t.id} className="p-4 bg-zinc-900 border border-zinc-800 rounded-lg">
                <div className="flex items-center justify-between">
                  <div>
                    <span className="font-mono font-bold">{t.ticker}</span>
                    <span className="text-zinc-500 ml-2 text-sm">{t.title}</span>
                  </div>
                  <div className="flex gap-4 text-sm">
                    <span className={t.side === "yes" ? "text-emerald-400" : "text-red-400"}>
                      {t.side.toUpperCase()} x{t.contracts}
                    </span>
                    <span>Entry: ${t.entry_price.toFixed(2)}</span>
                    <span className={t.edge > 0 ? "text-emerald-400" : "text-red-400"}>
                      Edge: {(t.edge * 100).toFixed(1)}pp
                    </span>
                    <span className="text-zinc-500">{t.confidence}</span>
                  </div>
                </div>
                {t.reasoning && <p className="text-zinc-500 text-xs mt-2">{t.reasoning}</p>}
              </div>
            ))}
          </div>
        )}

        {/* Trade History */}
        {tab === "trades" && (
          <div className="space-y-2">
            {trades.map((t) => (
              <div key={t.id} className="p-3 bg-zinc-900 border border-zinc-800 rounded-lg flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="text-lg">
                    {t.outcome === "win" ? "+" : t.outcome === "loss" ? "-" : "~"}
                  </span>
                  <span className="font-mono text-sm">{t.ticker}</span>
                  <span className={`text-sm ${t.side === "yes" ? "text-emerald-400" : "text-red-400"}`}>
                    {t.side.toUpperCase()} x{t.contracts}
                  </span>
                  <span className="text-zinc-500 text-sm">@ ${t.entry_price.toFixed(2)}</span>
                </div>
                <div className="flex items-center gap-4 text-sm">
                  {t.settled ? (
                    <span className={t.pnl >= 0 ? "text-emerald-400" : "text-red-400"}>
                      ${t.pnl >= 0 ? "+" : ""}{t.pnl.toFixed(2)}
                    </span>
                  ) : (
                    <span className="text-zinc-500">open</span>
                  )}
                  <span className="text-zinc-600 text-xs">{t.timestamp.slice(0, 16)}</span>
                </div>
              </div>
            ))}
            {trades.length === 0 && <p className="text-zinc-500 text-sm">No trades yet</p>}
          </div>
        )}

        {/* News */}
        {tab === "news" && (
          <div className="space-y-2">
            {news.map((n) => (
              <div key={n.id} className="p-3 bg-zinc-900 border border-zinc-800 rounded-lg">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs px-2 py-0.5 bg-zinc-800 rounded text-zinc-400">{n.source}</span>
                  {n.keyword && (
                    <span className="text-xs px-2 py-0.5 bg-zinc-800 rounded text-emerald-400">{n.keyword}</span>
                  )}
                  <span className="text-xs text-zinc-600">{n.timestamp.slice(0, 16)}</span>
                </div>
                {n.url ? (
                  <a href={n.url} target="_blank" rel="noopener noreferrer" className="text-sm hover:text-emerald-400 transition">
                    {n.title}
                  </a>
                ) : (
                  <p className="text-sm">{n.title}</p>
                )}
                {n.snippet && <p className="text-xs text-zinc-500 mt-1">{n.snippet.slice(0, 200)}</p>}
              </div>
            ))}
            {news.length === 0 && <p className="text-zinc-500 text-sm">No news scraped yet</p>}
          </div>
        )}

        {/* Agent Log */}
        {tab === "agent" && (
          <div className="space-y-2">
            {cycles.map((c) => (
              <div key={c.id} className="p-3 bg-zinc-900 border border-zinc-800 rounded-lg">
                <div className="flex items-center gap-2 mb-1">
                  <span className={`w-2 h-2 rounded-full ${c.status === "ok" ? "bg-emerald-500" : "bg-red-500"}`} />
                  <span className="text-sm text-zinc-400">{c.timestamp.slice(0, 19)}</span>
                  <span className="text-sm text-zinc-500">{c.duration_s}s</span>
                </div>
                {c.output_summary && <p className="text-xs text-zinc-500 mt-1">{c.output_summary.slice(0, 400)}</p>}
              </div>
            ))}
            {cycles.length === 0 && <p className="text-zinc-500 text-sm">No agent cycles yet</p>}
          </div>
        )}
      </div>
    </div>
  );
}

function MetricCard({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="p-4 bg-zinc-900 border border-zinc-800 rounded-lg">
      <p className="text-xs text-zinc-500 uppercase tracking-wider">{label}</p>
      <p className={`text-2xl font-bold mt-1 ${color || "text-zinc-100"}`}>{value}</p>
    </div>
  );
}
