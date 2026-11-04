"""GitHub REST API: find company-wise LeetCode list repos, then pull files that mention the company.

Per repo, a file qualifies if its path names the company (e.g. companies/Glean.csv) or if
code search finds the company name in its contents. Files named after the company are kept
whole; other files (a README covering hundreds of companies) keep only the lines around each
mention, and the stored doc is marked as an excerpt.
"""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

import httpx

from iqbank.models import RawDoc
from iqbank.net import HttpClient
from iqbank.sources.base import Candidate, SkipDoc, Source, SourceUnavailable

if TYPE_CHECKING:
    from iqbank.store import Store

log = logging.getLogger(__name__)

API = "https://api.github.com"
MAX_FILE_BYTES = 2_000_000
CODE_SEARCH_INTERVAL = 6.5  # code search allows 10 requests/minute when authenticated
MAX_RATE_LIMIT_SLEEP = 900


def mention_excerpt(text: str, term: str, context: int = 15, max_windows: int = 40) -> str | None:
    """Lines around each case-insensitive whole-word mention of `term`, merged where they overlap."""
    lines = text.splitlines()
    pattern = re.compile(rf"\b{re.escape(term)}\b", re.I)
    hits = [i for i, line in enumerate(lines) if pattern.search(line)]
    if not hits:
        return None
    windows: list[list[int]] = []
    for i in hits:
        lo, hi = max(0, i - context), min(len(lines), i + context + 1)
        if windows and lo <= windows[-1][1]:
            windows[-1][1] = max(windows[-1][1], hi)
        else:
            windows.append([lo, hi])
    parts = []
    # Tables: keep the header row so the excerpt stays readable.
    if lines and lines[0].lstrip().startswith("|") and windows[0][0] > 0:
        parts.append("\n".join(lines[:2]))
    for lo, hi in windows[:max_windows]:
        parts.append(f"[lines {lo + 1}-{hi}]\n" + "\n".join(lines[lo:hi]))
    if len(windows) > max_windows:
        parts.append(f"[{len(windows) - max_windows} more matching sections omitted]")
    return "\n...\n".join(parts)


class GitHubSource(Source):
    name = "github"

    def __init__(self, settings, http: HttpClient):
        super().__init__(settings)
        self.http = http
        self.http.limiter.set_interval("github-code-search", CODE_SEARCH_INTERVAL)
        self.http.limiter.set_interval("github", 0.5)

    def check_config(self) -> str | None:
        return None if self.settings.github_token else "set GITHUB_TOKEN in .env (code search requires auth)"

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.settings.github_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def plan(self, store: "Store") -> list[str]:
        s = self.settings
        return [
            *(f"search repositories {q!r} (by stars)" for q in s.github_repo_queries),
            f"take the top {s.github_max_repos} repos; in each, list files whose path or contents mention "
            f"{s.company!r} (up to {s.github_max_files_per_repo} files per repo)",
        ]

    def _get(self, path: str, *, params: dict[str, Any] | None = None, accept: str | None = None,
             rate_key: str = "github") -> httpx.Response:
        headers = dict(self.headers)
        if accept:
            headers["Accept"] = accept
        try:
            resp = self.http.request("GET", API + path, params=params, headers=headers, rate_key=rate_key)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 401:
                raise SourceUnavailable("GitHub rejected GITHUB_TOKEN (401)") from exc
            raise
        remaining, reset = resp.headers.get("x-ratelimit-remaining"), resp.headers.get("x-ratelimit-reset")
        if remaining == "0" and reset and reset.isdigit():
            wait = int(reset) - time.time() + 1
            if wait > MAX_RATE_LIMIT_SLEEP:
                raise SourceUnavailable(f"GitHub rate limit exhausted for {wait / 60:.0f} more minutes")
            if wait > 0:
                log.info("github: rate limit reached; sleeping %.0fs", wait)
                time.sleep(wait)
        return resp

    def _repos(self) -> list[dict[str, Any]]:
        repos: dict[str, dict[str, Any]] = {}
        for q in self.settings.github_repo_queries:
            try:
                data = self._get(
                    "/search/repositories",
                    params={"q": q, "sort": "stars", "order": "desc", "per_page": self.settings.github_max_repos},
                ).json()
            except SourceUnavailable:
                raise
            except Exception as exc:  # noqa: BLE001
                log.warning("github: repo search %r failed: %s", q, exc)
                continue
            for item in data.get("items", []):
                if not item.get("fork"):  # forks mostly duplicate the original's files
                    repos.setdefault(item["full_name"], item)
        ranked = sorted(repos.values(), key=lambda r: r.get("stargazers_count", 0), reverse=True)
        return ranked[: self.settings.github_max_repos]

    def _matching_paths(self, repo: dict[str, Any]) -> dict[str, int | None]:
        full, branch = repo["full_name"], repo.get("default_branch") or "main"
        company = self.settings.company.lower()
        paths: dict[str, int | None] = {}
        try:
            tree = self._get(f"/repos/{full}/git/trees/{quote(branch, safe='')}", params={"recursive": "1"}).json()
            for node in tree.get("tree", []):
                if node.get("type") == "blob" and company in node.get("path", "").lower():
                    paths[node["path"]] = node.get("size")
        except SourceUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001
            log.warning("github: tree listing failed for %s: %s", full, exc)
        try:
            found = self._get(
                "/search/code",
                params={"q": f'"{self.settings.company}" repo:{full}', "per_page": 50},
                rate_key="github-code-search",
            ).json()
            for item in found.get("items", []):
                paths.setdefault(item["path"], None)
        except SourceUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001
            log.warning("github: code search failed for %s: %s", full, exc)
        return paths

    def discover(self) -> Iterator[Candidate]:
        for repo in self._repos():
            full, branch = repo["full_name"], repo.get("default_branch") or "main"
            paths = self._matching_paths(repo)
            log.info("github: %s (%d stars) -> %d matching files", full, repo.get("stargazers_count", 0), len(paths))
            # Files named after the company first: they're the company-specific lists.
            company = self.settings.company.lower()
            ordered = sorted(paths, key=lambda p: (company not in p.lower(), p))
            for path in ordered[: self.settings.github_max_files_per_repo]:
                size = paths[path]
                if size is not None and size > MAX_FILE_BYTES:
                    log.info("github: skipping %s/%s (%d bytes)", full, path, size)
                    continue
                yield Candidate(
                    url=f"https://github.com/{full}/blob/{quote(branch)}/{quote(path)}",
                    title=f"{full}: {path}",
                    data={"repo": full, "branch": branch, "path": path, "stars": repo.get("stargazers_count", 0)},
                )

    def fetch(self, candidate: Candidate) -> RawDoc:
        d = candidate.data
        try:
            resp = self._get(
                f"/repos/{d['repo']}/contents/{quote(d['path'])}",
                params={"ref": d["branch"]},
                accept="application/vnd.github.raw",
            )
        except httpx.HTTPStatusError as exc:
            raise SkipDoc(f"HTTP {exc.response.status_code}") from exc
        body = resp.content
        if len(body) > MAX_FILE_BYTES:
            raise SkipDoc("file too large")
        if b"\x00" in body[:8192]:
            raise SkipDoc("binary file")
        text = body.decode("utf-8", errors="replace")
        company = self.settings.company
        excerpt = company.lower() not in d["path"].lower()
        if excerpt:
            text = mention_excerpt(text, company)
            if text is None:
                raise SkipDoc(f"file does not mention {company}")
        header = (
            f"Repository: {d['repo']} ({d['stars']} stars)\nFile: {d['path']}\n"
            + (f"(Excerpt: only the lines around each mention of {company}.)\n" if excerpt else "")
        )
        return RawDoc(
            url=candidate.url,
            source=self.name,
            title=candidate.title,
            raw_text=header + "\n" + text.strip() + "\n",
            meta={"repo": d["repo"], "path": d["path"], "branch": d["branch"], "stars": d["stars"],
                  "excerpt": excerpt},
        )
