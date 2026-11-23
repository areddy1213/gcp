# Meta Production Engineer: study notes for every round

Compiled Nov 2026 from 2025–2026 candidate reports (LeetCode Discuss, Glassdoor, Blind, 1point3acres, Prepfully, prep-site aggregators, candidate blogs). Each file names its sources inline.

## Your loop and where to study for each round

| Round (as reported for PE) | What to study | Hands-on |
|---|---|---|
| Recruiter screen · online Linux quiz | [05 §1](05-behavioral-and-loop-structure.md) · quick-fire list in [02 §C](02-linux-systems-and-troubleshooting.md) | — |
| Technical screen: coding + troubleshooting | [01](01-coding-and-scripting.md) (PE file-processing tasks, LeetCode set) · [02 §B](02-linux-systems-and-troubleshooting.md) | Worked solutions in [01 §F](01-coding-and-scripting.md); mock dialogue in [02 §E](02-linux-systems-and-troubleshooting.md) |
| **AI-enabled coding** (your recruiter mentioned it) | [06](06-ai-enabled-coding-round.md): format, rubric, a 60-minute plan, prompting, the problem pool, the other AI rounds | [`ai-round-practice/`](ai-round-practice/README.md): a timed, multi-file maze-solver mock with tests |
| Onsite coding (traditional) | [01 §B–C](01-coding-and-scripting.md) | [01 §E–F](01-coding-and-scripting.md) |
| Onsite systems: Linux internals and troubleshooting | [02](02-linux-systems-and-troubleshooting.md) · basic networking in [03](03-networking-and-protocols.md) | [02 §E](02-linux-systems-and-troubleshooting.md) |
| Networking (separate round in NPE and in some PE loops) | [03](03-networking-and-protocols.md) | Model answer at the end of [03](03-networking-and-protocols.md) |
| PE system design | [04](04-system-design-and-architecture.md) | Worked deployment-system design in [04](04-system-design-and-architecture.md) |
| Behavioral (and possibly AI-oriented behavioral) | [05](05-behavioral-and-loop-structure.md) · [06 §9.3](06-ai-enabled-coding-round.md) | Story template [05 §6](05-behavioral-and-loop-structure.md), annotated story [05 §7](05-behavioral-and-loop-structure.md) |

**Evidence tags used in every file:**
- `CR-25` / `CR-26`: a first-hand candidate report from that year. `CR-old`: earlier than 2025.
- `AG`: an aggregator or prep site.
- `PR`: my own practice material or synthesis.
- **(snippet)**: the source was seen only through search excerpts, because the site blocks automated reads.
- Reddit couldn't be reached at all; each file ends with search queries to check it yourself.

## Run the AI-round mock

From this directory:

```bash
cd ai-round-practice && python -m unittest -v
```

On the untouched project you should see **1 failure, 2 errors, 10 skipped**: the Phase 1 and Phase 2 bugs, plus the phases you haven't reached yet. Read [`ai-round-practice/README.md`](ai-round-practice/README.md) before starting the 60-minute timer.

## A 4-week plan, about 2 hours a day (`PR`)

Every day, add **one Meta-tagged LeetCode problem without AI**, and **one 15-minute troubleshooting drill** said out loud (pick from [02 §B](02-linux-systems-and-troubleshooting.md)).

| Week | Focus | Done when |
|---|---|---|
| 1 | Coding and scripting ([01](01-coding-and-scripting.md)); Linux internals ([02 §A](02-linux-systems-and-troubleshooting.md)) | You can write Dino CSV, `tail -f` and the host sweep from memory in under 20 minutes each, and explain A1–A11 without notes |
| 2 | Troubleshooting ([02 §B–E](02-linux-systems-and-troubleshooting.md)); networking ([03](03-networking-and-protocols.md)) | You can deliver the facebook.com answer in 3 minutes, and handle 3 goalpost changes in a mock |
| 3 | **AI round** ([06](06-ai-enabled-coding-round.md)): practice-kit run 1, the warm-up problems, run 2 with a weaker model. Design ([04](04-system-design-and-architecture.md)): two prompt families | The mock reaches Phase 5 within 60 minutes, with the full suite re-run after every change; the design outline holds to time |
| 4 | Behavioral stories ([05](05-behavioral-and-loop-structure.md)); full mock loop; the recruiter's practice CoderPad | 6–8 stories mapped to the signals; one dress rehearsal of every round |

## The day before
- Confirm your language, and whether the AI round is in the pad you practiced in.
- Re-read the 60-minute plan ([06 §5](06-ai-enabled-coding-round.md)) and the AI-output checklist ([06 §6](06-ai-enabled-coding-round.md)).
- Re-read your story bank. Prepare 2 questions for each interviewer.
- Sleep. In every round, narrate, measure before optimizing, and re-run the whole suite after each change.
