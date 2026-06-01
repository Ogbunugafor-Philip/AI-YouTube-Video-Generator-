"""Breaking-news discovery + scoring.

Pulls AI/tech stories from several RSS feeds, scores each one with the LLM for
viral potential and relevance, then returns the top stories worth turning into a
video. All network access uses ``requests``; feeds are parsed with feedparser.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, List

import feedparser
import requests

from core.logger import get_logger
from services import llm_service

log = get_logger(__name__)

# (source label, feed URL)
NEWS_FEEDS = [
    ("Google News", "https://news.google.com/rss/search?q=artificial+intelligence&hl=en-US&gl=US&ceid=US:en"),
    ("TechCrunch", "https://techcrunch.com/feed/"),
    ("The Verge", "https://www.theverge.com/rss/index.xml"),
    ("Wired", "https://www.wired.com/feed/rss"),
]

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; VidGenNewsBot/1.0)"}
_FETCH_TIMEOUT = 15
_MAX_PER_FEED = 10  # cap stories pulled per feed to keep scoring costs sane


def _story_id(title: str, url: str) -> str:
    return hashlib.sha1(f"{title}|{url}".encode("utf-8")).hexdigest()[:12]


def _clean_html(text: str) -> str:
    """Strip HTML tags and collapse whitespace from RSS summaries."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def fetch_breaking_news() -> List[Dict[str, Any]]:
    """Fetch and parse every configured RSS feed.

    Returns a combined list of stories, each with: title, summary, url, source,
    published_date. Network/parse failures on one feed never abort the others.
    """
    stories: List[Dict[str, Any]] = []
    for source, url in NEWS_FEEDS:
        try:
            log.info("Fetching feed: %s", source)
            resp = requests.get(url, headers=_HEADERS, timeout=_FETCH_TIMEOUT)
            resp.raise_for_status()
            parsed = feedparser.parse(resp.content)
            entries = parsed.entries[:_MAX_PER_FEED]
            for entry in entries:
                title = _clean_html(getattr(entry, "title", "")).strip()
                if not title:
                    continue
                summary = _clean_html(
                    getattr(entry, "summary", "") or getattr(entry, "description", "")
                )
                link = getattr(entry, "link", "")
                published = (
                    getattr(entry, "published", "")
                    or getattr(entry, "updated", "")
                    or ""
                )
                stories.append(
                    {
                        "story_id": _story_id(title, link),
                        "title": title,
                        "summary": summary[:1200],
                        "url": link,
                        "source": source,
                        "published_date": published,
                    }
                )
            log.info("  %s: %d stories", source, len(entries))
        except (requests.RequestException, Exception) as exc:  # noqa: BLE001
            log.error("Failed to fetch %s: %s", source, exc)
            continue
    log.info("Fetched %d stories total", len(stories))
    return stories


def score_story(story: Dict[str, Any]) -> Dict[str, Any]:
    """Score one story with the LLM and return it enriched with scoring fields.

    Adds: viral_score, relevance_score, estimated_views, recommended_duration,
    suggested_title. On any failure, returns the story with safe zero scores so
    it is naturally filtered out downstream.
    """
    prompt = (
        "You are a YouTube growth strategist for an AI/tech news channel. Score "
        "the following news story. Respond with ONLY a JSON object with keys:\n"
        '  "viral_score": int 1-10 (breaking news, controversy, major '
        "announcements score higher),\n"
        '  "relevance_score": int 1-10 (must be directly about AI, ML, or major '
        "tech to score high),\n"
        '  "estimated_views": one of "low" (1k-10k), "medium" (10k-100k), '
        '"high" (100k+),\n'
        '  "recommended_duration": one of 3, 4, 5 (minutes),\n'
        '  "suggested_title": a catchy, curiosity-driven YouTube title string.\n\n'
        f"STORY TITLE: {story.get('title', '')}\n"
        f"SOURCE: {story.get('source', '')}\n"
        f"SUMMARY: {story.get('summary', '')}"
    )
    enriched = dict(story)
    try:
        raw = llm_service.chat(
            [{"role": "user", "content": prompt}], temperature=0.3, max_tokens=512
        )
        data = llm_service.parse_json(raw)
        enriched["viral_score"] = int(data.get("viral_score", 0))
        enriched["relevance_score"] = int(data.get("relevance_score", 0))
        enriched["estimated_views"] = str(data.get("estimated_views", "low")).lower()
        dur = int(data.get("recommended_duration", 3))
        enriched["recommended_duration"] = dur if dur in (3, 4, 5) else 3
        enriched["suggested_title"] = (
            str(data.get("suggested_title", "")).strip() or story.get("title", "")
        )
    except Exception as exc:  # noqa: BLE001
        log.error("Scoring failed for %r: %s", story.get("title", "")[:60], exc)
        enriched.update(
            viral_score=0,
            relevance_score=0,
            estimated_views="low",
            recommended_duration=3,
            suggested_title=story.get("title", ""),
        )
    return enriched


def _dedupe_by_title(stories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Drop near-duplicate stories by normalised title."""
    seen: set[str] = set()
    unique: List[Dict[str, Any]] = []
    for s in stories:
        key = re.sub(r"[^a-z0-9 ]", "", s.get("title", "").lower()).strip()
        # Collapse to first 8 significant words for fuzzy matching.
        key = " ".join(key.split()[:8])
        if key and key not in seen:
            seen.add(key)
            unique.append(s)
    return unique


def get_top_stories() -> List[Dict[str, Any]]:
    """Fetch, score, filter, dedupe — return the top 3 stories by viral score.

    Filter: viral_score >= 7 AND relevance_score >= 7.
    """
    raw_stories = fetch_breaking_news()
    raw_stories = _dedupe_by_title(raw_stories)

    scored = [score_story(s) for s in raw_stories]
    qualified = [
        s for s in scored
        if s.get("viral_score", 0) >= 7 and s.get("relevance_score", 0) >= 7
    ]
    qualified.sort(key=lambda s: s.get("viral_score", 0), reverse=True)
    top = qualified[:3]
    log.info(
        "Top stories: %d qualified of %d scored (returning %d)",
        len(qualified), len(scored), len(top),
    )
    return top
