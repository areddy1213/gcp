# iqbank

A small CLI that collects interview questions reported for one company and role, pulls the
individual questions out with Claude, merges near-duplicates, and writes a frequency-ranked
question bank plus a summary of what the interview loop looks like.

Defaults: company **Glean**, roles **Platform Security Engineer / Software Engineer**.

```
collect  ─▶  SQLite (raw docs)  ─▶  extract (Claude)  ─▶  dedupe (Claude)  ─▶  report
reddit · web · github · inbox        questions + loop info     clusters + counts     questions.csv / .md
```

## Setup

Python 3.11+.

```bash
cd iqbank
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env        # then fill in the keys you have
```

| Source | Needs | Notes |
|---|---|---|
| Claude | `ANTHROPIC_API_KEY` (or `ant auth login`) | extraction, dedupe, loop summary |
| Reddit | `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USER_AGENT` | a "script" app from reddit.com/prefs/apps; read-only API via PRAW |
| Web | `SERPER_API_KEY` **or** `BRAVE_API_KEY` | search API; result pages fetched with httpx + trafilatura |
| GitHub | `GITHUB_TOKEN` | fine-grained token, public read-only is enough (code search needs auth) |
| Inbox | nothing | `.txt` / `.md` files you save into `./inbox/` |

Sources without credentials are skipped with a warning, so you can start with just the inbox.

## Usage

```bash
iqbank --dry-run run          # what would happen: no network, no Claude calls, nothing written
iqbank run                    # collect -> extract -> dedupe -> report
```

Or step by step:

```bash
iqbank collect                       # all configured sources
iqbank collect --source inbox        # just your pasted files
iqbank extract                       # only new/changed docs
iqbank dedupe                        # Claude clustering (or --method lexical, offline)
iqbank report                        # writes ./out/
iqbank status                        # what's in the database
```

Other targets:

```bash
iqbank --company Databricks --role "Security Engineer" --db databricks.db run
```

Global flags: `--company`, `--role` (repeatable), `--config`, `--env-file`, `--db`, `--inbox`,
`--model`, `--dry-run`, `-v` / `-vv`, `--log-file`. Every subcommand also accepts `--dry-run`.

### Output (`./out/`)

- **questions.csv**: one row per unique question: `round_type, rank, question, category,
  source_count, mention_count, verbatim, first_reported, last_reported, roles, source_urls, variants`.
- **questions.md**: grouped by round type (phone screen, coding, system design, security deep dive,
  AI exercise, behavioral, hiring manager, unknown), sorted by number of independent sources, with
  links and alternate phrasings.
- **loop_summary.md**: also embedded at the top of questions.md. Statistics over every source that
  described the process (number of rounds, round types, lengths, formats, timelines), plus a short
  Claude-written summary that cites the reports. `--no-llm-summary` keeps just the statistics.

`source_count` counts *independent* sources: identical documents count once, and an inbox file whose
`Source:` line points at a URL counts as the same source as that URL. `mention_count` counts every
extracted mention, including repeats within a Reddit thread.

## How it works

**Collect** (`sources/`). Each source first *discovers* candidates (search API calls), then *fetches*
only the ones not already in the database.
- `reddit.py`: searches r/cscareerquestions, r/leetcode, r/ExperiencedDevs and r/csMajors for
  "Glean interview", "Glean onsite" and "Glean phone screen". Stores each post plus its top 40
  comments, sorted by score, with dates. Threads that never mention the company are skipped.
- `websearch.py`: Serper or Brave queries. Result pages are fetched only if robots.txt allows it.
  Reddit links found by web search go through the Reddit API instead of being scraped.
- `github.py`: searches repositories for company-wise LeetCode lists (top 8 by stars, forks skipped).
  In each one, it pulls files whose path names the company (kept whole) and files where code search
  finds the company name (only the lines around each mention are kept, marked as an excerpt).
- `inbox.py`: each `.txt`/`.md` file is one source. Edited files are picked up again automatically.
  See [inbox/README.md](inbox/README.md).

**Store** (`store.py`). SQLite: `docs(url, source, title, fetched_at, raw_text, content_hash, meta)`,
plus `skipped` (URLs we chose not to keep, re-checked after 30 days), `extractions`, `questions`,
`clusters` and `meta`. Reruns are incremental:
- a URL already in `docs` is never refetched;
- a doc is re-extracted only if its text changed or its last extraction errored;
- dedupe runs again only when the set of questions changed;
- the loop summary is cached on a fingerprint of its inputs.

**Extract** (`extract.py`). One Claude call per document, or per chunk for documents over 150k
characters. Long documents are split, never truncated. Claude answers under a strict JSON schema:

```json
{"question": "...", "round_type": "security_deep_dive", "category": "TLS/mTLS",
 "date_if_known": "2025-02", "source_url": "https://...", "verbatim_or_paraphrased": "paraphrased",
 "role_if_known": "Security Engineer"}
```

plus `relevant` (false for "glean" the verb) and a `loop` object (rounds, format, duration, timeline).
The output still goes through `parse_extraction`, which validates each item separately and normalizes
labels: "tech screen" becomes `phone_screen`, "mTLS" becomes `TLS/mTLS`, "March 2024" becomes `2024-03`.
It also replaces any `source_url` the document didn't supply with the document's own URL. A malformed
item is dropped without losing the rest of the document. Scraped docs that never name the company are
marked irrelevant without a Claude call; inbox files are always sent.

**Dedupe** (`dedupe.py`). Exact matches (case and punctuation ignored) collapse first. Claude then
clusters the rest in batches of 300 and writes a canonical phrasing for each cluster. When there are
more than 300, each batch is clustered, and then the batch representatives are clustered again, so
duplicates that landed in different batches still merge. Claude's grouping is validated: every
question ends up in exactly one cluster, and anything it forgets becomes a singleton. A cluster's round
type and category are the majority vote of its members. If a batch fails, that batch falls back to
lexical similarity. `--method lexical` skips Claude entirely: free, but it misses paraphrases.

**Report** (`report.py`). See [Output](#output-out).

## Responsible collection

- **robots.txt** is checked for every fetched page and every redirect hop. If robots.txt itself
  can't be fetched (5xx, network error), the host is not crawled. `Crawl-delay` is honored (capped at 60 s).
- **Rate limits.** At most one request per host every 2 s. Search APIs and GitHub use their own
  limits (code search: one request per 6.5 s), and GitHub's `x-ratelimit-*` headers are respected.
  PRAW follows Reddit's rate-limit headers.
- **Retries.** Transport errors, 429 and 5xx are retried up to 5 times with exponential backoff and
  jitter, or after `Retry-After` when the server sends one. The Anthropic SDK retries its own calls
  the same way (up to 5 retries).
- **No login bypass, no CAPTCHA solving.** 401/403 responses, login walls and CAPTCHA pages are
  recorded as skipped and never retried another way.
- **Blocklist.** `glassdoor.*` (every Glassdoor TLD), `teamblind.com`, `leetcode.com` and
  `1point3acres.com` are never fetched, including through redirects. Configure it in `iqbank.toml`
  (`[web] blocklist` / `extra_blocklist`), with `IQBANK_BLOCKLIST`, or with `iqbank collect --block
  example.com`. Content from those sites goes in the inbox, copied by hand.
- **Official APIs only** for Reddit and GitHub.
- Collected text stays in your local SQLite file and `out/`, both git-ignored, as is `inbox/`. It's
  for personal prep: don't republish other people's posts.

## Claude usage and cost

- Model: `claude-sonnet-5-5` (override with `--model` or `IQBANK_MODEL`), effort `medium`
  (`IQBANK_EFFORT`). Requests use structured outputs, are streamed, and mark the system prompt as cacheable.
- Server-side refusal fallbacks are on (`fallbacks: "default"`), because security-interview content
  can occasionally trip a safety classifier. If a document is still declined, it's recorded as
  `refused` and skipped. `iqbank extract --reextract` retries it. Turn fallbacks off with
  `IQBANK_FALLBACKS=0`, for example when routing through a platform that doesn't support them.
- Document text is wrapped as untrusted data, and the prompt tells Claude to ignore instructions
  inside it.
- Expect roughly one extraction call per document, a few dedupe calls per run, and one summary call.
  `iqbank --dry-run extract` lists the pending documents with a rough token estimate. Every command
  that calls Claude prints its token usage.

## Configuration

Precedence: defaults < `iqbank.toml` (see [iqbank.example.toml](iqbank.example.toml)) < `.env` /
environment < CLI flags. Credentials only come from the environment. Query templates accept
`{company}`.

## Development

```bash
pip install -e '.[dev]'
pytest
```

The tests need no network or API keys. Claude is replaced by a fake, and HTTP by `httpx.MockTransport`.
`tests/test_extract_parsing.py` covers the extraction parser: fenced or prose-wrapped JSON,
alternate shapes, per-item validation, label/date normalization, source-URL handling, loop parsing,
chunking and the schema. The other test files cover incremental storage, the collect pipeline,
robots.txt/redirect/blocklist handling, retries, each source with fakes, dedupe validation and source
counting, and report rendering.

```
src/iqbank/
  cli.py        click entry point (collect / extract / dedupe / report / run / status)
  config.py     settings: defaults, iqbank.toml, .env
  net.py        httpx client: retries + backoff, per-host rate limit, robots.txt, blocklist
  store.py      SQLite
  extract.py    prompt, JSON schema, parse_extraction + normalizers, extract pipeline
  dedupe.py     exact + Claude/lexical clustering, independent-source counting
  report.py     CSV / Markdown / loop summary
  llm.py        Anthropic SDK wrapper (structured outputs, streaming, fallbacks, error mapping)
  models.py     shared dataclasses
  sources/      base.py, reddit.py, websearch.py, github.py, inbox.py, and the collect pipeline
```
