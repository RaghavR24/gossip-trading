"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { TopBar } from "@/components/TopBar";
import { PortfolioStrip } from "@/components/PortfolioStrip";
import { PositionsPanel } from "@/components/PositionsPanel";
import { MarketScanner } from "@/components/MarketScanner";
import { LiveStream } from "@/components/LiveStream";
import { NewsFeed } from "@/components/NewsFeed";
import { AgentLog } from "@/components/AgentLog";
import type {
  Portfolio,
  Trade,
  NewsArticle,
  Market,
  AgentCycle,
  StreamLine,
} from "@/lib/types";

export default function Dashboard() {
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [news, setNews] = useState<NewsArticle[]>([]);
  const [markets, setMarkets] = useState<Market[]>([]);
  const [cycles, setCycles] = useState<AgentCycle[]>([]);
  const [rationale, setRationale] = useState("");
  const [customPrompt, setCustomPrompt] = useState("");
  const [agentStatus, setAgentStatus] = useState("");
  const [loopInterval, setLoopInterval] = useState(900);
  const [streamLines, setStreamLines] = useState<StreamLine[]>([]);
  const [liveStatus, setLiveStatus] = useState<string>("idle");
  const streamOffset = useRef(0);

  const fetchAll = useCallback(async () => {
    try {
      const [p, t, n, m, a] = await Promise.all([
        fetch("/api/portfolio").then((r) => r.json()),
        fetch("/api/trades").then((r) => r.json()),
        fetch("/api/news").then((r) => r.json()),
        fetch("/api/markets").then((r) => r.json()),
        fetch("/api/agent").then((r) => r.json()),
      ]);
      setPortfolio(p);
      setTrades(t);
      setNews(n);
      setMarkets(m);
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

  useEffect(() => {
    const pollStream = async () => {
      try {
        const res = await fetch(
          `/api/agent/stream?offset=${streamOffset.current}`
        );
        const data = await res.json();
        setLiveStatus(data.status?.status || "idle");
        if (data.lines.length > 0) {
          setStreamLines((prev) => {
            const next = [...prev, ...data.lines];
            return next.length > 500 ? next.slice(-500) : next;
          });
          streamOffset.current = data.offset;
        }
        if (data.offset < streamOffset.current) {
          setStreamLines([]);
          streamOffset.current = 0;
        }
      } catch {
        // ignore
      }
    };
    const id = setInterval(pollStream, 1000);
    return () => clearInterval(id);
  }, []);

  const runCycle = async (prompt?: string) => {
    setAgentStatus("Starting cycle...");
    setStreamLines([]);
    streamOffset.current = 0;
    const res = await fetch("/api/agent", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "run_cycle", prompt }),
    });
    const data = await res.json();
    setAgentStatus(data.message || data.status);
  };

  const startLoop = async () => {
    setAgentStatus(`Starting loop (${loopInterval}s)...`);
    const res = await fetch("/api/agent", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "start_loop", interval: loopInterval }),
    });
    const data = await res.json();
    setAgentStatus(`Loop: ${data.interval}s interval`);
  };

  const submitRationale = async () => {
    if (!rationale.trim()) return;
    setAgentStatus("Researching thesis...");
    const res = await fetch("/api/agent", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "submit_rationale", rationale }),
    });
    const data = await res.json();
    setAgentStatus(data.message || data.status);
    setRationale("");
  };

  return (
    <div className="h-screen flex flex-col overflow-hidden bg-background">
      <TopBar
        liveStatus={liveStatus}
        agentStatus={agentStatus}
        rationale={rationale}
        loopInterval={loopInterval}
        onRationaleChange={setRationale}
        onSubmitRationale={submitRationale}
        onRunCycle={() => runCycle()}
        onStartLoop={startLoop}
        onRefresh={fetchAll}
        onLoopIntervalChange={setLoopInterval}
      />

      <PortfolioStrip portfolio={portfolio} />

      <div className="flex-1 grid grid-cols-1 md:grid-cols-[280px_1fr] lg:grid-cols-[280px_1fr_320px] min-h-0">
        {/* Left column: Positions + Markets */}
        <div className="hidden md:flex flex-col border-r border-border min-h-0">
          <div className="flex-1 min-h-0">
            <PositionsPanel
              positions={portfolio?.open_positions ?? []}
              trades={trades}
            />
          </div>
          <div className="h-[40%] min-h-0">
            <MarketScanner markets={markets} />
          </div>
        </div>

        {/* Center column: Live Stream */}
        <div className="flex flex-col min-h-0">
          <LiveStream
            lines={streamLines}
            liveStatus={liveStatus}
            customPrompt={customPrompt}
            onCustomPromptChange={setCustomPrompt}
            onSendCommand={(prompt) => {
              runCycle(prompt);
              setCustomPrompt("");
            }}
          />
        </div>

        {/* Right column: News + Agent Log */}
        <div className="hidden lg:flex flex-col border-l border-border min-h-0">
          <div className="flex-[3] min-h-0">
            <NewsFeed news={news} />
          </div>
          <div className="flex-[2] min-h-0">
            <AgentLog cycles={cycles} />
          </div>
        </div>
      </div>
    </div>
  );
}
