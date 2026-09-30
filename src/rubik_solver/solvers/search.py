from __future__ import annotations

from dataclasses import dataclass
from time import monotonic

from rubik_solver.cube.moves import MOVES, apply_move
from rubik_solver.cube.state import CubeState


@dataclass(frozen=True, slots=True)
class SearchResult:
    moves: tuple[str, ...]
    nodes: int
    depth: int
    elapsed_seconds: float


def heuristic(cube: CubeState) -> int:
    corners = sum(cube.cp[i] != i for i in range(8))
    edges = sum(cube.ep[i] != i for i in range(12))
    return max((corners + 3) // 4, (edges + 3) // 4)


class DepthSearch:
    """Generic iterative-deepening depth search over CubeState."""

    def __init__(self, max_depth: int = 20, timeout_seconds: float = 10.0, max_nodes: int = 2_000_000):
        self.max_depth = max_depth
        self.timeout_seconds = timeout_seconds
        self.max_nodes = max_nodes
        self.nodes = 0
        self.started = 0.0

    def solve(self, start: CubeState) -> SearchResult:
        if start.is_solved():
            return SearchResult((), 0, 0, 0.0)
        self.nodes = 0
        self.started = monotonic()
        path: list[str] = []
        for limit in range(1, self.max_depth + 1):
            result = self._search(start, 0, limit, path, None)
            if result is not None:
                return SearchResult(tuple(result), self.nodes, len(result), monotonic() - self.started)
        raise RuntimeError(f"No solution found within depth {self.max_depth}.")

    def _search(self, cube: CubeState, depth: int, limit: int, path: list[str], previous: str | None):
        self.nodes += 1
        if self.nodes > self.max_nodes:
            raise RuntimeError(f"Search node limit exceeded: {self.max_nodes}.")
        if monotonic() - self.started > self.timeout_seconds:
            raise TimeoutError(f"Search timeout exceeded: {self.timeout_seconds:.3f}s.")
        if depth + heuristic(cube) > limit:
            return None
        if cube.is_solved():
            return path.copy()
        if depth == limit:
            return None
        for move in MOVES:
            if previous is not None and move[0] == previous[0]:
                continue
            path.append(move)
            result = self._search(apply_move(cube, move), depth + 1, limit, path, move)
            path.pop()
            if result is not None:
                return result
        return None
