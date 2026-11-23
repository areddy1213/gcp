"""Phase 4 (feature): keys and doors.

Keys are 'a'-'d'; the matching doors are 'A'-'D'. Stepping onto a key picks it up
for the rest of the walk. A door can only be entered while holding its key.
The shortest path may revisit cells (for example, a detour to fetch a key).
"""

import unittest

from maze.grid import Grid
from maze.solver import solve
from tests.helpers import check_path, time_limit

SKIP = "Phase 4: delete this @unittest.skip line when you start the keys feature"


@unittest.skip(SKIP)
class KeyTest(unittest.TestCase):
    def solve_text(self, text):
        grid = Grid.parse(text)
        with time_limit(10):
            return grid, solve(grid)

    def test_detour_to_fetch_key(self):
        grid, path = self.solve_text("""
#########
#S..A..E#
#.#######
#...a...#
#########
""")
        check_path(self, grid, path, 16)

    def test_key_locked_behind_its_own_door(self):
        _, path = self.solve_text("""
########
#S.A.aE#
########
""")
        self.assertIsNone(path)

    def test_two_keys_must_be_collected_in_order(self):
        grid, path = self.solve_text("""
##############
#b.A.a.S.B..E#
##############
""")
        check_path(self, grid, path, 17)

    def test_gates_and_keys_together(self):
        grid, path = self.solve_text("""
#########
#S..>.A.#
#.#####.#
#a#####.#
#######E#
#########
""")
        check_path(self, grid, path, 13)


if __name__ == "__main__":
    unittest.main()
