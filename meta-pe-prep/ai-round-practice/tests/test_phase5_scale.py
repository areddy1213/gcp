"""Phase 5 (optimize): large mazes must each solve in under 1 second.

These mazes are generated in code, so there are no data files to read.
"""

import time
import unittest

from maze.grid import Grid
from maze.solver import solve
from tests.helpers import check_path, time_limit

SKIP = "Phase 5: delete this @unittest.skip line when you start the scale work"
SIZE = 150            # outer size including the border wall
BUDGET_SECONDS = 1.0


def open_maze(size=SIZE):
    rows = [["."] * size for _ in range(size)]
    for i in range(size):
        rows[0][i] = rows[size - 1][i] = rows[i][0] = rows[i][size - 1] = "#"
    return rows


@unittest.skip(SKIP)
class ScaleTest(unittest.TestCase):
    def timed_solve(self, grid):
        start = time.perf_counter()
        with time_limit(30):
            path = solve(grid)
        elapsed = time.perf_counter() - start
        self.assertLess(elapsed, BUDGET_SECONDS, f"solve took {elapsed:.2f}s")
        return path

    def test_large_open_maze(self):
        rows = open_maze()
        rows[1][1], rows[SIZE - 2][SIZE - 2] = "S", "E"
        grid = Grid(["".join(r) for r in rows])
        check_path(self, grid, self.timed_solve(grid), 2 * (SIZE - 3))

    def test_large_maze_with_key_and_door(self):
        rows = open_maze()
        wall_col = SIZE // 2 - 1                 # a full-height wall with one door at the top
        for r in range(1, SIZE - 1):
            rows[r][wall_col] = "#"
        rows[1][wall_col] = "A"
        rows[1][1] = "S"
        rows[SIZE - 2][1] = "a"                  # key in the bottom-left corner
        rows[1][SIZE - 2] = "E"
        grid = Grid(["".join(r) for r in rows])
        to_key = SIZE - 3
        key_to_door = (SIZE - 3) + (wall_col - 1)
        door_to_exit = (SIZE - 2) - wall_col
        check_path(self, grid, self.timed_solve(grid), to_key + key_to_door + door_to_exit)


if __name__ == "__main__":
    unittest.main()
