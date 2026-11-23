# AI-enabled coding round: practice project (maze solver)

This is a small multi-file Python project, modeled on the most-reported problem in Meta's AI-enabled coding round. One aggregator counts the maze solver in 15 of 32 reports that name a problem (see `../06-ai-enabled-coding-round.md`). It follows the reported structure:
- **Phases 1–2:** debug the existing code.
- **Phases 3–4:** add features that extend the search.
- **Phase 5:** make it fast on large inputs.
- **Phase 6:** a discussion-only follow-up.

It is a rehearsal, not the real question. The real pad's wording, symbols and language may differ.

## Set up the rehearsal

- **Time.** Set a **60-minute** timer and work through the phases in order. Not finishing is normal: one candidate who reached only part 3 of 4 still got an offer.
- **Language.** Python 3.9 or newer. Standard library only; there is nothing to install.
- **AI, phases 1–2.** Use **no AI**. Several interviewers have reportedly asked for this.
- **AI, phases 3–5.** Use a **chat-only** assistant in a browser tab: paste code in, and type or paste its answers back yourself. In the reported CoderPad setup, the AI can't edit your files.
  - Don't use an agent that edits the repo; that isn't the interview.
  - To feel the reported "weaker in the interview" effect, pick a smaller or faster model.
- **Talk out loud the whole time**, or record yourself. Narrating is part of the score.
- **Don't open `SOLUTIONS.md`** until the timer ends.

## Commands

Run all of these from this directory.

```bash
python -m unittest -v
```

```bash
python -m unittest tests.test_phase2_solver -v
```

```bash
python -m unittest tests.test_phase2_solver.SolverTest.test_open_room -v
```

```bash
python main.py
```

```bash
python -m cProfile -s cumtime main.py | head -30
```

They run, in order: every test; one file; one test; the solver on every maze in `mazes/` (printed with its path); and a profile of where the time goes.

## The project

| File | What it does |
|---|---|
| `maze/grid.py` | Parses a maze. Looks up cells, finds symbols, lists a cell's neighbors |
| `maze/solver.py` | `solve(grid)` returns the shortest S → E path as `[(row, col), ...]`, or `None` |
| `maze/render.py` | `render(grid, path)` draws the path as `*` |
| `main.py` | Solves and prints every maze in `mazes/` |
| `tests/` | One file per phase. Phases 3–5 start **skipped**: delete the `@unittest.skip` line when you reach that phase |

The maze symbols are `#` wall, `.` open, `S` start, `E` exit. Later phases add gates and keys.

## Phase 0: orient yourself (about 5 minutes)

Read every file before you run anything. One candidate regretted jumping straight to "run the tests." Then say out loud:
- What algorithm does `solve` use? What should its time and space complexity be, and what are they in this code?
- What does each test file check?

## Phase 1: debug the renderer (no AI)

`tests/test_phase1_render.py` fails. Find out why and fix it so the rendered output matches the contract in the docstring.

## Phase 2: debug the solver (no AI)

`tests/test_phase2_solver.py` has two failing tests: an open room, and a maze whose exit can't be reached. Fix the solver so both pass and the small maze still passes.

Before you change anything, explain the complexity of the current code. **Discuss:** is `MAX_STEPS` still needed after your fix?

## Phase 3: one-way gates (AI allowed)

Delete the skip line in `tests/test_phase3_gates.py`.

A gate cell can only be **entered** while moving in its arrow's direction:
- `>` moving right; `<` moving left; `v` moving down; `^` moving up.

You may leave a gate cell in any direction.

**Discuss:** is BFS still correct once moves are one-way?

## Phase 4: keys and doors (AI allowed)

Delete the skip line in `tests/test_phase4_keys.py`.

- Keys are `a`–`d`; their doors are `A`–`D`.
- Stepping onto a key picks it up for the rest of the walk.
- You can enter a door only while holding its key.
- The shortest path may revisit cells.

**Discuss:** what is the state space now? How big does it get with 26 keys?

## Phase 5: make it scale (AI allowed)

Delete the skip line in `tests/test_phase5_scale.py`. A 150×150 maze must solve in under 1 second.

**Measure before you change anything.** Name the bottleneck with numbers, fix it, and re-run the *whole* suite.

## Phase 6: discussion only (no code)

A new cell type `M` is a **Medusa**. You may never stand on a cell that the Medusa can see: any cell in the same row or column with no wall in between.

- How would you add this?
- What does it cost?
- What changes if the Medusa moves one cell every turn?

## After the timer: score yourself

Score yourself against the four reported competencies (detail in `../06-ai-enabled-coding-round.md`, section 4):

| Competency | Ask yourself |
|---|---|
| Problem solving | Did I state the algorithm and its complexity *before* coding each phase? |
| Code quality and understanding | Could I explain every line I pasted from the AI? Did I keep the existing structure? |
| Verification and debugging | Did I run the full suite after every change? Did I measure before optimizing? |
| Communication | Was I silent for more than 60 seconds at any point? Did I say what I was asking the AI, and why? |

Then read `SOLUTIONS.md` and compare.
