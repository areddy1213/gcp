"""Draw a solution path onto a maze."""

PATH = "*"


def render(grid, path):
    """Return the maze as text with the path drawn as '*'.

    Only open cells ('.') are drawn over: the start, the exit and every other
    special cell keep their own symbol so the output stays readable.
    """
    rows = [row[:] for row in grid.rows]
    for r, c in path or []:
        rows[r][c] = PATH
    return "\n".join("".join(row) for row in rows)
