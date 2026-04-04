"use client";

import {
  TrendingUp,
  TrendingDown,
  BarChart3,
  Trophy,
  Layers,
  Zap,
} from "lucide-react";
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
  const winRate =
    portfolio.total_trades > 0
      ? ((portfolio.wins / portfolio.total_trades) * 100).toFixed(0)
      : "0";

  return (
    <div className="h-[72px] flex items-center gap-6 px-6 border-b border-border bg-card/30 shrink-0 overflow-hidden">
      <div className="flex items-center gap-4">
        <div className="flex items-baseline gap-1">
          <span className="text-[10px] text-muted-foreground/50 uppercase tracking-wider self-start mt-1.5">
            USD
          </span>
          <span className="text-3xl font-bold font-mono tracking-tighter">
            {portfolio.bankroll.toLocaleString("en-US", {
              style: "currency",
              currency: "USD",
            })}
          </span>
        </div>
        <div
          className={`flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${
            pnlPositive
              ? "bg-primary/10 text-primary"
              : "bg-destructive/10 text-destructive"
          }`}
        >
          {pnlPositive ? (
            <TrendingUp className="h-3 w-3" />
          ) : (
            <TrendingDown className="h-3 w-3" />
          )}
          {pnlPositive ? "+" : ""}
          ${Math.abs(portfolio.total_pnl).toFixed(2)}
        </div>
      </div>

      <div className="h-8 w-px bg-border" />

      <div className="flex items-center gap-5">
        <Metric
          icon={<BarChart3 className="h-3.5 w-3.5" />}
          label="Trades"
          value={String(portfolio.total_trades)}
        />
        <Metric
          icon={<Trophy className="h-3.5 w-3.5" />}
          label="Win Rate"
          value={`${winRate}%`}
          valueColor={
            Number(winRate) >= 50 ? "text-primary" : "text-destructive"
          }
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
      <div className="p-1.5 rounded-md bg-secondary/50 text-muted-foreground">
        {icon}
      </div>
      <div>
        <p className="text-[9px] text-muted-foreground/60 uppercase tracking-wider leading-none mb-0.5">
          {label}
        </p>
        <p
          className={`text-base font-semibold font-mono leading-none ${valueColor || "text-foreground"}`}
        >
          {value}
        </p>
      </div>
    </div>
  );
}
