"""Phase 2 (debug): the solver must handle open areas and unreachable exits."""

import unittest

from maze.grid import Grid
from maze.solver import solve
from tests.helpers import check_path, time_limit

SMALL = """
#######
#S..#.#
#.#.#.#
#.#...#
#...#E#
#######
"""

ROOM = """
##########
#S.......#
#........#
#........#
#........#
#.......E#
##########
"""

UNREACHABLE = """
#######
#S....#
#.###.#
#.#E#.#
#.###.#
#.....#
#######
"""


class SolverTest(unittest.TestCase):
    def test_small_maze(self):
        grid = Grid.parse(SMALL)
        with time_limit(10):
            check_path(self, grid, solve(grid), 7)

    def test_open_room(self):
        grid = Grid.parse(ROOM)
        with time_limit(10):
            check_path(self, grid, solve(grid), 11)

    def test_unreachable_exit_returns_none(self):
        with time_limit(10):
            self.assertIsNone(solve(Grid.parse(UNREACHABLE)))


if __name__ == "__main__":
    unittest.main()
