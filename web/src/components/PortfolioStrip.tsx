"use client";

import type { Portfolio } from "@/lib/types";

interface PortfolioStripProps {
  portfolio: Portfolio | null;
}

export function PortfolioStrip({ portfolio }: PortfolioStripProps) {
  if (!portfolio) {
    return (
      <div className="h-[72px] flex items-center px-6 border-b border-border bg-card/30 shrink-0">
        <div className="h-4 w-32 bg-muted/30 rounded animate-pulse" />
      </div>
    );
  }

  const pnlPositive = portfolio.total_pnl >= 0;
  const settled = portfolio.wins + portfolio.losses;
  const winRate = settled > 0
    ? ((portfolio.wins / settled) * 100).toFixed(0)
    : null;
  const deployed = portfolio.open_positions.reduce((s, p) => s + p.cost, 0);
  const totalValue = portfolio.bankroll + deployed;
  const lastCycleLabel = portfolio.last_cycle_at ? timeAgo(portfolio.last_cycle_at) : "—";

  return (
    <div className="h-[72px] flex items-center gap-6 px-6 border-b border-border bg-card/30 shrink-0 overflow-hidden">
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-3">
          {deployed > 0 && (
            <MiniPie cash={portfolio.bankroll} deployed={deployed} />
          )}
          <div className="flex flex-col">
            <div className="flex items-baseline gap-1">
              <span className="text-[10px] text-muted-foreground/50 uppercase tracking-wider self-start mt-1.5">
                USD
              </span>
              <span className="text-3xl font-bold font-mono tracking-tighter">
                {totalValue.toLocaleString("en-US", {
                  style: "currency",
                  currency: "USD",
                })}
              </span>
            </div>
            {deployed > 0 && (
              <div className="flex items-center gap-2 ml-7 text-[10px] font-mono">
                <span className="flex items-center gap-1 text-muted-foreground/50">
                  <span className="inline-block w-1.5 h-1.5 rounded-full bg-primary/60" />
                  ${portfolio.bankroll.toFixed(2)} cash
                </span>
                <span className="flex items-center gap-1 text-muted-foreground/50">
                  <span className="inline-block w-1.5 h-1.5 rounded-full bg-amber-500/60" />
                  ${deployed.toFixed(2)} deployed
                </span>
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="h-8 w-px bg-border/50" />

      <div className="flex items-center gap-3 text-xs font-mono">
        <span className={pnlPositive ? "text-primary" : "text-destructive"}>
          {pnlPositive ? "+" : "-"}${Math.abs(portfolio.total_pnl).toFixed(2)} <span className="text-muted-foreground/40">realized</span>
        </span>
        <span className="text-muted-foreground/30">|</span>
        <span className="text-muted-foreground/60">{portfolio.total_trades} trades</span>
        <span className="text-muted-foreground/30">|</span>
        <span className={
          winRate === null
            ? "text-muted-foreground/60"
            : Number(winRate) >= 50 ? "text-primary/80" : "text-destructive/80"
        }>
          {winRate !== null ? `${winRate}%` : "—"} win
        </span>
        <span className="text-muted-foreground/30">|</span>
        <span className="text-muted-foreground/60">{portfolio.open_positions.length} open</span>
        <span className="text-muted-foreground/30">|</span>
        <span className="text-muted-foreground/40">{lastCycleLabel === "—" ? "no runs" : `${lastCycleLabel} since last run`}</span>
      </div>
    </div>
  );
}

function MiniPie({ cash, deployed }: { cash: number; deployed: number }) {
  const total = cash + deployed;
  const cashPct = total > 0 ? cash / total : 1;
  const cashDeg = cashPct * 360;
  return (
    <div
      className="w-10 h-10 rounded-full shrink-0"
      style={{
        background: `conic-gradient(#22c55e99 0deg ${cashDeg}deg, #f59e0b99 ${cashDeg}deg 360deg)`,
      }}
      title={`$${cash.toFixed(2)} cash / $${deployed.toFixed(2)} deployed`}
    >
      <div className="w-full h-full flex items-center justify-center">
        <div className="w-5 h-5 rounded-full bg-[#0a0a0a]" />
      </div>
    </div>
  );
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

