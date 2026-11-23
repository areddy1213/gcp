"""Solve every maze in mazes/ (or the files given as arguments) and print it with its path."""

import pathlib
import sys

from maze.grid import Grid
from maze.render import render
from maze.solver import solve


def main(paths):
    for p in paths:
        grid = Grid.load(p)
        path = solve(grid)
        print(f"== {p.name}: " + (f"{len(path) - 1} steps" if path else "no path"))
        print(render(grid, path))
        print()


if __name__ == "__main__":
    here = pathlib.Path(__file__).parent
    args = [pathlib.Path(a) for a in sys.argv[1:]] or sorted((here / "mazes").glob("*.txt"))
    main(args)
