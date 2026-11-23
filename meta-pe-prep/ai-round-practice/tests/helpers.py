"""Shared test helpers. You shouldn't need to change this file."""

import contextlib
import signal

GATES = {">": (0, 1), "<": (0, -1), "v": (1, 0), "^": (-1, 0)}
KEYS, DOORS = "abcd", "ABCD"


def check_path(test, grid, path, expected_steps):
    """Assert `path` is a legal S -> E path with exactly `expected_steps` moves.

    Legal means: adjacent steps only, no walls, gates entered only in their arrow's
    direction, and doors crossed only after picking up the matching key.
    """
    test.assertIsNotNone(path, "expected a path, got None")
    test.assertEqual(grid.at(path[0]), "S", "path must start at S")
    test.assertEqual(grid.at(path[-1]), "E", "path must end at E")
    keys = set()
    for prev, cur in zip(path, path[1:]):
        dr, dc = cur[0] - prev[0], cur[1] - prev[1]
        test.assertEqual(abs(dr) + abs(dc), 1, f"non-adjacent step {prev} -> {cur}")
        cell = grid.at(cur)
        test.assertNotEqual(cell, "#", f"path walks through a wall at {cur}")
        if cell in GATES:
            test.assertEqual((dr, dc), GATES[cell], f"entered gate {cell!r} at {cur} from the wrong side")
        if cell in DOORS:
            test.assertIn(cell.lower(), keys, f"crossed door {cell!r} at {cur} without its key")
        if cell in KEYS:
            keys.add(cell)
    test.assertEqual(len(path) - 1, expected_steps, "path is legal but not the shortest")


@contextlib.contextmanager
def time_limit(seconds):
    """Abort the block with TimeoutError after `seconds`. Unix only; a no-op elsewhere."""
    if not hasattr(signal, "setitimer"):
        yield
        return

    def on_alarm(signum, frame):
        raise TimeoutError(f"gave up after {seconds}s")

    previous = signal.signal(signal.SIGALRM, on_alarm)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)
