"use client";

import { useRef, useEffect, useState } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Send,
  Terminal,
  ChevronRight,
  ChevronDown,
  Play,
  CheckCircle2,
  XCircle,
} from "lucide-react";
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
        <div className="p-3 space-y-1">
          {lines.length === 0 && liveStatus !== "running" && (
            <p className="text-muted-foreground/40 text-center py-12 text-xs">
              Run a cycle to see live agent output
            </p>
          )}
          {lines.length === 0 && liveStatus === "running" && (
            <div className="flex items-center justify-center gap-2 py-12">
              <div className="h-1.5 w-1.5 rounded-full bg-primary animate-bounce [animation-delay:0ms]" />
              <div className="h-1.5 w-1.5 rounded-full bg-primary animate-bounce [animation-delay:150ms]" />
              <div className="h-1.5 w-1.5 rounded-full bg-primary animate-bounce [animation-delay:300ms]" />
            </div>
          )}
          {lines.map((line, i) => (
            <StreamLineItem key={i} line={line} nextLine={lines[i + 1]} />
          ))}
          <div ref={endRef} />
        </div>
      </ScrollArea>

      <div className="h-11 flex items-center gap-2 px-3 border-t border-border bg-card shrink-0">
        <span className="text-muted-foreground/30 text-xs font-mono">
          {">"}
        </span>
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

function StreamLineItem({
  line,
  nextLine,
}: {
  line: StreamLine;
  nextLine?: StreamLine;
}) {
  if (line.type === "text") {
    return (
      <div className="py-1.5 px-2">
        <p className="text-[13px] text-foreground/90 leading-relaxed whitespace-pre-wrap">
          {line.text}
        </p>
      </div>
    );
  }

  if (line.type === "tool_use") {
    return <ToolCallBlock line={line} resultLine={nextLine} />;
  }

  if (line.type === "tool_result") {
    return null;
  }

  if (line.type === "result") {
    return (
      <div className="my-2 p-3 border border-primary/20 rounded-lg bg-primary/5">
        <div className="flex items-center gap-2 mb-2">
          <CheckCircle2 className="h-3.5 w-3.5 text-primary" />
          <span className="text-[11px] text-primary font-semibold uppercase tracking-wider">
            Cycle Complete
          </span>
        </div>
        <p className="text-[12px] text-foreground/70 whitespace-pre-wrap leading-relaxed">
          {line.result}
        </p>
      </div>
    );
  }

  return null;
}

function ToolCallBlock({
  line,
  resultLine,
}: {
  line: StreamLine;
  resultLine?: StreamLine;
}) {
  const [expanded, setExpanded] = useState(false);
  const toolName = line.tool || "tool";
  const hasResult = resultLine?.type === "tool_result";
  const resultText = hasResult ? resultLine?.text : undefined;
  const isNoOutput =
    resultText === "(Bash completed with no output)" || !resultText;

  const shortInput = formatToolInput(line.input || "");

  return (
    <div className="my-0.5 rounded-md border border-border/50 bg-secondary/20 overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-2.5 py-1.5 text-left hover:bg-secondary/30 transition-colors"
      >
        <span className="text-muted-foreground/40 shrink-0">
          {expanded ? (
            <ChevronDown className="h-3 w-3" />
          ) : (
            <ChevronRight className="h-3 w-3" />
          )}
        </span>
        <span className="shrink-0">
          <ToolIcon name={toolName} />
        </span>
        <span className="text-[11px] font-medium text-primary/80 shrink-0">
          {toolName}
        </span>
        <span className="text-[10px] text-muted-foreground/40 truncate flex-1 font-mono">
          {shortInput}
        </span>
        {hasResult && (
          <span className="shrink-0">
            {isNoOutput ? (
              <span className="text-[9px] text-muted-foreground/30">
                no output
              </span>
            ) : (
              <CheckCircle2 className="h-3 w-3 text-primary/40" />
            )}
          </span>
        )}
      </button>

      {expanded && (
        <div className="border-t border-border/30 px-3 py-2 space-y-2">
          {line.input && (
            <div>
              <span className="text-[9px] text-muted-foreground/40 uppercase tracking-wider">
                Input
              </span>
              <pre className="text-[10px] text-muted-foreground/60 mt-0.5 font-mono whitespace-pre-wrap break-all leading-relaxed">
                {line.input}
              </pre>
            </div>
          )}
          {resultText && !isNoOutput && (
            <div>
              <span className="text-[9px] text-muted-foreground/40 uppercase tracking-wider">
                Output
              </span>
              <pre className="text-[10px] text-muted-foreground/50 mt-0.5 font-mono whitespace-pre-wrap break-all max-h-32 overflow-y-auto leading-relaxed">
                {resultText}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ToolIcon({ name }: { name: string }) {
  const lower = name.toLowerCase();
  if (lower === "bash") return <Play className="h-3 w-3 text-primary/60" />;
  if (lower.includes("read"))
    return (
      <span className="text-[10px] text-blue-400/60 font-mono font-bold">
        R
      </span>
    );
  if (lower.includes("search") || lower.includes("web"))
    return (
      <span className="text-[10px] text-amber-400/60 font-mono font-bold">
        W
      </span>
    );
  if (lower.includes("write") || lower.includes("edit"))
    return (
      <span className="text-[10px] text-orange-400/60 font-mono font-bold">
        E
      </span>
    );
  return (
    <span className="text-[10px] text-muted-foreground/40 font-mono font-bold">
      T
    </span>
  );
}

function formatToolInput(raw: string): string {
  try {
    const parsed = JSON.parse(raw);
    if (parsed.command) {
      const cmd = parsed.command as string;
      return cmd.length > 80 ? cmd.slice(0, 80) + "..." : cmd;
    }
    if (parsed.query) return parsed.query;
    if (parsed.file_path) return parsed.file_path;
    if (parsed.pattern) return parsed.pattern;
    return raw.length > 80 ? raw.slice(0, 80) + "..." : raw;
  } catch {
    return raw.length > 80 ? raw.slice(0, 80) + "..." : raw;
  }
}
