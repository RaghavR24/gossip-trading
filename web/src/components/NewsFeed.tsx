"use client";

import { useRef, useEffect, useState } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Rss, ExternalLink } from "lucide-react";
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
          <Rss className="h-3.5 w-3.5 text-muted-foreground" />
          <span className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
            News Feed
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="flex items-center gap-1 text-[10px] text-primary/70">
            <span className="w-1.5 h-1.5 rounded-full bg-primary pulse-glow" />
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
          <FeaturedArticle article={featured} isNew={newIds.has(featured.id)} />
        )}

        <div className="divide-y divide-border/20">
          {rest.map((n) => (
            <NewsRow
              key={n.id || n.title}
              article={n}
              isNew={newIds.has(n.id)}
            />
          ))}
        </div>
      </ScrollArea>
    </div>
  );
}

function FeaturedArticle({
  article: n,
  isNew,
}: {
  article: NewsArticle;
  isNew: boolean;
}) {
  const domain = extractDomain(n.url);

  return (
    <a
      href={n.url || undefined}
      target="_blank"
      rel="noopener noreferrer"
      className={`block border-b border-border hover:bg-secondary/20 transition-colors group ${isNew ? "news-new" : ""}`}
    >
      {n.image && (
        <ArticleImage src={n.image} alt={n.title} className="w-full h-36 object-cover" />
      )}
      <div className="p-3">
        <div className="flex items-center gap-2 mb-1.5">
          {domain && <SourceIcon domain={domain} />}
          <span className="text-[10px] text-muted-foreground/60 font-medium">
            {n.source || domain}
          </span>
          <span className="text-[10px] text-muted-foreground/30 ml-auto">
            {formatRelativeTime(n.timestamp)}
          </span>
        </div>
        <h3 className="text-[13px] font-medium leading-snug text-foreground group-hover:text-primary transition-colors line-clamp-2">
          {n.title}
        </h3>
        {n.snippet && !n.snippet.startsWith("&lt;") && (
          <p className="text-[11px] text-muted-foreground/40 mt-1 leading-relaxed line-clamp-2">
            {n.snippet}
          </p>
        )}
      </div>
    </a>
  );
}

function NewsRow({
  article: n,
  isNew,
}: {
  article: NewsArticle;
  isNew: boolean;
}) {
  const domain = extractDomain(n.url);
  const hasImage = !!n.image;

  return (
    <a
      href={n.url || undefined}
      target="_blank"
      rel="noopener noreferrer"
      className={`flex items-start gap-2.5 px-3 py-2.5 hover:bg-secondary/20 transition-colors group ${isNew ? "news-new" : ""}`}
    >
      {hasImage ? (
        <ArticleImage
          src={n.image!}
          alt=""
          className="w-16 h-12 rounded object-cover shrink-0 mt-0.5"
        />
      ) : domain ? (
        <div className="mt-0.5 shrink-0">
          <SourceIcon domain={domain} size={14} />
        </div>
      ) : null}
      <div className="flex-1 min-w-0">
        <p className="text-[11px] text-foreground/80 group-hover:text-primary transition-colors leading-snug line-clamp-2">
          {n.title}
        </p>
        <div className="flex items-center gap-1.5 mt-0.5">
          {hasImage && domain && <SourceIcon domain={domain} size={10} />}
          <span className="text-[9px] text-muted-foreground/40">
            {n.source || domain}
          </span>
          <span className="text-[9px] text-muted-foreground/20">·</span>
          <span className="text-[9px] text-muted-foreground/30">
            {formatRelativeTime(n.timestamp)}
          </span>
        </div>
      </div>
      <ExternalLink className="h-3 w-3 text-muted-foreground/0 group-hover:text-muted-foreground/30 transition-colors mt-0.5 shrink-0" />
    </a>
  );
}

function ArticleImage({
  src,
  alt,
  className,
}: {
  src: string;
  alt: string;
  className?: string;
}) {
  const [errored, setErrored] = useState(false);

  if (errored) return null;

  return (
    <img
      src={src}
      alt={alt}
      className={className}
      onError={() => setErrored(true)}
      loading="lazy"
    />
  );
}

function SourceIcon({ domain, size = 16 }: { domain: string; size?: number }) {
  const [errored, setErrored] = useState(false);

  if (errored) {
    return (
      <div
        className="rounded bg-secondary/50 flex items-center justify-center text-[8px] font-bold text-muted-foreground/40 uppercase"
        style={{ width: size, height: size }}
      >
        {domain[0]}
      </div>
    );
  }

  return (
    <img
      src={`https://www.google.com/s2/favicons?domain=${domain}&sz=${size * 2}`}
      alt=""
      width={size}
      height={size}
      className="rounded"
      onError={() => setErrored(true)}
    />
  );
}

function extractDomain(url: string): string {
  if (!url) return "";
  try {
    const u = new URL(url.startsWith("http") ? url : `https://${url}`);
    return u.hostname.replace("www.", "");
  } catch {
    return "";
  }
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
