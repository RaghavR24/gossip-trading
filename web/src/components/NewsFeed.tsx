"use client";

import { useRef, useEffect, useState } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Newspaper, ExternalLink, Rss } from "lucide-react";
import type { NewsArticle } from "@/lib/types";

interface NewsFeedProps {
  news: NewsArticle[];
}

export function NewsFeed({ news }: NewsFeedProps) {
  const [newIds, setNewIds] = useState<Set<number>>(new Set());
  const prevNewsRef = useRef<NewsArticle[]>([]);

  useEffect(() => {
    if (prevNewsRef.current.length > 0 && news.length > 0) {
      const prevTitles = new Set(prevNewsRef.current.map((n) => n.title));
      const fresh = news.filter((n) => !prevTitles.has(n.title));
      if (fresh.length > 0) {
        setNewIds(new Set(fresh.map((n) => n.id)));
        setTimeout(() => setNewIds(new Set()), 3000);
      }
    }
    prevNewsRef.current = news;
  }, [news]);

  const featured = news[0];
  const rest = news.slice(1);

  return (
    <div className="flex flex-col h-full">
      <div className="h-9 flex items-center justify-between px-3 border-b border-border bg-card shrink-0">
        <div className="flex items-center gap-2">
          <Newspaper className="h-3.5 w-3.5 text-muted-foreground" />
          <span className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
            News Feed
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="flex items-center gap-1 text-[10px] text-primary/70">
            <Rss className="h-2.5 w-2.5" />
            Live
          </span>
          <span className="text-[10px] text-muted-foreground/40 font-mono">
            {news.length}
          </span>
        </div>
      </div>

      <ScrollArea className="flex-1">
        {news.length === 0 && (
          <div className="flex flex-col items-center justify-center py-16 px-4">
            <Rss className="h-8 w-8 text-muted-foreground/20 mb-3" />
            <p className="text-xs text-muted-foreground/40 text-center">
              Fetching latest news...
            </p>
          </div>
        )}

        {featured && (
          <div
            className={`p-4 border-b border-border ${newIds.has(featured.id) ? "news-new" : ""}`}
          >
            <div className="flex items-center gap-2 mb-2">
              <Badge variant="secondary" className="text-[9px] h-4 px-1.5 font-normal">
                {featured.source}
              </Badge>
              {featured.keyword && (
                <Badge
                  variant="outline"
                  className="text-[9px] h-4 px-1.5 text-primary border-primary/20 font-normal"
                >
                  {featured.keyword}
                </Badge>
              )}
              <span className="text-[10px] text-muted-foreground/40 ml-auto shrink-0">
                {formatRelativeTime(featured.timestamp)}
              </span>
            </div>
            {featured.url ? (
              <a
                href={featured.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-[13px] font-medium leading-snug hover:text-primary transition-colors flex items-start gap-1.5 group"
              >
                <span className="line-clamp-3">{featured.title}</span>
                <ExternalLink className="h-3 w-3 mt-0.5 opacity-0 group-hover:opacity-100 transition-opacity shrink-0" />
              </a>
            ) : (
              <p className="text-[13px] font-medium leading-snug line-clamp-3">
                {featured.title}
              </p>
            )}
            {featured.snippet && (
              <p className="text-[11px] text-muted-foreground/50 mt-2 leading-relaxed line-clamp-2">
                {featured.snippet}
              </p>
            )}
          </div>
        )}

        <div className="divide-y divide-border/30">
          {rest.map((n) => (
            <div
              key={n.id || n.title}
              className={`px-3 py-2.5 hover:bg-secondary/30 transition-colors ${newIds.has(n.id) ? "news-new" : ""}`}
            >
              <div className="flex items-center gap-1.5 mb-1">
                <span className="text-[9px] text-muted-foreground/40 font-mono shrink-0 w-10">
                  {formatRelativeTime(n.timestamp)}
                </span>
                <span className="text-[9px] text-muted-foreground/50 truncate">
                  {n.source}
                </span>
              </div>
              {n.url ? (
                <a
                  href={n.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-[11px] text-foreground/80 hover:text-primary transition-colors leading-snug line-clamp-2"
                >
                  {n.title}
                </a>
              ) : (
                <p className="text-[11px] text-foreground/80 leading-snug line-clamp-2">
                  {n.title}
                </p>
              )}
            </div>
          ))}
        </div>
      </ScrollArea>
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
