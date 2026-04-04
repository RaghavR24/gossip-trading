"use client";

import { useRef, useEffect, useState } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Newspaper, ExternalLink } from "lucide-react";
import type { NewsArticle } from "@/lib/types";

interface NewsFeedProps {
  news: NewsArticle[];
}

export function NewsFeed({ news }: NewsFeedProps) {
  const [lastSeenId, setLastSeenId] = useState<number>(0);
  const [newIds, setNewIds] = useState<Set<number>>(new Set());
  const prevNewsRef = useRef<NewsArticle[]>([]);

  useEffect(() => {
    if (prevNewsRef.current.length > 0 && news.length > 0) {
      const prevTopId = prevNewsRef.current[0]?.id ?? 0;
      const fresh = news.filter((n) => n.id > prevTopId);
      if (fresh.length > 0) {
        setNewIds(new Set(fresh.map((n) => n.id)));
        setTimeout(() => setNewIds(new Set()), 2500);
      }
    }
    if (news.length > 0 && lastSeenId === 0) {
      setLastSeenId(news[0].id);
    }
    prevNewsRef.current = news;
  }, [news, lastSeenId]);

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
        <span className="text-[10px] text-muted-foreground/60 font-mono">
          {news.length}
        </span>
      </div>

      <ScrollArea className="flex-1">
        {news.length === 0 && (
          <p className="text-xs text-muted-foreground/40 text-center py-12">
            No news scraped yet
          </p>
        )}

        {featured && (
          <div
            className={`p-4 border-b border-border ${newIds.has(featured.id) ? "news-new" : ""}`}
          >
            <div className="flex items-center gap-2 mb-2">
              <Badge variant="secondary" className="text-[9px] h-4 px-1.5">
                {featured.source}
              </Badge>
              {featured.keyword && (
                <Badge
                  variant="outline"
                  className="text-[9px] h-4 px-1.5 text-primary border-primary/30"
                >
                  {featured.keyword}
                </Badge>
              )}
              <span className="text-[10px] text-muted-foreground/40 ml-auto">
                {formatRelativeTime(featured.timestamp)}
              </span>
            </div>
            {featured.url ? (
              <a
                href={featured.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm font-medium hover:text-primary transition-colors leading-snug flex items-start gap-1.5 group"
              >
                {featured.title}
                <ExternalLink className="h-3 w-3 mt-0.5 opacity-0 group-hover:opacity-100 transition-opacity shrink-0" />
              </a>
            ) : (
              <p className="text-sm font-medium leading-snug">{featured.title}</p>
            )}
            {featured.snippet && (
              <p className="text-[11px] text-muted-foreground/60 mt-2 leading-relaxed line-clamp-3">
                {featured.snippet}
              </p>
            )}
          </div>
        )}

        <div className="divide-y divide-border/50">
          {rest.map((n) => (
            <div
              key={n.id}
              className={`px-3 py-2.5 hover:bg-secondary/30 transition-colors ${newIds.has(n.id) ? "news-new" : ""}`}
            >
              <div className="flex items-center gap-2 mb-1">
                <span className="text-[9px] text-muted-foreground/40 font-mono shrink-0">
                  {formatRelativeTime(n.timestamp)}
                </span>
                <Badge
                  variant="secondary"
                  className="text-[8px] h-3.5 px-1 rounded"
                >
                  {n.source}
                </Badge>
                {n.keyword && (
                  <span className="text-[9px] text-primary/60">{n.keyword}</span>
                )}
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
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}
