from __future__ import annotations

from dataclasses import dataclass, field
from collections import deque
from time import monotonic

from rubik_solver.cube.moves import MOVES, apply_move, apply_moves, inverse_move
from rubik_solver.cube.state import CubeState
from rubik_solver.model.solution import Solution, SolutionPhase
from rubik_solver.solvers.base import Solver
from rubik_solver.solvers.kociemba_engine import Cube as EngineCube
from rubik_solver.solvers.kociemba_engine import init_solver as init_kociemba_engine


_ALL_MOVES = tuple(MOVES)
_CROSS_EDGES = (4, 5, 6, 7)  # DR, DF, DL, DB on the D face.
_CROSS_PDBS: dict[tuple[int, ...], dict[tuple[tuple[int, ...], tuple[int, ...]], int]] = {}
_CROSS_MOVE_TRANSITIONS: dict[str, tuple[tuple[int, int], ...]] | None = None


_X2_CORNER_MAP = (7, 6, 5, 4, 3, 2, 1, 0)
_X2_EDGE_MAP = (4, 7, 6, 5, 0, 3, 2, 1, 11, 10, 9, 8)


def _to_x2_coordinate_frame(cube: CubeState) -> CubeState:
    """Convert a physical x2-rotated cube into the canonical solver frame."""
    rotated = _apply_oll_algorithm(cube, "x2")
    corner_inverse = [0] * 8
    edge_inverse = [0] * 12
    for canonical, rotated_piece in enumerate(_X2_CORNER_MAP):
        corner_inverse[rotated_piece] = canonical
    for canonical, rotated_piece in enumerate(_X2_EDGE_MAP):
        edge_inverse[rotated_piece] = canonical
    return CubeState(
        cp=tuple(corner_inverse[piece] for piece in rotated.cp),
        co=rotated.co,
        ep=tuple(edge_inverse[piece] for piece in rotated.ep),
        eo=rotated.eo,
    )


def _rotation_solved(cube: CubeState) -> bool:
    """Recognize a solved cubie state in any y/x2 whole-cube orientation."""
    for y_rotation in range(4):
        rotation = " ".join(("y",) * y_rotation + ("x2",))
        if not rotation:
            rotation = ""
        expected = _apply_oll_algorithm(CubeState.solved(), rotation)
        if cube == expected:
            return True
    return cube == CubeState.solved()


_CONJUGATION_MOVE_CACHE: dict[str, dict[str, str]] = {}


def _inverse_algorithm_tokens(sequence: str) -> tuple[str, ...]:
    tokens = tuple(sequence.split())
    return tuple(inverse_move(token) for token in reversed(tokens))


def _conjugate_moves(rotation: str, moves: tuple[str, ...]) -> tuple[str, ...]:
    """Convert canonical-frame moves into moves for a physically rotated cube."""
    cache = _CONJUGATION_MOVE_CACHE.setdefault(rotation, {})
    inverse_rotation = " ".join(_inverse_algorithm_tokens(rotation))
    candidates = tuple(
        f"{base}{suffix}"
        for base in "URFDLBMESxyzurfdlb"
        for suffix in ("", "2", "'")
    )
    for move in moves:
        if move in cache:
            continue
        target = _apply_oll_algorithm(
            CubeState.solved(),
            " ".join(part for part in (rotation, move, inverse_rotation) if part),
        )
        match = next(
            (candidate for candidate in candidates
             if _apply_oll_algorithm(CubeState.solved(), candidate) == target),
            None,
        )
        if match is None:
            raise RuntimeError(f"Cannot conjugate move {move!r} by rotation {rotation!r}")
        cache[move] = match
    return tuple(cache[move] for move in moves)


def _cfop_solved(cube: CubeState) -> bool:
    """Accept a solved cube regardless of the final whole-cube orientation."""
    return pll_solved(cube) or _rotation_solved(cube)


def cross_solved(cube: CubeState, edges: tuple[int, ...] = _CROSS_EDGES) -> bool:
    """Return whether the canonical D-layer cross edges are solved."""
    return all(cube.ep[i] == i and cube.eo[i] == 0 for i in edges)


def _cross_goal(
    cube: CubeState,
    target_pieces: tuple[int, ...],
    target_positions: tuple[int, ...],
) -> bool:
    return all(
        cube.ep[position] == piece and cube.eo[position] == 0
        for piece, position in zip(target_pieces, target_positions)
    )


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


def _build_cross_pdb(
    target_positions: tuple[int, ...] = _CROSS_EDGES,
) -> dict[tuple[tuple[int, ...], tuple[int, ...]], int]:
    """Build the exact distance table for the four cross edges only."""
    global _CROSS_MOVE_TRANSITIONS
    if _CROSS_MOVE_TRANSITIONS is None:
        _CROSS_MOVE_TRANSITIONS = _build_cross_move_transitions()

    solved = (tuple(target_positions), (0, 0, 0, 0))
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


def cross_heuristic(
    cube: CubeState,
    target_pieces: tuple[int, ...] = _CROSS_EDGES,
    target_positions: tuple[int, ...] = _CROSS_EDGES,
) -> int:
    """Exact lower bound for the Cross abstraction."""
    pdb = _CROSS_PDBS.get(target_positions)
    if pdb is None:
        pdb = _build_cross_pdb(target_positions)
        _CROSS_PDBS[target_positions] = pdb
    # The PDB stores four abstract cross pieces in target-slot order. This
    # lets CFOP reuse the same exact table when x2 maps the white U Cross to
    # D while the physical piece IDs remain the original U pieces.
    positions = tuple(cube.ep.index(piece) for piece in target_pieces)
    orientations = tuple(cube.eo[position] for position in positions)
    return pdb[(positions, orientations)]


@dataclass(slots=True)
class _CrossSearch:
    max_depth: int
    max_nodes: int | None
    timeout_seconds: float | None
    target_pieces: tuple[int, ...] = _CROSS_EDGES
    target_positions: tuple[int, ...] = _CROSS_EDGES
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
        if _cross_goal(cube, self.target_pieces, self.target_positions):
            return ()

        for threshold in range(
            cross_heuristic(cube, self.target_pieces, self.target_positions),
            self.max_depth + 1,
        ):
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

        h = cross_heuristic(cube, self.target_pieces, self.target_positions)
        if depth + h > threshold:
            return None
        if _cross_goal(cube, self.target_pieces, self.target_positions):
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
    """CFOP Cross phase solver for a configurable set of four edge slots."""

    method = "cfop-cross"

    def __init__(
        self,
        *,
        max_depth: int = 8,
        max_nodes: int | None = 1_000_000,
        timeout_seconds: float | None = 10.0,
        target_pieces: tuple[int, ...] = _CROSS_EDGES,
        target_positions: tuple[int, ...] = _CROSS_EDGES,
    ) -> None:
        self.max_depth = max_depth
        self.max_nodes = max_nodes
        self.timeout_seconds = timeout_seconds
        self.target_pieces = target_pieces
        self.target_positions = target_positions

    def solve(self, cube: CubeState) -> Solution:
        search = _CrossSearch(
            self.max_depth,
            self.max_nodes,
            self.timeout_seconds,
            self.target_pieces,
            self.target_positions,
        )
        moves = search.solve(cube)
        after = cube
        for move in moves:
            after = apply_move(after, move)

        if not _cross_goal(after, self.target_pieces, self.target_positions):
            raise RuntimeError("CFOP Cross returned an invalid phase solution")

        phase = SolutionPhase(
            name="Cross",
            moves=moves,
            description="Solve the four Cross edges in their correct slots.",
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
_F2L_SLOT_FACES = (("U", "R", "F"), ("U", "F", "L"), ("U", "L", "B"), ("U", "B", "R"))  # DFR/FR, DLF/FL, DBL/BL, DRB/BR_F2L_SLOT_FACES = (("U", "R", "F"), ("U", "F", "L"), ("U", "L", "B"), ("U", "B", "R"))
_F2L_PAIR_PDBS: dict[tuple[int, int, int, int], dict[tuple[int, int, int, int], int]] = {}
_F2L_PAIR_TRANSITIONS: dict[str, tuple[tuple[int, int], ...]] | None = None


def f2l_slot_solved(
    cube: CubeState,
    corner: int,
    edge: int,
    corner_piece: int | None = None,
    edge_piece: int | None = None,
) -> bool:
    corner_piece = corner if corner_piece is None else corner_piece
    edge_piece = edge if edge_piece is None else edge_piece
    return (
        cube.cp[corner] == corner_piece
        and cube.co[corner] == 0
        and cube.ep[edge] == edge_piece
        and cube.eo[edge] == 0
    )


def f2l_solved(
    cube: CubeState,
    *,
    slots: tuple[tuple[int, int], ...] = _F2L_SLOTS,
    pieces: tuple[tuple[int, int], ...] = _F2L_SLOTS,
    cross_pieces: tuple[int, ...] = _CROSS_EDGES,
    cross_positions: tuple[int, ...] = _CROSS_EDGES,
) -> bool:
    return (
        _cross_goal(cube, cross_pieces, cross_positions)
        and all(
            f2l_slot_solved(cube, corner_goal, edge_goal, corner_piece, edge_piece)
            for (corner_goal, edge_goal), (corner_piece, edge_piece) in zip(slots, pieces)
        )
    )


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


def _build_f2l_pair_pdb(
    corner_piece: int,
    edge_piece: int,
    corner_goal: int,
    edge_goal: int,
) -> dict[tuple[int, int, int, int], int]:
    global _F2L_PAIR_TRANSITIONS
    if _F2L_PAIR_TRANSITIONS is None:
        _F2L_PAIR_TRANSITIONS = _build_f2l_pair_transitions()

    solved = (corner_goal, 0, edge_goal, 0)
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


def _f2l_pair_heuristic(
    cube: CubeState,
    corner_piece: int,
    edge_piece: int,
    corner_goal: int,
    edge_goal: int,
) -> int:
    key = (corner_piece, edge_piece, corner_goal, edge_goal)
    pdb = _F2L_PAIR_PDBS.get(key)
    if pdb is None:
        pdb = _build_f2l_pair_pdb(corner_piece, edge_piece, corner_goal, edge_goal)
        _F2L_PAIR_PDBS[key] = pdb
    corner_pos = cube.cp.index(corner_piece)
    edge_pos = cube.ep.index(edge_piece)
    return pdb[(corner_pos, cube.co[corner_pos], edge_pos, cube.eo[edge_pos])]


@dataclass(slots=True)
class _F2LSearch:
    target_corner: int
    target_edge: int
    target_corner_goal: int
    target_edge_goal: int
    protected_slots: tuple[tuple[int, int], ...]
    protected_pieces: tuple[tuple[int, int], ...]
    cross_pieces: tuple[int, ...]
    cross_positions: tuple[int, ...]
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
            _cross_goal(cube, self.cross_pieces, self.cross_positions)
            and f2l_slot_solved(
                cube,
                self.target_corner_goal,
                self.target_edge_goal,
                self.target_corner,
                self.target_edge,
            )
            and all(
                f2l_slot_solved(cube, corner_goal, edge_goal, corner_piece, edge_piece)
                for (corner_goal, edge_goal), (corner_piece, edge_piece) in zip(
                    self.protected_slots, self.protected_pieces
                )
            )
        )

    def _heuristic(self, cube: CubeState) -> int:
        values = [
            cross_heuristic(cube, self.cross_pieces, self.cross_positions),
            _f2l_pair_heuristic(
                cube,
                self.target_corner,
                self.target_edge,
                self.target_corner_goal,
                self.target_edge_goal,
            ),
        ]
        values.extend(
            _f2l_pair_heuristic(cube, corner_piece, edge_piece, corner_goal, edge_goal)
            for (corner_goal, edge_goal), (corner_piece, edge_piece) in zip(
                self.protected_slots, self.protected_pieces
            )
        )
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
        preferred_faces = set(self.allowed_faces)
        ordered_moves = sorted(
            _ALL_MOVES,
            key=lambda move: (
                0 if move[0] in preferred_faces else 1,
                0 if move[0] == "U" else 1,
                1 if move[0] == "D" else 0,
                1 if move.endswith("2") else 0,
            ),
        )
        for move in ordered_moves:
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
        slots: tuple[tuple[int, int], ...] = _F2L_SLOTS,
        pieces: tuple[tuple[int, int], ...] = _F2L_SLOTS,
        cross_pieces: tuple[int, ...] = _CROSS_EDGES,
        cross_positions: tuple[int, ...] = _CROSS_EDGES,
    ) -> None:
        self.max_depth = max_depth
        self.max_nodes = max_nodes
        self.timeout_seconds = timeout_seconds
        self.slots = slots
        self.pieces = pieces
        self.cross_pieces = cross_pieces
        self.cross_positions = cross_positions

    def solve(self, cube: CubeState) -> Solution:
        if not _cross_goal(cube, self.cross_pieces, self.cross_positions):
            raise RuntimeError("F2L requires a solved CFOP Cross")

        state = cube
        phases: list[SolutionPhase] = []
        total_moves: list[str] = []
        total_nodes = 0

        for index, ((corner_goal, edge_goal), (corner, edge)) in enumerate(
            zip(self.slots, self.pieces), start=1
        ):
            protected = self.slots[: index - 1]
            protected_pieces = self.pieces[: index - 1]
            search = _F2LSearch(
                target_corner=corner,
                target_edge=edge,
                target_corner_goal=corner_goal,
                target_edge_goal=edge_goal,
                protected_slots=protected,
                protected_pieces=protected_pieces,
                allowed_faces=_F2L_SLOT_FACES[index - 1],
                max_depth=self.max_depth,
                max_nodes=self.max_nodes,
                timeout_seconds=self.timeout_seconds,
                cross_pieces=self.cross_pieces,
                cross_positions=self.cross_positions,
            )
            moves = search.solve(state)
            for move in moves:
                state = apply_move(state, move)
            if not f2l_slot_solved(state, corner_goal, edge_goal, corner, edge):
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

        if not all(
            f2l_slot_solved(state, corner_goal, edge_goal, corner, edge)
            for (corner_goal, edge_goal), (corner, edge) in zip(self.slots, self.pieces)
        ) or not _cross_goal(state, self.cross_pieces, self.cross_positions):
            raise RuntimeError("F2L returned an invalid first-two-layers state")

        return Solution(
            method=self.method,
            moves=tuple(total_moves),
            metric="HTM",
            verified=True,
            phases=tuple(phases),
            metadata={
                "algorithm": "CFOP F2L",
                "search": "IDA* with exact corner-edge pair PDB and human-style move ordering",
                "nodes": total_nodes,
                "slots": len(self.slots),
            },
        )


# ---------------------------------------------------------------------------
# OLL
# ---------------------------------------------------------------------------


def oll_solved(cube: CubeState) -> bool:
    return f2l_solved(cube) and all(x == 0 for x in cube.co) and all(x == 0 for x in cube.eo)


_OLL_ALGORITHMS: tuple[tuple[int, str], ...] = (
    (1, "R U2 R2 F R F' U2 R' F R F'"),
    (2, "F R U R' U' F' f R U R' U' f'"),
    (3, "f R U R' U' f' U' F R U R' U' F'"),
    (4, "f R U R' U' f' U F R U R' U' F'"),
    (5, "r' U2 R U R' U r"),
    (6, "r U2 R' U' R U' r'"),
    (7, "r U R' U R U2 r'"),
    (8, "r' U' R U' R' U2 r"),
    (9, "R U R' U' R' F R2 U R' U' F'"),
    (10, "R U R' U R' F R F' R U2 R'"),
    (11, "r U R' U R' F R F' R U2 r'"),
    (12, "M' R' U' R U' R' U2 R U' R r'"),
    (13, "F U R U' R2 F' R U R U' R'"),
    (14, "R' F R U R' F' R F U' F'"),
    (15, "l' U' l L' U' L U l' U l"),
    (16, "r U r' R U R' U' r U' r'"),
    (17, "R U R' U R' F R F' U2 R' F R F'"),
    (18, "r U R' U R U2 r2 U' R U' R' U2 r"),
    (19, "r' R U R U R' U' M' R' F R F'"),
    (20, "r U R' U' M2 U R U' R' U' M'"),
    (21, "R U2 R' U' R U R' U' R U' R'"),
    (22, "R U2 R2 U' R2 U' R2 U2 R"),
    (23, "R2 D R' U2 R D' R' U2 R'"),
    (24, "r U R' U' r' F R F'"),
    (25, "F' r U R' U' r' F R"),
    (26, "R U2 R' U' R U' R'"),
    (27, "R U R' U R U2 R'"),
    (28, "r U R' U' r' R U R U' R'"),
    (29, "R U R' U' R U' R' F' U' F R U R'"),
    (30, "F R' F R2 U' R' U' R U R' F2"),
    (31, "R' U' F U R U' R' F' R"),
    (32, "S R U R' U' R' F R f'"),
    (33, "R U R' U' R' F R F'"),
    (34, "R U R2 U' R' F R U R U' F'"),
    (35, "R U2 R2 F R F' R U2 R'"),
    (36, "L' U' L U' L' U L U L F' L' F"),
    (37, "F R' F' R U R U' R'"),
    (38, "R U R' U R U' R' U' R' F R F'"),
    (39, "L F' L' U' L U F U' L'"),
    (40, "R' F R U R' U' F' U R"),
    (41, "R U R' U R U2 R' F R U R' U' F'"),
    (42, "R' U' R U' R' U2 R F R U R' U' F'"),
    (43, "F' U' L' U L F"),
    (44, "F U R U' R' F'"),
    (45, "F R U R' U' F'"),
    (46, "R' U' R' F R F' U R"),
    (47, "R' U' R' F R F' R' F R F' U R"),
    (48, "F R U R' U' R U R' U' F'"),
    (49, "r U' r2 U r2 U r2 U' r"),
    (50, "r' U r2 U' r2 U' r2 U r'"),
    (51, "F U R U' R' U R U' R' F'"),
    (52, "R U R' U R U' B U' B' R'"),
    (53, "l' U' L U' L' U L U' L' U2 l"),
    (54, "r U R' U R U' R' U R U2 r'"),
    (55, "R U2 R2 U' R U' R' U2 F R F'"),
    (56, "r U r' U R U' R' U R U' R' r U' r'"),
    (57, "R U R' U' M' U R U' r'"),
)

_OLL_CASE_LOOKUP: dict[tuple[tuple[int, ...], tuple[int, ...]], tuple[int, str]] | None = None
_OLL_ENGINE_READY = False


def _ensure_oll_engine() -> None:
    global _OLL_ENGINE_READY
    if not _OLL_ENGINE_READY:
        init_kociemba_engine()
        _OLL_ENGINE_READY = True


def _to_engine_cube(cube: CubeState) -> EngineCube:
    result = EngineCube()
    result.cp[:] = cube.cp
    result.co[:] = cube.co
    result.ep[:] = cube.ep
    result.eo[:] = cube.eo
    return result


def _from_engine_cube(cube: EngineCube) -> CubeState:
    return CubeState(
        cp=tuple(cube.cp),
        co=tuple(cube.co),
        ep=tuple(cube.ep),
        eo=tuple(cube.eo),
    )


def _apply_oll_algorithm(cube: CubeState, algorithm: str) -> CubeState:
    _ensure_oll_engine()
    engine_cube = _to_engine_cube(cube)
    engine_cube.move(algorithm)
    return _from_engine_cube(engine_cube)


def _to_white_down_frame(cube: CubeState) -> CubeState:
    """Rotate the standard white-on-U cube so white is the internal D face."""
    return _apply_oll_algorithm(cube, "x2")


def _oll_orientation_key(cube: CubeState) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """Return the OLL orientation pattern; AUF is handled in the lookup table."""
    return cube.co[:4], cube.eo[:4]


def _build_oll_case_lookup() -> dict[tuple[tuple[int, ...], tuple[int, ...]], tuple[int, str]]:
    lookup: dict[tuple[tuple[int, ...], tuple[int, ...]], tuple[int, str]] = {}
    solved = CubeState.solved()
    for case_number, algorithm in _OLL_ALGORITHMS:
        case = _apply_oll_algorithm(solved, _inverse_algorithm(algorithm))
        if not f2l_solved(case):
            raise RuntimeError(f"OLL case {case_number} does not preserve F2L")
        current = case
        auf_inverse = ("", "U'", "U2", "U")
        for rotation in range(4):
            key = _oll_orientation_key(current)
            candidate = (auf_inverse[rotation] + (" " if auf_inverse[rotation] else "") + algorithm).strip()
            if key in lookup and lookup[key][0] != case_number:
                raise RuntimeError(
                    f"OLL case collision: {case_number} conflicts with {lookup[key][0]}"
                )
            lookup[key] = (case_number, candidate)
            current = apply_move(current, "U")
    if len(lookup) < 57:
        raise RuntimeError(f"Expected at least 57 OLL orientation cases, generated {len(lookup)}")
    return lookup


def _inverse_algorithm(algorithm: str) -> str:
    result = []
    for move in reversed(algorithm.split()):
        if move.endswith("2"):
            result.append(move)
        elif move.endswith("'"):
            result.append(move[:-1])
        else:
            result.append(move + "'")
    return " ".join(result)


class OLLSolver(Solver):
    """CFOP OLL solver using the complete 57-case one-look algorithm table."""

    method = "cfop-oll"

    def __init__(
        self,
        *,
        max_depth: int = 15,
        max_nodes: int | None = 2_000_000,
        timeout_seconds: float | None = 15.0,
        f2l_slots: tuple[tuple[int, int], ...] = _F2L_SLOTS,
        f2l_pieces: tuple[tuple[int, int], ...] = _F2L_SLOTS,
        cross_pieces: tuple[int, ...] = _CROSS_EDGES,
        cross_positions: tuple[int, ...] = _CROSS_EDGES,
    ) -> None:
        self.max_depth = max_depth
        self.max_nodes = max_nodes
        self.timeout_seconds = timeout_seconds
        self.f2l_slots = f2l_slots
        self.f2l_pieces = f2l_pieces
        self.cross_pieces = cross_pieces
        self.cross_positions = cross_positions

    def solve(self, cube: CubeState) -> Solution:
        if not f2l_solved(
            cube,
            slots=self.f2l_slots,
            pieces=self.f2l_pieces,
            cross_pieces=self.cross_pieces,
            cross_positions=self.cross_positions,
        ):
            raise RuntimeError("OLL requires solved CFOP F2L")
        if f2l_solved(
            cube,
            slots=self.f2l_slots,
            pieces=self.f2l_pieces,
            cross_pieces=self.cross_pieces,
            cross_positions=self.cross_positions,
        ) and all(x == 0 for x in cube.co) and all(x == 0 for x in cube.eo):
            return Solution(
                method=self.method,
                moves=(),
                metric="HTM",
                verified=True,
                phases=(SolutionPhase(name="OLL", moves=(), description="Last layer is already oriented."),),
                metadata={"algorithm": "CFOP OLL", "search": "57-case OLL algorithm database", "case": 0, "depth": 0},
            )

        global _OLL_CASE_LOOKUP
        if _OLL_CASE_LOOKUP is None:
            _OLL_CASE_LOOKUP = _build_oll_case_lookup()

        case_number, algorithm = _OLL_CASE_LOOKUP[_oll_orientation_key(cube)]
        after = _apply_oll_algorithm(cube, algorithm)
        moves = tuple(algorithm.split())

        if not (
            f2l_solved(
                after,
                slots=self.f2l_slots,
                pieces=self.f2l_pieces,
                cross_pieces=self.cross_pieces,
                cross_positions=self.cross_positions,
            )
            and all(x == 0 for x in after.co)
            and all(x == 0 for x in after.eo)
        ):
            raise RuntimeError(f"OLL case {case_number} algorithm failed verification")

        phase = SolutionPhase(
            name="OLL",
            moves=moves,
            description="One-look OLL: recognize the complete last-layer orientation case and execute one algorithm.",
        )
        return Solution(
            method=self.method,
            moves=moves,
            metric="HTM",
            verified=True,
            phases=(phase,),
            metadata={
                "algorithm": "CFOP OLL",
                "search": "57-case OLL algorithm database",
                "case": case_number,
                "depth": len(moves),
            },
        )


# ---------------------------------------------------------------------------
# PLL
# ---------------------------------------------------------------------------

_PLL_ALGORITHMS: tuple[tuple[str, str], ...] = (
    ("Ua", "M2 U' M U2 M' U' M2"),
    ("Ub", "M2 U M U2 M' U M2"),
    ("H", "M2 U M2 U2 M2 U M2"),
    ("Z", "M' U M2 U M2 U M' U2 M2"),
    ("Aa", "x' R2 D2 R' U' R D2 R' U R' x"),
    ("Ab", "x' R U' R D2 R' U R D2 R2 x"),
    ("E", "x' R U' R' D R U R' D' R U R' D R U' R' D' x"),
    ("T", "R U R' U' R' F R2 U' R' U' R U R' F'"),
    ("F", "R' U' F' R U R' U' R' F R2 U' R' U' R U R' U R"),
    ("Ja", "x R2 F R F' R U2 r' U r U2 x'"),
    ("Jb", "R U R' F' R U R' U' R' F R2 U' R'"),
    ("Ra", "R U' R' U' R U R D R' U' R D' R' U2 R'"),
    ("Rb", "R' U2 R U2 R' F R U R' U' R' F' R2"),
    ("Y", "F R U' R' U' R U R' F' R U R' U' R' F R F'"),
    ("V", "R' U R' U' R D' R' D R' U D' R2 U' R2 D R2"),
    ("Na", "R U R' U R U R' F' R U R' U' R' F R2 U' R' U2 R U' R'"),
    ("Nb", "R' U L' U2 R U' L R' U L' U2 R U' L"),
    ("Ga", "R2 U R' U R' U' R U' R2 D U' R' U R D'"),
    ("Gb", "R' U' R U D' R2 U R' U R U' R U' R2 D"),
    ("Gc", "R2 U' R U' R U R' U R2 U D' R U' R' D"),
    ("Gd", "R U R' U' D R2 U' R U' R' U R' U R2 D'"),
)

_PLL_CASE_LOOKUP: dict[tuple[tuple[int, ...], tuple[int, ...]], tuple[str, str]] | None = None


def pll_solved(
    cube: CubeState,
    *,
    f2l_slots: tuple[tuple[int, int], ...] = _F2L_SLOTS,
    f2l_pieces: tuple[tuple[int, int], ...] = _F2L_SLOTS,
    cross_pieces: tuple[int, ...] = _CROSS_EDGES,
    cross_positions: tuple[int, ...] = _CROSS_EDGES,
    solved_cp: tuple[int, ...] = tuple(range(8)),
    solved_ep: tuple[int, ...] = tuple(range(12)),
) -> bool:
    return (
        f2l_solved(
            cube,
            slots=f2l_slots,
            pieces=f2l_pieces,
            cross_pieces=cross_pieces,
            cross_positions=cross_positions,
        )
        and all(x == 0 for x in cube.co)
        and all(x == 0 for x in cube.eo)
        and cube.cp == solved_cp
        and cube.ep == solved_ep
    )


def _pll_key(
    cube: CubeState,
    corner_map: dict[int, int] | None = None,
    edge_map: dict[int, int] | None = None,
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    if corner_map is None:
        return cube.cp[:4], cube.ep[:4]
    return (
        tuple(corner_map[piece] for piece in cube.cp[:4]),
        tuple(edge_map[piece] for piece in cube.ep[:4]),
    )


_X2_CONJUGATION = {
    "U": "D", "D": "U", "R": "R", "L": "L", "F": "B", "B": "F",
    "M": "M", "E": "E'", "S": "S'", "x": "x", "y": "y'", "z": "z'",
    "r": "r", "l": "l", "u": "d", "d": "u", "f": "b", "b": "f",
}


def _conjugate_x2_move(move: str) -> str:
    suffix = ""
    if move.endswith("2"):
        suffix, base = "2", move[:-1]
    elif move.endswith("'"):
        suffix, base = "'", move[:-1]
    else:
        base = move
    mapped = _X2_CONJUGATION[base]
    if mapped.endswith("'"):
        if suffix == "'":
            return mapped[:-1]
        if suffix == "2":
            return mapped[:-1] + "2"
        return mapped
    return mapped + suffix


def _build_pll_case_lookup(
    solved: CubeState | None = None,
    key_transform=None,
) -> dict[tuple[tuple[int, ...], tuple[int, ...]], tuple[str, str]]:
    lookup: dict[tuple[tuple[int, ...], tuple[int, ...]], tuple[str, str]] = {}
    solved = CubeState.solved() if solved is None else solved
    key_transform = _pll_key if key_transform is None else key_transform
    for name, algorithm in _PLL_ALGORITHMS:
        # A standard PLL case can be viewed from any of the four sides of
        # the cube.  Generate those y-rotated orientations as well as all
        # four AUF prefixes.  This still represents the same 21 PLL cases;
        # it only makes recognition independent of which side is facing F.
        for y_rotation in range(4):
            y_prefix = " ".join("y" for _ in range(y_rotation))
            y_suffix = " ".join("y'" for _ in range(y_rotation))
            oriented_algorithm = " ".join(
                part for part in (y_prefix, algorithm, y_suffix) if part
            )
            case = _apply_oll_algorithm(solved, _inverse_algorithm(oriented_algorithm))
            preserves_f2l = (
                case.cp[4:] == solved.cp[4:]
                and case.ep[4:] == solved.ep[4:]
                and all(x == 0 for x in case.co)
                and all(x == 0 for x in case.eo)
            )
            if not preserves_f2l:
                raise RuntimeError(f"PLL case {name} does not preserve OLL/F2L")

            current = case
            auf_prefixes = ("", "U'", "U2", "U")
            for rotation in range(4):
                key = key_transform(current)
                candidate = (
                    auf_prefixes[rotation]
                    + (" " if auf_prefixes[rotation] else "")
                    + oriented_algorithm
                ).strip()
                # Different y/AUF representations can describe the same
                # legal permutation. Keep the first valid representation;
                # this is a recognition alias, not a new PLL case.
                lookup.setdefault(key, (name, candidate))
                current = apply_move(current, "U")

    # There are 288 legal permutations of four U-layer corners and four
    # U-layer edges with matching permutation parity. Four are solved states
    # differing only by AUF, which PLLSolver handles before this lookup.
    if len(lookup) < 280:
        raise RuntimeError(f"PLL lookup is incomplete: generated {len(lookup)} legal keys")
    return lookup


class PLLSolver(Solver):
    """CFOP PLL solver using the complete 21-case algorithm database."""

    method = "cfop-pll"

    def __init__(
        self,
        *,
        f2l_slots: tuple[tuple[int, int], ...] = _F2L_SLOTS,
        f2l_pieces: tuple[tuple[int, int], ...] = _F2L_SLOTS,
        cross_pieces: tuple[int, ...] = _CROSS_EDGES,
        cross_positions: tuple[int, ...] = _CROSS_EDGES,
        solved_cp: tuple[int, ...] = tuple(range(8)),
        solved_ep: tuple[int, ...] = tuple(range(12)),
        corner_map: dict[int, int] | None = None,
        edge_map: dict[int, int] | None = None,
    ) -> None:
        self.f2l_slots = f2l_slots
        self.f2l_pieces = f2l_pieces
        self.cross_pieces = cross_pieces
        self.cross_positions = cross_positions
        self.solved_cp = solved_cp
        self.solved_ep = solved_ep
        self.corner_map = corner_map
        self.edge_map = edge_map

    def solve(self, cube: CubeState) -> Solution:
        if not f2l_solved(
            cube,
            slots=self.f2l_slots,
            pieces=self.f2l_pieces,
            cross_pieces=self.cross_pieces,
            cross_positions=self.cross_positions,
        ) or not all(x == 0 for x in cube.co) or not all(x == 0 for x in cube.eo):
            raise RuntimeError("PLL requires solved CFOP OLL")
        if pll_solved(
            cube,
            f2l_slots=self.f2l_slots,
            f2l_pieces=self.f2l_pieces,
            cross_pieces=self.cross_pieces,
            cross_positions=self.cross_positions,
            solved_cp=self.solved_cp,
            solved_ep=self.solved_ep,
        ):
            return Solution(
                method=self.method,
                moves=(),
                metric="HTM",
                verified=True,
                phases=(SolutionPhase(name="PLL", moves=(), description="Last layer is already permuted."),),
                metadata={"algorithm": "CFOP PLL", "search": "21-case PLL algorithm database", "case": "Solved", "depth": 0},
            )

        # F2L/OLL may legitimately leave the last layer solved up to AUF.
        # This is not a PLL case; it only needs the final U alignment.
        auf_moves = ("", "U", "U2", "U'")
        aligned = cube
        for auf in auf_moves:
            if aligned.cp == self.solved_cp and aligned.ep == self.solved_ep:
                moves = tuple(auf.split()) if auf else ()
                return Solution(
                    method=self.method,
                    moves=moves,
                    metric="HTM",
                    verified=True,
                    phases=(SolutionPhase(name="PLL", moves=moves, description="Last layer is solved; apply final AUF."),),
                    metadata={"algorithm": "CFOP PLL", "search": "AUF", "case": "Solved", "depth": len(moves)},
                )
            aligned = apply_move(aligned, "U")

        global _PLL_CASE_LOOKUP
        if _PLL_CASE_LOOKUP is None:
            _PLL_CASE_LOOKUP = _build_pll_case_lookup()

        key = _pll_key(cube, self.corner_map, self.edge_map)
        case_name, algorithm = _PLL_CASE_LOOKUP[key]
        if self.corner_map is not None:
            algorithm = " ".join(_conjugate_x2_move(move) for move in algorithm.split())
        after = _apply_oll_algorithm(cube, algorithm)
        moves = tuple(algorithm.split())
        if not pll_solved(after):
            raise RuntimeError(f"PLL case {case_name} algorithm failed verification")

        phase = SolutionPhase(
            name="PLL",
            moves=moves,
            description="One-look PLL: recognize the complete last-layer permutation case and execute one algorithm.",
        )
        return Solution(
            method=self.method,
            moves=moves,
            metric="HTM",
            verified=True,
            phases=(phase,),
            metadata={
                "algorithm": "CFOP PLL",
                "search": "21-case PLL algorithm database",
                "case": case_name,
                "depth": len(moves),
            },
        )


class CFOPSolver(Solver):
    """Complete CFOP solver with a pre-Cross white-D orientation."""

    method = "cfop"

    def __init__(
        self,
        *,
        cross_max_depth: int = 10,
        cross_max_nodes: int | None = 2_000_000,
        cross_timeout_seconds: float | None = 15.0,
        f2l_max_depth: int = 14,
        f2l_max_nodes: int | None = 10_000_000,
        f2l_timeout_seconds: float | None = 60.0,
        oll_max_depth: int = 15,
        oll_max_nodes: int | None = 2_000_000,
        oll_timeout_seconds: float | None = 15.0,
    ) -> None:
        # Cross is solved on the canonical D layer after the pre-Cross x2
        # orientation. This keeps the established F2L/OLL/PLL coordinate frame.
        self.cross_solver = CrossSolver(
            max_depth=cross_max_depth,
            max_nodes=cross_max_nodes,
            timeout_seconds=cross_timeout_seconds,
        )
        self.f2l_solver = F2LSolver(max_depth=f2l_max_depth, max_nodes=f2l_max_nodes, timeout_seconds=f2l_timeout_seconds)
        self.oll_solver = OLLSolver(max_depth=oll_max_depth, max_nodes=oll_max_nodes, timeout_seconds=oll_timeout_seconds)
        self.pll_solver = PLLSolver()

    def solve(self, cube: CubeState) -> Solution:
        # x2 puts white on D. A y rotation before x2 is equivalent to the
        # inverse y rotation after x2, so solve Cross once in the canonical
        # x2 frame and evaluate all four front-face choices by conjugating the
        # same Cross. This keeps the actual search on D while allowing the
        # returned execution to favor finger-trick-friendly faces.
        state = _to_x2_coordinate_frame(cube)
        cross_result = self.cross_solver.solve(state)
        orientation_candidates: list[tuple[tuple[int, int, int, int], str, tuple[str, ...]]] = []
        for y_count, y_cost in ((0, 0), (1, 1), (2, 2), (3, 1)):
            y_after_x2 = " ".join(("y'",) * y_count)
            y_conjugation = " ".join(("y",) * y_count)
            cross_moves = _conjugate_moves(y_conjugation, cross_result.moves) if y_conjugation else cross_result.moves
            awkward = sum(move[0] in {"B", "L", "D"} for move in cross_moves)
            doubles = sum(move.endswith("2") for move in cross_moves)
            score = (len(cross_moves), awkward, doubles, y_cost)
            orientation_candidates.append((score, y_after_x2, cross_moves))

        _, y_after_x2, cross_moves = min(orientation_candidates, key=lambda item: item[0])
        y_conjugation = " ".join("y" for _ in y_after_x2.split())
        orientation = " ".join(part for part in ("x2", y_after_x2) if part)
        phases: list[SolutionPhase] = []
        orientation_moves = tuple(orientation.split())
        total_moves: list[str] = list(orientation_moves)
        phase_results: list[Solution] = []

        state = apply_moves(state, cross_result.moves)
        phases.append(
            SolutionPhase(
                name="Orientation",
                moves=orientation_moves,
                description="Orient the cube before Cross: x2 places white on D; y rotation chooses the most convenient Cross view.",
            )
        )
        phases.extend(
            SolutionPhase(
                name=phase.name,
                moves=cross_moves,
                description=phase.description,
            )
            for phase in cross_result.phases
        )
        total_moves.extend(cross_moves)
        phase_results.append(cross_result)

        for solver in (self.f2l_solver, self.oll_solver, self.pll_solver):
            result = solver.solve(state)
            # OLL/PLL algorithms may contain wide/slice/rotation notation
            # (for example `r`, `M`, or `x`) which the core face-move model
            # intentionally does not expose. Use the vendored engine as the
            # move executor whenever a phase contains extended notation.
            if any(len(move) > 2 or move[0] not in "URFDLB" for move in result.moves):
                state = _apply_oll_algorithm(state, " ".join(result.moves))
            else:
                state = apply_moves(state, result.moves)
            phases.extend(
                SolutionPhase(
                    name=phase.name,
                    moves=_conjugate_moves(y_conjugation, phase.moves) if y_conjugation else phase.moves,
                    description=phase.description,
                )
                for phase in result.phases
            )
            total_moves.extend(_conjugate_moves(y_conjugation, result.moves) if y_conjugation else result.moves)
            phase_results.append(result)

        if not pll_solved(state):
            raise RuntimeError("CFOP returned an invalid full-cube solution")

        final_state = _apply_oll_algorithm(cube, " ".join(total_moves))
        expected_orientation = _apply_oll_algorithm(CubeState.solved(), orientation)
        if final_state != expected_orientation:
            raise RuntimeError("CFOP returned an invalid standard-orientation solution")

        return Solution(
            method=self.method,
            moves=tuple(total_moves),
            metric="HTM",
            verified=True,
            phases=tuple(phases),
            metadata={
                "algorithm": "CFOP",
                "phases": [phase.name for phase in phases],
                "orientation": orientation,
                "cross": phase_results[0].metadata,
                "f2l": phase_results[1].metadata,
                "oll": phase_results[2].metadata,
                "pll": phase_results[3].metadata,
            },
        )
