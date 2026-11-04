"""Sources and the polite-HTTP layer, without real network access."""

from __future__ import annotations

import httpx
import pytest

from iqbank.config import Settings
from iqbank.models import RawDoc
from iqbank.net import (
    FetchRefused,
    HttpClient,
    blocked_by,
    canonical_url,
    parse_retry_after,
)
from iqbank.sources import Candidate, SkipDoc, Source, SourceUnavailable, collect
from iqbank.sources.github import mention_excerpt
from iqbank.sources.inbox import InboxSource, detect_original_url
from iqbank.sources.websearch import (
    WebSearchSource,
    page_to_text,
    parse_brave,
    parse_serper,
)

BLOCK = ["glassdoor.*", "teamblind.com", "leetcode.com", "1point3acres.com"]


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://www.glassdoor.com/Interview/Glean.htm", "glassdoor.*"),
        ("https://www.glassdoor.co.uk/Interview/x", "glassdoor.*"),
        ("https://uk.glassdoor.com/x", "glassdoor.*"),
        ("https://www.teamblind.com/post/abc", "teamblind.com"),
        ("https://leetcode.com/discuss/interview-question/1", "leetcode.com"),
        ("https://www.1point3acres.com/bbs/thread-1", "1point3acres.com"),
        ("https://notleetcode.com/x", None),
        ("https://leetcode.com.evil.example/x", None),
        ("https://medium.com/@someone/glean-interview", None),
    ],
)
def test_blocklist(url, expected):
    assert blocked_by(url, BLOCK) == expected


def test_canonical_url():
    assert canonical_url("https://Example.com/a/?utm_source=x&id=3#frag") == "https://example.com/a?id=3"
    a = canonical_url("https://www.reddit.com/r/cscareerquestions/comments/AbC12/glean_onsite/?share_id=1")
    b = canonical_url("https://old.reddit.com/r/CSCareerQuestions/comments/abc12/")
    assert a == b == "https://www.reddit.com/comments/abc12/"


def test_parse_retry_after():
    assert parse_retry_after("7") == 7.0
    assert parse_retry_after(None) is None
    assert parse_retry_after("soon") is None


def test_search_result_parsing():
    serper = {"organic": [{"title": "T", "link": "https://a.example/x", "snippet": "s", "date": "Mar 1, 2024"},
                          {"title": "no link"}]}
    brave = {"web": {"results": [{"title": "B", "url": "https://b.example/y", "description": "d", "page_age": "2024"}]}}
    assert [(r.url, r.date) for r in parse_serper(serper)] == [("https://a.example/x", "Mar 1, 2024")]
    assert [(r.url, r.snippet) for r in parse_brave(brave)] == [("https://b.example/y", "d")]
    assert parse_brave({}) == []


def test_mention_excerpt_merges_windows_and_keeps_table_header():
    lines = ["| Company | Problem |", "|---|---|"] + [f"| Other{i} | p{i} |" for i in range(50)]
    lines[20] = "| Glean | Merge Intervals |"
    lines[23] = "| glean | LRU Cache |"
    excerpt = mention_excerpt("\n".join(lines), "Glean", context=2)
    assert excerpt.startswith("| Company | Problem |")
    assert "Merge Intervals" in excerpt and "LRU Cache" in excerpt
    assert excerpt.count("[lines") == 1  # overlapping windows merged
    assert "Other40" not in excerpt
    assert mention_excerpt("Gleaning facts", "Glean") is None  # whole word only


def test_inbox_source(tmp_path):
    inbox = tmp_path / "inbox"
    (inbox / "blind").mkdir(parents=True)
    (inbox / "gd.md").write_text("Source: https://www.glassdoor.com/Interview/x.htm\n\n# Glean SWE onsite\nMerge intervals")
    (inbox / "blind" / "post.txt").write_text("https://www.teamblind.com/post/abc\nGlean security loop")
    (inbox / "README.md").write_text("instructions")
    (inbox / "notes.pdf").write_bytes(b"%PDF")
    (inbox / "empty.txt").write_text("  \n")
    src = InboxSource(Settings(inbox_dir=inbox))
    cands = list(src.discover())
    assert [c.url for c in cands] == ["inbox://blind/post.txt", "inbox://empty.txt", "inbox://gd.md"]
    post = src.fetch(cands[0])
    assert post.meta["original_url"] == "https://www.teamblind.com/post/abc"
    assert post.title == "Glean security loop"
    gd = src.fetch(cands[2])
    assert gd.meta["original_url"].endswith("x.htm") and gd.title == "Glean SWE onsite"
    with pytest.raises(SkipDoc):
        src.fetch(cands[1])


def test_detect_original_url():
    assert detect_original_url("URL: <https://a.example/x>\nbody") == "https://a.example/x"
    assert detect_original_url("just text\nmore") is None


# ---- collect pipeline ----------------------------------------------------------------------


class FakeSource(Source):
    name = "fake"

    def __init__(self, settings, behaviors):
        super().__init__(settings)
        self.behaviors = behaviors
        self.fetched: list[str] = []

    def check_config(self):
        return None

    def plan(self, store):
        return ["would do things"]

    def discover(self):
        for url in self.behaviors:
            yield Candidate(url=url, title=url)

    def fetch(self, cand):
        self.fetched.append(cand.url)
        behavior = self.behaviors[cand.url]
        if behavior == "skip":
            raise SkipDoc("robots")
        if behavior == "skip-transient":
            raise SkipDoc("blocklisted", remember=False)
        if behavior == "boom":
            raise RuntimeError("network down")
        if behavior == "unavailable":
            raise SourceUnavailable("quota")
        return RawDoc(url=cand.url, source="fake", title="t", raw_text=f"Glean {cand.url}")


def test_collect_is_incremental_and_resilient(store, settings):
    src = FakeSource(settings, {"u1": "ok", "u2": "skip", "u3": "boom", "u4": "skip-transient", "u5": "ok"})
    stats = collect(store, [src], settings)["fake"]
    assert (stats.discovered, stats.new, stats.skipped, stats.failed) == (5, 2, 2, 1)

    src.fetched.clear()
    stats = collect(store, [src], settings)["fake"]
    # stored and remembered-skipped URLs are not fetched again; failures and transient skips are retried
    assert sorted(src.fetched) == ["u3", "u4"]
    assert stats.unchanged == 2


def test_collect_stops_a_source_that_becomes_unavailable(store, settings):
    src = FakeSource(settings, {"u1": "ok", "u2": "unavailable", "u3": "ok"})
    stats = collect(store, [src], settings)["fake"]
    assert stats.status.startswith("stopped") and src.fetched == ["u1", "u2"]


def test_collect_dry_run_only_plans(store, settings):
    src = FakeSource(settings, {"u1": "ok"})
    out = []
    collect(store, [src], settings, dry_run=True, echo=out.append)
    assert src.fetched == [] and out == ["[dry-run] fake:", "  - would do things"]


# ---- HTTP: robots.txt, redirects, blocklist, retries ----------------------------------------

ARTICLE = (
    "<html><head><title>My Glean interview</title></head><body><article><h1>My Glean interview</h1><p>"
    + "I interviewed at Glean for a platform security role and was asked to design mTLS between services. " * 8
    + "</p></article></body></html>"
)


def make_http(handler, **settings_kw) -> HttpClient:
    s = Settings(min_host_interval=0.0, **settings_kw)
    return HttpClient(s, client=httpx.Client(transport=httpx.MockTransport(handler), headers={"User-Agent": s.user_agent}))


def test_fetch_page_honors_robots_and_redirect_blocklist():
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.endswith("/robots.txt"):
            if request.url.host == "blog.example":
                return httpx.Response(200, text="User-agent: *\nDisallow: /private/\n")
            return httpx.Response(404)
        if url == "https://blog.example/post":
            return httpx.Response(200, text=ARTICLE, headers={"content-type": "text/html; charset=utf-8"})
        if url == "https://short.example/go":
            return httpx.Response(301, headers={"location": "https://www.glassdoor.com/Interview/x"})
        if url == "https://blog.example/pdf":
            return httpx.Response(200, content=b"%PDF", headers={"content-type": "application/pdf"})
        return httpx.Response(500)

    http = make_http(handler)
    page = http.fetch_page("https://blog.example/post", BLOCK)
    title, text, _ = page_to_text(page.body, page.url)
    assert title == "My Glean interview" and "mTLS" in text

    with pytest.raises(FetchRefused, match="robots"):
        http.fetch_page("https://blog.example/private/notes", BLOCK)
    with pytest.raises(FetchRefused, match="blocklisted"):
        http.fetch_page("https://short.example/go", BLOCK)
    with pytest.raises(FetchRefused, match="content type"):
        http.fetch_page("https://blog.example/pdf", BLOCK)


def test_retries_on_429_then_succeeds(monkeypatch):
    monkeypatch.setattr("iqbank.net._wait", lambda state: 0)
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(429, headers={"retry-after": "0"})
        return httpx.Response(200, json={"ok": True})

    http = make_http(handler)
    assert http.request("GET", "https://api.example/x").json() == {"ok": True}
    assert calls["n"] == 3


def test_robots_unreachable_means_do_not_fetch(monkeypatch):
    monkeypatch.setattr("iqbank.net._wait", lambda state: 0)

    def handler(request):
        return httpx.Response(503)

    http = make_http(handler)
    with pytest.raises(FetchRefused, match="robots"):
        http.fetch_page("https://down.example/post", BLOCK)


def test_web_source_skips_login_walls_and_blocklisted(store):
    wall = "<html><body><p>Please sign in to continue</p></body></html>"

    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        if request.url.path == "/wall":
            return httpx.Response(200, text=wall, headers={"content-type": "text/html"})
        if request.url.path == "/forbidden":
            return httpx.Response(403)
        return httpx.Response(200, text=ARTICLE, headers={"content-type": "text/html"})

    settings = Settings(serper_api_key="k", blocklist=list(BLOCK))
    web = WebSearchSource(settings, make_http(handler))
    with pytest.raises(SkipDoc, match="CAPTCHA|login"):
        web.fetch(Candidate(url="https://site.example/wall", data={"raw_url": "https://site.example/wall"}))
    with pytest.raises(SkipDoc, match="login required"):
        web.fetch(Candidate(url="https://site.example/forbidden", data={"raw_url": "https://site.example/forbidden"}))
    with pytest.raises(SkipDoc) as exc:
        web.fetch(Candidate(url="https://www.teamblind.com/x", data={"raw_url": "https://www.teamblind.com/x"}))
    assert exc.value.remember is False
    with pytest.raises(SkipDoc, match="Reddit API"):
        web.fetch(Candidate(url="https://www.reddit.com/comments/abc/", data={"raw_url": "https://reddit.com/r/x/comments/abc/t/"}))
    doc = web.fetch(Candidate(url="https://site.example/ok", title="t", data={"raw_url": "https://site.example/ok", "query": "q"}))
    assert doc.raw_text.startswith("Title: My Glean interview") and doc.meta["query"] == "q"


# ---- GitHub & Reddit with fakes -------------------------------------------------------------


def test_github_source_discovers_and_excerpts():
    from iqbank.sources.github import GitHubSource

    readme = "\n".join(["| Company | Problems |", "|---|---|"] + [f"| Co{i} | x |" for i in range(80)]
                       + ["| Glean | Merge Intervals, LRU Cache |"] + [f"| Zz{i} | y |" for i in range(80)])

    def handler(request):
        path = request.url.path
        assert request.headers["authorization"] == "Bearer tok"
        if path == "/search/repositories":
            return httpx.Response(200, json={"items": [
                {"full_name": "a/lists", "default_branch": "main", "stargazers_count": 900, "fork": False},
                {"full_name": "b/fork", "default_branch": "main", "stargazers_count": 5, "fork": True},
            ]})
        if path == "/repos/a/lists/git/trees/main":
            return httpx.Response(200, json={"tree": [
                {"type": "blob", "path": "companies/Glean.csv", "size": 100},
                {"type": "blob", "path": "companies/Other.csv", "size": 100},
            ]})
        if path == "/search/code":
            assert "repo:a/lists" in request.url.params["q"]
            return httpx.Response(200, json={"items": [{"path": "README.md"}, {"path": "companies/Glean.csv"}]})
        if path == "/repos/a/lists/contents/companies/Glean.csv":
            return httpx.Response(200, text="Title,Difficulty\nMerge Intervals,Medium\nLRU Cache,Medium\n")
        if path == "/repos/a/lists/contents/README.md":
            return httpx.Response(200, text=readme)
        return httpx.Response(404)

    http = make_http(handler)
    src = GitHubSource(Settings(github_token="tok", github_repo_queries=["q"]), http)
    http.limiter._intervals.clear()  # no sleeping in tests
    cands = list(src.discover())
    assert [c.data["path"] for c in cands] == ["companies/Glean.csv", "README.md"]  # company-named first
    whole = src.fetch(cands[0])
    assert "LRU Cache,Medium" in whole.raw_text and whole.meta["excerpt"] is False
    part = src.fetch(cands[1])
    assert part.meta["excerpt"] is True and "Glean | Merge Intervals" in part.raw_text
    assert "Co10 " not in part.raw_text and len(part.raw_text) < len(readme)


def test_reddit_thread_formatting_and_relevance():
    from types import SimpleNamespace as NS

    from iqbank.sources.reddit import RedditSource, format_thread

    sub = NS(title="Glean onsite experience", subreddit=NS(display_name="cscareerquestions"), created_utc=1714521600,
             score=42, num_comments=3, selftext="Had my Glean onsite last week.", permalink="/r/cscareerquestions/comments/abc12/glean/",
             url="")
    comments = [
        NS(body="They asked merge intervals", score=10, created_utc=1714608000, author="u1", depth=0),
        NS(body="[deleted]", score=99, created_utc=1714608000, author=None, depth=0),
        NS(body="Rules reminder", score=50, created_utc=1714608000, author="AutoModerator", depth=0),
        NS(body="Same, plus system design", score=3, created_utc=1714608000, author="u2", depth=1),
    ]
    text = format_thread(sub, comments, comment_limit=10)
    assert "Posted: 2024-05-01" in text and "[10 points, 2024-05-02] They asked merge intervals" in text
    assert "(reply)" in text and "deleted" not in text and "Rules reminder" not in text
    assert text.index("merge intervals") < text.index("system design")  # sorted by score

    src = RedditSource(Settings(reddit_client_id="i", reddit_client_secret="s", reddit_user_agent="ua"))
    src._load_comments = lambda s: comments  # no network
    doc = src.fetch(Candidate(url="x", data=sub))
    assert doc.url == "https://www.reddit.com/comments/abc12/" and doc.meta["subreddit"] == "cscareerquestions"
    off_topic = NS(**{**sub.__dict__, "title": "Startup interviews", "selftext": "general advice"})
    src._load_comments = lambda s: []
    with pytest.raises(SkipDoc):
        src.fetch(Candidate(url="y", data=off_topic))
