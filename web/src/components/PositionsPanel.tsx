"use client";

import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { Trade } from "@/lib/types";

interface PositionsPanelProps {
  positions: Trade[];
  trades: Trade[];
}

export function PositionsPanel({ positions, trades }: PositionsPanelProps) {
  return (
    <div className="flex flex-col h-full">
      <PanelHeader title="Positions" count={positions.length} />
      <ScrollArea className="flex-1">
        <div className="p-2">
          {positions.length === 0 && (
            <p className="text-xs text-muted-foreground p-3 text-center">
              No open positions
            </p>
          )}
          {positions.map((t) => (
            <div
              key={t.id}
              className="p-3 rounded-lg mb-1.5 bg-secondary/30 hover:bg-secondary/50 transition-colors"
            >
              <div className="flex items-center justify-between mb-1">
                <span className="font-mono text-xs font-semibold truncate mr-2">
                  {t.ticker}
                </span>
                <Badge
                  variant={t.side === "yes" ? "default" : "destructive"}
                  className="text-[10px] h-4 px-1.5"
                >
                  {t.side.toUpperCase()}
                </Badge>
              </div>
              <p className="text-[10px] text-muted-foreground truncate mb-2">
                {t.title}
              </p>
              <div className="flex items-center gap-3 text-[10px]">
                <span className="text-muted-foreground">
                  {t.contracts}x @ ${t.entry_price.toFixed(2)}
                </span>
                <span
                  className={
                    t.edge > 0 ? "text-primary" : "text-destructive"
                  }
                >
                  {(t.edge * 100).toFixed(1)}pp edge
                </span>
                <span className="text-muted-foreground/60 capitalize">
                  {t.confidence}
                </span>
              </div>
            </div>
          ))}
        </div>

        {trades.length > 0 && (
          <>
            <div className="px-3 py-2">
              <p className="text-[10px] text-muted-foreground uppercase tracking-wider font-medium">
                Recent Trades
              </p>
            </div>
            <div className="px-2 pb-2">
              {trades.slice(0, 15).map((t) => (
                <div
                  key={t.id}
                  className="flex items-center justify-between px-3 py-2 rounded-md hover:bg-secondary/30 transition-colors"
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <span
                      className={`text-xs font-bold ${
                        t.outcome === "win"
                          ? "text-primary"
                          : t.outcome === "loss"
                            ? "text-destructive"
                            : "text-muted-foreground"
                      }`}
                    >
                      {t.outcome === "win" ? "+" : t.outcome === "loss" ? "-" : "~"}
                    </span>
                    <span className="font-mono text-[11px] truncate">{t.ticker}</span>
                    <span
                      className={`text-[10px] ${t.side === "yes" ? "text-primary/70" : "text-destructive/70"}`}
                    >
                      {t.side.toUpperCase()}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-[10px] shrink-0">
                    {t.settled ? (
                      <span
                        className={`font-mono font-medium ${t.pnl >= 0 ? "text-primary" : "text-destructive"}`}
                      >
                        {t.pnl >= 0 ? "+" : ""}${t.pnl.toFixed(2)}
                      </span>
                    ) : (
                      <span className="text-muted-foreground">open</span>
                    )}
                    <span className="text-muted-foreground/40">
                      {formatRelativeTime(t.timestamp)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </ScrollArea>
    </div>
  );
}

function PanelHeader({ title, count }: { title: string; count: number }) {
  return (
    <div className="h-9 flex items-center justify-between px-3 border-b border-border bg-card shrink-0">
      <span className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
        {title}
      </span>
      <span className="text-[10px] text-muted-foreground/60 font-mono">
        {count}
      </span>
    </div>
  );
}

function formatRelativeTime(ts: string): string {
  const diff = Date.now() - new Date(ts).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "now";
  if (mins < 60) return `${mins}m`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h`;
  return `${Math.floor(hrs / 24)}d`;
}
