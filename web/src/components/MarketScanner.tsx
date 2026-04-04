"use client";

import { useState } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ArrowUpDown } from "lucide-react";
import type { Market } from "@/lib/types";

interface MarketScannerProps {
  markets: Market[];
}

type SortKey = "volume" | "mid" | "ticker";

export function MarketScanner({ markets }: MarketScannerProps) {
  const [sortBy, setSortBy] = useState<SortKey>("volume");

  const sorted = [...markets].sort((a, b) => {
    if (sortBy === "volume") return b.volume - a.volume;
    if (sortBy === "mid") return b.mid - a.mid;
    return a.ticker.localeCompare(b.ticker);
  });

  return (
    <div className="flex flex-col h-full border-t border-border">
      <div className="h-9 flex items-center justify-between px-3 border-b border-border bg-card shrink-0">
        <span className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
          Markets
        </span>
        <button
          onClick={() =>
            setSortBy((p) =>
              p === "volume" ? "mid" : p === "mid" ? "ticker" : "volume"
            )
          }
          className="flex items-center gap-1 text-[10px] text-muted-foreground/60 hover:text-muted-foreground transition-colors"
        >
          <ArrowUpDown className="h-2.5 w-2.5" />
          {sortBy}
        </button>
      </div>

      <ScrollArea className="flex-1">
        <table className="w-full text-[10px]">
          <thead>
            <tr className="text-muted-foreground/50 border-b border-border">
              <th className="text-left px-3 py-1.5 font-medium">Ticker</th>
              <th className="text-right px-2 py-1.5 font-medium">Bid/Ask</th>
              <th className="text-right px-2 py-1.5 font-medium">Mid</th>
              <th className="text-right px-3 py-1.5 font-medium">Vol</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((m) => (
              <tr
                key={m.id}
                className="border-b border-border/30 hover:bg-secondary/30 transition-colors"
              >
                <td className="px-3 py-1.5">
                  <div className="font-mono font-medium truncate max-w-[120px]">
                    {m.ticker}
                  </div>
                  <div className="text-muted-foreground/40 truncate max-w-[120px]">
                    {m.title}
                  </div>
                </td>
                <td className="text-right px-2 py-1.5 font-mono text-muted-foreground">
                  {m.yes_bid.toFixed(0)}
                  <span className="text-muted-foreground/30">/</span>
                  {m.yes_ask.toFixed(0)}
                </td>
                <td className="text-right px-2 py-1.5 font-mono font-medium">
                  {(m.mid * 100).toFixed(0)}
                  <span className="text-muted-foreground/40">%</span>
                </td>
                <td className="text-right px-3 py-1.5 font-mono text-muted-foreground">
                  {formatVolume(m.volume)}
                </td>
              </tr>
            ))}
            {markets.length === 0 && (
              <tr>
                <td
                  colSpan={4}
                  className="text-center py-6 text-muted-foreground/60"
                >
                  No market data
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </ScrollArea>
    </div>
  );
}

function formatVolume(v: number): string {
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `${(v / 1_000).toFixed(1)}K`;
  return String(v);
}
