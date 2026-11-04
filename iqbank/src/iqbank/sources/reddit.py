"""Reddit via PRAW (the official API, read-only). PRAW handles Reddit's rate-limit headers itself."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from iqbank.extract import mentions
from iqbank.models import RawDoc
from iqbank.net import canonical_url, with_retries
from iqbank.sources.base import Candidate, SkipDoc, Source, SourceUnavailable

if TYPE_CHECKING:
    from iqbank.store import Store

log = logging.getLogger(__name__)


def _prawcore_retryable() -> tuple[type[BaseException], ...]:
    try:
        from prawcore import exceptions as e
    except ImportError:  # pragma: no cover
        return ()
    return (e.ServerError, e.RequestException, e.TooManyRequests)


def _prawcore_auth_errors() -> tuple[type[BaseException], ...]:
    try:
        from prawcore import exceptions as e
    except ImportError:  # pragma: no cover
        return ()
    return (e.OAuthException, e.InvalidToken, e.Forbidden, e.InsufficientScope)


_retry = with_retries(attempts=5, extra_exceptions=_prawcore_retryable())


def _date(ts: float | None) -> str:
    if not ts:
        return "unknown"
    return datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()


def format_thread(submission: Any, comments: list[Any], comment_limit: int) -> str:
    """Render a post and its top comments as plain text for extraction."""
    lines = [
        f"Title: {submission.title}",
        f"Subreddit: r/{submission.subreddit.display_name}",
        f"Posted: {_date(submission.created_utc)} | Score: {submission.score} | "
        f"Comments: {submission.num_comments}",
        "",
        (submission.selftext or "").strip() or f"(link post: {getattr(submission, 'url', '')})",
    ]
    kept = [
        c
        for c in comments
        if getattr(c, "body", None)
        and c.body not in ("[deleted]", "[removed]")
        and str(getattr(c, "author", "") or "") != "AutoModerator"
    ]
    kept.sort(key=lambda c: c.score or 0, reverse=True)
    if kept:
        lines += ["", "--- Top comments ---"]
        for c in kept[:comment_limit]:
            reply = " (reply)" if getattr(c, "depth", 0) else ""
            lines.append(f"[{c.score} points, {_date(c.created_utc)}{reply}] {c.body.strip()}")
            lines.append("")
    return "\n".join(lines).strip() + "\n"


class RedditSource(Source):
    name = "reddit"

    def __init__(self, settings):
        super().__init__(settings)
        self._client = None

    def check_config(self) -> str | None:
        s = self.settings
        missing = [
            name
            for name, value in (
                ("REDDIT_CLIENT_ID", s.reddit_client_id),
                ("REDDIT_CLIENT_SECRET", s.reddit_client_secret),
                ("REDDIT_USER_AGENT", s.reddit_user_agent),
            )
            if not value
        ]
        return f"missing {', '.join(missing)} in .env" if missing else None

    @property
    def client(self):
        if self._client is None:
            import praw

            self._client = praw.Reddit(
                client_id=self.settings.reddit_client_id,
                client_secret=self.settings.reddit_client_secret,
                user_agent=self.settings.reddit_user_agent,
                check_for_async=False,
                timeout=int(self.settings.request_timeout),
            )
            self._client.read_only = True
        return self._client

    def _queries(self) -> list[str]:
        return [self.settings.fmt(q) for q in self.settings.reddit_queries]

    def plan(self, store: "Store") -> list[str]:
        return [
            f"search r/{sub} for {q!r} (up to {self.settings.reddit_post_limit} posts; "
            f"top {self.settings.reddit_comment_limit} comments each)"
            for sub in self.settings.subreddits
            for q in self._queries()
        ]

    @_retry
    def _search(self, subreddit: str, query: str) -> list[Any]:
        return list(
            self.client.subreddit(subreddit).search(
                query, sort="relevance", time_filter="all", limit=self.settings.reddit_post_limit
            )
        )

    def discover(self) -> Iterator[Candidate]:
        seen: set[str] = set()
        for sub in self.settings.subreddits:
            for query in self._queries():
                try:
                    results = self._search(sub, query)
                except _prawcore_auth_errors() as exc:
                    raise SourceUnavailable(f"Reddit rejected the credentials ({exc})") from exc
                except Exception as exc:  # noqa: BLE001 - one failed search shouldn't stop the others
                    log.warning("reddit: search r/%s %r failed: %s", sub, query, exc)
                    continue
                log.info("reddit: r/%s %r -> %d posts", sub, query, len(results))
                for s in results:
                    if s.id in seen:
                        continue
                    seen.add(s.id)
                    yield Candidate(url=canonical_url(f"https://www.reddit.com{s.permalink}"), title=s.title, data=s)

    @_retry
    def _load_comments(self, submission: Any) -> list[Any]:
        submission.comment_sort = "top"
        submission.comments.replace_more(limit=0)
        return submission.comments.list()

    def _doc(self, submission: Any, query: str | None = None) -> RawDoc:
        comments = self._load_comments(submission)
        text = format_thread(submission, comments, self.settings.reddit_comment_limit)
        if not mentions(self.settings.company, text):
            raise SkipDoc(f"thread does not mention {self.settings.company}")
        meta = {
            "subreddit": submission.subreddit.display_name,
            "score": submission.score,
            "num_comments": submission.num_comments,
            "created": _date(submission.created_utc),
            "permalink": f"https://www.reddit.com{submission.permalink}",
        }
        if query:
            meta["query"] = query
        return RawDoc(
            url=canonical_url(f"https://www.reddit.com{submission.permalink}"),
            source=self.name,
            title=submission.title,
            raw_text=text,
            meta=meta,
        )

    def fetch(self, candidate: Candidate) -> RawDoc:
        return self._doc(candidate.data)

    def fetch_url(self, url: str) -> RawDoc:
        """Fetch a thread found by web search, through the API rather than scraping reddit.com."""
        try:
            submission = self.client.submission(url=url)
            _ = submission.title  # force the lazy load so errors surface here
        except _prawcore_auth_errors() as exc:
            raise SourceUnavailable(f"Reddit rejected the credentials ({exc})") from exc
        except Exception as exc:  # noqa: BLE001
            raise SkipDoc(f"reddit API could not load thread: {exc}", remember=False) from exc
        return self._doc(submission)
