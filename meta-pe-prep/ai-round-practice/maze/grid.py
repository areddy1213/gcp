"""Maze grid: parsing, cell lookup and neighbor generation."""

WALL, OPEN, START, EXIT = "#", ".", "S", "E"


class Grid:
    """A rectangular maze. Positions are (row, col) tuples; (0, 0) is top-left."""

    def __init__(self, rows):
        if not rows:
            raise ValueError("empty maze")
        width = len(rows[0])
        if any(len(row) != width for row in rows):
            raise ValueError("maze rows must all be the same width")
        self.rows = [list(row) for row in rows]
        self.height = len(rows)
        self.width = width

    @classmethod
    def parse(cls, text):
        return cls(text.strip("\n").splitlines())

    @classmethod
    def load(cls, path):
        with open(path) as f:
            return cls.parse(f.read())

    def at(self, pos):
        r, c = pos
        return self.rows[r][c]

    def in_bounds(self, pos):
        r, c = pos
        return 0 <= r < self.height and 0 <= c < self.width

    def find(self, ch):
        """Return the position of the first cell equal to `ch`."""
        for r in range(self.height):
            for c in range(self.width):
                if self.rows[r][c] == ch:
                    return (r, c)
        raise ValueError(f"maze has no {ch!r} cell")

    def is_exit(self, pos):
        return pos == self.find(EXIT)

    def neighbors(self, pos):
        """Yield the in-bounds, non-wall cells next to `pos` (up, down, left, right)."""
        r, c = pos
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nxt = (r + dr, c + dc)
            if self.in_bounds(nxt) and self.at(nxt) != WALL:
                yield nxt

    def __str__(self):
        return "\n".join("".join(row) for row in self.rows)
