from __future__ import annotations

from dataclasses import dataclass
from math import inf
from time import monotonic
from typing import Optional

from rubik_solver.cube.moves import MOVES, apply_move
from rubik_solver.cube.state import CubeState


@dataclass(frozen=True, slots=True)
class SearchResult:
    moves: tuple[str, ...]
    nodes: int
    depth: int
    elapsed_seconds: float


def heuristic(cube: CubeState) -> int:
    """Admissible lower bound based on misplaced cubies.

    A single face turn can affect at most four corners and four edges, so
    ceil(misplaced / 4) is a lower bound for each cubie type.
    """
    corners = sum(cube.cp[i] != i for i in range(8))
    edges = sum(cube.ep[i] != i for i in range(12))
    return max((corners + 3) // 4, (edges + 3) // 4)


class DepthSearch:
    """Generic IDA* search over the project's CubeState representation.

    The search is intentionally small and reusable: it provides the
    correctness/search foundation for later CFOP and Optimal components.
    """

    def __init__(
        self,
        max_depth: int = 20,
        timeout_seconds: float = 10.0,
        max_nodes: int = 2_000_000,
    ) -> None:
        if max_depth < 0:
            raise ValueError("max_depth must be non-negative.")
        if timeout_seconds < 0:
            raise ValueError("timeout_seconds must be non-negative.")
        if max_nodes < 1:
            raise ValueError("max_nodes must be at least 1.")

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
        threshold = heuristic(start)

        while threshold <= self.max_depth:
            result, next_threshold = self._search(
                start,
                depth=0,
                threshold=threshold,
                path=path,
                previous=None,
            )
            if result is not None:
                return SearchResult(
                    tuple(result),
                    self.nodes,
                    len(result),
                    monotonic() - self.started,
                )
            if next_threshold == inf:
                break
            threshold = next_threshold

        raise RuntimeError(f"No solution found within depth {self.max_depth}.")

    def _search(
        self,
        cube: CubeState,
        depth: int,
        threshold: int,
        path: list[str],
        previous: Optional[str],
    ) -> tuple[Optional[list[str]], float]:
        self._check_limits()
        self.nodes += 1

        estimate = depth + heuristic(cube)
        if estimate > threshold:
            return None, estimate

        if cube.is_solved():
            return path.copy(), inf

        if depth >= self.max_depth:
            return None, inf

        next_threshold: float = inf
        for move in MOVES:
            # Consecutive turns of the same face can always be normalized
            # into a single move, so they are redundant in this search.
            if previous is not None and move[0] == previous[0]:
                continue

            path.append(move)
            result, candidate_threshold = self._search(
                apply_move(cube, move),
                depth + 1,
                threshold,
                path,
                move,
            )
            path.pop()

            if result is not None:
                return result, inf
            next_threshold = min(next_threshold, candidate_threshold)

        return None, next_threshold

    def _check_limits(self) -> None:
        if self.nodes >= self.max_nodes:
            raise RuntimeError(f"Search node limit exceeded: {self.max_nodes}.")
        if monotonic() - self.started >= self.timeout_seconds:
            raise TimeoutError(
                f"Search timeout exceeded: {self.timeout_seconds:.3f}s."
            )
