from __future__ import annotations

from dataclasses import dataclass, field
from collections import deque
from time import monotonic

from rubik_solver.cube.moves import MOVES, apply_move
from rubik_solver.cube.state import CubeState
from rubik_solver.model.solution import Solution, SolutionPhase
from rubik_solver.solvers.base import Solver


_ALL_MOVES = tuple(MOVES)
_CROSS_EDGES = (4, 5, 6, 7)  # DR, DF, DL, DB on the D face.
_CROSS_PDB: dict[tuple[tuple[int, ...], tuple[int, ...]], int] | None = None
_CROSS_MOVE_TRANSITIONS: dict[str, tuple[tuple[int, int], ...]] | None = None


def cross_solved(cube: CubeState) -> bool:
    """Return whether the four D-layer cross edges are solved in place."""
    return all(cube.ep[i] == i and cube.eo[i] == 0 for i in _CROSS_EDGES)


def _build_cross_move_transitions() -> dict[str, tuple[tuple[int, int], ...]]:
    transitions: dict[str, tuple[tuple[int, int], ...]] = {}
    for move, definition in MOVES.items():
        inverse_ep = [0] * 12
        for new_pos, old_pos in enumerate(definition.ep):
            inverse_ep[old_pos] = new_pos
        transitions[move] = tuple(
            (inverse_ep[old_pos], definition.eo[inverse_ep[old_pos]])
            for old_pos in range(12)
        )
    return transitions


def _build_cross_pdb() -> dict[tuple[tuple[int, ...], tuple[int, ...]], int]:
    """Build the exact distance table for the four cross edges only."""
    global _CROSS_MOVE_TRANSITIONS
    if _CROSS_MOVE_TRANSITIONS is None:
        _CROSS_MOVE_TRANSITIONS = _build_cross_move_transitions()

    solved = (tuple(_CROSS_EDGES), (0, 0, 0, 0))
    distances = {solved: 0}
    queue = deque([solved])
    while queue:
        positions, orientations = queue.popleft()
        distance = distances[(positions, orientations)]
        for move in _ALL_MOVES:
            transition = _CROSS_MOVE_TRANSITIONS[move]
            next_positions = [0] * 4
            next_orientations = [0] * 4
            for piece_index, old_pos in enumerate(positions):
                new_pos, flip = transition[old_pos]
                next_positions[piece_index] = new_pos
                next_orientations[piece_index] = orientations[piece_index] ^ flip
            next_state = (tuple(next_positions), tuple(next_orientations))
            if next_state not in distances:
                distances[next_state] = distance + 1
                queue.append(next_state)
    return distances


def cross_heuristic(cube: CubeState) -> int:
    """Exact lower bound for the Cross abstraction."""
    global _CROSS_PDB
    if _CROSS_PDB is None:
        _CROSS_PDB = _build_cross_pdb()
    positions = tuple(cube.ep.index(piece) for piece in _CROSS_EDGES)
    orientations = tuple(cube.eo[position] for position in positions)
    return _CROSS_PDB[(positions, orientations)]


@dataclass(slots=True)
class _CrossSearch:
    max_depth: int
    max_nodes: int | None
    timeout_seconds: float | None
    nodes: int = field(init=False, default=0)
    started: float = field(init=False, default=0.0)
    path: list[str] = field(init=False, default_factory=list)
    seen: dict[tuple[CubeState, str | None], int] = field(init=False, default_factory=dict)

    def __post_init__(self) -> None:
        self.started = monotonic()

    def _check_limits(self) -> None:
        if self.max_nodes is not None and self.nodes >= self.max_nodes:
            raise RuntimeError("Cross search node limit exceeded")
        if (
            self.timeout_seconds is not None
            and monotonic() - self.started >= self.timeout_seconds
        ):
            raise TimeoutError("Cross search timeout exceeded")

    def solve(self, cube: CubeState) -> tuple[str, ...]:
        if cross_solved(cube):
            return ()

        for threshold in range(cross_heuristic(cube), self.max_depth + 1):
            result = self._dfs(cube, 0, threshold, None)
            if result is not None:
                return result
        raise RuntimeError(f"Cross search failed within depth {self.max_depth}")

    def _dfs(
        self,
        cube: CubeState,
        depth: int,
        threshold: int,
        previous_face: str | None,
    ) -> tuple[str, ...] | None:
        self._check_limits()
        self.nodes += 1

        h = cross_heuristic(cube)
        if depth + h > threshold:
            return None
        if cross_solved(cube):
            return tuple(self.path)
        if depth == threshold:
            return None

        for move in _ALL_MOVES:
            if previous_face is not None and move[0] == previous_face:
                continue
            self.path.append(move)
            result = self._dfs(apply_move(cube, move), depth + 1, threshold, move[0])
            self.path.pop()
            if result is not None:
                return result
        return None


class CrossSolver(Solver):
    """CFOP Cross phase solver for the D-layer cross."""

    method = "cfop-cross"

    def __init__(
        self,
        *,
        max_depth: int = 8,
        max_nodes: int | None = 1_000_000,
        timeout_seconds: float | None = 10.0,
    ) -> None:
        self.max_depth = max_depth
        self.max_nodes = max_nodes
        self.timeout_seconds = timeout_seconds

    def solve(self, cube: CubeState) -> Solution:
        search = _CrossSearch(self.max_depth, self.max_nodes, self.timeout_seconds)
        moves = search.solve(cube)
        after = cube
        for move in moves:
            after = apply_move(after, move)

        if not cross_solved(after):
            raise RuntimeError("CFOP Cross returned an invalid phase solution")

        phase = SolutionPhase(
            name="Cross",
            moves=moves,
            description="Solve the four D-layer cross edges in their correct slots.",
        )
        return Solution(
            method=self.method,
            moves=moves,
            metric="HTM",
            verified=True,
            phases=(phase,),
            metadata={
                "algorithm": "CFOP Cross",
                "search": "IDA*",
                "nodes": search.nodes,
                "depth": len(moves),
            },
        )

# ---------------------------------------------------------------------------
# F2L
# ---------------------------------------------------------------------------

_F2L_SLOTS = ((4, 8), (5, 9), (6, 10), (7, 11))
_F2L_SLOT_FACES = (("U", "R", "F"), ("U", "F", "L"), ("U", "L", "B"), ("U", "B", "R"))  # DFR/FR, DLF/FL, DBL/BL, DRB/BR\n_F2L_SLOT_FACES = (("U", "R", "F"), ("U", "F", "L"), ("U", "L", "B"), ("U", "B", "R"))
_F2L_PAIR_PDBS: dict[tuple[int, int], dict[tuple[int, int, int, int], int]] = {}
_F2L_PAIR_TRANSITIONS: dict[str, tuple[tuple[int, int], ...]] | None = None


def f2l_slot_solved(cube: CubeState, corner: int, edge: int) -> bool:
    return (
        cube.cp[corner] == corner
        and cube.co[corner] == 0
        and cube.ep[edge] == edge
        and cube.eo[edge] == 0
    )


def f2l_solved(cube: CubeState) -> bool:
    return all(f2l_slot_solved(cube, corner, edge) for corner, edge in _F2L_SLOTS) and cross_solved(cube)


def _build_f2l_pair_transitions() -> dict[str, tuple[tuple[int, int], ...]]:
    transitions: dict[str, tuple[tuple[int, int], ...]] = {}
    for move, definition in MOVES.items():
        inverse_cp = [0] * 8
        inverse_ep = [0] * 12
        for new_pos, old_pos in enumerate(definition.cp):
            inverse_cp[old_pos] = new_pos
        for new_pos, old_pos in enumerate(definition.ep):
            inverse_ep[old_pos] = new_pos
        transitions[move] = tuple(
            (inverse_cp[old_pos], definition.co[inverse_cp[old_pos]]) for old_pos in range(8)
        ) + tuple(
            (inverse_ep[old_pos], definition.eo[inverse_ep[old_pos]]) for old_pos in range(12)
        )
    return transitions


def _build_f2l_pair_pdb(corner_piece: int, edge_piece: int) -> dict[tuple[int, int, int, int], int]:
    global _F2L_PAIR_TRANSITIONS
    if _F2L_PAIR_TRANSITIONS is None:
        _F2L_PAIR_TRANSITIONS = _build_f2l_pair_transitions()

    solved = (corner_piece, 0, edge_piece, 0)
    distances = {solved: 0}
    queue = deque([solved])
    while queue:
        state = queue.popleft()
        distance = distances[state]
        corner_pos, corner_ori, edge_pos, edge_ori = state
        for move in _ALL_MOVES:
            transition = _F2L_PAIR_TRANSITIONS[move]
            new_corner_pos, corner_delta = transition[corner_pos]
            new_edge_pos, edge_delta = transition[8 + edge_pos]
            next_state = (
                new_corner_pos,
                (corner_ori + corner_delta) % 3,
                new_edge_pos,
                edge_ori ^ edge_delta,
            )
            if next_state not in distances:
                distances[next_state] = distance + 1
                queue.append(next_state)
    return distances


def _f2l_pair_heuristic(cube: CubeState, corner_piece: int, edge_piece: int) -> int:
    pdb = _F2L_PAIR_PDBS.get((corner_piece, edge_piece))
    if pdb is None:
        pdb = _build_f2l_pair_pdb(corner_piece, edge_piece)
        _F2L_PAIR_PDBS[(corner_piece, edge_piece)] = pdb
    corner_pos = cube.cp.index(corner_piece)
    edge_pos = cube.ep.index(edge_piece)
    return pdb[(corner_pos, cube.co[corner_pos], edge_pos, cube.eo[edge_pos])]


@dataclass(slots=True)
class _F2LSearch:
    target_corner: int
    target_edge: int
    protected_slots: tuple[tuple[int, int], ...]
    allowed_faces: tuple[str, ...]
    max_depth: int
    max_nodes: int | None
    timeout_seconds: float | None
    nodes: int = field(init=False, default=0)
    started: float = field(init=False, default=0.0)
    path: list[str] = field(init=False, default_factory=list)
    seen: dict[tuple[CubeState, str | None], int] = field(init=False, default_factory=dict)

    def __post_init__(self) -> None:
        self.started = monotonic()

    def _check_limits(self) -> None:
        if self.max_nodes is not None and self.nodes >= self.max_nodes:
            raise RuntimeError("F2L search node limit exceeded")
        if self.timeout_seconds is not None and monotonic() - self.started >= self.timeout_seconds:
            raise TimeoutError("F2L search timeout exceeded")

    def _goal(self, cube: CubeState) -> bool:
        return (
            cross_solved(cube)
            and f2l_slot_solved(cube, self.target_corner, self.target_edge)
            and all(f2l_slot_solved(cube, corner, edge) for corner, edge in self.protected_slots)
        )

    def _heuristic(self, cube: CubeState) -> int:
        values = [cross_heuristic(cube), _f2l_pair_heuristic(cube, self.target_corner, self.target_edge)]
        values.extend(_f2l_pair_heuristic(cube, corner, edge) for corner, edge in self.protected_slots)
        return max(values)

    def solve(self, cube: CubeState) -> tuple[str, ...]:
        if self._goal(cube):
            return ()
        for threshold in range(self._heuristic(cube), self.max_depth + 1):
            result = self._dfs(cube, 0, threshold, None)
            if result is not None:
                return result
        raise RuntimeError(f"F2L slot search failed within depth {self.max_depth}")

    def _dfs(self, cube: CubeState, depth: int, threshold: int, previous_face: str | None) -> tuple[str, ...] | None:
        self._check_limits()
        self.nodes += 1
        if depth + self._heuristic(cube) > threshold:
            return None
        if self._goal(cube):
            return tuple(self.path)
        if depth == threshold:
            return None
        for move in _ALL_MOVES:
            if previous_face is not None and move[0] == previous_face:
                continue
            self.path.append(move)
            result = self._dfs(apply_move(cube, move), depth + 1, threshold, move[0])
            self.path.pop()
            if result is not None:
                return result
        return None

class F2LSolver(Solver):
    """CFOP F2L solver that inserts one corner-edge pair at a time."""

    method = "cfop-f2l"

    def __init__(
        self,
        *,
        max_depth: int = 14,
        max_nodes: int | None = 2_000_000,
        timeout_seconds: float | None = 10.0,
    ) -> None:
        self.max_depth = max_depth
        self.max_nodes = max_nodes
        self.timeout_seconds = timeout_seconds

    def solve(self, cube: CubeState) -> Solution:
        if not cross_solved(cube):
            raise RuntimeError("F2L requires a solved CFOP Cross")

        state = cube
        phases: list[SolutionPhase] = []
        total_moves: list[str] = []
        total_nodes = 0

        for index, (corner, edge) in enumerate(_F2L_SLOTS, start=1):
            protected = _F2L_SLOTS[: index - 1]
            search = _F2LSearch(
                target_corner=corner,
                target_edge=edge,
                protected_slots=protected,
                allowed_faces=_F2L_SLOT_FACES[index - 1],
                max_depth=self.max_depth,
                max_nodes=self.max_nodes,
                timeout_seconds=self.timeout_seconds,
            )
            moves = search.solve(state)
            for move in moves:
                state = apply_move(state, move)
            if not f2l_slot_solved(state, corner, edge):
                raise RuntimeError(f"F2L slot {index} returned an invalid solution")
            total_nodes += search.nodes
            total_moves.extend(moves)
            phases.append(
                SolutionPhase(
                    name=f"F2L-{index}",
                    moves=moves,
                    description=f"Solve F2L corner-edge pair {index} while preserving previous pairs.",
                )
            )

        if not f2l_solved(state):
            raise RuntimeError("F2L returned an invalid first-two-layers state")

        return Solution(
            method=self.method,
            moves=tuple(total_moves),
            metric="HTM",
            verified=True,
            phases=tuple(phases),
            metadata={
                "algorithm": "CFOP F2L",
                "search": "IDA* with exact corner-edge pair PDB",
                "nodes": total_nodes,
                "slots": len(_F2L_SLOTS),
            },
        )
