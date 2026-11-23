"""Breadth-first maze solver."""

from .grid import START

# Safety net so a malformed maze can't hang the solver.
MAX_STEPS = 10_000


def solve(grid):
    """Return the shortest path from S to E as a list of (row, col), or None if E is unreachable.

    The path includes both the start cell and the exit cell.
    """
    start = grid.find(START)
    queue = [(start, [start])]
    steps = 0
    while queue:
        steps += 1
        if steps > MAX_STEPS:
            raise RuntimeError(f"search exceeded {MAX_STEPS} steps")
        pos, path = queue.pop(0)
        if grid.is_exit(pos):
            return path
        for nxt in grid.neighbors(pos):
            queue.append((nxt, path + [nxt]))
    return None
