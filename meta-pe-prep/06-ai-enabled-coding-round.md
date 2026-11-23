# 06 · The AI-enabled coding round, plus the other AI-flavored rounds

> Compiled 2026-11-23, after your recruiter mentioned an AI round in your loop.
> **Evidence tags.** `CR-25` / `CR-26` = first-hand candidate report from that year. `AG` = an aggregator or prep site compiling candidate reports. `PR` = my own analysis or practice material.
> Meta has not published the format. Everything here is candidate-reported, so check the details against the **practice CoderPad your recruiter can send** (section 10).
> **Hands-on:** [`ai-round-practice/`](ai-round-practice/README.md) is a timed, multi-file mock of the most-reported problem. Run it at least twice.

---

## 1. Ten-line summary

1. **Format.** One extended problem in a **multi-file project** inside CoderPad, with an **AI chat panel**, runnable **tests**, and about **60 minutes**.
2. **Phases.** *Fix a bug* (often no AI) → *implement the core* (AI expected) → *optimize or extend on harder data*. Some problems have 4–5 parts.
3. **Finishing isn't required.** Candidates got offers after reaching part 3 of 4. *Correctness* and *understanding* outweigh coverage.
4. **Rubric.** The same four competencies as other coding rounds: **Problem Solving · Code Development & Understanding · Verification & Debugging · Technical Communication.**
5. **What gets people rejected.** Pasting AI code they can't explain, and **optimizing code that still has a bug.** Leaning only on the AI is noticed, and so is refusing to use it.
6. **The live AI is weaker than you expect.** Several candidates found it slower or less accurate than in practice. Plan to do the thinking yourself.
7. **The problem pool is small.** Maze solver (most frequent), maximize unique characters, the sum-to-15 card game, friend recommendations, plus a few rarer ones (section 7).
8. **Read every file before you press Run.** Name the algorithm and its complexity before you write any code.
9. **Prompt in narrow slices,** review every diff, and run the *full* suite after each change. Narrate while the AI is generating.
10. **For PE specifically,** one prep site says the round is "expected but unconfirmed for Production engineers in their SWE coding rounds." Your recruiter has now mentioned it, so treat it as real and ask which round it replaces (section 12).

---

## 2. Format and environment

| Topic | What's reported | Sources |
|---|---|---|
| Start and scope | Piloted from **Oct 2025**, replacing one of the two onsite coding rounds for SWE. From **16 Apr 2026**, some SWE loops have *both* coding rounds AI-enabled, with the first part often AI-free. | [interviewing.io](https://interviewing.io/blog/how-to-use-ai-in-meta-s-ai-assisted-coding-interview-with-real-prompts-and-examples) `AG`; [1point3acres Q4 2026](https://www.1point3acres.com/interview/guides/meta-interview-trend-2026q4) `AG` |
| Roles | SWE and EM, up to E7/M2 ([Hello Interview](https://www.hellointerview.com/blog/meta-ai-enabled-coding)); SWE, MLE, M1, and "expected but unconfirmed for Production engineers" ([coditioning, updated 3 Nov 2026](https://www.coditioning.com/blog/13/meta-ai-enabled-coding-interview-guide)). | `AG` |
| Length | About **60 minutes**, of which the first 5–6 are orientation. One late-2026 report describes about 40 minutes per round, each in a fresh pad. | [Hello Interview](https://www.hellointerview.com/blog/meta-ai-enabled-coding); [FastPrep, Nov 2026](https://www.fastprep.io/experience/2026-meta-ai-native-coding-interview-experienced-swe-and-mle-onsite-3-experience-1av6vvamu0) `CR-26` |
| Layout | Three panels: **file explorer · editor · AI chat with the instructions**. The project has existing classes, data models and tests. | [Hello Interview](https://www.hellointerview.com/blog/meta-ai-enabled-coding); [dglearning](https://dglearning.substack.com/p/inside-metas-new-ai-enabled-coding) |
| Running code | You can run **tests and main** from a dropdown, and the pad re-runs on save. The output panel doesn't always clear between runs. Some tests may start commented out. | [Hello Interview](https://www.hellointerview.com/blog/meta-ai-enabled-coding); [coditioning](https://www.coditioning.com/blog/13/meta-ai-enabled-coding-interview-guide) |
| Can the AI edit files? | Most guides say **no**: it answers in chat and you paste the code. CoderPad itself offers an *Ask* mode and an *Edit* mode, and the reports don't say which one Meta enables. | [Hello Interview](https://www.hellointerview.com/blog/meta-ai-enabled-coding); [PracHub](https://prachub.com/resources/meta-ai-coding-interview) |
| Models | The lists change over time. Late 2025: GPT-4o mini, GPT-5, Claude Haiku 3.5/4.5, Sonnet 4/4.5, Opus 4, Gemini 2.5 Pro, Llama 4 Maverick. A Sep 2026 report: "Claude 4.8 and GPT 5.5." Advice: pick the most capable model that is still fast (GPT-5 was called slow), and switch if one stalls. | [Hello Interview](https://www.hellointerview.com/blog/meta-ai-enabled-coding); [FastPrep](https://www.fastprep.io/experience/2026-meta-ai-native-coding-interview-experienced-swe-and-mle-onsite-3-experience-1av6vvamu0); [PracHub](https://prachub.com/resources/meta-ai-coding-interview) |
| Languages | Java, C++, C#, Python, Kotlin, TypeScript. Java projects use Maven; Python uses `unittest`. **Confirm yours.** | [Hello Interview](https://www.hellointerview.com/blog/meta-ai-enabled-coding); [coditioning](https://www.coditioning.com/blog/13/meta-ai-enabled-coding-interview-guide) |
| Sandbox limits | About **1.5 CPU cores and 2 GB RAM**. Don't run big stress suites early. Tools can be flaky: one edit reported a timeout but had actually applied. | [FastPrep](https://www.fastprep.io/experience/2026-meta-ai-native-coding-interview-experienced-swe-and-mle-onsite-3-experience-1av6vvamu0); [PracHub](https://prachub.com/resources/meta-ai-coding-interview) |
| How the AI behaves live | It's "less useful in the live interview": wrong answers, and when asked to describe the code it didn't flag any bugs. One theory is a modified system prompt. One candidate's AI did spot a bug unprompted. Newer models may **start test runs on their own**, which burns time. | [Hello Interview](https://www.hellointerview.com/blog/meta-ai-enabled-coding); [aicodinginterview](https://aicodinginterview.com/interviews/meta/) `AG`; [FastPrep](https://www.fastprep.io/experience/2026-meta-ai-native-coding-interview-experienced-swe-and-mle-onsite-3-experience-1av6vvamu0) |
| Interviewer behavior | Some say "no AI for this part." Some stopped candidates from querying the AI and told them to "look closer themselves." One required the candidate to **explain the plan before each prompt** and get approval. Many ask for the complexity of the existing brute-force code. | [aicodinginterview](https://aicodinginterview.com/interviews/meta/); [FastPrep](https://www.fastprep.io/experience/2026-meta-ai-native-coding-interview-experienced-swe-and-mle-onsite-3-experience-1av6vvamu0); [PracHub](https://prachub.com/resources/meta-ai-coding-interview) |

---

## 3. How a question is structured

| Phase | What happens | AI? | How long |
|---|---|---|---|
| 0. Orientation | Read the instructions, the file tree and the tests. Explain the existing code, name its algorithm, give its complexity. | — | 5–6 min |
| 1. Bug fix | Usually *not* an algorithmic bug: an int/double cast, an off-by-one, a wrong condition, a path printer drawing over start and exit, a 10,000-iteration safety cap that throws when the real fix is a visited set. | Often **forbidden** or discouraged | 10–15 min |
| 2. Core implementation | Around 120+ lines, "harder than a medium LeetCode problem." | **Expected** | 15–20 min |
| 3+. Optimize or extend | Tiered data files that stress different dimensions. You may need to change algorithm: greedy → trie, DFS → bitmask, add BFS state. | Expected | The rest |

- **How many checkpoints.** Coditioning reports that clearing **3 checkpoints** "appears to be the minimum threshold"; aim for 4 or more. Hello Interview and PracHub both report offers for candidates who didn't finish. Optimize for *correct and explained*, not *covered*.
- **Non-coding questions get mixed in:** runtime analysis, trade-offs, contract changes, reasoning about the data ([coditioning](https://www.coditioning.com/blog/13/meta-ai-enabled-coding-interview-guide)).

---

## 4. Rubric: the four competencies

| Competency | Strong signals | Reported failure modes |
|---|---|---|
| **Problem Solving** | You restate the problem and clarify the rules. You name the algorithm and its complexity *before* prompting. You know when to switch algorithms. | Asking the AI to "solve this problem for me." Not preparing an optimal approach (from one rejected candidate's account). |
| **Code Development & Understanding** (also called *Code Quality*) | You work within the existing structure and contracts. You make small, reviewable changes. You can explain every line, including the AI's. | Pasting about 150 lines of AI-written DP that passed the tests, then stumbling when walking through it. A candidate who "appeared to rely heavily on AI, which impacted the quality of their solution." |
| **Verification & Debugging** | You read the tests first, run the **full** suite after each change, add your own edge-case or stress tests, and measure before optimizing. | **Optimizing AI code that still had a bug**: the interviewer tested correctness with about 10 minutes left, and the candidate was rejected. |
| **Technical Communication** | You narrate continuously, say what you're asking the AI and why, and take hints well. | Long silences. Several candidates said keeping the dialogue going was "harder than the actual coding." |

> An internal source relayed by Hello Interview: *"Should use AI, but need to show you understand the code. Explain the output. Test before using. Don't prompt your way out of it."*
> On the other side: one rejected candidate's recruiter feedback was "should less manual work, more on AI" ([PracHub](https://prachub.com/resources/meta-ai-coding-interview)). **The target is balance:** think it through yourself, then use the AI to implement what you've already decided.

---

## 5. A minute-by-minute plan for 60 minutes (`PR`)

| Clock | Do | Say something like |
|---|---|---|
| 0–5 | Read the instructions, the file tree, every source file and every test. Don't press Run yet. | "The entry point is `main`. `solve` does BFS but has no visited set, so it's exponential in path length. Is AI allowed for part 1?" |
| 5–15 | **Part 1.** Run the tests and read the first failure. Form a hypothesis, make the smallest fix, re-run **everything**. | "The test expects S and E preserved. `render` draws `*` over every path cell, so I'll draw only on open cells." |
| 15–35 | **Part 2.** State the approach and its complexity. Ask the AI for **one slice at a time**. Review the diff, paste it, run the tests. | "I want the BFS state to become `(pos, keymask)`. I'll ask the AI only for the state and transition changes, and leave reconstruction as is." |
| 35–50 | **Part 3+.** Measure first: a timer, `cProfile`, or a small stress test. Name the bottleneck, change the algorithm or data structure, re-run the full suite. | "`find()` is an O(V) scan on every dequeue, so O(V²) overall. I'll cache the exit position." |
| 50–60 | Wrap up: the final complexity, what's left, how you'd finish. | "If I had 10 more minutes, I'd add bidirectional BFS. Here's why it's awkward with one-way gates." |

**If you're stuck for more than 3 minutes,** say so. Explain what you've ruled out and ask a precise question, of the AI or the interviewer.

---

## 6. How to use the AI (`PR`, built from the reported dos and don'ts)

### When to use it and when not to
- **Do it yourself:** part 1 debugging, choosing the algorithm, complexity analysis, the first read of the code.
- **Use the AI for:**
  - Boilerplate and mechanical edits.
  - Implementing an approach you've *already* stated.
  - Writing extra test cases.
  - Explaining an unfamiliar API.
  - Generating stress data.
- **Avoid:** "fix this," "solve this," "optimize this," pasting the whole repo, accepting rewrites of more than about 40 lines.

### Prompt template
```
Context: <file/function> [paste only the relevant code]
Goal: <one change, stated precisely>
Constraints: keep signature/contract X; don't touch Y; <language/version>
Output: only the changed function (or a unified diff), no explanation unless asked
```
Coditioning's example: *"Implement only `guess` and `display` methods. No changes to `__init__` or game state tracking."*

### Check the AI's output before you paste it
1. Does it change *only* what you asked? Are the signatures and contracts intact?
2. Does it handle edge cases: empty input, unreachable, duplicates, ties, huge input?
3. Does its complexity match what you stated?
4. Watch for off-by-one errors, int vs float, mutation of shared state, and hidden O(n) calls inside loops.
5. **Can you explain every line?** If not, ask for a smaller version, or write it yourself.

### Talk while the AI works
- Narrate what you expect the AI to produce while it's generating ("pipelining").
- Tell the interviewer what you're about to check in its output.
- After pasting, re-read the edited file. FastPrep's advice: "re-read files after each edit."

### When the AI is wrong
- Say so plainly: "this would revisit cells, so I'm rejecting it."
- Fix it yourself, or re-prompt with the specific defect.
- Treat a wrong AI answer as a chance to show judgment, not as a setback.

---

## 7. The problem pool

The "parts" below are as candidates reported them; the approaches are mine (`PR`).

> **Frequency, two counts.**
> - [PracHub](https://prachub.com/resources/meta-ai-coding-interview) (32 reports that name a problem, as of 2 Nov 2026): maze 15 · unique characters 10 · card game 7 · friend recommendations 2 · word containment 2.
> - [1point3acres](https://www.1point3acres.com/interview/guides/meta-interview-trend-2026q4), May–Oct 2026: maze 6, down from 20 in the prior six months; card game 5; unique characters 4. From August onward, mainly card game and friend recommendations.
> - Hello Interview relays an internal estimate of "roughly 9" problems in total.

### 7.1 Maze solver (path printing, gates, keys) → practice with [`ai-round-practice/`](ai-round-practice/README.md)
- **Reported parts.** Sources: [Hello Interview problem page](https://www.hellointerview.com/community/questions/maze-solver-path/cmjlp495e05fs08adwrayjwbr), [PracHub](https://prachub.com/resources/meta-ai-coding-interview), [aicodinginterview](https://aicodinginterview.com/interviews/meta/).
  1. Fix path printing (start and end were being overwritten).
  2. Fix revisiting cells: add a visited set. One variant has a 10,000-step cap that throws.
  3. One-way gates or chutes (`<` `>`).
  4. Keys and doors (`a → A`), which means extending the visited state.
  5. A "Medusa" (avoid her line of sight) or bombs. Sometimes discussion only.
- **Approach.**
  - BFS with parent pointers. Mark cells visited on *enqueue*.
  - Gates make the graph directed, and BFS still works.
  - Keys: the state becomes `(r, c, mask)`, giving O(R·C·2^K).
  - Medusa: precompute the gaze cells by ray-casting from each `M` until you hit a wall.
- **Follow-ups.**
  1. Why a bitmask rather than a set of keys?
  2. What if there are 26 keys? (Search over key locations with precomputed distances, using Dijkstra.)
  3. What if the Medusa moves? (Add time mod period to the state.)

### 7.2 Maximize unique characters from a word list
- **Reported parts.**
  1. Fix a counting bug, or 2 of 4 failing util tests.
  2. Backtracking on a sample of about 12 words.
  3. Datasets of thousands of words.
  - One report: a project of `main.py`, `test.py`, `solve.py`, `utils.py` and a data folder. The interviewer pushed past an exponential solution, and "the problem turned out to be NP-complete."
  - Sources: [Hello Interview](https://www.hellointerview.com/community/questions/unique-characters-subset/cmjdgvdgd00bn08adhvz1s58g), [PracHub](https://prachub.com/resources/meta-ai-coding-interview), [aicodinginterview](https://aicodinginterview.com/interviews/meta/).
- **Approach.** It's close to LeetCode 1239 and is a form of maximum-weight set packing, which is NP-hard. Say that early.
  - Drop words that repeat a letter internally; turn each word into a 26-bit mask; deduplicate identical masks.
  - Sort by length, longest first. Backtrack with **branch and bound**: prune when `current + remaining_possible ≤ best` or once all 26 letters are used.
  - For thousands of words, keep the set of reachable masks (iterate over words; at most 2^26 states) or memoize on `(index, mask)`. Use greedy plus local search when exactness can't be had in time.
- **Follow-ups.**
  1. Prove the problem is hard, or at least explain why greedy fails.
  2. What's your upper bound for pruning?
  3. How does memory grow with the reachable-mask approach?

### 7.3 Card game: three cards summing to 15
- **Reported parts.**
  1. Fix a failing test; the bug was in validating invalid moves.
  2. Implement a strategy that keeps picking valid triples from the cards on the table until none remain.
  3. Measure the perfect-game rate over 1,000+ games, then improve it.
  - The setup in one report: **36 cards** with values 1–9 (four of each), **16 on the table**, 3 more dealt after each pick; you win if all 36 are used. One candidate reported a 99.97% win rate on the 10,000-game case, in 40 seconds.
  - Sources: [Hello Interview](https://www.hellointerview.com/community/questions/cards-sum-15/cmj313k1c05rj08adjuwctql8), [FastPrep](https://www.fastprep.io/experience/2026-meta-ai-native-coding-interview-experienced-swe-and-mle-onsite-3-experience-1av6vvamu0), [PracHub](https://prachub.com/resources/meta-ai-coding-interview) (greedy wins about 20–40% of games; backtracking or DP about 60–90%).
- **Approach.**
  - **The arithmetic.** There are only **13 value-triples** that sum to 15: {1,5,9} {1,6,8} {1,7,7} {2,4,9} {2,5,8} {2,6,7} {3,3,9} {3,4,8} {3,5,7} {3,6,6} {4,4,7} {4,5,6} {5,5,5}. The deck totals 180 = 12 × 15, so a perfect game partitions all 36 cards into 12 such triples.
  - **Work on counts.** Represent the table as 9 counts per value rather than individual cards; you can enumerate the legal moves from the 13 patterns.
  - **A better strategy.** You can infer how many of each value remain unseen (table + unseen = everything not yet used). Prefer moves after which **table + unseen can still be partitioned** into sum-15 triples; check this with a memoized search over count vectors (at most 5^9 ≈ 2M states). Break ties toward keeping the table flexible: 5s fit 5 of the 13 patterns. Then add lookahead or Monte Carlo rollouts if time allows.
  - **Measure honestly.** Use fixed seeds, start with 20 → 100 → full samples, and keep a changelog of each change and its win rate (FastPrep's advice).
- **Follow-ups.**
  1. Why does greedy fail? Show a hand where it gets stuck.
  2. What's the complexity of your feasibility check?
  3. How do you know an improvement is real and not noise? (Same seeds, enough games, a confidence interval.)

### 7.4 Friend recommendations
- **Reported parts.**
  - Suggest **up to 5** friends per user, excluding the user and their existing friends.
  - Three test suites; the largest has about **100k users and 1.5M friend pairs**.
  - Twists: a "random friend finder," weighted shortest paths, and *evaluating* recommendation quality (split into training and validation sets, then measure overlap).
  - Sources: [Hello Interview](https://www.hellointerview.com/community/questions/friend-recommendation-system/cmmjgcgav052c0eadi8f91wl8), [FastPrep](https://www.fastprep.io/experience/2026-meta-ai-native-coding-interview-experienced-swe-and-mle-onsite-3-experience-1av6vvamu0).
- **Approach.**
  - Build adjacency **sets**. For each user, count friends-of-friends by number of mutual friends, then take the top 5 with `heapq.nlargest`. Break ties deterministically, by ID.
  - The cost is Σ deg(f)² over friends f, so high-degree users dominate. Cap or sample their friend lists, use integer IDs and arrays, and avoid building per-user Python dicts in hot loops.
  - To evaluate: hold out about 10% of edges, then measure precision@5 or recall@5 against a random baseline.
- **Follow-ups.**
  1. How does the cost grow on a power-law graph?
  2. How do you test randomized output? (Fixed seed, or check properties rather than exact values.)
  3. Recommendations must refresh every hour for 3B users. What changes? (Batch vs incremental, sharding.)

### 7.5 Rarer reported problems
- **Word containment / substring solver.** DFS and backtracking with a **trie**. The phase 3 data favored the trie with many short words and greedy with fewer, longer words ([Hello Interview](https://www.hellointerview.com/blog/meta-ai-enabled-coding)). Related: LeetCode 472 (Concatenated Words) and 212 (Word Search II).
- **Kitchen orders.** Assign recipe steps to 3 chefs to finish an order as early as possible, where both assignment and ordering matter ([FastPrep](https://www.fastprep.io/experience/2026-meta-ai-native-coding-interview-experienced-swe-and-mle-onsite-3-experience-1av6vvamu0)).
  - It's scheduling with precedence constraints, which is NP-hard in general.
  - Use list scheduling with a longest-remaining-path (critical path) priority, plus branch-and-bound for small inputs.
  - Compare against the lower bound `max(critical path, total work / 3)`.

### LeetCode warm-ups for the pool (no AI)
- **Keys and BFS state:** 864 (Shortest Path to Get All Keys), 1293.
- **Unique characters:** 1239.
- **Triples, partitioning, backtracking:** 15, 698.
- **Tries and words:** 212, 472.
- **Graphs and top-k:** 347, plus a people-you-may-know variant.
- **BFS basics:** 1091, 490/505 (The Maze).

---

## 8. Language and tooling prep

**Python**

```bash
python -m unittest -v
```

```bash
python -m unittest tests.test_solver.SolverTest.test_open_room -v
```

```bash
python -m cProfile -s cumtime main.py | head -30
```

- In order: run every test; run one test; profile where the time goes.
- Debug with `breakpoint()` (pdb) or print statements. Hello Interview mentions ipdb for Python.
- Know `collections.deque`, `heapq`, `functools.lru_cache`, `itertools.combinations`, `int.bit_count()` (Python 3.10+), and `time.perf_counter()`.

**Java (Maven projects were reported)**

```bash
mvn -q test
```

```bash
mvn -q -Dtest=SolverTest#testOpenRoom test
```

**Reading unfamiliar code quickly**
1. Find the entry point and the tests.
2. Trace one input end to end.
3. List the data structures and who mutates them.
4. Write down the complexity of each hot function.

Hello Interview suggests practicing on unfamiliar repos, with tools such as DeepWiki.

---

## 9. The other AI-flavored rounds

These come from 2026 SWE reports; whether they apply to PE is **unconfirmed**.

### 9.1 AI-native phone screen
- **What's reported.** Since September 2026, some phone screens open with a **discussion of an AI system you built**, followed by AI-assisted coding ([1point3acres](https://www.1point3acres.com/interview/guides/meta-interview-trend-2026q4)). The classic screen (two Meta-tagged problems in 45 minutes, no AI) still exists.
- **Prep (`PR`).** Have one AI-assisted project ready to whiteboard. Cover:
  - The problem and the architecture.
  - How you evaluated quality.
  - Its failure modes (hallucination, prompt injection, cost spikes).
  - Guardrails, latency and cost numbers, and what you would change.
- **PE-friendly examples:** an AI-assisted incident-triage or log-summarization tool, a runbook assistant, a guarded infra-automation agent.
  - Your [GCP sandbox kit](../README.md) is directly usable here: the guardrail rules in `AGENTS.md`, the plan scanner `scripts/plan-check.sh`, and the recovery drills.

### 9.2 AI-enabled system design
- **What's reported.** "AI-enabled SWE system design" with a chat window "to unblock yourself." One candidate found it close to useless ([FastPrep](https://www.fastprep.io/experience/2026-meta-ai-native-coding-interview-experienced-swe-and-mle-onsite-3-experience-1av6vvamu0)). Others describe using the AI to generate user scenarios, missing requirements and edge cases ([Blind](https://www.teamblind.com/post/cracking-ai-coding-ai-system-design-ai-behavioral-interviews-ua0zvnzn), snippet).
- **Prep (`PR`).** Run your file-04 answer outline as usual, and use the AI only for:
  - Back-of-envelope arithmetic.
  - A list of failure scenarios to check *against your own list*.
  - Recalling an API.
  
  Say out loud which of its suggestions you reject, and why.
- **If you get an AI-serving prompt** ("design an LLM inference platform"), the PE angles are:
  - GPU capacity and bin-packing; request batching; KV-cache memory.
  - Latency SLOs for time-to-first-token and tokens per second.
  - Per-tenant rate limits; fallback to a smaller model under overload.
  - Canary rollout for a new model version; token- and cost-based observability.

### 9.3 AI-oriented behavioral
- **What's reported.** Interviewers ask **when you would and wouldn't use AI**, and want a concrete example where the AI was **hard to steer**. You stay accountable for the result ([Blind](https://www.teamblind.com/post/cracking-ai-coding-ai-system-design-ai-behavioral-interviews-ua0zvnzn), snippet; [1point3acres](https://www.1point3acres.com/interview/guides/meta-interview-trend-2026q4) lists an "AI-Oriented Behavioral" round).
- **Answer outlines (`PR`):**
  - *When not to use AI:*
    - Anything destructive or irreversible in production, unless a human reviews it and there's a dry run (`terraform plan`, `--dry-run`, a canary).
    - Secrets.
    - Debugging during an incident where the AI's confidence outruns its evidence.
  - *"Hard to steer":* the AI kept proposing a broad IAM role, or a `0.0.0.0/0` firewall rule.
    - You caught it by reading the plan.
    - You constrained it with a rules file.
    - You added an automated check so it can't recur. That's the guardrails → plan-check → recovery-drill loop from your GCP kit.
  - *Accountability:* "I own whatever ships. AI output gets the same code review and tests as a junior engineer's PR."
- **Follow-ups.**
  1. How do you verify AI-written code you don't fully understand?
  2. Have you ever shipped a bug the AI introduced? What changed afterwards?
  3. How do you decide whether a task is worth delegating to AI?

---

## 10. Practice plan: 8 sessions (`PR`)

| # | Session | Goal |
|---|---|---|
| 1 | Ask your recruiter for the **practice CoderPad**. It's reportedly available only once your interview is scheduled, and it uses a sample problem called "the puzzle," said to be harder than the real ones. | Learn the panels, the run dropdown and the model picker |
| 2 | [`ai-round-practice/`](ai-round-practice/README.md), timed 60 minutes, with a capable model | Get a baseline. Note where the time went |
| 3 | LeetCode warm-ups from section 7, **no AI** | Have the algorithms ready before the AI is involved |
| 4 | Build a mini-project for **unique characters** or the **card game**: ask an AI in a separate chat for a 4-file Python project with 2 hidden *non-algorithmic* bugs and unittest tests. Solve it in a fresh chat. | Practice on code you haven't seen |
| 5 | Re-run the practice kit with a **small, weak model** | Rehearse a live AI that's worse than expected |
| 6 | A mock with a friend playing interviewer: approval before each prompt, "no AI for part 1," and correctness tests sprung on you mid-way | Practice the dialogue and the interruptions |
| 7 | Friend-recommendation mini-project at 100k users / 1.5M pairs (generate a random graph) | Measure before optimizing, inside a small memory budget |
| 8 | A full dress rehearsal in your interview language, recorded | Check you're never silent for more than 60 seconds; count your full-suite runs |

---

## 11. Follow-ups interviewers ask in this round

1. What is the time and space complexity of the *existing* code? And of yours?
2. Walk me through the code the AI just wrote, line by line.
3. Why did you accept that suggestion? What did you check?
4. How do you know this is correct beyond the provided tests? Write one more test.
5. This test file is 10× bigger. What breaks first: time or memory?
6. You changed the function's contract. Who else calls it?
7. If you had 10 more minutes, what would you do next?

## 12. Questions to ask your recruiter now
1. Which round is AI-enabled: one coding round, both, the phone screen, or the system design round?
2. Which languages can I use? Is the project Maven or Gradle for Java, `unittest` or `pytest` for Python?
3. Can you send the practice CoderPad with the AI assistant turned on?
4. Is the AI chat-only, or can it edit files?
5. Is there still a traditional no-AI coding round in my loop?
6. Is the behavioral round AI-oriented?

---

### Sources (all third-party; dates as shown on each page)
- **Prep guides:**
  - [Hello Interview: Meta's AI-enabled coding interview](https://www.hellointerview.com/blog/meta-ai-enabled-coding) (undated, maintained), and its problem pages: [maze](https://www.hellointerview.com/community/questions/maze-solver-path/cmjlp495e05fs08adwrayjwbr), [unique characters](https://www.hellointerview.com/community/questions/unique-characters-subset/cmjdgvdgd00bn08adhvz1s58g), [cards sum 15](https://www.hellointerview.com/community/questions/cards-sum-15/cmj313k1c05rj08adjuwctql8), [friend recommendations](https://www.hellointerview.com/community/questions/friend-recommendation-system/cmmjgcgav052c0eadi8f91wl8).
  - [coditioning: AI-enabled coding guide](https://www.coditioning.com/blog/13/meta-ai-enabled-coding-interview-guide) (updated 3 Nov 2026).
  - [interviewing.io](https://interviewing.io/blog/how-to-use-ai-in-meta-s-ai-assisted-coding-interview-with-real-prompts-and-examples) · [Prepfully](https://prepfully.com/interview-guides/meta-ai-assisted-coding-interview) · [dglearning](https://dglearning.substack.com/p/inside-metas-new-ai-enabled-coding) (Apr 2026) · [intervue.io](https://www.intervue.io/blog/meta-interview-experience) (Nov 2026).
- **Candidate-report aggregators:**
  - [PracHub](https://prachub.com/resources/meta-ai-coding-interview): 35 reports, counts as of 2 Nov 2026.
  - [aicodinginterview](https://aicodinginterview.com/interviews/meta/): 20 reports, updated 1 Nov 2026.
  - [FastPrep: 3 onsite experiences](https://www.fastprep.io/experience/2026-meta-ai-native-coding-interview-experienced-swe-and-mle-onsite-3-experience-1av6vvamu0): Sep–Nov 2026.
  - [1point3acres 2026 Q4 trends](https://www.1point3acres.com/interview/guides/meta-interview-trend-2026q4): 4 Nov 2026, partly paywalled.
- **Couldn't be read** (blocked or login-only): interviewdb, IGotAnOffer, the Blind and LeetCode threads (seen via search excerpts only), and Reddit.
