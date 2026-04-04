"use client";

import { useRef, useEffect } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Send, Terminal } from "lucide-react";
import type { StreamLine } from "@/lib/types";

interface LiveStreamProps {
  lines: StreamLine[];
  liveStatus: string;
  customPrompt: string;
  onCustomPromptChange: (v: string) => void;
  onSendCommand: (prompt: string) => void;
}

export function LiveStream({
  lines,
  liveStatus,
  customPrompt,
  onCustomPromptChange,
  onSendCommand,
}: LiveStreamProps) {
  const endRef = useRef<HTMLDivElement>(null);
  const prevLinesCount = useRef(0);

  useEffect(() => {
    if (lines.length > 0 && lines.length !== prevLinesCount.current) {
      endRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
    prevLinesCount.current = lines.length;
  }, [lines.length]);

  return (
    <div className="flex flex-col h-full">
      <div className="h-9 flex items-center justify-between px-3 border-b border-border bg-card shrink-0">
        <div className="flex items-center gap-2">
          <Terminal className="h-3.5 w-3.5 text-muted-foreground" />
          <span className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
            Live Stream
          </span>
        </div>
        {liveStatus === "running" && (
          <span className="text-[10px] text-primary font-medium flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-primary pulse-glow" />
            Streaming
          </span>
        )}
      </div>

      <ScrollArea className="flex-1 min-h-0">
        <div className="p-4 font-mono text-xs space-y-2">
          {lines.length === 0 && liveStatus !== "running" && (
            <p className="text-muted-foreground/40 text-center py-12">
              Run a cycle to see live agent output
            </p>
          )}
          {lines.length === 0 && liveStatus === "running" && (
            <p className="text-muted-foreground animate-pulse text-center py-12">
              Waiting for agent output...
            </p>
          )}
          {lines.map((line, i) => (
            <StreamLineItem key={i} line={line} />
          ))}
          <div ref={endRef} />
        </div>
      </ScrollArea>

      <div className="h-11 flex items-center gap-2 px-3 border-t border-border bg-card shrink-0">
        <span className="text-muted-foreground/30 text-xs font-mono">{">"}</span>
        <input
          type="text"
          value={customPrompt}
          onChange={(e) => onCustomPromptChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && customPrompt.trim()) {
              onSendCommand(customPrompt);
              onCustomPromptChange("");
            }
          }}
          placeholder="Send a command to the agent..."
          className="flex-1 bg-transparent text-xs focus:outline-none placeholder:text-muted-foreground/30"
        />
        <button
          onClick={() => {
            if (customPrompt.trim()) {
              onSendCommand(customPrompt);
              onCustomPromptChange("");
            }
          }}
          className="text-muted-foreground/40 hover:text-primary transition-colors"
        >
          <Send className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}

function StreamLineItem({ line }: { line: StreamLine }) {
  if (line.type === "text") {
    return (
      <p className="text-foreground/90 whitespace-pre-wrap leading-relaxed">
        {line.text}
      </p>
    );
  }

  if (line.type === "tool_use") {
    return (
      <div className="flex items-center gap-2 py-0.5">
        <span className="text-[10px] px-1.5 py-0.5 bg-primary/10 text-primary rounded font-medium">
          {line.tool}
        </span>
        <span className="text-muted-foreground/40 text-[10px] truncate">
          {line.input}
        </span>
      </div>
    );
  }

  if (line.type === "tool_result") {
    return (
      <pre className="text-muted-foreground/50 text-[10px] bg-secondary/30 p-2 rounded-md overflow-x-auto max-h-24 overflow-y-auto leading-relaxed">
        {line.text}
      </pre>
    );
  }

  if (line.type === "result") {
    return (
      <div className="mt-2 p-3 border border-primary/20 rounded-lg bg-primary/5">
        <p className="text-primary text-[10px] font-semibold uppercase tracking-wider mb-1">
          Cycle Complete
        </p>
        <p className="text-foreground/70 text-[11px] whitespace-pre-wrap leading-relaxed">
          {line.result}
        </p>
      </div>
    );
  }

  return null;
}
