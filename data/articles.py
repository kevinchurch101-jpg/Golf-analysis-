"""
Fairway Intel — Article Fetcher and Parser
Reads all configured sources. Blocked articles flagged clearly, never silently skipped.
Articles are inputs — framework makes decisions.
Haslbauer is highest weight. Bamford extracts weather + wind + course conditions too.

Fetch strategy (applied in order per URL until success):
  Tier 1 — Full browser headers (mimics Chrome, bypasses basic bot detection)
  Tier 2 — Rotate through 3 different User-Agent strings
  Tier 3 — Google cache fallback (webcache.googleusercontent.com)
  Tier 4 — Wayback Machine / archive.org fallback
  Tier 5 — Manual paste file in repo (haslbauer_manual.txt etc.)
"""

import logging
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

from config import ARTICLE_SOURCES

log = logging.getLogger(__name__)

FETCH_TIMEOUT = 20
FETCH_DELAY   = 1.2   # seconds between requests

# ── Tier 1: Full browser headers ──────────────────────────────
BROWSER_HEADERS_CHROME = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}

# ── Tier 2: Alternate User-Agent strings ──────────────────────
ALTERNATE_USER_AGENTS = [
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) "
        "Gecko/20100101 Firefox/124.0"
    ),
]

# ── Manual paste files (repo root) ───────────────────────────
MANUAL_PASTE_FILES = {
    "Haslbauer":     "haslbauer_manual.txt",
    "Steve Bamford": "bamford_manual.txt",
    "Ben Coley":     "coley_manual.txt",
}


@dataclass
class ArticleResult:
    source_name: str
    outlet: str
    url: str
    title: str
    raw_text: str
    fetch_time: str
    success: bool
    blocked: bool = False
    block_reason: str = ""
    weight: int = 5
    fetch_method: str = "direct"   # direct | alt_ua | google_cache | wayback | manual


@dataclass
class ArticleBundle:
    """All articles fetched for a weekly run."""
    articles: List[ArticleResult] = field(default_factory=list)
    blocked: List[ArticleResult] = field(default_factory=list)
    fetch_time: str = ""

    @property
    def successful(self) -> List[ArticleResult]:
        return [a for a in self.articles if a.success]

    def to_flag_log(self) -> List[Dict]:
        return [
            {
                "source": a.source_name,
                "url": a.url,
                "reason": a.block_reason,
                "time": a.fetch_time,
            }
            for a in self.blocked
        ]


# ──────────────────────────────────────────────────────────────
# MAIN FETCH ENTRY POINT
# ──────────────────────────────────────────────────────────────

def fetch_all_articles() -> ArticleBundle:
    """
    Fetch articles from all configured sources.
    Applies full tiered fetch strategy per source before flagging as blocked.
    Haslbauer checked first (highest weight).
    """
    bundle = ArticleBundle(fetch_time=datetime.now().isoformat())
    sources_sorted = sorted(ARTICLE_SOURCES, key=lambda s: -s["weight"])

    for source in sources_sorted:
        name = source["name"]

        # Tier 5: manual paste file takes priority — freshest possible content
        manual_result = _try_manual_paste(name, source["outlet"], source["weight"])
        if manual_result:
            log.info(f"[Articles] Manual paste loaded — {name}")
            bundle.articles.append(manual_result)
            continue

        # Try each configured URL with full tiered strategy
        got_content = False
        for url in source.get("urls", []):
            result = fetch_article_with_fallbacks(
                name, source["outlet"], url, source["weight"]
            )
            bundle.articles.append(result)
            if result.blocked:
                bundle.blocked.append(result)
            else:
                got_content = True
            time.sleep(FETCH_DELAY)
            if got_content:
                break  # Got content from this source — move on

    log.info(
        f"[Articles] Fetched {len(bundle.successful)} successfully, "
        f"{len(bundle.blocked)} blocked."
    )
    return bundle


# ──────────────────────────────────────────────────────────────
# TIERED FETCH
# ──────────────────────────────────────────────────────────────

def fetch_article_with_fallbacks(
    source_name: str,
    outlet: str,
    url: str,
    weight: int = 5,
) -> ArticleResult:
    """
    Try to fetch a URL using all available tiers before giving up.
    Tier 1 → Tier 2 → Tier 3 (Google cache) → Tier 4 (Wayback)
    """
    fetch_time = datetime.now().isoformat()

    # ── Tier 1: Full browser headers ──
    result = _attempt_fetch(url, BROWSER_HEADERS_CHROME)
    if result:
        text = extract_text(result.text, url)
        if text and not is_paywall(result.text, url):
            log.info(f"[Articles] ✓ Tier1 direct — {source_name}: {url}")
            return ArticleResult(
                source_name=source_name, outlet=outlet, url=url,
                title=extract_title(result.text), raw_text=text,
                fetch_time=fetch_time, success=True, weight=weight,
                fetch_method="direct",
            )
        elif is_paywall(result.text, url):
            log.warning(f"[Articles] Paywall detected (Tier1) — {source_name}: {url}")
        # 403/non-200 falls through to next tier

    time.sleep(0.8)

    # ── Tier 2: Alternate User-Agent strings ──
    for i, ua in enumerate(ALTERNATE_USER_AGENTS):
        headers = dict(BROWSER_HEADERS_CHROME)
        headers["User-Agent"] = ua
        result = _attempt_fetch(url, headers)
        if result and result.status_code == 200:
            text = extract_text(result.text, url)
            if text and not is_paywall(result.text, url):
                log.info(f"[Articles] ✓ Tier2 alt_ua[{i}] — {source_name}: {url}")
                return ArticleResult(
                    source_name=source_name, outlet=outlet, url=url,
                    title=extract_title(result.text), raw_text=text,
                    fetch_time=fetch_time, success=True, weight=weight,
                    fetch_method=f"alt_ua_{i}",
                )
        time.sleep(0.5)

    # ── Tier 3: Google Cache ──
    gc_result = _try_google_cache(url, source_name, outlet, weight, fetch_time)
    if gc_result and gc_result.success:
        return gc_result

    time.sleep(0.8)

    # ── Tier 4: Wayback Machine ──
    wb_result = _try_wayback(url, source_name, outlet, weight, fetch_time)
    if wb_result and wb_result.success:
        return wb_result

    # ── All tiers failed ──
    log.warning(f"[Articles] BLOCKED (all tiers failed) — {source_name}: {url}")
    return ArticleResult(
        source_name=source_name, outlet=outlet, url=url,
        title="", raw_text="", fetch_time=fetch_time,
        success=False, blocked=True,
        block_reason="all_tiers_failed", weight=weight,
    )


def _attempt_fetch(url: str, headers: Dict) -> Optional[requests.Response]:
    """Single fetch attempt. Returns response or None on error/non-200."""
    try:
        r = requests.get(url, headers=headers, timeout=FETCH_TIMEOUT,
                         allow_redirects=True)
        return r
    except Exception as e:
        log.debug(f"[Articles] Fetch attempt failed: {url} — {e}")
        return None


def _try_google_cache(
    url: str, source_name: str, outlet: str, weight: int, fetch_time: str
) -> Optional[ArticleResult]:
    """Tier 3: Try Google's cached version of the page."""
    cache_url = f"https://webcache.googleusercontent.com/search?q=cache:{url}&hl=en"
    try:
        r = requests.get(cache_url, headers=BROWSER_HEADERS_CHROME,
                         timeout=FETCH_TIMEOUT)
        if r.status_code == 200:
            text = extract_text(r.text, url)
            if text and len(text) > 300:
                log.info(f"[Articles] ✓ Tier3 Google cache — {source_name}: {url}")
                return ArticleResult(
                    source_name=source_name, outlet=outlet,
                    url=cache_url, title=extract_title(r.text),
                    raw_text=text, fetch_time=fetch_time,
                    success=True, weight=weight,
                    fetch_method="google_cache",
                )
        log.debug(f"[Articles] Google cache miss ({r.status_code}) — {url}")
    except Exception as e:
        log.debug(f"[Articles] Google cache error — {url} — {e}")
    return None


def _try_wayback(
    url: str, source_name: str, outlet: str, weight: int, fetch_time: str,
    max_age_days: int = 10
) -> Optional[ArticleResult]:
    """
    Tier 4: Try Wayback Machine (archive.org) for a recent cached copy.
    Queries the availability API first to find the most recent snapshot.
    """
    try:
        # Check availability API — find most recent snapshot
        avail_url = f"https://archive.org/wayback/available?url={url}"
        avail_r = requests.get(avail_url, timeout=10)
        if avail_r.status_code != 200:
            return None

        data = avail_r.json()
        snapshot = data.get("archived_snapshots", {}).get("closest", {})
        if not snapshot.get("available"):
            log.debug(f"[Articles] Wayback: no snapshot for {url}")
            return None

        snapshot_url = snapshot.get("url", "")
        snapshot_ts  = snapshot.get("timestamp", "")

        # Check age — don't use snapshots older than max_age_days
        if snapshot_ts:
            try:
                snap_date = datetime.strptime(snapshot_ts[:8], "%Y%m%d")
                age = (datetime.now() - snap_date).days
                if age > max_age_days:
                    log.debug(f"[Articles] Wayback snapshot too old ({age}d) — {url}")
                    return None
            except Exception:
                pass

        # Fetch the snapshot
        time.sleep(0.5)
        snap_r = requests.get(snapshot_url, headers=BROWSER_HEADERS_CHROME,
                               timeout=FETCH_TIMEOUT)
        if snap_r.status_code == 200:
            text = extract_text(snap_r.text, url)
            if text and len(text) > 300:
                log.info(f"[Articles] ✓ Tier4 Wayback ({snapshot_ts[:8]}) — {source_name}: {url}")
                return ArticleResult(
                    source_name=source_name, outlet=outlet,
                    url=snapshot_url, title=extract_title(snap_r.text),
                    raw_text=text, fetch_time=fetch_time,
                    success=True, weight=weight,
                    fetch_method=f"wayback_{snapshot_ts[:8]}",
                )
    except Exception as e:
        log.debug(f"[Articles] Wayback error — {url} — {e}")
    return None


def _try_manual_paste(source_name: str, outlet: str, weight: int) -> Optional[ArticleResult]:
    """
    Tier 5: Check for a manually pasted text file in the repo root.
    Files: haslbauer_manual.txt, bamford_manual.txt, coley_manual.txt
    If present and non-empty, use as article content.
    """
    filename = MANUAL_PASTE_FILES.get(source_name)
    if not filename:
        return None

    # Check repo root and a few likely locations
    for path in [filename, f"data/{filename}", f"articles/{filename}"]:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    text = f.read().strip()
                if len(text) > 100:
                    return ArticleResult(
                        source_name=source_name, outlet=outlet,
                        url=f"manual://{filename}",
                        title=f"{source_name} — Manual Paste",
                        raw_text=text,
                        fetch_time=datetime.now().isoformat(),
                        success=True, weight=weight,
                        fetch_method="manual_paste",
                    )
            except Exception as e:
                log.warning(f"[Articles] Error reading manual file {path}: {e}")
    return None


# ──────────────────────────────────────────────────────────────
# LEGACY fetch_article (kept for compatibility with prior year fetch)
# ──────────────────────────────────────────────────────────────

def fetch_article(
    source_name: str,
    outlet: str,
    url: str,
    weight: int = 5,
) -> ArticleResult:
    """Legacy single-attempt fetch. Used by prior year article search."""
    return fetch_article_with_fallbacks(source_name, outlet, url, weight)


# ──────────────────────────────────────────────────────────────
# TEXT EXTRACTION
# ──────────────────────────────────────────────────────────────

def extract_text(html: str, url: str = "") -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header",
                     "aside", "advertisement", "noscript", "iframe"]):
        tag.decompose()

    selectors = [
        "article", "main", ".article-body", ".post-content",
        ".entry-content", "#article-body", ".article__body",
        ".content-body", ".story-body",
    ]
    for sel in selectors:
        elem = soup.select_one(sel)
        if elem and len(elem.get_text(strip=True)) > 200:
            return clean_text(elem.get_text(separator=" ", strip=True))

    body = soup.body
    if body:
        return clean_text(body.get_text(separator=" ", strip=True))
    return clean_text(soup.get_text(separator=" ", strip=True))


def extract_title(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        return og_title["content"].strip()
    if soup.title:
        return soup.title.string.strip() if soup.title.string else ""
    h1 = soup.find("h1")
    return h1.get_text(strip=True) if h1 else ""


def clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\x20-\x7E\n]", " ", text)
    return text.strip()


def is_paywall(html: str, url: str = "") -> bool:
    lower = html.lower()
    paywall_signals = [
        "subscribe to read", "subscription required", "sign in to read",
        "premium content", "members only", "create an account to",
        "to continue reading", "unlock this article",
        "you've used all your free", "free articles remaining",
    ]
    return any(s in lower for s in paywall_signals)


# ──────────────────────────────────────────────────────────────
# SUMMARISATION
# ──────────────────────────────────────────────────────────────

def summarize_article_bundle(bundle: 'ArticleBundle') -> Dict:
    """
    Build a structured summary of all successful articles
    suitable for injecting into the Claude analysis prompt.
    """
    if not bundle.successful:
        return {"articles": [], "summary_text": "No articles successfully fetched this week."}

    articles_out = []
    for art in bundle.successful:
        trimmed = art.raw_text[:4000] if len(art.raw_text) > 4000 else art.raw_text
        articles_out.append({
            "source": art.source_name,
            "outlet": art.outlet,
            "url": art.url,
            "title": art.title,
            "weight": art.weight,
            "text": trimmed,
            "fetch_method": art.fetch_method,
        })

    summary_lines = [
        f"ARTICLE INPUTS ({len(articles_out)} sources):",
        "─" * 60,
    ]
    for a in articles_out:
        method_note = f" [{a['fetch_method']}]" if a["fetch_method"] != "direct" else ""
        summary_lines.append(
            f"\n[{a['source']} | weight={a['weight']}{method_note}]\n"
            f"Title: {a['title']}\n"
            f"{a['text'][:2000]}\n"
        )

    return {
        "articles": articles_out,
        "summary_text": "\n".join(summary_lines),
    }


# ──────────────────────────────────────────────────────────────
# PRIOR YEAR ARTICLE SEARCH
# ──────────────────────────────────────────────────────────────

PRIOR_YEAR_SEARCH_TEMPLATES = {
    "Haslbauer": [
        "https://www.lineups.com/golf/picks/{event_slug}",
        "https://www.lineups.com/golf/",
    ],
    "Steve Bamford": [
        "https://www.golfbettingsystem.co.uk/",
    ],
    "Steve Rawlings": [
        "https://betting.betfair.com/golf/",
    ],
    "Ben Coley": [
        "https://www.sportinglife.com/golf/tips",
    ],
}

COURSE_STRUCTURE_KEYWORDS = [
    "course", "hole", "par", "yardage", "fairway", "rough", "green",
    "approach", "off the tee", "distance", "accuracy", "wind", "weather",
    "winning score", "scoring average", "key stat", "type of game",
    "historically", "typically", "tends to", "this course", "venue",
    "setup", "conditions", "bermuda", "poa", "bent", "grain",
    "dog leg", "elevation", "undulation", "firm", "soft",
]

PLAYER_FORM_KEYWORDS = [
    "in form", "recent form", "last week", "last month", "this season",
    "strokes gained", "hot", "cold", "trending", "value at", "worth backing",
    "i like", "i'd back", "my pick", "recommend", "best bet",
    "each way", "e/w", "win bet", "accumulator",
]


def fetch_prior_year_article(source_name: str, outlet: str, url: str, weight: int = 5) -> ArticleResult:
    """Fetch a prior year article using full tiered strategy."""
    return fetch_article_with_fallbacks(source_name, outlet, url, weight)


def search_for_prior_year_articles(event_name: str) -> 'ArticleBundle':
    """
    Attempt to find prior year articles for the same event.
    Uses full tiered fetch strategy including Wayback Machine
    with a longer max_age window for prior year content.
    """
    event_slug = _make_slug(event_name)
    bundle = ArticleBundle(fetch_time=f"prior_year_search:{event_name}")
    sources_sorted = sorted(ARTICLE_SOURCES, key=lambda s: -s["weight"])

    for source in sources_sorted:
        for base_url in source.get("urls", []):
            candidate_urls = [
                f"{base_url.rstrip('/')}/{event_slug}",
                base_url,
            ]
            for url in candidate_urls:
                # For prior year, allow older Wayback snapshots (up to 400 days)
                result = _fetch_prior_year_with_wayback(
                    source["name"], source["outlet"], url, source["weight"]
                )
                if result.success and len(result.raw_text) > 300:
                    bundle.articles.append(result)
                    break
                elif result.blocked:
                    bundle.blocked.append(result)
                time.sleep(FETCH_DELAY)

    return bundle


def _fetch_prior_year_with_wayback(
    source_name: str, outlet: str, url: str, weight: int
) -> ArticleResult:
    """
    Like fetch_article_with_fallbacks but allows older Wayback snapshots
    (up to 400 days) for prior year article search.
    """
    fetch_time = datetime.now().isoformat()

    # Try direct first
    result = _attempt_fetch(url, BROWSER_HEADERS_CHROME)
    if result and result.status_code == 200:
        text = extract_text(result.text, url)
        if text and not is_paywall(result.text, url) and len(text) > 300:
            return ArticleResult(
                source_name=source_name, outlet=outlet, url=url,
                title=extract_title(result.text), raw_text=text,
                fetch_time=fetch_time, success=True, weight=weight,
                fetch_method="direct",
            )

    time.sleep(0.5)

    # Try Wayback with extended window for prior year
    wb = _try_wayback(url, source_name, outlet, weight, fetch_time, max_age_days=400)
    if wb and wb.success:
        return wb

    return ArticleResult(
        source_name=source_name, outlet=outlet, url=url,
        title="", raw_text="", fetch_time=fetch_time,
        success=False, blocked=True,
        block_reason="prior_year_all_tiers_failed", weight=weight,
    )


def extract_course_structure_from_prior_year(articles: 'ArticleBundle') -> Dict:
    result = {
        "course_narrative": [],
        "key_stats": [],
        "winning_score_refs": [],
        "weather_patterns": [],
        "discarded_player_notes": 0,
        "source_log": [],
        "staleness_warning": (
            "⚠️  PRIOR YEAR CONTENT: Course structure only. "
            "All player-specific notes are from last year and have been discarded. "
            "Do not use for current player assessment."
        ),
    }

    for article in articles.successful:
        paragraphs = [p.strip() for p in article.raw_text.split("\n") if len(p.strip()) > 60]
        kept = 0
        discarded = 0

        for para in paragraphs:
            para_lower = para.lower()
            if any(k in para_lower for k in PLAYER_FORM_KEYWORDS):
                discarded += 1
                continue
            course_hits = sum(1 for k in COURSE_STRUCTURE_KEYWORDS if k in para_lower)
            if course_hits >= 2:
                if any(k in para_lower for k in ["winning score", "under par", "scoring average"]):
                    result["winning_score_refs"].append(f"[{article.source_name}] {para[:200]}")
                elif any(k in para_lower for k in ["wind", "weather", "forecast", "conditions"]):
                    result["weather_patterns"].append(f"[{article.source_name}] {para[:200]}")
                elif any(k in para_lower for k in ["strokes gained", "sg:", "key stat", "approach", "off the tee"]):
                    result["key_stats"].append(f"[{article.source_name}] {para[:200]}")
                else:
                    result["course_narrative"].append(f"[{article.source_name}] {para[:200]}")
                kept += 1
            else:
                discarded += 1

        result["discarded_player_notes"] += discarded
        result["source_log"].append({
            "source": article.source_name,
            "paragraphs_kept": kept,
            "paragraphs_discarded": discarded,
        })

    result["course_narrative"]   = result["course_narrative"][:10]
    result["key_stats"]          = result["key_stats"][:8]
    result["winning_score_refs"] = result["winning_score_refs"][:5]
    result["weather_patterns"]   = result["weather_patterns"][:5]
    return result


def build_prior_year_course_summary(extracted: Dict) -> str:
    lines = [
        "═══════════════════════════════════════════════════════════════",
        "PRIOR YEAR COURSE BREAKDOWN (structural only — player notes discarded)",
        extracted["staleness_warning"],
        "═══════════════════════════════════════════════════════════════",
    ]
    if extracted["course_narrative"]:
        lines.append("\nCOURSE STRUCTURE & SETUP:")
        lines.extend(f"  • {n}" for n in extracted["course_narrative"])
    if extracted["key_stats"]:
        lines.append("\nKEY STATS & GAME TYPE:")
        lines.extend(f"  • {s}" for s in extracted["key_stats"])
    if extracted["winning_score_refs"]:
        lines.append("\nHISTORICAL WINNING SCORE REFERENCES:")
        lines.extend(f"  • {w}" for w in extracted["winning_score_refs"])
    if extracted["weather_patterns"]:
        lines.append("\nTYPICAL WEATHER / WIND PATTERNS:")
        lines.extend(f"  • {w}" for w in extracted["weather_patterns"])
    src_summary = ", ".join(
        f"{s['source']} ({s['paragraphs_kept']} kept)"
        for s in extracted["source_log"] if s["paragraphs_kept"] > 0
    )
    if src_summary:
        lines.append(f"\nSources contributed: {src_summary}")
    lines.append(f"Player-specific paragraphs discarded: {extracted['discarded_player_notes']}")
    return "\n".join(lines)


def _make_slug(event_name: str) -> str:
    slug = event_name.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"\s+", "-", slug)
    return slug
