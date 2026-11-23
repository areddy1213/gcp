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

## D. Meta's AI-enabled coding round → see [file 06](06-ai-enabled-coding-round.md)

Your recruiter mentioned an AI round, so it now has its own file, [`06-ai-enabled-coding-round.md`](06-ai-enabled-coding-round.md), and a timed, runnable mock in [`ai-round-practice/`](ai-round-practice/README.md). In short:

- **Format.** One multi-file project in CoderPad with an AI chat panel and runnable tests, about 60 minutes. The phases are *fix a bug* (often no AI) → *implement the core* → *optimize or extend*.
- **Scoring.** Problem solving · code development & understanding · verification & debugging · communication. Not finishing is OK; **pasting code you can't explain, or optimizing code that is still buggy, is not.**
- **Reported problem pool:** maze solver (most frequent), maximize unique characters, the sum-to-15 card game, friend recommendations, plus a few rarer ones.

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

## F. Worked solutions (all tested on Python 3.13)

### F1. Dino CSV (task A1)

```python
import csv
import math
import sys

G = 9.8  # m/s^2


def load_leg_lengths(path):
    """NAME -> LEG_LENGTH from the first file; bad rows are counted, not fatal."""
    legs, bad = {}, 0
    with open(path, newline="") as f:
        for row in csv.DictReader(f):               # header order doesn't matter
            try:
                legs[row["NAME"].strip()] = float(row["LEG_LENGTH"])
            except (KeyError, ValueError, TypeError, AttributeError):
                bad += 1
    return legs, bad


def fastest_bipeds(legs_path, strides_path):
    legs, bad = load_leg_lengths(legs_path)         # small side: keep in memory
    speeds = []
    with open(strides_path, newline="") as f:
        for row in csv.DictReader(f):               # big side: stream it
            name = (row.get("NAME") or "").strip()
            if (row.get("STANCE") or "").strip().lower() != "bipedal" or name not in legs:
                continue
            try:
                stride = float(row["STRIDE_LENGTH"])
            except (KeyError, ValueError, TypeError):
                bad += 1
                continue
            leg = legs[name]
            if leg <= 0:                            # avoid divide-by-zero / sqrt of negative
                bad += 1
                continue
            speeds.append((((stride / leg) - 1) * math.sqrt(leg * G), name))
    speeds.sort(key=lambda t: (-t[0], t[1]))        # fastest first; ties by name
    return [name for _, name in speeds], bad


if __name__ == "__main__":
    names, bad = fastest_bipeds(sys.argv[1], sys.argv[2])
    print("\n".join(names))
    if bad:
        print(f"skipped {bad} malformed rows", file=sys.stderr)
```

**The test data.** Illustrative data in the commonly circulated format, with one malformed row added: T-Rex (leg 2.5, stride 5.76), Velociraptor (1.0, 2.72), Struthiomimus (0.92, 1.34) and Hadrosaurus (1.2, 1.4) are bipedal. Deinonychus has a stride but no leg length, and `Broken` has stride `abc`.

**Output:** `Tyrannosaurus Rex`, `Velociraptor`, `Struthiomimus`, `Hadrosaurus`, plus `skipped 1 malformed rows` on stderr.

**What to say while coding**
- "I'm joining on NAME. I'll load the leg lengths into a dict and stream the strides file."
- "Malformed rows are counted and reported rather than crashing the run."
- "Ties sort by name, so the output is deterministic."
- "That's O(n + m) to read, plus O(k log k) to sort the k bipeds."

**Answers to the A1 follow-ups**
- **Both files are huge.** Hash-partition both files by `hash(NAME) % N` into N bucket files, then join bucket by bucket. Or sort both by NAME externally and merge-join.
- **Only the top N is needed.** `heapq.nlargest(N, ...)` in O(k log N).
- **The formula must be pluggable.** Pass it in as a function of a row dict, so the parser never changes.

### F2. Goat Latin (LeetCode 824, from a 2025 PE screen)

```python
def to_goat_latin(sentence):
    out = []
    for i, word in enumerate(sentence.split(), start=1):
        if word[0].lower() not in "aeiou":
            word = word[1:] + word[0]
        out.append(word + "ma" + "a" * i)
    return " ".join(out)

assert to_goat_latin("I speak Goat Latin") == "Imaa peaksmaaa oatGmaaaa atinLmaaaaa"
```

**Follow-ups.**
- What's the complexity? (O(n + w²), where n is the input length and w the word count: the `"a" * i` suffixes add 1 + 2 + … + w characters.)
- Uppercase vowels: is that handled? (Yes, through `.lower()`.)
- Punctuation attached to words: what should happen to it?

### F3. `tail -f` that survives rotation (the A2 follow-up)

```python
import os
import time


def follow(path, poll=0.5):
    """Return an iterator of complete lines appended to `path` from now on.

    Opens and seeks *now* (a generator body would only run on the first next()),
    and survives log rotation (new inode) and in-place truncation.
    """
    f = open(path)
    f.seek(0, os.SEEK_END)
    return _lines(path, f, poll)


def _lines(path, f, poll):
    inode, buf = os.fstat(f.fileno()).st_ino, ""
    while True:
        chunk = f.readline()
        if chunk:
            buf += chunk
            if buf.endswith("\n"):          # only emit whole lines
                yield buf
                buf = ""
            continue
        try:
            st = os.stat(path)
        except FileNotFoundError:           # mid-rotation: new file not created yet
            time.sleep(poll)
            continue
        if st.st_ino != inode:              # rotated: old file is drained, switch to the new one
            f.close()
            f = open(path)
            inode = os.fstat(f.fileno()).st_ino
        elif st.st_size < f.tell():         # truncated in place (logrotate copytruncate)
            f.seek(0)
        else:
            time.sleep(poll)
```

- **What the test covered:** an appended line, a line written in two parts, rotation by rename-and-recreate, and truncate-and-rewrite.
- **A bug worth telling the interviewer about.** My first version put the `open` and `seek` *inside* the generator. A generator body doesn't run until the first `next()`, so lines written between calling `follow()` and the first `next()` were silently skipped and the test hung.
- **Remaining gaps to discuss:**
  - Lines written to the old file after we drained it but before the rename.
  - Polling vs `inotify`.
  - Truncation that lands back at exactly the same size.

---

## G. Checking these threads yourself

- **Reddit** (I couldn't reach it). Search these in your browser:
  - `site:reddit.com/r/leetcode "production engineer" meta 2025`
  - `site:reddit.com/r/cscareerquestions meta "production engineer" phone screen`
  - `site:reddit.com/r/sre meta "production engineer"`
- **The AI-round launch thread** on r/leetcode, cited by Prepfully (I haven't opened it): [Officially live: Meta's new AI-enabled coding round](https://www.reddit.com/r/leetcode/comments/1o47lk2/officially_live_metas_new_aienabled_coding_round/).
- **LeetCode Discuss:** search "Production Engineer" and sort by newest. Threads used here: [7214157](https://leetcode.com/discuss/post/7214157/), [6805017](https://leetcode.com/discuss/post/6805017/), [6380204 (intern, London/Dublin)](https://leetcode.com/discuss/post/6380204/meta-production-engineer-intern-london-d-irhs/), [6296514 (new grad)](https://leetcode.com/discuss/interview-experience/6296514/), [7335102 (AI round)](https://leetcode.com/discuss/post/7335102/usa-meta-ai-coding-round-by-mathrules-z3bd/).
- **2026 PE phone screen** covering coding and troubleshooting (login required): [1point3acres 1162101, Jan–Mar 2026](https://www.1point3acres.com/interview/thread/1162101).
