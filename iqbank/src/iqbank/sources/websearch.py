"""Web search (Serper or Brave API), then fetch result pages with httpx and extract text with trafilatura.

Pages are fetched only when robots.txt allows it, at most one request per host every
`min_host_interval` seconds (longer if robots.txt sets Crawl-delay), and never from blocklisted
domains. Login walls and CAPTCHAs are skipped, never worked around. Reddit hits are fetched
through the Reddit API source instead of scraping reddit.com.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import httpx

from iqbank.models import RawDoc
from iqbank.net import FetchRefused, HttpClient, blocked_by, canonical_url, is_reddit
from iqbank.sources.base import Candidate, SkipDoc, Source, SourceUnavailable

if TYPE_CHECKING:
    from iqbank.sources.reddit import RedditSource
    from iqbank.store import Store

log = logging.getLogger(__name__)

SERPER_URL = "https://google.serper.dev/search"
BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"
MIN_TEXT_CHARS = 300
_WALL_MARKERS = re.compile(
    r"captcha|verify you are (a )?human|are you a robot|sign in to (continue|view)|log ?in to (continue|view)"
    r"|enable javascript and cookies|access denied",
    re.I,
)


@dataclass
class SearchResult:
    url: str
    title: str
    snippet: str = ""
    date: str | None = None


def parse_serper(data: dict[str, Any]) -> list[SearchResult]:
    return [
        SearchResult(url=r["link"], title=r.get("title", ""), snippet=r.get("snippet", ""), date=r.get("date"))
        for r in data.get("organic", [])
        if r.get("link")
    ]


def parse_brave(data: dict[str, Any]) -> list[SearchResult]:
    return [
        SearchResult(
            url=r["url"],
            title=r.get("title", ""),
            snippet=r.get("description", ""),
            date=r.get("page_age") or r.get("age"),
        )
        for r in (data.get("web") or {}).get("results", [])
        if r.get("url")
    ]


def page_to_text(body: bytes, url: str) -> tuple[str, str, str | None]:
    """Return (title, text, published_date) for an HTML page. Raises SkipDoc if there's no article."""
    import trafilatura

    doc = trafilatura.bare_extraction(
        body,
        url=url,
        with_metadata=True,
        include_comments=True,  # comment threads under blog posts often hold interview reports
        include_tables=True,
        favor_recall=True,
    )
    text = (getattr(doc, "text", None) or "").strip() if doc else ""
    comments = (getattr(doc, "comments", None) or "").strip() if doc else ""
    if comments:
        text = f"{text}\n\n--- Comments ---\n{comments}"
    if len(text) < MIN_TEXT_CHARS:
        if _WALL_MARKERS.search(text) or _WALL_MARKERS.search(body[:20000].decode("utf-8", "ignore")):
            raise SkipDoc("login wall or CAPTCHA (not bypassing)")
        raise SkipDoc("no extractable article text")
    return (getattr(doc, "title", None) or "", text, getattr(doc, "date", None))


class WebSearchSource(Source):
    name = "web"

    def __init__(self, settings, http: HttpClient, reddit: "RedditSource | None" = None):
        super().__init__(settings)
        self.http = http
        self.reddit = reddit

    @property
    def provider(self) -> str | None:
        p = (self.settings.search_provider or "").lower()
        if p in ("serper", "brave"):
            return p
        if self.settings.serper_api_key:
            return "serper"
        if self.settings.brave_api_key:
            return "brave"
        return None

    def check_config(self) -> str | None:
        p = self.provider
        if p is None:
            return "set SERPER_API_KEY or BRAVE_API_KEY in .env"
        if p == "serper" and not self.settings.serper_api_key:
            return "SEARCH_PROVIDER=serper but SERPER_API_KEY is not set"
        if p == "brave" and not self.settings.brave_api_key:
            return "SEARCH_PROVIDER=brave but BRAVE_API_KEY is not set"
        return None

    def _queries(self) -> list[str]:
        return [self.settings.fmt(q) for q in self.settings.web_queries]

    def plan(self, store: "Store") -> list[str]:
        lines = [
            f"{self.provider} search {q!r} (top {self.settings.web_results_per_query} results)"
            for q in self._queries()
        ]
        lines.append(f"skip domains: {', '.join(self.settings.blocklist)}")
        lines.append("fetch new result pages (robots.txt honored, per-host rate limit), extract text with trafilatura")
        return lines

    def search(self, query: str) -> list[SearchResult]:
        n = self.settings.web_results_per_query
        try:
            if self.provider == "serper":
                resp = self.http.request(
                    "POST",
                    SERPER_URL,
                    json={"q": query, "num": n},
                    headers={"X-API-KEY": self.settings.serper_api_key or ""},
                    rate_key="serper",
                )
                return parse_serper(resp.json())
            resp = self.http.request(
                "GET",
                BRAVE_URL,
                params={"q": query, "count": min(n, 20)},
                headers={"X-Subscription-Token": self.settings.brave_api_key or "", "Accept": "application/json"},
                rate_key="brave",
            )
            return parse_brave(resp.json())
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (401, 402, 403):
                raise SourceUnavailable(
                    f"{self.provider} rejected the request ({exc.response.status_code}): check the API key/quota"
                ) from exc
            raise

    def discover(self) -> Iterator[Candidate]:
        seen: set[str] = set()
        for query in self._queries():
            try:
                results = self.search(query)
            except SourceUnavailable:
                raise
            except Exception as exc:  # noqa: BLE001 - keep going with the other queries
                log.warning("web: search %r failed: %s", query, exc)
                continue
            log.info("web: %r -> %d results", query, len(results))
            for r in results:
                url = canonical_url(r.url)
                if url in seen:
                    continue
                seen.add(url)
                yield Candidate(url=url, title=r.title, data={"query": query, "snippet": r.snippet, "date": r.date,
                                                              "raw_url": r.url})

    def fetch(self, candidate: Candidate) -> RawDoc:
        raw_url = candidate.data.get("raw_url", candidate.url) if candidate.data else candidate.url
        if entry := blocked_by(raw_url, self.settings.blocklist):
            raise SkipDoc(f"blocklisted domain ({entry})", remember=False)
        if is_reddit(raw_url):
            if self.reddit is None or self.reddit.check_config():
                raise SkipDoc("reddit thread: configure the Reddit API source to collect it", remember=False)
            try:
                doc = self.reddit.fetch_url(candidate.url)
            except SourceUnavailable as exc:
                raise SkipDoc(str(exc), remember=False) from exc
            doc.meta["found_by"] = f"web search: {candidate.data.get('query')}"
            return doc
        try:
            page = self.http.fetch_page(raw_url, self.settings.blocklist)
        except FetchRefused as exc:
            raise SkipDoc(exc.reason, remember=not exc.reason.startswith("blocklisted")) from exc
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            reason = "login required (not bypassing)" if code in (401, 403) else f"HTTP {code}"
            raise SkipDoc(reason) from exc
        title, text, published = page_to_text(page.body, page.url)
        title = title or candidate.title
        header = [f"Title: {title}", f"URL: {page.url}"]
        if published or candidate.data.get("date"):
            header.append(f"Published: {published or candidate.data.get('date')}")
        return RawDoc(
            url=candidate.url,
            source=self.name,
            title=title,
            raw_text="\n".join(header) + "\n\n" + text + "\n",
            meta={
                "query": candidate.data.get("query"),
                "final_url": page.url,
                "published": published,
                "snippet": candidate.data.get("snippet"),
            },
        )
