"""Manual inbox: every .txt / .md file under ./inbox/ is one source document.

Use it for content you saved by hand from sites this tool deliberately doesn't crawl
(Glassdoor, Blind, LeetCode Discuss). Put a line like "Source: https://..." near the top
and the report will link to the original instead of the local file.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

from iqbank.models import RawDoc
from iqbank.sources.base import Candidate, SkipDoc, Source
from iqbank.store import content_hash

if TYPE_CHECKING:
    from iqbank.store import Store

SUFFIXES = {".txt", ".md"}
IGNORED_NAMES = {"readme.md", "readme.txt"}
_SOURCE_LINE = re.compile(r"^\s*(?:source|url|link|from|original)\s*[:=]\s*<?(https?://\S+?)>?\s*$", re.I)
_BARE_URL = re.compile(r"^\s*<?(https?://\S+?)>?\s*$")


def detect_original_url(text: str, max_lines: int = 10) -> str | None:
    """Find a declared source URL in the first few non-empty lines."""
    lines = [ln for ln in text.splitlines() if ln.strip()][:max_lines]
    for line in lines:
        if m := _SOURCE_LINE.match(line):
            return m.group(1).rstrip(").,;")
    if lines and (m := _BARE_URL.match(lines[0])):
        return m.group(1).rstrip(").,;")
    return None


def title_from(text: str, fallback: str) -> str:
    for line in text.splitlines():
        line = line.strip().lstrip("#").strip()
        if line and not _SOURCE_LINE.match(line) and not _BARE_URL.match(line):
            return line[:120]
    return fallback


class InboxSource(Source):
    name = "inbox"
    refetch_known = True

    def check_config(self) -> str | None:
        return None

    def _files(self) -> list[Path]:
        root = self.settings.inbox_dir
        if not root.is_dir():
            return []
        return sorted(
            p
            for p in root.rglob("*")
            if p.is_file()
            and p.suffix.lower() in SUFFIXES
            and p.name.lower() not in IGNORED_NAMES
            and not any(part.startswith(".") for part in p.relative_to(root).parts)
        )

    def _url(self, path: Path) -> str:
        return "inbox://" + path.relative_to(self.settings.inbox_dir).as_posix()

    def plan(self, store: "Store") -> list[str]:
        files = self._files()
        if not files:
            return [f"no .txt/.md files in {self.settings.inbox_dir}/"]
        lines = []
        for p in files:
            existing = store.get_doc(self._url(p))
            text = p.read_text(encoding="utf-8", errors="replace")
            if existing is None:
                status = "new"
            elif existing.content_hash != content_hash(text):
                status = "changed"
            else:
                status = "unchanged"
            lines.append(f"{status:9} {p}")
        return lines

    def discover(self) -> Iterator[Candidate]:
        for p in self._files():
            yield Candidate(url=self._url(p), title=p.name, data=p)

    def fetch(self, candidate: Candidate) -> RawDoc:
        path: Path = candidate.data
        text = path.read_text(encoding="utf-8", errors="replace")
        if not text.strip():
            raise SkipDoc("empty file", remember=False)
        meta: dict[str, str] = {"path": str(path)}
        if original := detect_original_url(text):
            meta["original_url"] = original
        return RawDoc(
            url=candidate.url,
            source=self.name,
            title=title_from(text, path.name),
            raw_text=text,
            meta=meta,
        )
