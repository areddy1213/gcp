# Solutions and discussion answers (spoilers)

Each phase gives a hint first; the code is folded under it. All of this code was run against the test suite on Python 3.13. The final solver passes all 15 tests, and the 150×150 maze takes about 0.016 s.

---

## Phase 0: what's wrong with the starter, at a glance

<details><summary>Answer</summary>

- **The algorithm.** BFS, which *should* run in O(V + E) time and O(V) space.
- **What it actually does: no visited set.** BFS without one explores *walks*, not cells. The number of walks grows exponentially with path length (about 4^d in an open room).
- **What it actually does: copied paths.** Every queue entry copies its whole path, so each enqueue costs O(L).
- **What it actually does: `queue.pop(0)`.** It is O(n) per pop on a Python list.
- **What it actually does: `grid.is_exit(pos)`.** It calls `find("E")`, which scans the whole grid, on **every** dequeue: O(V) per step.
- **`MAX_STEPS`** hides the exponential blow-up by throwing. Later it also caps legitimate large searches.
</details>

## Phase 1: renderer

**Hint:** compare the `render` docstring with its loop.

<details><summary>Fix</summary>

The path includes S and E, and the loop draws `*` over every path cell. Draw only on open cells:

```python
from .grid import OPEN

PATH = "*"


def render(grid, path):
    rows = [row[:] for row in grid.rows]
    for r, c in path or []:
        if rows[r][c] == OPEN:
            rows[r][c] = PATH
    return "\n".join("".join(row) for row in rows)
```

**Say this out loud:** checking `== OPEN` is safer than `not in "SE"`. It also keeps gates, keys and doors visible in later phases.
</details>

## Phase 2: solver

**Hint:** why does a maze with *no* path throw an exception instead of returning `None`?

<details><summary>Minimal fix (the one tested at this phase)</summary>

```python
def solve(grid):
    start = grid.find(START)
    queue = [(start, [start])]
    visited = {start}
    steps = 0
    while queue:
        steps += 1
        if steps > MAX_STEPS:
            raise RuntimeError(f"search exceeded {MAX_STEPS} steps")
        pos, path = queue.pop(0)
        if grid.is_exit(pos):
            return path
        for nxt in grid.neighbors(pos):
            if nxt not in visited:
                visited.add(nxt)
                queue.append((nxt, path + [nxt]))
    return None
```

- **Mark cells visited when you *enqueue* them, not when you dequeue them.** Otherwise the same cell can sit in the queue many times.
- **Is `MAX_STEPS` still needed?** With a visited set, the loop runs at most once per reachable cell (later, once per state), so it always terminates. A fixed cap of 10,000 is now just a bug waiting for a big maze. Phase 5 hits it. Remove it, or derive it from the state count if you want a sanity check.
</details>

## Phase 3: one-way gates

**Hint:** the legality of a move now depends on its *direction*, so neighbor generation needs to know `(dr, dc)`.

<details><summary>Approach</summary>

When you consider moving from `(r, c)` by `(dr, dc)` onto a gate cell, allow it only if `GATES[cell] == (dr, dc)`. Leaving a gate is unrestricted. You can do this inside `solve`, as below, or by changing `Grid.neighbors` to yield the direction.

```python
GATES = {">": (0, 1), "<": (0, -1), "v": (1, 0), "^": (-1, 0)}
...
if cell in GATES and GATES[cell] != (dr, dc):
    continue
```

**Is BFS still correct?** Yes. The graph becomes *directed*, and BFS gives shortest paths on any unweighted graph, directed or not. Note that S → E can now be reachable while E → S is not.
</details>

## Phase 4: keys and doors

**Hint:** "visited" can no longer be just a position. Standing on the same cell holding different keys is a different situation.

<details><summary>Approach</summary>

- **The state** is `(position, keys_held)`. Store the keys as a **bitmask**: it is hashable and cheap, where a `frozenset` would also work but is slower.
- **Moves.** Picking up a key sets a bit. A door is passable only if its bit is set.
- **Visited and reconstruction.** Keep `parent[state]` both as the visited set and to rebuild the path. Positions can repeat in the path because the states differ.
- **Complexity.** O(R · C · 2^K) states, each with 4 moves.
  - With K = 4 that's 16× the grid.
  - With 26 keys it's 2^26 ≈ 67M × cells: infeasible.
  - At that scale, run BFS from S, E and each key to precompute pairwise distances, then search over `(key location, mask)` with Dijkstra, ideally pruning keys that don't matter.
</details>

## Phase 5: scale

**Hint:** run `python -m cProfile -s cumtime main.py` on a big maze, or time `solve` directly, before you change any code.

<details><summary>What the profile shows, and the fix</summary>

- **Bottleneck 1.** The fixed 10,000-step cap throws on a 150×150 maze, which has about 22,000 reachable cells.
- **Bottleneck 2, the big one.** `is_exit` calls `find("E")` on every dequeue: an O(V) scan each step, so O(V²) overall. In my run, removing the cap but keeping `is_exit` took **12.6 s**. Caching the exit position brought it to **0.016 s**.
- **Cleanups worth saying out loud:**
  - Use `collections.deque` for the O(1) `popleft`.
  - Use **parent pointers** instead of copying each path, which cuts memory from O(V·L) to O(V).
- After the change, re-run the **whole** suite, not just Phase 5.

Final `maze/solver.py`:

```python
"""Breadth-first maze solver: gates, keys and doors, linear in the state space."""

from collections import deque

from .grid import EXIT, START, WALL

GATES = {">": (0, 1), "<": (0, -1), "v": (1, 0), "^": (-1, 0)}
KEYS, DOORS = "abcd", "ABCD"
DIRECTIONS = ((-1, 0), (1, 0), (0, -1), (0, 1))


def solve(grid):
    start, exit_ = grid.find(START), grid.find(EXIT)    # look these up once, not per step
    first = (start, 0)                                  # state = (position, bitmask of keys held)
    parent = {first: None}                              # doubles as the visited set
    queue = deque([first])
    while queue:
        state = queue.popleft()
        (r, c), keys = state
        if (r, c) == exit_:
            return _path_to(state, parent)
        for dr, dc in DIRECTIONS:
            nr, nc = r + dr, c + dc
            if not (0 <= nr < grid.height and 0 <= nc < grid.width):
                continue
            cell = grid.rows[nr][nc]
            if cell == WALL:
                continue
            if cell in GATES and GATES[cell] != (dr, dc):
                continue
            if cell in DOORS and not keys & (1 << DOORS.index(cell)):
                continue
            next_keys = keys | (1 << KEYS.index(cell)) if cell in KEYS else keys
            nxt = ((nr, nc), next_keys)
            if nxt not in parent:
                parent[nxt] = state
                queue.append(nxt)
    return None


def _path_to(state, parent):
    path = []
    while state is not None:
        path.append(state[0])
        state = parent[state]
    return path[::-1]
```

**Possible follow-ups:**
- *Bidirectional BFS:* about √ of the frontier on open grids, but awkward with one-way gates and key state.
- *A\* with a Manhattan heuristic:* helps when the exit is far and the maze is open. Keys weaken the heuristic.
</details>

## Phase 6: Medusa (discussion)

<details><summary>Answer</summary>

- **A static Medusa.** Before the search, cast rays in 4 directions from each `M` until you hit a wall, and mark those cells forbidden.
  - The precompute costs O(#M · (R + C)) in the worst case, and the search stays O(states).
  - Decide whether a door or gate blocks her line of sight, and say so.
- **A moving Medusa** with period P: add time to the state, `(pos, keys, t mod P)`, and check the gaze for the time you *arrive*. The state space grows ×P.
- **Can you wait in place?** If waiting is allowed, add "stay" as a move.
</details>

## Prompts that worked well in rehearsal (phases 3–5)

- *"Here is `solve()` [paste]. Add one-way gates: a cell `>`/`<`/`v`/`^` can only be entered while moving right/left/down/up. Change only the neighbor check inside the loop, keep the function signature, and don't touch `render`. Return just the changed lines."*
- *"The BFS state must now include which keys `a`–`d` I hold, as a bitmask. Show the changes to the queue entries, the visited check and the door check. Explain why `(pos, mask)` is enough state."*
- *"This profile shows 95% of the time in `Grid.find` called from `is_exit` [paste]. Propose the smallest change that removes it, and list any other O(n)-per-step operations in this function."*

**Bad prompts:** "fix the tests", "solve this problem", "optimize this", or pasting the whole repo and accepting a 150-line rewrite.
