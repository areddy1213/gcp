# 01 · Coding and scripting (Meta Production Engineer)

> Compiled 2026-11-23.
> **Evidence tags.** `CR-25` / `CR-26` = first-hand candidate report from that year. `CR-old` = a pre-2025 report, kept only because the question keeps recurring. `AG` = a prep or aggregator site summarizing reports. `PR` = a practice item I derived from a reported topic; it was not reported word for word.
> **(snippet)** = LeetCode Discuss, Glassdoor and Blind block automated reads, so I saw that thread only through search-engine excerpts. Open it before you rely on the detail. Reddit could not be searched from here at all; queries to check it yourself are at the bottom.

---

## What the PE coding bar looks like in 2025–2026

- **Two flavors of coding round.**
  - *PE coding:* practical file and data processing (parse CSV or logs, aggregate, sort, print).
  - *SWE coding:* two Meta-tagged LeetCode easy or medium problems in about 45 minutes.
  - A 2026 new-grad guide places PE Coding in the screen and SWE Coding in the onsite.
  - Sources: [coditioning, updated 30 Jan 2026](https://www.coditioning.com/blog/9/meta-production-engineer-interview-new-grad-guide) `AG`.
- **File-handling questions are the usual surprise.** One candidate said they were the hardest part and warned against relying only on Meta-tagged LeetCode.
  - Sources: [LeetCode: Meta PE Phone Screen](https://leetcode.com/discuss/post/7214157/) (snippet) `CR-25`.
- **"Clarity > complexity."** Interviewers valued clear explanations over unnecessarily optimized solutions.
  - Sources: [Reliability Whisperer: From Prep to Offer, Apr 2025](https://reliabilitywhisperer.substack.com/p/2025-meta-from-prep-to-offer-my-meta) `CR-25`.
- **The follow-ups are the real test.** One onsite was "another file parsing question with numerous follow-ups" on optimizing and extending the solution.
  - Sources: [Reliability Whisperer: E4 PE, interviewed Mar 2025](https://reliabilitywhisperer.substack.com/p/2025meta-e4-production-engineer-interview) `CR-25`.
- **You may not be able to run the code.** In the traditional CoderPad round, expect to check correctness by hand. Handle malformed input such as missing fields.
  - Sources: [coditioning](https://www.coditioning.com/blog/9/meta-production-engineer-interview-new-grad-guide) `AG`.

---

## A. Reported practical scripting tasks

Every row is a reported prompt. The follow-ups are the ones an interviewer would realistically push.

### A1. Dino CSV: join two files, compute, sort
- **Prompt.** Two CSV files hold dinosaur data. Compute `speed = ((STRIDE_LENGTH / LEG_LENGTH) - 1) * sqrt(LEG_LENGTH * g)` and print the bipedal dinosaurs from fastest to slowest.
  - The commonly circulated version has `NAME,LEG_LENGTH,DIET` in one file, `NAME,STRIDE_LENGTH,STANCE` in the other, and `g = 9.8`.
- **Sources.** [RW E4 screen, Mar 2025](https://reliabilitywhisperer.substack.com/p/2025meta-e4-production-engineer-interview) `CR-25` (called "Dino CSV data"); [Prepfully PE guide](https://prepfully.com/interview-guides/meta-production-engineer) `AG`.
- **What it probes.** Joining on a key, rows present in only one file, parsing floats, filtering, and a stable sort.
- **Follow-ups.**
  1. The files are 50 GB each. What changes? (Load the smaller file into a dict and stream the larger one; use `heapq.nlargest` if only the top N is needed; fall back to an external sort.)
  2. Some rows are malformed or the header order differs. Do you skip, log, or fail, and how do you report it? (Use `csv.DictReader` and keep a counter of rejected rows.)
  3. Add a new output column, or make the formula pluggable, without rewriting the parser.

### A2. Reimplement `tail` in a scripting language
- **Sources.** [Glassdoor question page](https://www.glassdoor.ca/Interview/reimplement-tail-in-a-scripting-language-QTN_1243813.htm) `CR-old`. Search results show it listed again in a later Glassdoor review (snippet). It recurs for a decade, so it is cheap insurance.
- **What it probes.** Not reading the whole file; seeking from the end; off-by-one errors around the trailing newline.
- **Follow-ups.**
  1. Implement `tail -f`. How do you detect log rotation and truncation? (Compare `os.stat().st_ino` with the open file's inode; if the size shrank below your offset, the file was truncated.)
  2. What if the file is 100 GB and has no newlines?
  3. Follow 50 files at once without 50 busy loops. (Use `inotify`, `select` on pipes, or one poll loop.)

### A3. Watch a program's stdout and print a line when a field changes
- **Sources.** [Glassdoor PE questions](https://www.glassdoor.com/Interview/Facebook-Production-Engineer-Interview-Questions-EI_IE40772.0,8_KO9,28.htm) (snippet; the date is unclear).
- **What it probes.** Streaming input, `subprocess` pipes, keeping state across lines.
- **Follow-ups.**
  1. Output arrives in bursts. Why? (The child buffers stdout when it isn't a TTY; fix with `stdbuf -oL`, `python -u`, or a pty.)
  2. Track changes per key, for example per host, rather than globally.
  3. The child dies. How do you detect that and surface its exit code?

### A4. Count email-address occurrences in a file
- **Sources.** [Prepfully PE guide](https://prepfully.com/interview-guides/meta-production-engineer) `AG`.
- **What it probes.** A regex you can defend, normalization (lower-casing the domain), `Counter`, top-k.
- **Follow-ups.**
  1. Where does your regex fail (`+` tags, quoted local parts, trailing punctuation)?
  2. The input is 1 TB across 1,000 hosts: map/reduce the counts.
  3. Return the top 10 domains instead of the top 10 addresses.

### A5. Words common to multiple files
- **Sources.** LeetCode Discuss PE threads, seen as snippets: [7214157](https://leetcode.com/discuss/post/7214157/), [6805017 (new grad)](https://leetcode.com/discuss/post/6805017/) `CR-25`.
- **What it probes.** Set intersection, tokenization, memory use.
- **Follow-ups.**
  1. Return the words that appear in at least k of N files.
  2. Rank the common words by total frequency.
  3. The files live on different hosts. What do you ship over the network?

### A6. Read JSON from an API and reorganize it; paginated deduplication
- **Prompt.** "Read data from an API call in JSON format, organise it as requested."
  - One candidate's variant: an API returns `(book, score)` pairs, and the same book can repeat across pages. Keep calling until you have 5 unique books with `score > 100`, aggregating the duplicates.
- **Sources.** [Prepfully PE guide](https://prepfully.com/interview-guides/meta-production-engineer) `AG`; [bugfree.ai candidate write-up](https://blog.bugfree.ai/meta-production-engineer-interview-experience-coding-os-system-design) `AG` (one candidate, undated).
- **What it probes.** When to stop paginating, what "aggregate" means (sum, max, or latest?), and handling errors.
- **Follow-ups (these lead into rate limiting, `PR`).**
  1. The API returns HTTP 429 or 5xx intermittently. Add retries with exponential backoff and jitter.
  2. The API allows only 10 requests per second. Add a client-side token bucket (snippet below).
  3. Fetch pages concurrently without breaking the ordering or the stop condition.

### A7. Connect to 100 hosts, find a process, email a report
- **Sources.** [Prepfully PE guide](https://prepfully.com/interview-guides/meta-production-engineer) `AG`.
- **What it probes.** Concurrency, timeouts, partial failure, and security hygiene: SSH agent or certificates, never passwords in the script.
- **Follow-ups (these lead into multi-threaded execution, `PR`).**
  1. Ten hosts hang. Make sure one slow host can't stall the report. (Per-host timeout; `ThreadPoolExecutor`; collect results with `as_completed`.)
  2. Threads, processes, or asyncio for this, and why? (The work is I/O-bound, so threads or asyncio. The GIL doesn't matter because the time is spent waiting on `ssh`.)
  3. Scale to 100,000 hosts. What breaks first? (File descriptors and ephemeral ports on the client, SSH connection rate limits.) What would you use instead? (A fleet-wide agent or a pull model.)

### A8. Filter logs with Python and build a structure from them
- **Sources.** [Glassdoor PE questions](https://www.glassdoor.com/Interview/Facebook-Production-Engineer-Interview-Questions-EI_IE40772.0,8_KO9,28.htm) (snippet).
- **Follow-ups.**
  1. Report the error rate per endpoint per minute.
  2. Lines are interleaved from several threads. How do you correlate them by request ID?
  3. Turn the script into a reusable CLI: arguments, exit codes, stdin support.

### A9. Evaluate `"2*3+4"` using only `+` and `*` (non-negative integers, no parentheses)
- **Sources.** [bugfree.ai](https://blog.bugfree.ai/meta-production-engineer-interview-experience-coding-os-system-design) `AG`. It is a subset of LeetCode 227 (Basic Calculator II).
- **Follow-ups.**
  1. Add `-` and `/` with truncation toward zero.
  2. Add parentheses.
  3. The input contains spaces or invalid tokens. Validate it and give a useful error.

> **About your examples.** I found **no 2025–26 PE report** of a rate-limiter or multi-threading question in the *coding* round. Rate limiting appears as a **design** prompt (see file 04). Concurrency and rate limiting are natural follow-ups to A6 and A7, so practice them as extensions rather than standalone problems.

---

## B. LeetCode-style problems reported in PE loops

| Problem as reported | Likely LeetCode mapping | Source |
|---|---|---|
| Goat Latin | 824 | [RW E4 screen, 2025](https://reliabilitywhisperer.substack.com/p/2025meta-e4-production-engineer-interview) `CR-25` |
| "Find an almost palindrome" | 680 Valid Palindrome II | [Prepfully](https://prepfully.com/interview-guides/meta-production-engineer) `AG` |
| "Split an array so the sum is the same for both partitions" | 416 if it is any subset; 1013 or 724 if it must be contiguous. **Ask which.** | [Prepfully](https://prepfully.com/interview-guides/meta-production-engineer) `AG` |
| Two Sum; longest substring without repeating characters | 1; 3 | [Prepfully](https://prepfully.com/interview-guides/meta-production-engineer) `AG` |
| BFS/DFS basics, plus a harder grid variant | 200, 994, 1091 | Glassdoor 2025 (snippet); [LeetCode PE threads](https://leetcode.com/discuss/post/6805017/) (snippet) |
| k-th smallest in a BST; reverse a linked list; maximum subarray; palindrome check | 230, 206, 53, 125 | [Prepfully](https://prepfully.com/interview-guides/meta-production-engineer) `AG` |
| String, list and dictionary manipulation with file input | — | [Glassdoor PE](https://www.glassdoor.com/Interview/Facebook-Production-Engineer-Interview-Questions-EI_IE40772.0,8_KO9,28.htm) (snippet) |

**Follow-ups interviewers add to these problems**
1. What is the time and space complexity? Can you do it in O(1) extra space?
2. Walk me through your code with this edge case: empty input, one element, all duplicates.
3. The input is now a stream, or doesn't fit in memory. What changes?

---

## C. The Meta-tagged high-frequency set (SWE-style round)

> **Caveat.** No verified public ranking exists. LeetCode's company tag (Premium, filter "last 6 months", sort by frequency) is the authority. The list below is the core that recurs across 2024–25 community lists such as [1point3acres: Meta high-frequency ranked by 6/12/24 months](https://www.1point3acres.com/interview/thread/1041607) and [Blind: Meta top 100 tagged](https://www.teamblind.com/post/meta-top-100-tagged-vy0kdkcg). Treat it as a floor, then work the live tag.

| Pattern | Problems |
|---|---|
| Strings and stacks (most relevant to PE parsing work) | 1249 Minimum Remove to Make Valid Parentheses · 680 Valid Palindrome II · 408 Valid Word Abbreviation · 71 Simplify Path · 227 Basic Calculator II · 921 Minimum Add to Make Parentheses Valid · 791 Custom Sort String |
| Hashing, prefix sums, intervals | 560 Subarray Sum Equals K · 1570 Dot Product of Two Sparse Vectors · 1762 Buildings With an Ocean View · 56 Merge Intervals · 528 Random Pick with Weight · 346 Moving Average from Data Stream |
| Heaps and selection | 215 Kth Largest Element · 973 K Closest Points to Origin · 347 Top K Frequent Elements |
| Trees | 314 Binary Tree Vertical Order Traversal · 1650 / 236 Lowest Common Ancestor · 199 Right Side View · 938 Range Sum of BST · 543 Diameter · 129 Sum Root to Leaf Numbers |
| Graphs and grids | 200 Number of Islands · 1091 Shortest Path in Binary Matrix · 339 Nested List Weight Sum |
| Binary search and math | 162 Find Peak Element · 50 Pow(x, n) |

**PE priority:** strings and stacks, hashing, heaps, BFS. These match the file-processing flavor. Skip hard DP unless the recruiter says the loop is SWE-style.

---

## D. Meta's AI-enabled coding round

All sources here are secondary, and they disagree in places; the disagreements are noted.

**What the sources agree on**
- **Start date.** It started in **October 2025**. It replaces one of the two onsite coding rounds.
- **Length and environment.** 60 minutes, in CoderPad with an AI chat panel.
  - The layout has three panels: a file explorer, the editor, and the AI chat with the instructions.
  - There is a **Run Tests** button.
  - The AI **cannot edit your files**; you write or paste the code yourself.
  - Sources: [dglearning, Apr 2026](https://dglearning.substack.com/p/inside-metas-new-ai-enabled-coding).
- **It is a multi-file, existing project.** Prepfully mentions "multiple files, dependencies, and configuration files like requirements.txt."
  - Sources: [Prepfully AI-assisted guide](https://prepfully.com/interview-guides/meta-ai-assisted-coding-interview), [interviewing.io](https://interviewing.io/blog/how-to-use-ai-in-meta-s-ai-assisted-coding-interview-with-real-prompts-and-examples).
- **Three task shapes.**
  1. Build a feature into the existing structure.
  2. Finish partially implemented code (stubs marked `TODO`).
  3. Debug a broken implementation that has failing tests.
  - Sources: Prepfully, dglearning.
- **Three stages.** One source frames the round as *Understand → Build → Verify and explain*. Non-coding questions are mixed in, such as why you'd change a function signature, the runtime, or swapping a data structure.
  - Sources: [intervue.io, Nov 2026](https://www.intervue.io/blog/meta-interview-experience).

**Models offered**
- One list: GPT-4o mini, GPT-5, Claude Sonnet 4/4.5, Claude Haiku 3.5/4.5, Gemini 2.5 Pro, Llama 4 Maverick. Source: [interviewing.io](https://interviewing.io/blog/how-to-use-ai-in-meta-s-ai-assisted-coding-interview-with-real-prompts-and-examples).
- One candidate saw only lighter models: o4-mini, Claude Haiku, Llama 4 Maverick. Source: [LeetCode: [USA] Meta AI Coding Round](https://leetcode.com/discuss/post/7335102/usa-meta-ai-coding-round-by-mathrules-z3bd/) (snippet) `CR-25`.

**How it is scored (as reported; Meta has not published this)**
- dglearning's version has three dimensions: **problem solving**, **code development and understanding**, and **verification and debugging**.
- intervue's version: decomposition, judgement, verification, communication, ownership.
- Prepfully: the interviewer sees every prompt and every AI response, and you must be able to defend every line.
- "Using the AI is optional." Every source says that in practice, *how well you steer it* is graded.

**2026 changes (SWE pipeline)**
- **Both onsite coding rounds.** From **16 Apr 2026**, SWE onsites reportedly have *both* coding rounds AI-enabled, with the first part usually AI-free.
- **Phone screens.** Some phone screens have used AI-assisted coding since September 2026.
- **Most-reported AI-round problems, May–Oct 2026:** Maze Solver; Card Game ("three cards summing to 15"); Maximum Unique Character Subset; Friend Recommendation.
- Sources: [1point3acres 2026 Q4 trends, 4 Nov 2026](https://www.1point3acres.com/interview/guides/meta-interview-trend-2026q4) `AG` (partly paywalled).

**Status for PE roles: unconfirmed.**
- interviewing.io and intervue say the round is being rolled out to "back-end and ops-focused roles" in 2026.
- 1point3acres says Production Engineering "use[s] a different round mix."
- I found **no first-hand PE report** of an AI-enabled round. **Ask your recruiter** (see file 05).

**PE-flavored drills**
- Spend 10 minutes mapping an unfamiliar multi-file Python repo before you change anything: the entry point, how data flows, how tests run.
- Practice tasks:
  - Fix a log parser that has one failing test.
  - Add retries, backoff and a rate limit to an API client.
  - Add concurrency and timeouts to a host sweeper.
  - Fix a bug in a config loader.
- interviewing.io's *example prompts* (not confirmed interview tasks) are ops-flavored: grep for `ERROR` across `.log` files, a Bash deploy script, a Flask endpoint, a Dockerfile, Kubernetes YAML.
- Ask the AI for one function or one test at a time. Read the diff, run the tests, and narrate what you're doing.

**Follow-ups to expect in this round**
1. The AI's change makes the test pass. How do you know it didn't break something the tests don't cover?
2. Why did you accept that suggestion over the alternative? What is its complexity?
3. We now need to support Y, which changes this function's signature. What else in the codebase has to change?

---

## E. Reference snippets (tested on Python 3.13)

```bash
# Top client IPs, and 5xx count per path (common/combined log format: $7 = path, $9 = status)
awk '{print $1}' access.log | sort | uniq -c | sort -rn | head
awk '$9 ~ /^5/ {c[$7]++} END {for (u in c) print c[u], u}' access.log | sort -rn | head
```

```python
import os, re, time, threading, subprocess
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

def tail(path, n=10, block=4096):
    """Last n lines without reading the whole file (seek backwards in blocks)."""
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        pos, data = f.tell(), b""
        while pos > 0 and data.count(b"\n") <= n:
            step = min(block, pos)
            pos -= step
            f.seek(pos)
            data = f.read(step) + data
    return [l.decode(errors="replace") for l in data.splitlines()[-n:]]

LINE = re.compile(r'^(\S+) \S+ \S+ \[[^\]]+\] "(\S+) (\S+) [^"]*" (\d{3}) (\S+)')

def summarize(path, top=5):
    """Stream an access log: 5xx count per path, top client IPs, malformed lines."""
    errors, ips, bad = Counter(), Counter(), 0
    with open(path, errors="replace") as f:
        for line in f:                      # streams; constant memory per line
            m = LINE.match(line)
            if not m:
                bad += 1
                continue
            ip, _method, url, status, _size = m.groups()
            ips[ip] += 1
            if status.startswith("5"):
                errors[url] += 1
    return errors.most_common(top), ips.most_common(top), bad

def check(host, proc="nginx", timeout=10):
    cmd = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", host, "pgrep", "-x", proc]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return host, "timeout"
    except OSError as e:                    # ssh binary missing, fd exhaustion, etc.
        return host, f"error {e.strerror}"
    # pgrep: 0 = match, 1 = no match; ssh: 255 = connection/auth failure
    return host, {0: "running", 1: "not running"}.get(r.returncode, f"error rc={r.returncode}")

def sweep(hosts, workers=20):
    with ThreadPoolExecutor(max_workers=workers) as pool:   # I/O-bound, so threads are fine
        futures = [pool.submit(check, h) for h in hosts]
        return dict(f.result() for f in as_completed(futures))

class TokenBucket:
    """Thread-safe: `rate` tokens/sec, bursts up to `capacity`."""
    def __init__(self, rate, capacity):
        self.rate, self.capacity = rate, capacity
        self.tokens, self.last = float(capacity), time.monotonic()
        self.lock = threading.Lock()

    def acquire(self):
        while True:
            with self.lock:
                now = time.monotonic()
                self.tokens = min(self.capacity, self.tokens + (now - self.last) * self.rate)
                self.last = now
                if self.tokens >= 1:
                    self.tokens -= 1
                    return
                wait = (1 - self.tokens) / self.rate
            time.sleep(wait)                # sleep outside the lock
```

**What I checked:**
- `tail`: with and without a trailing newline, an empty file, and a block size smaller than a line.
- `summarize`: a malformed line is counted, not crashed on.
- `sweep`: returns an error status when `ssh` is missing. An earlier draft without the `OSError` branch crashed the whole sweep, which is a good thing to mention out loud.
- `TokenBucket(20, 5)`: 25 acquires take about 1.0 s.

---

## F. Checking these threads yourself

- **Reddit** (I couldn't reach it). Search these in your browser:
  - `site:reddit.com/r/leetcode "production engineer" meta 2025`
  - `site:reddit.com/r/cscareerquestions meta "production engineer" phone screen`
  - `site:reddit.com/r/sre meta "production engineer"`
- **The AI-round launch thread** on r/leetcode, cited by Prepfully (I haven't opened it): [Officially live: Meta's new AI-enabled coding round](https://www.reddit.com/r/leetcode/comments/1o47lk2/officially_live_metas_new_aienabled_coding_round/).
- **LeetCode Discuss:** search "Production Engineer" and sort by newest. Threads used here: [7214157](https://leetcode.com/discuss/post/7214157/), [6805017](https://leetcode.com/discuss/post/6805017/), [6380204 (intern, London/Dublin)](https://leetcode.com/discuss/post/6380204/meta-production-engineer-intern-london-d-irhs/), [6296514 (new grad)](https://leetcode.com/discuss/interview-experience/6296514/), [7335102 (AI round)](https://leetcode.com/discuss/post/7335102/usa-meta-ai-coding-round-by-mathrules-z3bd/).
- **2026 PE phone screen** covering coding and troubleshooting (login required): [1point3acres 1162101, Jan–Mar 2026](https://www.1point3acres.com/interview/thread/1162101).
