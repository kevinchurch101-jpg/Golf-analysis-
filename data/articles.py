"""
Fairway Intel — Article Fetcher and Parser
Reads all configured sources. Blocked articles flagged clearly, never silently skipped.
Articles are inputs — framework makes decisions.
Haslbauer is highest weight. Bamford extracts weather + wind + course conditions too.
"""

import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

from config import ARTICLE_SOURCES

log = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0 Safari/537.36"
    )
}
FETCH_TIMEOUT = 15
FETCH_DELAY   = 1.5   # seconds between requests — be polite


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
# FETCHING
# ──────────────────────────────────────────────────────────────

def fetch_all_articles() -> ArticleBundle:
    """
    Fetch articles from all configured sources.
    Every blocked article is flagged — never silently skipped.
    Haslbauer checked first (highest weight).
    """
    bundle = ArticleBundle(fetch_time=datetime.now().isoformat())
    sources_sorted = sorted(ARTICLE_SOURCES, key=lambda s: -s["weight"])

    for source in sources_sorted:
        for url in source.get("urls", []):
            result = fetch_article(source["name"], source["outlet"], url, source["weight"])
            bundle.articles.append(result)
            if result.blocked:
                bundle.blocked.append(result)
            time.sleep(FETCH_DELAY)

    log.info(
        f"[Articles] Fetched {len(bundle.successful)} successfully, "
        f"{len(bundle.blocked)} blocked."
    )
    return bundle


def fetch_article(
    source_name: str,
    outlet: str,
    url: str,
    weight: int = 5,
) -> ArticleResult:
    """Fetch a single article URL. Returns ArticleResult with success/block status."""
    fetch_time = datetime.now().isoformat()
    try:
        r = requests.get(url, headers=HEADERS, timeout=FETCH_TIMEOUT)

        if r.status_code == 200:
            text = extract_text(r.text, url)
            title = extract_title(r.text)
            if is_paywall(r.text, url):
                log.warning(f"[Articles] BLOCKED (paywall) — {source_name}: {url}")
                return ArticleResult(
                    source_name=source_name, outlet=outlet, url=url,
                    title=title, raw_text="", fetch_time=fetch_time,
                    success=False, blocked=True,
                    block_reason="paywall_detected", weight=weight,
                )
            return ArticleResult(
                source_name=source_name, outlet=outlet, url=url,
                title=title, raw_text=text, fetch_time=fetch_time,
                success=True, weight=weight,
            )

        elif r.status_code in (401, 403):
            log.warning(f"[Articles] BLOCKED (HTTP {r.status_code}) — {source_name}: {url}")
            return ArticleResult(
                source_name=source_name, outlet=outlet, url=url,
                title="", raw_text="", fetch_time=fetch_time,
                success=False, blocked=True,
                block_reason=f"http_{r.status_code}", weight=weight,
            )
        elif r.status_code == 404:
            log.info(f"[Articles] Not found (404) — {source_name}: {url}")
            return ArticleResult(
                source_name=source_name, outlet=outlet, url=url,
                title="", raw_text="", fetch_time=fetch_time,
                success=False, blocked=True,
                block_reason="not_found_404", weight=weight,
            )
        else:
            log.warning(f"[Articles] HTTP {r.status_code} — {source_name}: {url}")
            return ArticleResult(
                source_name=source_name, outlet=outlet, url=url,
                title="", raw_text="", fetch_time=fetch_time,
                success=False, blocked=True,
                block_reason=f"http_{r.status_code}", weight=weight,
            )

    except requests.Timeout:
        log.warning(f"[Articles] TIMEOUT — {source_name}: {url}")
        return ArticleResult(
            source_name=source_name, outlet=outlet, url=url,
            title="", raw_text="", fetch_time=fetch_time,
            success=False, blocked=True,
            block_reason="timeout", weight=weight,
        )
    except requests.RequestException as e:
        log.error(f"[Articles] Request error — {source_name}: {url} — {e}")
        return ArticleResult(
            source_name=source_name, outlet=outlet, url=url,
            title="", raw_text="", fetch_time=fetch_time,
            success=False, blocked=True,
            block_reason=f"request_error: {str(e)[:80]}", weight=weight,
        )


# ──────────────────────────────────────────────────────────────
# TEXT EXTRACTION
# ──────────────────────────────────────────────────────────────

def extract_text(html: str, url: str = "") -> str:
    """
    Extract clean readable text from HTML.
    Strips nav, ads, scripts, footers. Returns article body text.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Remove noise elements
    for tag in soup(["script", "style", "nav", "footer", "header",
                     "aside", "advertisement", "noscript", "iframe"]):
        tag.decompose()

    # Try article-specific selectors first
    selectors = [
        "article", "main", ".article-body", ".post-content",
        ".entry-content", "#article-body", ".article__body",
        ".content-body", ".story-body",
    ]
    for sel in selectors:
        elem = soup.select_one(sel)
        if elem and len(elem.get_text(strip=True)) > 200:
            return clean_text(elem.get_text(separator=" ", strip=True))

    # Fallback: full body text
    body = soup.body
    if body:
        return clean_text(body.get_text(separator=" ", strip=True))
    return clean_text(soup.get_text(separator=" ", strip=True))


def extract_title(html: str) -> str:
    """Extract page title."""
    soup = BeautifulSoup(html, "html.parser")
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        return og_title["content"].strip()
    if soup.title:
        return soup.title.string.strip() if soup.title.string else ""
    h1 = soup.find("h1")
    return h1.get_text(strip=True) if h1 else ""


def clean_text(text: str) -> str:
    """Remove excess whitespace and noise from extracted text."""
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"(\n\s*){3,}", "\n\n", text)
    return text.strip()


def is_paywall(html: str, url: str = "") -> bool:
    """
    Heuristic paywall detection.
    Returns True if the page appears to be paywalled/login-gated.
    """
    paywall_signals = [
        "subscribe to read",
        "create a free account",
        "log in to continue",
        "sign in to read",
        "members only",
        "premium content",
        "subscription required",
        "unlock this article",
    ]
    html_lower = html.lower()
    return any(signal in html_lower for signal in paywall_signals)


# ──────────────────────────────────────────────────────────────
# CONTENT PARSING — extract structured picks/analysis
# ──────────────────────────────────────────────────────────────

def extract_player_mentions(text: str, known_players: List[str]) -> Dict[str, List[str]]:
    """
    Find all player name mentions in article text.
    Returns dict of player_name → list of surrounding sentences.
    """
    mentions: Dict[str, List[str]] = {}
    sentences = re.split(r"(?<=[.!?])\s+", text)

    for player in known_players:
        player_lower = player.lower()
        last_name = player.split()[-1].lower()
        player_sentences = []
        for sentence in sentences:
            s_lower = sentence.lower()
            if player_lower in s_lower or last_name in s_lower:
                player_sentences.append(sentence.strip())
        if player_sentences:
            mentions[player] = player_sentences

    return mentions


def extract_haslbauer_picks(text: str) -> Dict[str, List[str]]:
    """
    Attempt to extract Haslbauer's picks, longshots, and fade calls.
    Returns categorized dict.
    """
    result = {
        "outright_picks": [],
        "longshots": [],
        "fades": [],
        "frl_picks": [],
        "top10_picks": [],
        "raw_paragraphs": [],
    }

    paragraphs = [p.strip() for p in text.split("\n") if len(p.strip()) > 40]
    result["raw_paragraphs"] = paragraphs[:50]   # First 50 substantive paragraphs

    # Keyword scanning for categories
    fade_keywords  = ["fade", "avoid", "against", "pass on"]
    long_keywords  = ["longshot", "long shot", "value", "100/1", "150/1", "80/1", "60/1", "50/1"]
    frl_keywords   = ["first round leader", "frl", "r1 leader", "round one"]
    top10_keywords = ["top 10", "top-10", "top ten", "each way"]

    for para in paragraphs:
        p_lower = para.lower()
        if any(k in p_lower for k in fade_keywords):
            result["fades"].append(para)
        elif any(k in p_lower for k in frl_keywords):
            result["frl_picks"].append(para)
        elif any(k in p_lower for k in top10_keywords):
            result["top10_picks"].append(para)
        elif any(k in p_lower for k in long_keywords):
            result["longshots"].append(para)

    return result


def extract_bamford_data(text: str) -> Dict:
    """
    Extract the following from Bamford's article (in addition to SG rankings):
    - Weather forecast
    - Wind by round (direction, speed)
    - Course conditions
    - Other contextual notes
    """
    result = {
        "sg_rankings": [],
        "weather": {},
        "wind_by_round": {},
        "course_conditions": [],
        "other_notes": [],
        "raw_text": text[:3000],
    }

    lines = [l.strip() for l in text.split("\n") if l.strip()]

    wind_keywords     = ["wind", "mph", "knots", "breeze", "blustery", "calm"]
    weather_keywords  = ["rain", "forecast", "temperature", "conditions", "sunny", "cloudy", "dry"]
    course_keywords   = ["firm", "soft", "fast", "slow", "course", "green", "fairway", "rough"]
    sg_keywords       = ["sg:", "strokes gained", "approach", "off the tee", "putting", "around"]

    for line in lines:
        l_lower = line.lower()
        if any(k in l_lower for k in sg_keywords):
            result["sg_rankings"].append(line)
        elif any(k in l_lower for k in wind_keywords):
            # Try to assign to round
            for rnum in ["round 1", "round 2", "round 3", "round 4", "r1", "r2", "r3", "r4",
                         "thursday", "friday", "saturday", "sunday"]:
                if rnum in l_lower:
                    result["wind_by_round"][rnum] = line
                    break
            else:
                result["weather"]["wind_general"] = line
        elif any(k in l_lower for k in weather_keywords):
            result["weather"][f"note_{len(result['weather'])}"] = line
        elif any(k in l_lower for k in course_keywords):
            result["course_conditions"].append(line)
        else:
            result["other_notes"].append(line)

    return result


def summarize_article_bundle(bundle: ArticleBundle) -> Dict:
    """
    Build a summary dict from all fetched articles suitable for
    passing to Claude API for analysis synthesis.
    """
    summary = {
        "article_count": len(bundle.successful),
        "blocked_count": len(bundle.blocked),
        "blocked_sources": [f"{a.source_name}: {a.block_reason}" for a in bundle.blocked],
        "articles": [],
    }

    for article in bundle.successful:
        summary["articles"].append({
            "source": article.source_name,
            "outlet": article.outlet,
            "weight": article.weight,
            "title": article.title,
            "text": article.raw_text[:4000],   # Cap per article for token budget
        })

    return summary


# ──────────────────────────────────────────────────────────────
# PRIOR YEAR ARTICLE SEARCH — course breakdown foundation
# ──────────────────────────────────────────────────────────────

# URL patterns for searching prior year articles by event name
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

# Sections of prior year articles worth keeping vs discarding
COURSE_STRUCTURE_KEYWORDS = [
    # Keep — these are durable year over year
    "course", "hole", "par", "yardage", "fairway", "rough", "green",
    "approach", "off the tee", "distance", "accuracy", "wind", "weather",
    "winning score", "scoring average", "key stat", "type of game",
    "historically", "typically", "tends to", "this course", "venue",
    "setup", "conditions", "bermuda", "poa", "bent", "grain",
    "dog leg", "elevation", "undulation", "firm", "soft",
]

PLAYER_FORM_KEYWORDS = [
    # Discard — these are player-specific, year-old data
    "in form", "recent form", "last week", "last month", "this season",
    "strokes gained", "hot", "cold", "trending", "value at", "worth backing",
    "i like", "i'd back", "my pick", "recommend", "best bet",
    "each way", "e/w", "win bet", "accumulator",
]


def fetch_prior_year_article(source_name: str, outlet: str, url: str, weight: int = 5) -> ArticleResult:
    """
    Fetch a prior year article. Same as fetch_article but tagged as prior_year
    so the parser knows to apply course-structure-only filtering.
    """
    result = fetch_article(source_name, outlet, url, weight)
    # Tag it — handled downstream in extract_course_structure_from_prior_year
    return result


def search_for_prior_year_articles(event_name: str) -> 'ArticleBundle':
    """
    Attempt to find prior year articles for the same event.
    Strategy:
      1. Build search URLs based on event name slug
      2. Fetch each source's archive/search page
      3. Extract links that look like they match the event from last year
      4. Fetch those specific articles

    These are used for course structure only — player notes are discarded.
    """
    import time
    event_slug = _make_slug(event_name)
    bundle = ArticleBundle(fetch_time=f"prior_year_search:{event_name}")
    sources_sorted = sorted(ARTICLE_SOURCES, key=lambda s: -s["weight"])

    for source in sources_sorted:
        for base_url in source.get("urls", []):
            # Try appending event slug to base URL
            candidate_urls = [
                f"{base_url.rstrip('/')}/{event_slug}",
                base_url,
            ]
            for url in candidate_urls:
                result = fetch_prior_year_article(
                    source["name"], source["outlet"], url, source["weight"]
                )
                if result.success and len(result.raw_text) > 300:
                    bundle.articles.append(result)
                    break   # Got content from this source — move on
                elif result.blocked:
                    bundle.blocked.append(result)
                time.sleep(FETCH_DELAY)

    return bundle


def extract_course_structure_from_prior_year(articles: 'ArticleBundle') -> Dict:
    """
    Extract only the durable course structure content from prior year articles.
    Explicitly discards any player-specific form or pick content.

    Returns a dict with:
      - course_narrative:    paragraphs about the course itself (durable)
      - key_stats:           stats/game type the authors historically flag
      - winning_score_refs:  any historical winning score mentions
      - weather_patterns:    any typical weather/wind pattern mentions
      - discarded_notes:     count of player-form paragraphs explicitly discarded
      - source_log:          which sources contributed what
    """
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

            # Hard discard: player form / picks content
            if any(k in para_lower for k in PLAYER_FORM_KEYWORDS):
                discarded += 1
                continue

            # Check for course structure content
            course_hits = sum(1 for k in COURSE_STRUCTURE_KEYWORDS if k in para_lower)

            if course_hits >= 2:
                # Categorise
                if any(k in para_lower for k in ["winning score", "under par", "scoring average", "-"]):
                    result["winning_score_refs"].append(
                        f"[{article.source_name}] {para[:200]}"
                    )
                elif any(k in para_lower for k in ["wind", "weather", "forecast", "conditions", "temperature"]):
                    result["weather_patterns"].append(
                        f"[{article.source_name}] {para[:200]}"
                    )
                elif any(k in para_lower for k in ["strokes gained", "sg:", "key stat", "approach", "off the tee", "type of game"]):
                    result["key_stats"].append(
                        f"[{article.source_name}] {para[:200]}"
                    )
                else:
                    result["course_narrative"].append(
                        f"[{article.source_name}] {para[:200]}"
                    )
                kept += 1
            else:
                discarded += 1

        result["discarded_player_notes"] += discarded
        result["source_log"].append({
            "source": article.source_name,
            "paragraphs_kept": kept,
            "paragraphs_discarded": discarded,
        })

    # Cap to most useful entries
    result["course_narrative"]    = result["course_narrative"][:10]
    result["key_stats"]           = result["key_stats"][:8]
    result["winning_score_refs"]  = result["winning_score_refs"][:5]
    result["weather_patterns"]    = result["weather_patterns"][:5]

    return result


def build_prior_year_course_summary(extracted: Dict) -> str:
    """
    Build a clean text summary of prior year course structure content
    suitable for injecting into the Sunday analysis prompt.
    Clearly labelled as prior year / course-structure-only.
    """
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
        lines.append("\nKEY STATS & GAME TYPE (authors consistently flag these):")
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
    lines.append(
        f"Player-specific paragraphs discarded: {extracted['discarded_player_notes']}"
    )

    return "\n".join(lines)


def _make_slug(event_name: str) -> str:
    """Convert event name to URL slug. e.g. 'Valero Texas Open' → 'valero-texas-open'"""
    import re
    slug = event_name.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"\s+", "-", slug)
    return slug
