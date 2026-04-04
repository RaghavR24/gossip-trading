"use client";

import { TrendingUp, TrendingDown, BarChart3, Trophy, Layers, Zap } from "lucide-react";
import type { Portfolio } from "@/lib/types";

interface PortfolioStripProps {
  portfolio: Portfolio | null;
}

export function PortfolioStrip({ portfolio }: PortfolioStripProps) {
  if (!portfolio) {
    return (
      <div className="h-20 flex items-center px-6 border-b border-border bg-card/50 shrink-0">
        <div className="text-sm text-muted-foreground">Loading portfolio...</div>
      </div>
    );
  }

  const pnlPositive = portfolio.total_pnl >= 0;
  const winRate =
    portfolio.total_trades > 0
      ? ((portfolio.wins / portfolio.total_trades) * 100).toFixed(0)
      : "0";

  return (
    <div className="h-20 flex items-center gap-8 px-6 border-b border-border bg-card/50 shrink-0">
      <div className="flex items-baseline gap-3">
        <span className="text-3xl font-bold font-mono tracking-tight">
          ${portfolio.bankroll.toFixed(2)}
        </span>
        <div
          className={`flex items-center gap-1 text-sm font-medium ${
            pnlPositive ? "text-primary" : "text-destructive"
          }`}
        >
          {pnlPositive ? (
            <TrendingUp className="h-3.5 w-3.5" />
          ) : (
            <TrendingDown className="h-3.5 w-3.5" />
          )}
          <span>
            {pnlPositive ? "+" : ""}
            ${portfolio.total_pnl.toFixed(2)}
          </span>
        </div>
      </div>

      <div className="h-8 w-px bg-border" />

      <div className="flex items-center gap-6">
        <Metric
          icon={<BarChart3 className="h-3.5 w-3.5" />}
          label="Trades"
          value={String(portfolio.total_trades)}
        />
        <Metric
          icon={<Trophy className="h-3.5 w-3.5" />}
          label="Win Rate"
          value={`${winRate}%`}
          valueColor={Number(winRate) >= 50 ? "text-primary" : "text-destructive"}
        />
        <Metric
          icon={<Layers className="h-3.5 w-3.5" />}
          label="Open"
          value={String(portfolio.open_positions.length)}
        />
        <Metric
          icon={<Zap className="h-3.5 w-3.5" />}
          label="Cycles"
          value={String(portfolio.total_cycles)}
        />
      </div>
    </div>
  );
}

function Metric({
  icon,
  label,
  value,
  valueColor,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  valueColor?: string;
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-muted-foreground">{icon}</span>
      <div>
        <p className="text-[10px] text-muted-foreground uppercase tracking-wider leading-none">
          {label}
        </p>
        <p className={`text-lg font-semibold font-mono leading-tight ${valueColor || ""}`}>
          {value}
        </p>
      </div>
    </div>
  );
}
