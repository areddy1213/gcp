"""Source registry and the incremental collect pipeline."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from iqbank.config import Settings
from iqbank.net import HttpClient
from iqbank.sources.base import Candidate, SkipDoc, Source, SourceUnavailable
from iqbank.sources.github import GitHubSource
from iqbank.sources.inbox import InboxSource
from iqbank.sources.reddit import RedditSource
from iqbank.sources.websearch import WebSearchSource
from iqbank.store import Store

__all__ = ["Candidate", "SkipDoc", "Source", "SourceUnavailable", "SOURCE_NAMES", "build_sources", "collect"]

log = logging.getLogger(__name__)

SOURCE_NAMES = ("reddit", "web", "github", "inbox")


def build_sources(settings: Settings, names: list[str] | tuple[str, ...], http: HttpClient) -> list[Source]:
    names = list(names) or list(SOURCE_NAMES)
    reddit = RedditSource(settings)
    built: list[Source] = []
    for name in SOURCE_NAMES:  # fixed order regardless of how they were requested
        if name not in names:
            continue
        if name == "reddit":
            built.append(reddit)
        elif name == "web":
            built.append(WebSearchSource(settings, http, reddit=reddit))
        elif name == "github":
            built.append(GitHubSource(settings, http))
        elif name == "inbox":
            built.append(InboxSource(settings))
    return built


@dataclass
class CollectStats:
    discovered: int = 0
    new: int = 0
    updated: int = 0
    unchanged: int = 0  # already stored (not refetched), or refetched with identical content
    skipped: int = 0
    failed: int = 0
    status: str = "ok"

    def __str__(self) -> str:
        if self.status != "ok":
            return self.status
        return (
            f"{self.discovered} found: {self.new} new, {self.updated} updated, {self.unchanged} already stored, "
            f"{self.skipped} skipped, {self.failed} failed"
        )


def collect(
    store: Store, sources: list[Source], settings: Settings, *, dry_run: bool = False, echo=print
) -> dict[str, CollectStats]:
    results: dict[str, CollectStats] = {}
    for src in sources:
        stats = results.setdefault(src.name, CollectStats())
        if reason := src.check_config():
            log.warning("%s: not configured (%s); skipping this source", src.name, reason)
            stats.status = f"not configured: {reason}"
            continue
        if dry_run:
            echo(f"[dry-run] {src.name}:")
            for line in src.plan(store):
                echo(f"  - {line}")
            stats.status = "dry run"
            continue

        log.info("%s: collecting", src.name)
        try:
            for cand in src.discover():
                stats.discovered += 1
                if not src.refetch_known:
                    if store.has_doc(cand.url):
                        stats.unchanged += 1
                        continue
                    if store.is_skipped(cand.url, settings.skip_ttl_days):
                        stats.skipped += 1
                        continue
                try:
                    doc = src.fetch(cand)
                except SkipDoc as exc:
                    stats.skipped += 1
                    log.info("%s: skip %s (%s)", src.name, cand.url, exc.reason)
                    if exc.remember:
                        store.mark_skipped(cand.url, src.name, exc.reason)
                    continue
                except SourceUnavailable:
                    raise
                except Exception as exc:  # noqa: BLE001 - one bad document shouldn't end the run
                    stats.failed += 1
                    log.warning("%s: failed to fetch %s: %s", src.name, cand.url, exc)
                    log.debug("traceback", exc_info=True)
                    continue
                outcome = store.upsert_doc(doc)
                setattr(stats, outcome, getattr(stats, outcome) + 1)
                if outcome != "unchanged":
                    log.info("%s: %s %s", src.name, outcome, doc.url)
        except SourceUnavailable as exc:
            log.error("%s: stopping this source: %s", src.name, exc)
            stats.status = f"stopped: {exc} ({stats})"
        except KeyboardInterrupt:
            raise
        except Exception as exc:  # noqa: BLE001
            log.error("%s: discovery failed: %s", src.name, exc)
            log.debug("traceback", exc_info=True)
            stats.status = f"error: {exc} ({stats})"
    return results
