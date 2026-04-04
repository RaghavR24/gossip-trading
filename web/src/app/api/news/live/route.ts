import { NextResponse } from "next/server";

const TOPICS = [
  "financial markets today",
  "trump tariffs",
  "economy news",
  "prediction markets",
  "crypto regulation",
  "federal reserve",
];

interface RssItem {
  title: string;
  url: string;
  source: string;
  snippet: string;
  timestamp: string;
  image: string | null;
}

function parseRssItems(xml: string): RssItem[] {
  const items: RssItem[] = [];
  const itemRegex = /<item>([\s\S]*?)<\/item>/g;
  let match;
  while ((match = itemRegex.exec(xml)) !== null) {
    const block = match[1];
    const title = block.match(/<title><!\[CDATA\[(.*?)\]\]><\/title>/)?.[1]
      || block.match(/<title>(.*?)<\/title>/)?.[1]
      || "";
    const link = block.match(/<link>(.*?)<\/link>/)?.[1]
      || block.match(/<link\/>(.*?)(?=<)/)?.[1]
      || "";
    const pubDate = block.match(/<pubDate>(.*?)<\/pubDate>/)?.[1] || "";
    const source = block.match(/<source[^>]*>(.*?)<\/source>/)?.[1]
      || block.match(/<source[^>]*><!\[CDATA\[(.*?)\]\]><\/source>/)?.[1]
      || "Google News";
    const description = block.match(/<description><!\[CDATA\[(.*?)\]\]><\/description>/)?.[1]
      || block.match(/<description>(.*?)<\/description>/)?.[1]
      || "";

    const cleanTitle = title.replace(/<[^>]*>/g, "").trim();
    const cleanDesc = description.replace(/<[^>]*>/g, "").trim();

    if (cleanTitle) {
      items.push({
        title: cleanTitle,
        url: link,
        source,
        snippet: cleanDesc.slice(0, 200),
        timestamp: pubDate ? new Date(pubDate).toISOString() : new Date().toISOString(),
        image: null,
      });
    }
  }
  return items;
}

async function fetchOgImage(url: string): Promise<string | null> {
  try {
    const res = await fetch(url, {
      signal: AbortSignal.timeout(3000),
      headers: { "User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1)" },
      redirect: "follow",
    });
    if (!res.ok) return null;
    const text = await res.text();
    const head = text.slice(0, 15000);
    const ogMatch = head.match(/<meta[^>]*property=["']og:image["'][^>]*content=["']([^"']+)["']/i)
      || head.match(/<meta[^>]*content=["']([^"']+)["'][^>]*property=["']og:image["']/i);
    return ogMatch?.[1] || null;
  } catch {
    return null;
  }
}

let cache: { items: RssItem[]; fetchedAt: number } = { items: [], fetchedAt: 0 };
const CACHE_TTL = 120_000;

export async function GET() {
  const now = Date.now();
  if (cache.items.length > 0 && now - cache.fetchedAt < CACHE_TTL) {
    return NextResponse.json(cache.items);
  }

  const allItems: RssItem[] = [];

  const fetches = TOPICS.map(async (topic) => {
    try {
      const encoded = encodeURIComponent(topic);
      const res = await fetch(
        `https://news.google.com/rss/search?q=${encoded}&hl=en-US&gl=US&ceid=US:en`,
        { signal: AbortSignal.timeout(5000) }
      );
      if (!res.ok) return [];
      const xml = await res.text();
      return parseRssItems(xml).slice(0, 5);
    } catch {
      return [];
    }
  });

  const results = await Promise.all(fetches);
  for (const items of results) {
    allItems.push(...items);
  }

  allItems.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());

  const deduped = allItems.filter(
    (item, i, arr) => arr.findIndex((x) => x.title === item.title) === i
  );

  const top = deduped.slice(0, 30);

  const imageResults = await Promise.allSettled(
    top.map((item) => fetchOgImage(item.url))
  );
  for (let i = 0; i < top.length; i++) {
    const r = imageResults[i];
    if (r.status === "fulfilled" && r.value) {
      top[i].image = r.value;
    }
  }

  cache = { items: top, fetchedAt: now };
  return NextResponse.json(cache.items);
}
