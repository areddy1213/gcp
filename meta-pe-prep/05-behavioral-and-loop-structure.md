# 05 · Behavioral round and loop structure (Meta Production Engineer)

> Compiled 2026-11-23.
> **Evidence tags.** `CR-25` / `CR-26` = first-hand candidate report from that year. `CR-old` = pre-2025. `AG` = prep or aggregator site. `PR` = practice item or my own synthesis.
> **(snippet)** = the site blocks automated reads, so I saw only search excerpts; open the link to confirm.

---

## 1. The loop at a glance

The loop varies by level and track; the variations are listed below the table. **Confirm the details with your recruiter** using the questions in section 3.

| # | Stage | Format as reported | Sources |
|---|---|---|---|
| 1 | Recruiter screen | About 20–30 minutes: "Tell me about yourself," "Why Meta?" Sometimes quick Linux questions | [Prepfully](https://prepfully.com/interview-guides/meta-production-engineer) `AG`; [LeetCode 2043600](https://leetcode.com/discuss/post/2043600/meta-recruiter-phone-call-production-engineer-questions/) (snippet, `CR-old`) |
| 2 | Online Linux quiz (OA) | About 20 multiple-choice questions in about 18–20 minutes: Linux commands, OS concepts, networking. Mostly intern and new-grad tracks | [Prepfully](https://prepfully.com/interview-guides/meta-production-engineer); [Glassdoor PE](https://www.glassdoor.com/Interview/Facebook-Production-Engineer-Interview-Questions-EI_IE40772.0,8_KO9,28.htm) (snippet) |
| 3 | Technical screen | **Coding** (file parsing and/or LeetCode) **plus a Linux troubleshooting exercise**. Sometimes split across two days, or held weeks apart | [RW E4, 2025](https://reliabilitywhisperer.substack.com/p/2025meta-e4-production-engineer-interview) `CR-25`; [RW Prep to Offer](https://reliabilitywhisperer.substack.com/p/2025-meta-from-prep-to-offer-my-meta) `CR-25`; [Bala, 2024](https://bala-krishnan.com/posts/18-meta/) `CR-old`; [1point3acres, Jan–Mar 2026](https://www.1point3acres.com/interview/thread/1162101) `CR-26` (login required) |
| 4 | Team matching (may start here) | One 2025 E4 candidate matched with teams *after the screen*, before the onsite | [RW E4](https://reliabilitywhisperer.substack.com/p/2025meta-e4-production-engineer-interview) `CR-25`; [Blind](https://www.teamblind.com/post/production-engineer-meta-bvbtfmo7) (snippet) |
| 5 | Onsite ("full loop"), usually virtual and in one day | **Experienced:** four rounds of about 45 minutes each: Coding · Systems (Linux internals and troubleshooting) · PE system design · Behavioral. **New grad:** three rounds: SWE Coding · Systems (OS) · Behavioral | [RW E4](https://reliabilitywhisperer.substack.com/p/2025meta-e4-production-engineer-interview); [Bala](https://bala-krishnan.com/posts/18-meta/); [coditioning, Jan 2026](https://www.coditioning.com/blog/9/meta-production-engineer-interview-new-grad-guide) `AG`; Glassdoor 2025 (snippet) |
| 6 | Debrief → hiring committee → team match → offer | Behavioral notes go to a separate hiring committee. Your level can change at any point | [techinterview.org, Aug 2026](https://www.techinterview.org/post/3233477365/meta-behavioral-interview-cheat-sheet/) `AG`; [RW Prep to Offer](https://reliabilitywhisperer.substack.com/p/2025-meta-from-prep-to-offer-my-meta) (E5 → E4 after the screen) |

### Variations to know
- **Order of onsite rounds.** It isn't fixed. One 2025 loop ran Coding → System Design → Linux → Behavioral; a 2024 loop ran Coding → Systems Internals → Behavioral → Systems Design. Another report says the four ran "back to back."
- **Interns (London/Dublin).** OA → coding → a systems interview that "leaned more towards system design" ([LeetCode 6380204](https://leetcode.com/discuss/post/6380204/meta-production-engineer-intern-london-d-irhs/), snippet).
- **Quiz variants.** 18 questions in 20 minutes; a Dublin report had 15 MCQs in 16 minutes. One full-time candidate had 20 MCQs on OS, networking and basic algorithms ([bugfree.ai](https://blog.bugfree.ai/meta-production-engineer-interview-experience-coding-os-system-design)). Results can come back the same day.
- **Older guides list a separate Networking round** and a "Leadership & Drive" round ([Prepfully](https://prepfully.com/interview-guides/meta-production-engineer)). The 2025 first-hand reports instead put networking inside the Linux round.
- **NPE loops** have deep networking rounds (see file 03).
- **Timelines** run from about 2 weeks to 4+ months. The two 2025 write-ups ran Dec → Mar and Aug → Jan. Glassdoor puts the average at about 28 days (from 20 submissions) and rates difficulty about 3.0–3.4 out of 5 across snapshots (snippet).
- **Prep time.** Recruiter materials list "Linux, OS, networking, system design, LeetCode, and troubleshooting"; candidates on Blind and Levels.fyi suggest 3–6 months of prep ([Levels.fyi thread](https://www.levels.fyi/community/thread/SuNaPQ/meta-production-engineer-interview-preparation-needs-3-months)).

---

## 2. The AI rounds: your recruiter has mentioned one

**Your loop has an AI round,** according to your recruiter (Nov 2026). Prepare with [file 06](06-ai-enabled-coding-round.md) and the timed mock in [`ai-round-practice/`](ai-round-practice/README.md). What's publicly reported, mostly for SWE loops:

- **October 2025.** An AI-enabled coding round (about 60 minutes, CoderPad with an AI chat panel, a multi-file project with tests) replaced one of the two onsite coding rounds. One prep site lists it as "expected but unconfirmed for Production engineers in their SWE coding rounds" ([coditioning](https://www.coditioning.com/blog/13/meta-ai-enabled-coding-interview-guide)).
- **16 April 2026.** SWE onsites reportedly moved to an "AI-native" loop: two AI-enabled coding rounds, AI-enabled system design, and an "AI-Oriented Behavioral" round. Traditional behavioral "still appears in almost every loop" ([1point3acres 2026 Q4 trends](https://www.1point3acres.com/interview/guides/meta-interview-trend-2026q4) `AG`).
- **September 2026.** Some phone screens open with a discussion of an AI system the candidate built, followed by AI-assisted coding (same source).
- **For your loop, the open question** is *which* round is AI-enabled and whether the others changed. Ask the questions in section 3.

---

## 3. Questions to ask your recruiter now (`PR`)

1. Which rounds are in my onsite? How many coding rounds; is there a Systems/Linux round, a design round, a separate networking round?
2. **Which round is the AI round:** one coding round, both, the phone screen, or system design? Is a traditional no-AI coding round still in the loop?
3. **Can you send the practice CoderPad with the AI assistant enabled?** Which languages can I use, and which test framework (`unittest`/`pytest`, Maven)?
4. Is the coding PE-style (file and log processing) or SWE-style (Meta-tagged LeetCode)?
5. Is there an online Linux quiz for my track?
6. What level am I being considered for, and can the screen change it?
7. Does team matching happen before or after the onsite?
8. Can the screen be split across two days? One 2025 candidate recommends it ([RW Prep to Offer](https://reliabilitywhisperer.substack.com/p/2025-meta-from-prep-to-offer-my-meta)).
9. Is the behavioral round AI-oriented, with questions on when I use AI tools at work and when I don't? Answer outlines are in [file 06, section 9.3](06-ai-enabled-coding-round.md).

---

## 4. The behavioral round

### Format
- **Timing.** 45 minutes: about 5 minutes of introductions, about 35 minutes of "tell me about a time" questions, and about 5 minutes for your questions.
- **Setup.** There's no whiteboard, and the interviewer is often from outside your target team. Candidates call it the **"Jedi"** round; that's a nickname, not Meta's term.
- **Weight.** It is weighted as heavily as the technical rounds.
- Sources: [interviewing.io (ex-Meta EM)](https://interviewing.io/blog/how-software-engineering-behavioral-interviews-are-evaluated-meta) `AG` (undated); [techinterview.org, Aug 2026](https://www.techinterview.org/post/3233477365/meta-behavioral-interview-cheat-sheet/) `AG`.

### What's scored
The two sources label the signals differently; the core is the same.

| interviewing.io (8 focus areas) | techinterview.org (6 signals) |
|---|---|
| Motivation | Motivation |
| Ability to be Proactive | Autonomy and ownership in ambiguity |
| Able to work in an unstructured environment | (same as above) |
| Perseverance | Delivering results and perseverance |
| Conflict Resolution · Empathy | Conflict resolution |
| Growth | Growth mindset and feedback |
| Communication | Communication |

### How the level is set
The interviewer rates the **scope** of each story.
- **E4:** your own work, or within your team.
- **E5:** you coordinated three or more people and owned the result end to end.
- **E6:** multiple teams, or an org-level effort.

A weak behavioral round "can drop an E5 candidate to an E4 offer" ([intervue.io, Nov 2026](https://www.intervue.io/blog/meta-interview-experience)).

**Meta values** candidates tie their stories to: Move Fast; Build Awesome Things; Be Direct and Respect Your Colleagues; Focus on Long-Term Impact; Live in the Future; Meta, Metamates, Me ([techinterview.org](https://www.techinterview.org/post/3233477365/meta-behavioral-interview-cheat-sheet/); [Bala](https://bala-krishnan.com/posts/18-meta/) cites the first, third and fourth).

---

## 5. Behavioral prompts

### 5a. Reported in PE loops

| Prompt | Source |
|---|---|
| "How do you deal with conflicts?" · "How do you prioritize tasks across multiple projects?" · "Describe a time when you handled a disagreement with a colleague." | [Bala, Dec 2024](https://bala-krishnan.com/posts/18-meta/) `CR-old` |
| Themes: past experiences, collaboration, conflict resolution, technical leadership | [RW E4, 2025](https://reliabilitywhisperer.substack.com/p/2025meta-e4-production-engineer-interview) `CR-25` |
| "Why do you want to work at Meta as a Production Engineer?" · "Why Meta?" | [coditioning, 2026](https://www.coditioning.com/blog/9/meta-production-engineer-interview-new-grad-guide) `AG`; Glassdoor 2025 (snippet) |
| "Describe a conflict you dealt with." · The project you're most proud of · Your goals for the role | [Prepfully PE question bank](https://prepfully.com/interview-questions/meta/production-engineer) (snippet) |
| "What are the daily tasks of a production engineer?" · "How does your work impact customers?" · "How do you foster innovation in your work?" | [Prepfully PE guide](https://prepfully.com/interview-guides/meta-production-engineer) `AG` |
| "How would you handle a major outage for a critical service?" · "How would you troubleshoot a high-latency issue in a distributed system that you are unfamiliar with?" | [RW PE design list, Aug 2025](https://reliabilitywhisperer.substack.com/p/production-engineer-system-design) (the author tags these as asked at all companies) |

### 5b. PE-specific themes: incidents, postmortems, cross-team debugging (`PR`)

Few reports quote incident prompts word for word, so these are built from the PE role and the scored signals above. Expect at least one of them.

**B1. Incident response**
- **Prompt.** "Tell me about the worst production incident you were part of. What was *your* role?"
- **Signals.** Ownership in ambiguity; communication; perseverance.
- **What a strong answer has.**
  - A clear timeline.
  - Your own actions, as distinct from the team's.
  - Mitigation *before* root cause.
  - How often you sent updates, and to whom.
  - Numbers: how long it lasted and how many users were affected.
  - What changed afterwards.
- **Follow-ups.**
  1. What would you do differently in the first 10 minutes?
  2. How did you choose between rolling back and fixing forward?
  3. Who did you need to pull in, and how did you get their attention at 2 a.m.?

**B2. A postmortem you drove**
- **Prompt.** "Tell me about a postmortem you wrote or led. What changed because of it?"
- **Signals.** Growth; long-term impact; being direct.
- **What a strong answer has.**
  - A blameless framing.
  - The root cause separated from the contributing factors.
  - Action items with owners that were actually *finished*.
  - Evidence the problem didn't recur.
- **Follow-ups.**
  1. One action item never got done. Why, and what did you do about it?
  2. Someone wanted to blame an individual. How did you handle it?
  3. How do you decide which action items are worth their cost?

**B3. Debugging across team boundaries**
- **Prompt.** "Tell me about a time the root cause was in another team's system."
- **Signals.** Conflict resolution; empathy; being proactive.
- **What a strong answer has.**
  - The evidence that convinced the other team.
  - How you got the fix prioritized on their side.
  - A fix both teams owned.
- **Follow-ups.**
  1. They insisted it wasn't their bug. What evidence did you bring?
  2. How did you keep it from stalling for weeks?
  3. What did you change so the next person doesn't need you to repeat this?

**B4. You broke production**
- **Prompt.** "Tell me about a time a change of yours caused an outage."
- **Signals.** Growth; being direct.
- **Follow-ups.**
  1. How did you find out?
  2. What did you tell your manager, and when?
  3. What guardrail did you add so it can't happen the same way again?

**B5. Reliability work nobody asked for**
- **Prompt.** "Tell me about toil you automated or a reliability risk you fixed that nobody asked you to fix."
- **Signals.** Being proactive; motivation; impact.
- **Follow-ups.**
  1. How did you measure the impact?
  2. How did you get buy-in?
  3. What did you stop doing to make time for it?

**B6. On-call vs project work**
- **Prompt.** "How do you prioritize between on-call interrupts and roadmap work?" (A PE twist on Bala's reported prioritization prompt.)
- **Signals.** Delivering results; communication.
- **Follow-ups.**
  1. Give an example of pushing back on a request.
  2. Tell me about negotiating an SLO or a deadline.
  3. What did you do when the interrupts never stopped?

**B7. Reliability vs launch date**
- **Prompt.** "Tell me about a time you disagreed with a senior engineer or manager about a technical risk."
- **Signals.** Conflict resolution; being direct; empathy.
- **Follow-ups.**
  1. What data did you bring?
  2. What did you do once the decision went against you?
  3. Looking back, were you right?

---

## 6. Story bank template (`PR`)

Prepare 6–8 stories. Make sure each signal is covered by at least two of them, and that at least two show the scope of the level you're targeting.

| Story | Situation (1 line) | What *I* did | Result (with numbers) | Signals | Scope (E4/E5/E6) |
|---|---|---|---|---|---|
| e.g. the disk-full outage | | | e.g. "MTTR 40 → 8 min" | Ownership, Communication | |
| e.g. the cross-team DNS bug | | | | Conflict, Empathy | |
| e.g. a deploy that broke production | | | | Growth, Directness | |

**Delivery.**
- Use STAR, and spend about 60% of the time on Actions.
- Say "I," not "we."
- Quantify: minutes of downtime, error-rate change, hours of toil saved.
- End each story with what you'd do differently.
- Bring two real questions for the interviewer about the team's on-call and reliability culture.

---

## 7. Worked example: an annotated incident story (`PR`)

This is a **template with made-up details**. Swap in your own incident, keep the shape, and keep the numbers.

**The question:** "Tell me about the worst production incident you were part of. What was your role?"

| Part | What you say (about 2.5 minutes) | Signal it earns |
|---|---|---|
| **Situation** (15 s) | "Our checkout API's error rate went from 0.1% to 30% at 7 p.m. on a Friday. It's about $40k an hour of failed orders. I was the secondary on-call." | The scope and the stakes are clear |
| **Task** (10 s) | "The primary was handling customer comms, so I owned *finding and stopping* the errors." | Ownership |
| **Actions** (90 s) | "First I checked what had changed: no deploy, but a config push 12 minutes earlier had lowered the DB connection-pool size. I **rolled the config back before I'd proven root cause**, because rolling back was cheap and safe. Errors fell to 2% within 4 minutes, but not to zero. Tracing the remaining 2%, I found one host still holding the old pool and stuck in retry loops. I drained it. I posted updates in the incident channel every 15 minutes, written for non-engineers." | Mitigate before root cause; working from evidence; communication |
| **Result** (20 s) | "Impact lasted 19 minutes, and we were fully clean by minute 26. I wrote the postmortem, which produced 3 action items; I owned 2 of them." | Measurable outcome |
| **Learning** (25 s) | "The config push skipped the canary stage that code deploys go through. I got the config system changed to require a canary, and added a client-side retry budget. In the next quarter's game day, the same bad push was stopped automatically at 1%." | Growth; long-term impact; a systemic fix |

**How the scope changes by level:**
- **E4:** you did the debugging and the fix yourself.
- **E5:** you coordinated three or more people and drove the cross-team action items.
- **E6:** you changed a process or system for several teams, such as making config canaries mandatory org-wide.

**Likely follow-ups, and the short answer to have ready:**
- *"Why roll back before you knew the cause?"* → It was cheap, reversible and fast, and diagnosis could continue afterwards.
- *"What would you do differently?"* → Page the config owner earlier; I spent 3 minutes confirming something they could have told me in 30 seconds.
- *"How did you make sure the action items actually got done?"* → Owners and due dates in the tracker, and a review at the weekly ops meeting until they closed.

---

## 8. Checking these threads yourself

- **Reddit** (I couldn't reach it). Search these in your browser:
  - `site:reddit.com meta "production engineer" onsite behavioral`
  - `site:reddit.com/r/cscareerquestions meta PE "team matching"`
- **Blind:** [production engineer meta](https://www.teamblind.com/post/production-engineer-meta-bvbtfmo7); [new-grad PE 2025](https://www.teamblind.com/post/interview-meta-production-engineer-university-grad-2025-6bneioqh).
- **Glassdoor:** [PE interview questions](https://www.glassdoor.com/Interview/Facebook-Production-Engineer-Interview-Questions-EI_IE40772.0,8_KO9,28.htm) · [PE New Grad](https://www.glassdoor.com/Interview/Meta-Production-Engineer-New-Grad-Interview-Questions-EI_IE40772.0,4_KO5,33.htm) · [PE Intern](https://www.glassdoor.ca/Interview/Meta-Production-Engineer-Intern-Interview-Questions-EI_IE40772.0,4_KO5,31.htm). Filter by date: 2025–2026.
