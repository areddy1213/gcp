"""Phase 1 (debug): the rendered solution must keep S, E and other special cells visible."""

import unittest

from maze.grid import Grid
from maze.render import render

SMALL = """
#######
#S..#.#
#.#.#.#
#.#...#
#...#E#
#######
"""

SMALL_PATH = [(1, 1), (1, 2), (1, 3), (2, 3), (3, 3), (3, 4), (3, 5), (4, 5)]


class RenderTest(unittest.TestCase):
    def test_render_draws_path_but_keeps_start_and_exit(self):
        expected = "\n".join([
            "#######",
            "#S**#.#",
            "#.#*#.#",
            "#.#***#",
            "#...#E#",
            "#######",
        ])
        self.assertEqual(render(Grid.parse(SMALL), SMALL_PATH), expected)

    def test_render_without_path_returns_maze_unchanged(self):
        grid = Grid.parse(SMALL)
        self.assertEqual(render(grid, None), str(grid))


if __name__ == "__main__":
    unittest.main()
