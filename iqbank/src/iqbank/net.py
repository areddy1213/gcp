"""Polite HTTP: retries with backoff, per-host rate limiting, robots.txt, blocklist."""

from __future__ import annotations

import email.utils
import logging
import re
import time
import urllib.robotparser
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import httpx
from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception,
    stop_after_attempt,
)

from iqbank.config import Settings

log = logging.getLogger(__name__)

MAX_RETRY_SLEEP = 120.0


class RetryableHTTPError(Exception):
    """429 / 5xx / rate-limited 403: worth retrying, optionally after a server-given delay."""

    def __init__(self, status: int, url: str, retry_after: float | None = None):
        super().__init__(f"HTTP {status} for {url}")
        self.status = status
        self.url = url
        self.retry_after = retry_after


class FetchRefused(Exception):
    """We decided not to fetch or keep this URL (robots.txt, blocklist, size, content type)."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


# ---- URL helpers -----------------------------------------------------------

_TRACKING_PARAMS = re.compile(r"^(utm_|fbclid$|gclid$|mc_cid$|mc_eid$|ref$|ref_src$|share_id$)")
_REDDIT_THREAD = re.compile(r"/comments/([a-z0-9]+)", re.I)


def host_of(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def is_reddit(url: str) -> bool:
    host = host_of(url)
    return host == "reddit.com" or host.endswith(".reddit.com") or host == "redd.it"


def canonical_url(url: str) -> str:
    """Stable key for a URL: lowercase host, no fragment, no tracking params, no trailing slash.

    Reddit threads collapse to https://www.reddit.com/comments/<id>/ so the Reddit API source
    and web-search hits for the same thread share one key.
    """
    url = url.strip()
    if is_reddit(url) and (m := _REDDIT_THREAD.search(url)):
        return f"https://www.reddit.com/comments/{m.group(1).lower()}/"
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        return url
    query = urlencode([(k, v) for k, v in parse_qsl(parts.query) if not _TRACKING_PARAMS.match(k)])
    path = parts.path.rstrip("/") or "/"
    netloc = parts.netloc.lower()
    return urlunsplit((parts.scheme.lower(), netloc, path, query, ""))


def blocked_by(url: str, blocklist: list[str]) -> str | None:
    """Return the blocklist entry that matches the URL's host, or None."""
    host = host_of(url)
    if not host:
        return None
    labels = host.split(".")
    for entry in blocklist:
        entry = entry.strip().lower()
        if not entry:
            continue
        if entry.startswith("www."):
            entry = entry[4:]
        if entry.endswith(".*"):
            # "glassdoor.*" -> any host containing the label "glassdoor" followed by a TLD
            name = entry[:-2]
            name_labels = name.split(".")
            n = len(name_labels)
            for i in range(len(labels) - n):
                if labels[i : i + n] == name_labels:
                    return entry
        elif host == entry or host.endswith("." + entry):
            return entry
    return None


# ---- retries ----------------------------------------------------------------


def parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    value = value.strip()
    if value.isdigit():
        return float(value)
    try:
        dt = email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, dt.timestamp() - time.time())


def _is_retryable(exc: BaseException) -> bool:
    return isinstance(exc, (RetryableHTTPError, httpx.TransportError))


def _wait(state: RetryCallState) -> float:
    exc = state.outcome.exception() if state.outcome else None
    if isinstance(exc, RetryableHTTPError) and exc.retry_after is not None:
        return min(exc.retry_after + 1.0, MAX_RETRY_SLEEP)
    # exponential backoff with jitter: ~1, 2, 4, 8 ... seconds
    base = min(2 ** (state.attempt_number - 1), 60)
    return base + (time.time_ns() % 1000) / 1000.0


def _log_retry(state: RetryCallState) -> None:
    exc = state.outcome.exception() if state.outcome else None
    log.warning(
        "retrying %s after %s (attempt %d)",
        getattr(state.fn, "__name__", "call"),
        exc,
        state.attempt_number,
    )


def with_retries(attempts: int = 5, extra_exceptions: tuple[type[BaseException], ...] = ()):
    """Decorator: retry on transport errors, 429/5xx, and any `extra_exceptions`."""

    def predicate(exc: BaseException) -> bool:
        return _is_retryable(exc) or (bool(extra_exceptions) and isinstance(exc, extra_exceptions))

    return retry(
        retry=retry_if_exception(predicate),
        wait=lambda state: _wait(state),  # late-bound so tests can patch the backoff
        stop=stop_after_attempt(attempts),
        before_sleep=_log_retry,
        reraise=True,
    )


def raise_for_status(resp: httpx.Response) -> None:
    status = resp.status_code
    if status < 400:
        return
    if status == 429 or status >= 500:
        raise RetryableHTTPError(status, str(resp.url), parse_retry_after(resp.headers.get("retry-after")))
    if status == 403 and resp.headers.get("x-ratelimit-remaining") == "0":
        reset = resp.headers.get("x-ratelimit-reset")
        wait = max(0.0, float(reset) - time.time()) if reset and reset.isdigit() else None
        raise RetryableHTTPError(status, str(resp.url), wait)
    resp.raise_for_status()


# ---- rate limiting & robots ---------------------------------------------------


class RateLimiter:
    """Minimum interval between requests sharing a key (normally the host)."""

    def __init__(self, default_interval: float):
        self.default_interval = default_interval
        self._intervals: dict[str, float] = {}
        self._last: dict[str, float] = {}

    def set_interval(self, key: str, seconds: float) -> None:
        self._intervals[key] = max(seconds, self._intervals.get(key, 0.0))

    def wait(self, key: str) -> None:
        interval = self._intervals.get(key, self.default_interval)
        last = self._last.get(key)
        if last is not None:
            remaining = interval - (time.monotonic() - last)
            if remaining > 0:
                time.sleep(remaining)
        self._last[key] = time.monotonic()


class RobotsCache:
    MAX_CRAWL_DELAY = 60.0

    def __init__(self, http: "HttpClient"):
        self.http = http
        self._parsers: dict[str, urllib.robotparser.RobotFileParser | bool] = {}

    def _origin(self, url: str) -> str:
        p = urlsplit(url)
        return f"{p.scheme}://{p.netloc}"

    def _load(self, origin: str) -> urllib.robotparser.RobotFileParser | bool:
        if origin in self._parsers:
            return self._parsers[origin]
        robots_url = origin + "/robots.txt"
        result: urllib.robotparser.RobotFileParser | bool
        try:
            resp = self.http.get(robots_url, respect_robots=False)
            rp = urllib.robotparser.RobotFileParser(robots_url)
            rp.parse(resp.text.splitlines())
            result = rp
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            # 401/403 on robots.txt: treat as "disallow all"; other 4xx: no rules -> allow.
            result = code not in (401, 403)
        except (RetryableHTTPError, httpx.TransportError) as exc:
            log.info("robots.txt unavailable for %s (%s); not fetching from this host", origin, exc)
            result = False
        self._parsers[origin] = result
        return result

    def can_fetch(self, url: str) -> bool:
        rp = self._load(self._origin(url))
        if isinstance(rp, bool):
            return rp
        return rp.can_fetch(self.http.user_agent, url)

    def crawl_delay(self, url: str) -> float | None:
        rp = self._load(self._origin(url))
        if isinstance(rp, bool):
            return None
        delay = rp.crawl_delay(self.http.user_agent)
        return min(float(delay), self.MAX_CRAWL_DELAY) if delay else None


# ---- client -------------------------------------------------------------------


@dataclass
class Page:
    url: str  # final URL after redirects
    content_type: str
    body: bytes


class HttpClient:
    MAX_REDIRECTS = 5

    def __init__(self, settings: Settings, client: httpx.Client | None = None):
        self.settings = settings
        self.user_agent = settings.user_agent
        self.client = client or httpx.Client(
            timeout=settings.request_timeout,
            follow_redirects=False,  # redirects are followed manually so each hop is checked
            headers={"User-Agent": self.user_agent},
        )
        self.limiter = RateLimiter(settings.min_host_interval)
        self.robots = RobotsCache(self)

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> "HttpClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _rate_key(self, url: str, rate_key: str | None) -> str:
        return rate_key or host_of(url)

    @with_retries()
    def request(
        self,
        method: str,
        url: str,
        *,
        rate_key: str | None = None,
        follow_redirects: bool = True,
        **kwargs,
    ) -> httpx.Response:
        """API-style request (no robots.txt check): rate limited, retried, status-checked."""
        self.limiter.wait(self._rate_key(url, rate_key))
        resp = self.client.request(method, url, follow_redirects=follow_redirects, **kwargs)
        raise_for_status(resp)
        return resp

    def get(self, url: str, *, respect_robots: bool = True, rate_key: str | None = None, **kwargs) -> httpx.Response:
        if respect_robots and not self.robots.can_fetch(url):
            raise FetchRefused("disallowed by robots.txt")
        return self.request("GET", url, rate_key=rate_key, **kwargs)

    def fetch_page(self, url: str, blocklist: list[str]) -> Page:
        """Fetch an HTML/text page for extraction, honoring robots.txt and the blocklist on every hop."""
        current = url
        for _ in range(self.MAX_REDIRECTS + 1):
            if entry := blocked_by(current, blocklist):
                raise FetchRefused(f"blocklisted domain ({entry})")
            if not self.robots.can_fetch(current):
                raise FetchRefused("disallowed by robots.txt")
            if delay := self.robots.crawl_delay(current):
                self.limiter.set_interval(host_of(current), delay)
            page_or_redirect = self._get_capped(current)
            if isinstance(page_or_redirect, Page):
                return page_or_redirect
            current = page_or_redirect
        raise FetchRefused("too many redirects")

    @with_retries()
    def _get_capped(self, url: str) -> Page | str:
        self.limiter.wait(host_of(url))
        with self.client.stream("GET", url, headers={"Accept": "text/html,text/plain;q=0.9,*/*;q=0.1"}) as resp:
            if resp.is_redirect:
                location = resp.headers.get("location")
                if not location:
                    raise FetchRefused("redirect without location")
                return urljoin(url, location)
            raise_for_status(resp)
            ctype = resp.headers.get("content-type", "").split(";")[0].strip().lower()
            if ctype and not (ctype.startswith("text/") or ctype in ("application/xhtml+xml", "application/xml")):
                raise FetchRefused(f"unsupported content type {ctype}")
            declared = resp.headers.get("content-length")
            if declared and declared.isdigit() and int(declared) > self.settings.max_page_bytes:
                raise FetchRefused("page too large")
            chunks: list[bytes] = []
            size = 0
            for chunk in resp.iter_bytes():
                size += len(chunk)
                if size > self.settings.max_page_bytes:
                    raise FetchRefused("page too large")
                chunks.append(chunk)
            return Page(url=str(resp.url), content_type=ctype, body=b"".join(chunks))
