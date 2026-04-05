"""
News intelligence layer — Apify-powered scraping for Google News, Twitter/X, and web search.

CLI tool invoked by Claude Code agent:
    python3 gossip/news.py --keywords "bitcoin,tariff,cpi"
    python3 gossip/news.py --keywords "trump tariff" --hours 2
    python3 gossip/news.py --trending
    python3 gossip/news.py --source google --keywords "federal reserve"
    python3 gossip/news.py --source twitter --keywords "kalshi,polymarket"

All output is JSON to stdout. Logs go to stderr.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

from apify_client import ApifyClient
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

def log(msg: str) -> None:
    print(msg, file=sys.stderr)

def get_client() -> ApifyClient:
    token = os.getenv("APIFY_API_TOKEN", "")
    if not token:
        log("WARNING: APIFY_API_TOKEN not set")
        return ApifyClient("")
    return ApifyClient(token)


def scrape_google_news(keywords: list[str], hours_back: int = 4, max_results: int = 30) -> list[dict]:
    client = get_client()
    queries = [f"{kw} news" for kw in keywords]

    try:
        run = client.actor("apify/google-search-scraper").call(
            run_input={
                "queries": "\n".join(queries),
                "maxPagesPerQuery": 1,
                "resultsPerPage": max_results,
                "languageCode": "en",
                "countryCode": "us",
            },
            timeout_secs=120,
        )
    except Exception as e:
        log(f"Google News scrape failed: {e}")
        return []

    articles = []
    seen_urls = set()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)

    for item in client.dataset(run["defaultDatasetId"]).iterate_items():
        organic = item.get("organicResults", [])
        for r in organic:
            url = r.get("url", "")
            if url in seen_urls:
                continue
            seen_urls.add(url)

            articles.append({
                "title": r.get("title", ""),
                "url": url,
                "snippet": r.get("description", ""),
                "source": "google",
                "keyword": item.get("searchQuery", {}).get("term", ""),
                "position": r.get("position", 0),
            })

    return articles[:max_results]


def scrape_twitter(keywords: list[str], hours_back: int = 2, max_results: int = 20) -> list[dict]:
    """Search Twitter/X via Apify. Uses data-slayer~twitter-search (same actor as dashboard)."""
    token = os.getenv("APIFY_API_TOKEN", "")
    if not token:
        log("WARNING: APIFY_API_TOKEN not set")
        return []

    query = " OR ".join(f"({kw})" for kw in keywords)
    try:
        import urllib.request
        url = f"https://api.apify.com/v2/acts/data-slayer~twitter-search/run-sync-get-dataset-items?token={token}&timeout=120"
        req = urllib.request.Request(url, method="POST",
            data=json.dumps({"query": query, "maxResults": max_results}).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=130) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        log(f"Twitter scrape failed: {e}")
        return []

    if not isinstance(data, list):
        return []

    tweets = []
    for item in data:
        text = item.get("text", "")
        if not text:
            continue
        user_info = item.get("user_info", {})
        tweets.append({
            "text": text,
            "author": item.get("screen_name", ""),
            "author_name": user_info.get("name", item.get("screen_name", "")),
            "likes": item.get("favorites", 0),
            "retweets": item.get("retweets", 0),
            "replies": item.get("replies", 0),
            "url": f"https://x.com/{item.get('screen_name', '')}/status/{item.get('tweet_id', '')}",
            "source": "twitter",
            "created_at": item.get("created_at", ""),
        })

    tweets.sort(key=lambda t: t.get("likes", 0), reverse=True)
    return tweets[:max_results]


def scrape_truthsocial(username: str = "realDonaldTrump", max_results: int = 25) -> list[dict]:
    """Scrape Truth Social posts via Apify. Same actor as dashboard."""
    token = os.getenv("APIFY_API_TOKEN", "")
    if not token:
        return []

    try:
        import urllib.request
        url = f"https://api.apify.com/v2/acts/muhammetakkurtt~truth-social-scraper/run-sync-get-dataset-items?token={token}&timeout=60"
        req = urllib.request.Request(url, method="POST",
            data=json.dumps({"username": username, "maxPosts": max_results}).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=70) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        log(f"Truth Social scrape failed: {e}")
        return []

    if not isinstance(data, list):
        return []

    import re
    def strip_html(html: str) -> str:
        return re.sub(r'<[^>]+>', '', html).replace('&amp;', '&').strip()

    posts = []
    for item in data:
        if item.get("visibility") != "public":
            continue
        account = item.get("account", {})
        posts.append({
            "text": strip_html(item.get("content", "")),
            "author": account.get("username", username),
            "likes": item.get("favourites_count", 0),
            "reposts": item.get("reblogs_count", 0),
            "url": item.get("url", f"https://truthsocial.com/@{username}/{item.get('id', '')}"),
            "source": "truthsocial",
            "created_at": item.get("created_at", ""),
        })

    return posts[:max_results]


def scrape_reddit(subreddits: list[str] | None = None, max_results: int = 40) -> list[dict]:
    """Scrape Reddit hot posts via Apify. Same actor as dashboard."""
    token = os.getenv("APIFY_API_TOKEN", "")
    if not token:
        return []

    default_subs = [
        "https://www.reddit.com/r/wallstreetbets/hot/",
        "https://www.reddit.com/r/politics/hot/",
        "https://www.reddit.com/r/news/hot/",
        "https://www.reddit.com/r/worldnews/hot/",
        "https://www.reddit.com/r/economics/hot/",
    ]
    urls = [{"url": u} for u in (subreddits or default_subs)]

    try:
        import urllib.request
        url = f"https://api.apify.com/v2/acts/trudax~reddit-scraper-lite/run-sync-get-dataset-items?token={token}&timeout=60"
        req = urllib.request.Request(url, method="POST",
            data=json.dumps({"startUrls": urls, "maxItems": 150}).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=70) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        log(f"Reddit scrape failed: {e}")
        return []

    if not isinstance(data, list):
        return []

    posts = []
    for item in data:
        if item.get("dataType") != "post" or not item.get("title"):
            continue
        posts.append({
            "text": item.get("title", ""),
            "body": (item.get("body", "") or "")[:500],
            "author": item.get("username", ""),
            "subreddit": item.get("communityName", ""),
            "upvotes": item.get("upVotes", 0),
            "comments": item.get("numberOfComments", 0),
            "url": item.get("url", ""),
            "source": "reddit",
            "created_at": item.get("createdAt", ""),
        })

    posts.sort(key=lambda p: p.get("upvotes", 0), reverse=True)
    return posts[:max_results]


def scrape_web_search(keywords: list[str], max_results: int = 20) -> list[dict]:
    client = get_client()

    try:
        run = client.actor("apify/google-search-scraper").call(
            run_input={
                "queries": "\n".join(keywords),
                "maxPagesPerQuery": 1,
                "resultsPerPage": max_results,
                "languageCode": "en",
                "countryCode": "us",
            },
            timeout_secs=120,
        )
    except Exception as e:
        log(f"Web search failed: {e}")
        return []

    results = []
    seen = set()
    for item in client.dataset(run["defaultDatasetId"]).iterate_items():
        for r in item.get("organicResults", []):
            url = r.get("url", "")
            if url in seen:
                continue
            seen.add(url)
            results.append({
                "title": r.get("title", ""),
                "url": url,
                "snippet": r.get("description", ""),
                "source": "web",
                "keyword": item.get("searchQuery", {}).get("term", ""),
            })

    return results[:max_results]


def scrape_news_articles(urls: list[str]) -> list[dict]:
    """Use Apify web scraper to extract article text from URLs."""
    client = get_client()

    try:
        run = client.actor("apify/website-content-crawler").call(
            run_input={
                "startUrls": [{"url": u} for u in urls[:10]],
                "maxCrawlPages": len(urls),
                "crawlerType": "cheerio",
            },
            timeout_secs=180,
        )
    except Exception as e:
        log(f"Article scrape failed: {e}")
        return []

    articles = []
    for item in client.dataset(run["defaultDatasetId"]).iterate_items():
        articles.append({
            "url": item.get("url", ""),
            "title": item.get("metadata", {}).get("title", ""),
            "text": item.get("text", "")[:3000],
            "source": "article",
        })

    return articles


# --- Default keyword sets ---

BASE_KEYWORDS = [
    "breaking news today",
    "financial markets today",
]

def main():
    parser = argparse.ArgumentParser(description="News intelligence scraper")
    parser.add_argument("--keywords", type=str, default=None, help="Comma-separated keywords")
    parser.add_argument("--hours", type=int, default=4, help="Hours to look back")
    parser.add_argument("--source", choices=["google", "twitter", "truthsocial", "reddit", "web", "article", "all"], default="google")
    parser.add_argument("--limit", type=int, default=30, help="Max results")
    parser.add_argument("--trending", action="store_true", help="Use base trending keywords")
    parser.add_argument("--urls", type=str, default=None, help="Comma-separated URLs to scrape article text from")

    args = parser.parse_args()

    if args.urls:
        urls = [u.strip() for u in args.urls.split(",")]
        results = scrape_news_articles(urls)
        print(json.dumps(results, indent=2))
        return

    keywords = BASE_KEYWORDS if args.trending else []
    if args.keywords:
        keywords = [k.strip() for k in args.keywords.split(",")]

    if not keywords:
        keywords = BASE_KEYWORDS

    results = []
    if args.source in ("google", "all"):
        results.extend(scrape_google_news(keywords, args.hours, args.limit))
    if args.source in ("twitter", "all"):
        results.extend(scrape_twitter(keywords, args.hours, args.limit))
    if args.source in ("truthsocial",):
        results.extend(scrape_truthsocial())
    if args.source in ("reddit",):
        results.extend(scrape_reddit())
    if args.source in ("web", "all"):
        results.extend(scrape_web_search(keywords, args.limit))

    # persist to DB
    if results:
        try:
            import sys as _sys
            _sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
            from gossip.db import GossipDB
            db = GossipDB()
            db.insert_news(results)
        except Exception as e:
            log(f"DB write failed: {e}")

    print(json.dumps(results[:args.limit], indent=2))


if __name__ == "__main__":
    main()
