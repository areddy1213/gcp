"""Phase 3 (feature): one-way gates.

A gate cell can only be ENTERED while moving in the direction of its arrow:
'>' moving right, '<' moving left, 'v' moving down, '^' moving up.
You may leave a gate cell in any direction.
"""

import unittest

from maze.grid import Grid
from maze.solver import solve
from tests.helpers import check_path, time_limit

SKIP = "Phase 3: delete this @unittest.skip line when you start the gates feature"


@unittest.skip(SKIP)
class GateTest(unittest.TestCase):
    def solve_text(self, text):
        grid = Grid.parse(text)
        with time_limit(10):
            return grid, solve(grid)

    def test_wrong_way_gate_forces_detour(self):
        grid, path = self.solve_text("""
#########
#S..<..E#
#.#####.#
#.......#
#########
""")
        check_path(self, grid, path, 10)

    def test_right_way_gate_is_passable(self):
        grid, path = self.solve_text("""
#########
#S..>..E#
#.#####.#
#.......#
#########
""")
        check_path(self, grid, path, 6)

    def test_vertical_gates(self):
        blocked = """
######
#S...#
#^##.#
#....#
#E####
######
"""
        grid, path = self.solve_text(blocked)
        check_path(self, grid, path, 9)
        grid, path = self.solve_text(blocked.replace("^", "v"))
        check_path(self, grid, path, 3)

    def test_only_route_is_against_the_gate(self):
        _, path = self.solve_text("""
#######
#S.<.E#
#######
""")
        self.assertIsNone(path)


if __name__ == "__main__":
    unittest.main()
