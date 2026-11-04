"""Settings: built-in defaults < iqbank.toml < environment (.env) < CLI flags.

Credentials only ever come from the environment (normally a git-ignored .env file).
The TOML file is for non-secret tuning: queries, subreddits, blocklist, limits.
"""

from __future__ import annotations

import logging
import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

log = logging.getLogger(__name__)

DEFAULT_COMPANY = "Glean"
DEFAULT_ROLES = ["Platform Security Engineer", "Software Engineer"]

# Used only when company is the default, to disambiguate "glean" the verb.
COMPANY_DESCRIPTIONS = {
    "glean": "Glean (glean.com), the enterprise AI search and work-assistant company",
}

DEFAULT_SUBREDDITS = ["cscareerquestions", "leetcode", "ExperiencedDevs", "csMajors"]
DEFAULT_REDDIT_QUERIES = ["{company} interview", "{company} onsite", "{company} phone screen"]

DEFAULT_WEB_QUERIES = [
    "{company} software engineer interview questions",
    "{company} security engineer interview",
    "{company} system design interview",
]
# Entries match the domain and all of its subdomains. An entry ending in ".*"
# matches any TLD (glassdoor.* covers glassdoor.com, glassdoor.co.uk, ...).
DEFAULT_BLOCKLIST = ["glassdoor.*", "teamblind.com", "leetcode.com", "1point3acres.com"]

DEFAULT_GITHUB_REPO_QUERIES = [
    "company wise leetcode questions",
    "leetcode company wise problems",
    "leetcode questions by company",
]

DEFAULT_MODEL = "claude-sonnet-5-5"
DEFAULT_USER_AGENT = "iqbank/0.1 (personal interview-prep research; honors robots.txt)"


@dataclass
class Settings:
    company: str = DEFAULT_COMPANY
    roles: list[str] = field(default_factory=lambda: list(DEFAULT_ROLES))
    company_description: str = ""

    db_path: Path = Path("iqbank.db")
    inbox_dir: Path = Path("inbox")
    out_dir: Path = Path("out")

    # Claude
    model: str = DEFAULT_MODEL
    effort: str = "medium"
    use_fallbacks: bool = True
    max_chunk_chars: int = 150_000  # docs longer than this are split, never truncated
    dedupe_batch_size: int = 300

    # Reddit (PRAW, official API)
    reddit_client_id: str | None = None
    reddit_client_secret: str | None = None
    reddit_user_agent: str | None = None
    subreddits: list[str] = field(default_factory=lambda: list(DEFAULT_SUBREDDITS))
    reddit_queries: list[str] = field(default_factory=lambda: list(DEFAULT_REDDIT_QUERIES))
    reddit_post_limit: int = 25
    reddit_comment_limit: int = 40

    # Web search
    search_provider: str | None = None  # "serper" | "brave" | None (auto)
    serper_api_key: str | None = None
    brave_api_key: str | None = None
    web_queries: list[str] = field(default_factory=lambda: list(DEFAULT_WEB_QUERIES))
    web_results_per_query: int = 10
    blocklist: list[str] = field(default_factory=lambda: list(DEFAULT_BLOCKLIST))

    # GitHub
    github_token: str | None = None
    github_repo_queries: list[str] = field(default_factory=lambda: list(DEFAULT_GITHUB_REPO_QUERIES))
    github_max_repos: int = 8
    github_max_files_per_repo: int = 20

    # HTTP politeness
    user_agent: str = DEFAULT_USER_AGENT
    min_host_interval: float = 2.0  # seconds between requests to the same host
    request_timeout: float = 20.0
    max_page_bytes: int = 3_000_000
    skip_ttl_days: int = 30  # how long a skipped URL (robots, 404, no text) stays skipped

    # ---- derived helpers -------------------------------------------------

    def fmt(self, template: str) -> str:
        """Fill {company} / {role} placeholders in a query template."""
        return template.format(company=self.company, role=self.roles[0] if self.roles else "")

    @property
    def company_label(self) -> str:
        return self.company_description or COMPANY_DESCRIPTIONS.get(self.company.lower(), self.company)

    @property
    def roles_label(self) -> str:
        return " / ".join(self.roles) if self.roles else "any engineering role"

    # ---- loading ---------------------------------------------------------

    @classmethod
    def load(
        cls,
        config_path: Path | None = None,
        env_file: Path | None = None,
        overrides: dict[str, Any] | None = None,
    ) -> "Settings":
        s = cls()
        if config_path is None and Path("iqbank.toml").exists():
            config_path = Path("iqbank.toml")
        if config_path is not None:
            s._apply_toml(config_path)
        if env_file is not None:
            load_dotenv(env_file, override=False)
        else:
            load_dotenv(override=False)  # ./.env if present
        s._apply_env(os.environ)
        for key, value in (overrides or {}).items():
            if value is None or value == () or value == []:
                continue
            if not hasattr(s, key):
                raise ValueError(f"unknown setting {key!r}")
            setattr(s, key, list(value) if isinstance(value, tuple) else value)
        return s

    def _apply_toml(self, path: Path) -> None:
        with open(path, "rb") as fh:
            data = tomllib.load(fh)
        top = {
            "company": "company",
            "roles": "roles",
            "company_description": "company_description",
            "db_path": "db_path",
            "inbox_dir": "inbox_dir",
            "out_dir": "out_dir",
        }
        sections = {
            "llm": {
                "model": "model",
                "effort": "effort",
                "fallbacks": "use_fallbacks",
                "max_chunk_chars": "max_chunk_chars",
                "dedupe_batch_size": "dedupe_batch_size",
            },
            "reddit": {
                "subreddits": "subreddits",
                "queries": "reddit_queries",
                "post_limit": "reddit_post_limit",
                "comment_limit": "reddit_comment_limit",
            },
            "web": {
                "provider": "search_provider",
                "queries": "web_queries",
                "results_per_query": "web_results_per_query",
                "blocklist": "blocklist",
            },
            "github": {
                "repo_queries": "github_repo_queries",
                "max_repos": "github_max_repos",
                "max_files_per_repo": "github_max_files_per_repo",
            },
            "http": {
                "user_agent": "user_agent",
                "min_host_interval": "min_host_interval",
                "request_timeout": "request_timeout",
                "max_page_bytes": "max_page_bytes",
                "skip_ttl_days": "skip_ttl_days",
            },
        }
        for key, value in data.items():
            if key in top:
                self._set(top[key], value)
            elif key in sections and isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    if sub_key == "extra_blocklist" and key == "web":
                        self.blocklist.extend(sub_value)
                    elif sub_key in sections[key]:
                        self._set(sections[key][sub_key], sub_value)
                    else:
                        log.warning("%s: unknown key [%s].%s ignored", path, key, sub_key)
            else:
                log.warning("%s: unknown key %r ignored", path, key)

    def _apply_env(self, env: Any) -> None:
        def get(name: str) -> str | None:
            value = env.get(name)
            return value.strip() if value and value.strip() else None

        self.reddit_client_id = get("REDDIT_CLIENT_ID") or self.reddit_client_id
        self.reddit_client_secret = get("REDDIT_CLIENT_SECRET") or self.reddit_client_secret
        self.reddit_user_agent = get("REDDIT_USER_AGENT") or self.reddit_user_agent
        self.serper_api_key = get("SERPER_API_KEY") or self.serper_api_key
        self.brave_api_key = get("BRAVE_API_KEY") or self.brave_api_key
        self.search_provider = get("SEARCH_PROVIDER") or self.search_provider
        self.github_token = get("GITHUB_TOKEN") or self.github_token
        self.model = get("IQBANK_MODEL") or self.model
        self.effort = get("IQBANK_EFFORT") or self.effort
        self.user_agent = get("IQBANK_USER_AGENT") or self.user_agent
        if (fb := get("IQBANK_FALLBACKS")) is not None:
            self.use_fallbacks = fb.lower() not in {"0", "false", "no", "off"}
        if extra := get("IQBANK_BLOCKLIST"):
            self.blocklist.extend(d.strip() for d in extra.split(",") if d.strip())

    def _set(self, attr: str, value: Any) -> None:
        current = getattr(self, attr)
        if isinstance(current, Path) or attr.endswith(("_path", "_dir")):
            value = Path(value)
        setattr(self, attr, value)
