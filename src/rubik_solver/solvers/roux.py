from __future__ import annotations

from dataclasses import dataclass, field
from collections import deque
import json
from itertools import permutations
from pathlib import Path
from time import monotonic

from rubik_solver.cube.moves import MOVES, apply_move, apply_moves, inverse_move
from rubik_solver.cube.state import CubeState
from rubik_solver.model.solution import Solution, SolutionPhase
from rubik_solver.solvers.base import Solver
from rubik_solver.solvers.cfop import _f2l_pair_heuristic
from rubik_solver.solvers.kociemba import KociembaSolver
from rubik_solver.solvers.kociemba_engine import Cube as EngineCube
from rubik_solver.solvers.kociemba_engine import init_solver as init_kociemba_engine


_ALL_MOVES = tuple(MOVES)
# Roux can exploit wide/slice turns without preserving a CFOP cross. These
# are real one-move HTM choices, not setup rotations. Keep x/y/z out of this
# set: rotations remain setup-prefix-only by contract.
_ROUX_EXTRA_MOVES = ("r", "r2", "r'", "M", "M2", "M'")
# Wide-U is useful for Roux line/square construction. Keep ordinary U moves
# too, and treat all of these as normal construction moves (not rotations).
_ROUX_WIDE_MOVES = ("u", "u2", "u'")
_ROUX_MOVES = _ALL_MOVES + _ROUX_EXTRA_MOVES + _ROUX_WIDE_MOVES
# FB construction is center-aware. CubeState now carries the full center
# permutation, so Roux may use r/M/u during FB exactly like a human would.
# Candidate validation requires the final centers to match the active FB frame.
_FB_MOVES = _ROUX_MOVES
_SB_MOVES = (
    "U", "U2", "U'",
    "R", "R2", "R'",
    "M", "M2", "M'",
    "r", "r2", "r'",
)
_SB_EXCEPTIONAL_MOVES = (
    "F", "F2", "F'",
    "B", "B2", "B'",
    "L", "L2", "L'",
    "D", "D2", "D'",
)
_SB_FINAL_MOVES = frozenset({"R", "R2", "R'", "r", "r2", "r'"})
_SB_MOVE_PENALTY = {
    **{move: 0 for move in _SB_MOVES},
    **{move: 2 for move in ("F", "F2", "F'")},
    **{move: 4 for move in ("L", "L2", "L'")},
    **{move: 6 for move in ("B", "B2", "B'", "D", "D2", "D'")},
}

# A Roux FB is a 1x2x3 block on the LEFT. Its bottom must be made from the
# white stickers. The active setup frame is represented explicitly, including
# its center permutation, and FB construction must finish with those centers.
_FB_CORNER_GOALS = (5, 6)  # DLF, DBL
_FB_EDGE_GOALS = (6, 9, 10)  # DL, FL, BL
_SB_CORNER_GOALS = (4, 7)  # DFR, DBR
_SB_EDGE_GOALS = (4, 8, 11)  # DR, FR, BR
_CMLL_CORNER_GOALS = (0, 1, 2, 3)  # URF, UFL, ULB, UBR
_CMLL_DB_PATH = Path(__file__).resolve().parents[3] / "data" / "cmll_algorithms.json"
_LSE_DB_PATH = Path(__file__).resolve().parents[3] / "data" / "lse_algorithms.json"
_L4E_EDGE_GOALS = (1, 3, 5, 7)  # UF, UB, DF, DB
_ULUR_EDGE_GOALS = (0, 2)  # UR, UL


def _fb_frame(frame: int) -> tuple[str, ...]:
    frame %= 4
    y = ((), ("y",), ("y2",), ("y'",))[frame]
    return ("x2",) + y


def _fb_cubies_goal(cube: CubeState, reference: CubeState) -> bool:
    return all(
        cube.cp[pos] == reference.cp[pos] and cube.co[pos] == reference.co[pos]
        for pos in _FB_CORNER_GOALS
    ) and all(
        cube.ep[pos] == reference.ep[pos] and cube.eo[pos] == reference.eo[pos]
        for pos in _FB_EDGE_GOALS
    )


def _fb_goal(cube: CubeState, reference: CubeState) -> bool:
    return cube.center == reference.center and _fb_cubies_goal(cube, reference)


def _fb_centers_match_frame(moves: tuple[str, ...], frame: tuple[str, ...]) -> bool:
    """Return whether the physical FB sequence ends in the active frame."""
    actual = apply_moves(CubeState.solved(), moves)
    expected = apply_moves(CubeState.solved(), frame)
    return actual.center == expected.center


def first_block_solved(cube: CubeState, frame_index: int | None = None) -> bool:
    """Return whether the Roux FB is solved in the requested frame.

    With ``frame_index`` omitted this remains a convenient generic predicate
    for callers that do not track the active setup frame. Solver verification
    should always pass the exact frame selected for the current solve.
    """
    if cube.is_solved():
        return True
    solved = CubeState.solved()
    if frame_index is not None:
        reference = apply_moves(solved, _fb_frame(frame_index))
        return _fb_goal(cube, reference)
    for frame_index in range(4):
        frame = _fb_frame(frame_index)
        reference = apply_moves(solved, frame)
        if _fb_goal(cube, reference):
            return True
    return False


def second_block_solved(cube: CubeState) -> bool:
    """Return whether the canonical right Roux 1x2x3 block is solved.

    This check intentionally also requires one of the four possible white-
    bottom FB frames, because SB is only meaningful as an extension of the
    already-solved left block.
    """
    solved = CubeState.solved()
    for frame_index in range(4):
        reference = apply_moves(solved, _fb_frame(frame_index))
        if _fb_cubies_goal(cube, reference) and _centers_ready_for_eo_state(cube) and all(
            cube.cp[pos] == reference.cp[pos] and cube.co[pos] == reference.co[pos]
            for pos in _SB_CORNER_GOALS
        ) and all(
            cube.ep[pos] == reference.ep[pos] and cube.eo[pos] == reference.eo[pos]
            for pos in _SB_EDGE_GOALS
        ) and _u_corners_on_u_layer(cube, reference):
            return True
    return False


def _u_corners_on_u_layer(cube: CubeState, target: CubeState) -> bool:
    """Return whether all four U-layer corner pieces remain on U.

    Roux SB may permute/orient the four U-layer corners, but it must not leave
    one of them in the D layer. CMLL is defined on exactly this remaining
    four-corner set, so this is part of the SB goal even though it is not a
    fixed-position requirement.
    """
    u_pieces = {target.cp[pos] for pos in _CMLL_CORNER_GOALS}
    return all(cube.cp[pos] in u_pieces for pos in _CMLL_CORNER_GOALS)


def _cmll_corner_signature(cube: CubeState, target: CubeState) -> tuple[int, ...]:
    """Encode the four U-layer target cubies in the active Roux frame."""
    parts: list[int] = []
    for target_pos in _CMLL_CORNER_GOALS:
        piece = target.cp[target_pos]
        pos = cube.cp.index(piece)
        parts.extend((pos, cube.co[pos]))
    return tuple(parts)


def _cmll_u_turn(power: int) -> tuple[str, ...]:
    return ((), ("U",), ("U2",), ("U'",))[power % 4]


def _cmll_inverse(moves: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(inverse_move(move) for move in reversed(moves))


class _CMLLDatabase:
    """Local 42-case CMLL algorithm database.

    Recognition is generated from the algorithms themselves: each algorithm's
    inverse creates its canonical case, then all four U rotations are treated
    as AUF-equivalent. This avoids hard-coding colour-dependent sticker
    patterns and keeps recognition tied directly to the algorithm set.
    """

    def __init__(self, target: CubeState) -> None:
        with _CMLL_DB_PATH.open("r", encoding="utf-8") as handle:
            entries = json.load(handle)
        if len(entries) != 42:
            raise RuntimeError(f"CMLL database must contain exactly 42 cases, got {len(entries)}")
        self.target = target
        self.entries = tuple(entries)
        self._case_map: dict[tuple[int, ...], tuple[dict, tuple[int, ...]]] = {}
        for entry in self.entries:
            alg = tuple(entry["algorithm"].split())
            case = apply_moves(target, _cmll_inverse(alg))
            case_signature = _cmll_corner_signature(case, target)
            key = min(
                _cmll_corner_signature(apply_moves(case, _cmll_u_turn(power)), target)
                for power in range(4)
            )
            previous = self._case_map.get(key)
            if previous is not None and previous[0]["id"] != entry["id"]:
                raise RuntimeError(f"CMLL case collision: {previous[0]['id']} vs {entry['id']}")
            self._case_map[key] = (entry, case_signature)

    def recognize(self, cube: CubeState) -> tuple[dict, tuple[str, ...]]:
        for power in range(4):
            auf = _cmll_u_turn(power)
            rotated = apply_moves(cube, auf)
            if _cmll_solved(rotated, self.target):
                return {"id": "SOLVED", "family": "SOLVED", "name": "Already solved", "algorithm": ""}, auf
            canonical = min(
                _cmll_corner_signature(apply_moves(rotated, _cmll_u_turn(inner)), self.target)
                for inner in range(4)
            )
            record = self._case_map.get(canonical)
            if record is not None:
                entry, case_signature = record
                for extra in range(4):
                    if _cmll_corner_signature(apply_moves(rotated, _cmll_u_turn(extra)), self.target) == case_signature:
                        return entry, _cmll_u_turn(power + extra)
        raise RuntimeError("CMLL recognition failed: state is not one of the 42 CMLL corner cases")

    def solve(self, cube: CubeState) -> tuple[str, ...]:
        if _cmll_solved(cube, self.target):
            return ()
        try:
            entry, auf = self.recognize(cube)
            return auf + tuple(entry["algorithm"].split())
        except RuntimeError:
            return _cmll_two_look(cube, self.target)


def _sb_move_penalty(moves: tuple[str, ...]) -> int:
    return sum(_SB_MOVE_PENALTY[move] for move in moves)


def _sb_final_move_ok(moves: tuple[str, ...]) -> bool:
    return bool(moves) and moves[-1] in _SB_FINAL_MOVES


class CornerOrientationAnalyzer:
    """Analyze U-layer corner orientation and CMLL difficulty for final FR."""

    def __init__(self, target: CubeState, database: _CMLLDatabase | None = None) -> None:
        self.target = target
        self.database = database or _CMLLDatabase(target)

    def analyze(self, cube: CubeState) -> dict[str, object]:
        orientation = tuple(
            cube.co[cube.cp.index(self.target.cp[pos])]
            for pos in _CMLL_CORNER_GOALS
        )
        misoriented = sum(value != 0 for value in orientation)
        try:
            entry, auf = self.database.recognize(cube)
            cmll_moves = self.database.solve(cube)
            case_id = entry["id"]
            family = entry["family"]
            available = True
            error = None
        except RuntimeError:
            try:
                cmll_moves = _cmll_two_look(cube, self.target)
                case_id = "TWO_LOOK"
                family = "MU-compatible fallback"
                auf = ()
                available = True
                error = None
            except RuntimeError as exc:
                # This analyzer is advisory metadata. A recognition/search
                # failure must never abort the SB phase itself.
                case_id = "UNAVAILABLE"
                family = "CMLL analysis unavailable"
                cmll_moves = ()
                auf = ()
                available = False
                error = str(exc)

        return {
            "orientation": orientation,
            "misoriented_corners": misoriented,
            "case_id": case_id,
            "family": family,
            "cmll_algorithm_length": len(cmll_moves),
            "auf_length": len(auf),
            "available": available,
            "error": error,
            "score": (misoriented, len(cmll_moves), len(auf)) if available else (99, 99, 99),
        }


def _cmll_recognized(database: _CMLLDatabase, cube: CubeState) -> bool:
    try:
        database.recognize(cube)
    except RuntimeError:
        return False
    return True


def _cmll_solved(cube: CubeState, target: CubeState) -> bool:
    return all(
        cube.cp[pos] == target.cp[pos] and cube.co[pos] == target.co[pos]
        for pos in _CMLL_CORNER_GOALS
    )


def _roux_blocks_and_cmll_solved(cube: CubeState, target: CubeState) -> bool:
    """Return whether FB/SB and the CMLL corner set remain solved modulo AUF."""
    cmll_pieces = {target.cp[pos] for pos in _CMLL_CORNER_GOALS}
    cmll_preserved = all(
        cube.cp[pos] in cmll_pieces
        and cube.co[pos] == target.co[target.cp.index(cube.cp[pos])]
        for pos in _CMLL_CORNER_GOALS
    )
    return (
        _fb_cubies_goal(cube, target)
        and all(
            cube.cp[pos] == target.cp[pos] and cube.co[pos] == target.co[pos]
            for pos in _SB_CORNER_GOALS
        )
        and all(
            cube.ep[pos] == target.ep[pos] and cube.eo[pos] == target.eo[pos]
            for pos in _SB_EDGE_GOALS
        )
        and cmll_preserved
    )


_CMLL_2LOOK_ORIENT_ALGS = (
    ("R", "U", "R'", "U", "R", "U2", "R'"),  # Sune
    ("R", "U2", "R'", "U'", "R", "U'", "R'"),  # Anti-Sune
    ("U", "R", "U", "R'", "U", "R", "U'", "R'", "U", "R", "U2", "R'"),  # H
    ("R", "U", "R'", "U'", "R'", "F", "R", "F'"),  # T
    ("F", "R'", "F'", "R", "U", "R", "U'", "R'"),  # L
    ("F", "R", "U", "R'", "U'", "F'"),  # U
    ("F", "R", "U", "R'", "U'", "R", "U", "R'", "U'", "F'"),  # Pi
)
_CMLL_2LOOK_PERM_ALGS = (
    ("R", "U", "R'", "F'", "R", "U", "R'", "U'", "R'", "F", "R2", "U'", "R'"),  # J
    ("F", "R", "U'", "R'", "U'", "R", "U", "R'", "F'", "R", "U", "R'", "U'", "R'", "F", "R", "F'"),  # Y
)


def _corner_projection(cube: CubeState) -> tuple[int, ...]:
    return tuple(cube.cp) + tuple(cube.co)


def _cmll_two_look(cube: CubeState, target: CubeState) -> tuple[str, ...]:
    """Complete CMLL when the compact 42-case recognizer has no exact case.

    Full CMLL has 42 named algorithms but 162 AUF-equivalent corner states.
    The fallback uses the standard Roux two-look CMLL subsets (7 orientation
    algorithms + J/Y permutation) and searches only their corner projection.
    These algorithms preserve the two solved blocks by construction.
    """
    movesets = _CMLL_2LOOK_ORIENT_ALGS + _CMLL_2LOOK_PERM_ALGS + (("U",), ("U2",), ("U'",))

    def apply_macro(state: CubeState, macro: tuple[str, ...]) -> CubeState:
        return apply_moves(state, macro)

    def goal_orientation(state: CubeState) -> bool:
        return all(state.co[pos] == target.co[pos] for pos in _CMLL_CORNER_GOALS)

    def goal(state: CubeState) -> bool:
        return _cmll_solved(state, target)

    def search(start: CubeState, predicate) -> tuple[str, ...]:
        queue = deque([(start, ())])
        seen = {_corner_projection(start)}
        while queue:
            state, path = queue.popleft()
            if predicate(state):
                return path
            for macro in movesets:
                nxt = apply_macro(state, macro)
                key = _corner_projection(nxt)
                if key in seen:
                    continue
                seen.add(key)
                queue.append((nxt, path + macro))
        raise RuntimeError("Roux two-look CMLL search failed")

    orient_moves = search(cube, goal_orientation)
    oriented = apply_moves(cube, orient_moves)
    perm_moves = search(oriented, goal)
    return orient_moves + perm_moves


def _lse_key(cube: CubeState, target: CubeState) -> tuple[int, ...]:
    parts: list[int] = list(cube.center)
    for pos in (0, 1, 2, 3, 5, 7):
        piece = target.ep[pos]
        current = cube.ep.index(piece)
        parts.extend((current, cube.eo[current]))
    for pos in _CMLL_CORNER_GOALS:
        piece = target.cp[pos]
        current = cube.cp.index(piece)
        parts.extend((current, cube.co[current]))
    return tuple(parts)


def _solve_eo_intuitive(cube: CubeState, target: CubeState) -> tuple[str, ...]:
    """Exact MU-only EO search on the six Roux last-layer edges."""
    moves = (("M",), ("M2",), ("M'",), ("U",), ("U2",), ("U'",))

    def goal(state: CubeState) -> bool:
        return state.center == target.center and _eo_solved(state, target) and all(
            state.cp[pos] == target.cp[pos] and state.co[pos] == target.co[pos]
            for pos in range(8)
        )

    queue = deque([(cube, ())])
    seen = {_lse_key(cube, target)}
    while queue:
        state, path = queue.popleft()
        if goal(state):
            return path
        for macro in moves:
            nxt = apply_moves(state, macro)
            key = _lse_key(nxt, target)
            if key in seen:
                continue
            seen.add(key)
            queue.append((nxt, path + macro))
    raise RuntimeError("Roux EO MU-only search failed")


def _solve_lse_subphase(
    cube: CubeState,
    target: CubeState,
    goal,
) -> tuple[str, ...]:
    """Exact MU-only BFS over the six free edges and U-layer corners."""
    moves = (("M",), ("M2",), ("M'",), ("U",), ("U2",), ("U'",))
    queue = deque([(cube, ())])
    seen = {_lse_key(cube, target)}
    while queue:
        state, path = queue.popleft()
        if goal(state):
            return path
        for macro in moves:
            nxt = apply_moves(state, macro)
            key = _lse_key(nxt, target)
            if key in seen:
                continue
            seen.add(key)
            queue.append((nxt, path + macro))
    raise RuntimeError("Roux LSE MU-only search failed")


@dataclass(slots=True)
class _ULURIDAStar:
    """Exact IDA* for UL/UR using only M/M2/M' and U/U2/U'."""

    target: CubeState
    max_depth: int = 18
    max_nodes: int | None = 10_000_000
    timeout_seconds: float | None = 60.0
    l4e_database: object | None = None
    nodes: int = field(init=False, default=0)
    started: float = field(init=False, default=0.0)
    path: list[str] = field(init=False, default_factory=list)
    pattern_db: dict[tuple[int, ...], int] = field(init=False, default_factory=dict)
    pattern_db_alt: dict[tuple[int, ...], int] = field(init=False, default_factory=dict)
    _alt_target: CubeState = field(init=False)
    handoff_db: dict[tuple[int, ...], int] = field(init=False, default_factory=dict)
    transposition: dict[tuple[tuple[int, ...], str | None], int] = field(init=False, default_factory=dict)

    def __post_init__(self) -> None:
        self.started = monotonic()
        self.pattern_db = self._build_pattern_db()
        alt_ep = list(self.target.ep)
        alt_eo = list(self.target.eo)
        alt_ep[0], alt_ep[1], alt_ep[2], alt_ep[7] = self.target.ep[1], self.target.ep[0], self.target.ep[7], self.target.ep[2]
        alt_eo[0], alt_eo[1], alt_eo[2], alt_eo[7] = self.target.eo[1], self.target.eo[0], self.target.eo[7], self.target.eo[2]
        self._alt_target = CubeState(
            cp=self.target.cp,
            co=self.target.co,
            ep=tuple(alt_ep),
            eo=tuple(alt_eo),
            center=self.target.center,
        )
        self.pattern_db_alt = self._build_pattern_db(self._alt_target)
        self.handoff_db = self._build_handoff_db()

    def _pattern_key(self, cube: CubeState, target: CubeState | None = None) -> tuple[int, ...]:
        target = self.target if target is None else target
        parts: list[int] = []
        for pos in _CMLL_CORNER_GOALS:
            piece = target.cp[pos]
            current = cube.cp.index(piece)
            parts.extend((current, cube.co[current]))
        for pos in (2, 0):
            piece = target.ep[pos]
            current = cube.ep.index(piece)
            parts.extend((current, cube.eo[current]))
        return tuple(parts)

    def _build_pattern_db(self, target: CubeState | None = None) -> dict[tuple[int, ...], int]:
        target = self.target if target is None else target
        distances = {self._pattern_key(target, target): 0}
        queue = deque([(target, 0)])
        while queue:
            state, depth = queue.popleft()
            for move in _ULUR_MOVES:
                nxt = apply_move(state, move)
                key = self._pattern_key(nxt, target)
                if key in distances:
                    continue
                distances[key] = depth + 1
                queue.append((nxt, depth + 1))
        return distances

    def _handoff_key(self, cube: CubeState) -> tuple[int, ...]:
        parts: list[int] = list(cube.center)
        for pos in _CMLL_CORNER_GOALS:
            piece = self.target.cp[pos]
            current = cube.cp.index(piece)
            parts.extend((current, cube.co[current]))
        # ULUR leaves every non-M edge fixed. L4E owns only UF/UB/DF/DB.
        for pos in (0, 2, 4, 6, 8, 9, 10, 11):
            piece = self.target.ep[pos]
            current = cube.ep.index(piece)
            parts.extend((current, cube.eo[current]))
        return tuple(parts)

    def _build_handoff_db(self) -> dict[tuple[int, ...], int]:
        """Exact distance to the Roux ULUR handoff projection."""
        goals: list[CubeState] = []
        middle_positions = (1, 3, 5, 7)
        middle_pieces = tuple(self.target.ep[pos] for pos in middle_positions)
        for perm in permutations(middle_pieces):
            ep = list(self.target.ep)
            eo = list(self.target.eo)
            for pos, piece in zip(middle_positions, perm):
                ep[pos] = piece
                eo[pos] = self.target.eo[self.target.ep.index(piece)]
            goals.append(
                CubeState(
                    cp=self.target.cp,
                    co=self.target.co,
                    ep=tuple(ep),
                    eo=tuple(eo),
                    center=self.target.center,
                )
            )

        distances: dict[tuple[int, ...], int] = {}
        queue = deque()
        for goal in goals:
            key = self._handoff_key(goal)
            if key not in distances:
                distances[key] = 0
                queue.append((goal, 0))
        while queue:
            state, depth = queue.popleft()
            for move in _ULUR_MOVES:
                nxt = apply_move(state, move)
                key = self._handoff_key(nxt)
                if key in distances:
                    continue
                distances[key] = depth + 1
                queue.append((nxt, depth + 1))
        return distances

    def _check_limits(self) -> None:
        if self.max_nodes is not None and self.nodes >= self.max_nodes:
            raise RuntimeError("Roux ULUR IDA* node limit exceeded")
        if self.timeout_seconds is not None and monotonic() - self.started >= self.timeout_seconds:
            raise TimeoutError("Roux ULUR IDA* timeout exceeded")

    def _heuristic(self, cube: CubeState) -> int:
        return self.handoff_db[self._handoff_key(cube)]

    def solve(self, cube: CubeState) -> tuple[str, ...]:
        if self._goal(cube):
            return ()
        for threshold in range(self._heuristic(cube), self.max_depth + 1):
            self.transposition.clear()
            result = self._dfs(cube, 0, threshold, None)
            if result is not None:
                return result
        raise RuntimeError(f"Roux ULUR IDA* failed within depth {self.max_depth}")

    def _goal(self, cube: CubeState) -> bool:
        return cube.center == self.target.center and _ulur_solved(cube, self.target)

    def _dfs(self, cube: CubeState, depth: int, threshold: int, previous_face: str | None):
        self._check_limits()
        self.nodes += 1
        if depth + self._heuristic(cube) > threshold:
            return None
        if self._goal(cube):
            return tuple(self.path)
        if depth == threshold:
            return None
        remaining = threshold - depth
        tt_key = (self._handoff_key(cube), previous_face)
        previous_remaining = self.transposition.get(tt_key)
        if previous_remaining is not None and previous_remaining >= remaining:
            return None
        self.transposition[tt_key] = remaining
        for move in _ULUR_MOVES:
            face = move[0]
            if previous_face is not None and face == previous_face:
                continue
            self.path.append(move)
            result = self._dfs(apply_move(cube, move), depth + 1, threshold, face)
            self.path.pop()
            if result is not None:
                return result
        return None


def _centers_ready_for_eo_state(cube: CubeState) -> bool:
    """Return whether the U/D center positions contain the white/yellow pair."""
    return {cube.center[0], cube.center[3]} == {0, 3}


def _edges_solved(cube: CubeState, target: CubeState, positions: tuple[int, ...]) -> bool:
    return all(cube.ep[pos] == target.ep[pos] and cube.eo[pos] == target.eo[pos] for pos in positions)


def _eo_solved(cube: CubeState, target: CubeState) -> bool:
    return all(cube.eo[pos] == target.eo[pos] for pos in range(12))


_ULUR_MOVES = ("M", "M2", "M'", "U", "U2", "U'")
_ULUR_GOAL_EDGES = (0, 2)  # UR/UL: both edges are solved before L4E.


def _ulur_solved(cube: CubeState, target: CubeState) -> bool:
    """ULUR boundary: U corners + UL/UR solved; only M-slice edges remain."""
    if not all(
        cube.cp[pos] == target.cp[pos] and cube.co[pos] == target.co[pos]
        for pos in _CMLL_CORNER_GOALS
    ):
        return False
    fixed_edges = all(
        cube.ep[pos] == target.ep[pos] and cube.eo[pos] == target.eo[pos]
        for pos in (0, 2, 4, 6, 8, 9, 10, 11)
    )
    return fixed_edges and _eo_solved(cube, target)


def _l4e_solved(cube: CubeState, target: CubeState) -> bool:
    return _edges_solved(cube, target, tuple(range(12))) and all(cube.cp[pos] == target.cp[pos] and cube.co[pos] == target.co[pos] for pos in range(8))



def _lse_u_turn(power: int) -> tuple[str, ...]:
    return ((), ("U",), ("U2",), ("U'",))[power % 4]


class _LSEFormulaDatabase:
    """Recognition/execution for the published Roux LSE formula sets."""

    def __init__(self) -> None:
        with _LSE_DB_PATH.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        self.eo = tuple(data["eo"])
        self.ulur = tuple(data["ulur"])
        self.l4e = tuple(data["l4e"])
        self.l4e_vn = tuple(entry for entry in self.l4e if entry["family"].startswith("roux_method_vn"))

    @staticmethod
    def _moves(entry: dict) -> tuple[str, ...]:
        return tuple(entry["algorithm"].split())

    def _try_phase(self, cube, target, entries, goal, auf_powers=(0, 1, 2, 3)):
        for power in auf_powers:
            auf = _lse_u_turn(power)
            rotated = apply_moves(cube, auf)
            for entry in entries:
                moves = self._moves(entry)
                if goal(apply_moves(rotated, moves), target):
                    return entry, auf + moves
        return None

    def solve_eo(self, cube: CubeState, target: CubeState):
        centered_goal = lambda state, goal_target: state.center == goal_target.center and _eo_solved(state, goal_target)
        if centered_goal(cube, target):
            return {"id": "SOLVED", "family": "SOLVED", "algorithm": ""}, ()
        result = self._try_phase(cube, target, self.eo, centered_goal)
        if result is None:
            return {"id": "INTUITIVE_MU", "family": "MU-only", "algorithm": ""}, _solve_eo_intuitive(cube, target)
        return result

    def solve_ulur_formula(self, cube: CubeState, target: CubeState):
        centered_goal = lambda state, goal_target: state.center == goal_target.center and _ulur_solved(state, goal_target)
        if centered_goal(cube, target):
            return {"id": "SOLVED", "family": "SOLVED", "algorithm": ""}, ()
        return self._try_phase(cube, target, self.ulur, centered_goal)

    def solve_l4e(self, cube: CubeState, target: CubeState):
        centered_goal = lambda state, goal_target: state.center == goal_target.center and _l4e_solved(state, goal_target)
        if centered_goal(cube, target):
            return {"id": "SOLVED", "family": "SOLVED", "algorithm": ""}, ()
        # The Roux Method VN L4E page is a finite recognition table.  Its
        # 8 + 8 + special cases collapse to the 12 distinct edge permutations
        # represented by CubeState (centers/sticker colours are not modeled).
        # Recognize those cases directly with AUF, then execute the published
        # formula.  Do not turn this into a generic MU search: that would hide
        # recognition errors and violate the formula-driven L4E contract.
        result = self._try_phase(cube, target, self.l4e_vn, centered_goal)
        if result is not None:
            return result

        # Ez L4E uses the documented steering macros to turn awkward cases
        # into one of the easy published cases. Keep this as a second-stage
        # recognizer, not an arbitrary search: every terminal solve still has
        # to be one of the Roux Method VN formula entries above.
        steering = (
            ("U", "M2", "U"),
            ("U", "M2", "U'"),
            ("U'", "M2", "U"),
            ("U'", "M2", "U'"),
            ("U2", "M2", "U2"),
            ("U2", "M2", "U2", "M2"),
            ("M", "U2", "M"),
            ("M'", "U2", "M"),
            ("M", "U2", "M'"),
            ("M'", "U2", "M'"),
            ("E2", "M", "E2", "M"),
            ("E2", "M'", "E2", "M'"),
        )
        for setup in steering:
            rotated = apply_moves(cube, setup)
            result = self._try_phase(rotated, target, self.l4e_vn, centered_goal)
            if result is not None:
                entry, moves = result
                return entry, setup + moves
        return None


def _solve_ulur_intuitive(cube: CubeState, target: CubeState) -> tuple[str, ...]:
    """Use the documented Roux <M,U2> ULUR procedure when no simple alg matches."""
    if _ulur_solved(cube, target):
        return ()
    moves = ("U", "U2", "U'", "M", "M'", "M2")
    target_edges = tuple(target.ep[pos] for pos in (0, 2, 4, 5, 6, 7, 8, 9, 10, 11))

    def key(state: CubeState) -> tuple:
        parts = []
        for piece in target_edges:
            pos = state.ep.index(piece)
            parts.extend((pos, state.eo[pos]))
        for piece in tuple(target.cp[pos] for pos in _CMLL_CORNER_GOALS):
            pos = state.cp.index(piece)
            parts.extend((pos, state.co[pos]))
        return tuple(parts)

    queue = deque([(cube, ())])
    seen = {key(cube)}
    while queue:
        state, path = queue.popleft()
        if _ulur_solved(state, target):
            return path
        if len(path) >= 18:
            continue
        previous = path[-1][0] if path else None
        for move in moves:
            if previous is not None and move[0] == previous:
                continue
            nxt = apply_move(state, move)
            state_key = key(nxt)
            if state_key in seen:
                continue
            seen.add(state_key)
            queue.append((nxt, path + (move,)))
    raise RuntimeError("Roux ULUR intuitive M/U2 procedure failed")


@dataclass(slots=True)
class _SBOpportunityDetector:
    """Recognize already-useful SB material before starting DR-first.

    This is intentionally recognition, not a global optimizer. The detector
    looks for exact human-friendly structures in the fixed post-FB state so
    the planner can exploit a free pair/square instead of destroying it to
    satisfy a generic DR-first script.
    """

    target: CubeState

    def detect(self, cube: CubeState) -> dict[str, object]:
        free_squares: list[str] = []
        if _pair_goal(cube, self.target, 4, 4) and _edge_goal(cube, self.target, 8):
            free_squares.append("FR")
        if _pair_goal(cube, self.target, 7, 4) and _edge_goal(cube, self.target, 11):
            free_squares.append("BR")

        free_pairs: list[str] = []
        if _pair_goal(cube, self.target, 4, 8):
            free_pairs.append("FR")
        if _pair_goal(cube, self.target, 7, 11):
            free_pairs.append("BR")
        if _pair_goal(cube, self.target, 4, 4):
            free_pairs.append("DR")

        if free_squares:
            return {
                "strategy": "FREE_SQUARE",
                "squares": tuple(free_squares),
                "pairs": tuple(free_pairs),
            }
        if free_pairs:
            return {
                "strategy": "FREE_PAIR",
                "squares": (),
                "pairs": tuple(free_pairs),
            }
        return {"strategy": "DR_FIRST", "squares": (), "pairs": ()}


@dataclass(slots=True)
class _SecondBlockSearch:
    target: CubeState
    max_depth: int = 14
    max_nodes: int | None = 2_000_000
    timeout_seconds: float | None = 10.0
    nodes: int = field(init=False, default=0)
    started: float = field(init=False, default=0.0)
    path: list[str] = field(init=False, default_factory=list)

    def __post_init__(self) -> None:
        self.started = monotonic()

    def _check_limits(self) -> None:
        if self.max_nodes is not None and self.nodes >= self.max_nodes:
            raise RuntimeError("Roux Second Block search node limit exceeded")
        if self.timeout_seconds is not None and monotonic() - self.started >= self.timeout_seconds:
            raise TimeoutError("Roux Second Block search timeout exceeded")

    def _goal(self, cube: CubeState) -> bool:
        return _fb_cubies_goal(cube, self.target) and _centers_ready_for_eo_state(cube) and all(
            cube.cp[pos] == self.target.cp[pos] and cube.co[pos] == self.target.co[pos]
            for pos in _SB_CORNER_GOALS
        ) and all(
            cube.ep[pos] == self.target.ep[pos] and cube.eo[pos] == self.target.eo[pos]
            for pos in _SB_EDGE_GOALS
        ) and _u_corners_on_u_layer(cube, self.target)

    def _projection_key(self, cube: CubeState) -> tuple:
        """Project the state onto the six SB cubies.

        SB is a partial-state goal: only DFR/DBR and DR/FR/BR matter, plus
        the center frame is validated separately by the SB goal. A
        bidirectional search keyed by the complete CubeState is therefore
        incorrect because the other cubies may differ from the target. Encode
        only the relevant target cubies and orientations here; center state is
        checked at the phase boundary rather than multiplying the projection.
        """
        corner_parts = []
        corner_pieces = tuple(self.target.cp[pos] for pos in _SB_CORNER_GOALS)
        for piece in corner_pieces:
            pos = cube.cp.index(piece)
            corner_parts.extend((pos, cube.co[pos]))
        # The four U-layer corners are not fixed by SB, but their positions
        # are part of the partial state because SB must preserve them on U so
        # that the resulting state is a valid CMLL starting position. Their
        # orientations are intentionally omitted: SB does not constrain them,
        # and CMLL owns their orientation after the phase boundary.
        for piece in (self.target.cp[pos] for pos in _CMLL_CORNER_GOALS):
            pos = cube.cp.index(piece)
            corner_parts.append(pos)
        # Slice/wide SB moves can permute all six centers, and the next
        # center transition depends on their current side-center arrangement.
        # Keep the full center permutation in the projection so the state key
        # remains Markovian; the cubie projection itself is intentionally
        # limited to SB/CMLL pieces.
        edge_parts = list(cube.center)
        edge_pieces = tuple(self.target.ep[pos] for pos in _SB_EDGE_GOALS)
        for piece in edge_pieces:
            pos = cube.ep.index(piece)
            edge_parts.extend((pos, cube.eo[pos]))
        return tuple(corner_parts + edge_parts)

    def _heuristic(self, cube: CubeState) -> int:
        return max(
            _f2l_pair_heuristic(cube, self.target.cp[4], self.target.ep[8], 4, 8, self.target.co[4], self.target.eo[8]),
            _f2l_pair_heuristic(cube, self.target.cp[7], self.target.ep[11], 7, 11, self.target.co[7], self.target.eo[11]),
            _f2l_pair_heuristic(cube, self.target.cp[4], self.target.ep[4], 4, 4, self.target.co[4], self.target.eo[4]),
        )

    def solve(self, cube: CubeState) -> tuple[str, ...]:
        if self._goal(cube):
            return ()
        # SB is a small subgroup when FB is fixed. Bidirectional breadth-first
        # search gives an exact shortest HTM result without the enormous
        # one-sided IDA* branching seen at depths 10-12.
        # Keep the target-side table slightly shallower because center-aware
        # keys are substantially larger than the legacy cubie-only projection.
        # The start side gets the extra depth so 14-move solutions remain
        # reachable without exhausting the shared node budget while building
        # the goal frontier.
        half = max(1, self.max_depth // 2 - 1)
        inverse = {
            "U": "U'", "U'": "U", "U2": "U2",
            "R": "R'", "R'": "R", "R2": "R2",
            "M": "M'", "M'": "M", "M2": "M2",
            "r": "r'", "r'": "r", "r2": "r2",
        }

        def key(state: CubeState) -> tuple:
            return self._projection_key(state)

        # Store the shortest target->state path. The reverse of this path is
        # the state->target continuation once the two frontiers meet.
        goal_map: dict[tuple, tuple[str, ...]] = {key(self.target): ()}
        goal_queue = deque([(self.target, None, 0)])
        while goal_queue:
            state, previous_face, depth = goal_queue.popleft()
            if depth >= half:
                continue
            for move in _SB_MOVES:
                face = move[0]
                if previous_face is not None and face == previous_face:
                    continue
                nxt = apply_move(state, move)
                k = key(nxt)
                if k in goal_map:
                    continue
                goal_map[k] = (inverse[move],) + goal_map[key(state)]
                goal_queue.append((nxt, face, depth + 1))
                self.nodes += 1
                self._check_limits()

        frontier = {key(cube): (cube, ())}
        for depth in range(self.max_depth - half + 1):
            next_frontier: dict[tuple, tuple[CubeState, tuple[str, ...]]] = {}
            for k, (state, path) in frontier.items():
                if k in goal_map:
                    return path + goal_map[k]
                if depth >= self.max_depth - half:
                    continue
                previous_face = path[-1][0] if path else None
                for move in _SB_MOVES:
                    face = move[0]
                    if previous_face is not None and face == previous_face:
                        continue
                    nxt = apply_move(state, move)
                    nk = key(nxt)
                    if nk in next_frontier:
                        continue
                    next_frontier[nk] = (nxt, path + (move,))
                    self.nodes += 1
                    self._check_limits()
            frontier = next_frontier

        raise RuntimeError(f"Roux Second Block search failed within depth {self.max_depth}")


@dataclass(slots=True)
class _StagedSBSearch:
    """Recognition-first SB planner: DR pair -> square -> remaining pair."""

    target: CubeState
    # Human-style SB is bounded by the same configurable depth/node/time
    # budget as the direct SB oracle. Individual stages use that depth as their
    # recognition/search ceiling rather than expanding indefinitely.
    max_depth: int | None = 14
    max_nodes: int | None = 2_000_000
    timeout_seconds: float | None = 10.0
    nodes: int = field(init=False, default=0)
    started: float = field(init=False, default=0.0)
    path: list[str] = field(init=False, default_factory=list)
    strategy: str = field(init=False, default="DR_FIRST")
    opportunity: dict[str, object] = field(init=False, default_factory=dict)
    dr_candidate_limit: int = 3
    use_corner_orientation_analyzer: bool = True
    dr_candidates_found: int = field(init=False, default=0)
    selected_pair_order: str | None = field(init=False, default=None)
    planner_score: tuple | None = field(init=False, default=None)
    pair_order_evaluations: list[dict[str, object]] = field(init=False, default_factory=list)
    corner_orientation_analyzer: CornerOrientationAnalyzer = field(init=False)
    corner_orientation_analysis: dict[str, object] | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        self.started = monotonic()
        self.corner_orientation_analyzer = CornerOrientationAnalyzer(self.target)

    def _check_limits(self) -> None:
        if self.max_nodes is not None and self.nodes >= self.max_nodes:
            raise RuntimeError("Roux staged SB search node limit exceeded")
        if self.timeout_seconds is not None and monotonic() - self.started >= self.timeout_seconds:
            raise TimeoutError("Roux staged SB search timeout exceeded")

    def _goal(self, cube: CubeState) -> bool:
        return _fb_cubies_goal(cube, self.target) and _centers_ready_for_eo_state(cube) and all(
            cube.cp[pos] == self.target.cp[pos] and cube.co[pos] == self.target.co[pos]
            for pos in _SB_CORNER_GOALS
        ) and all(
            cube.ep[pos] == self.target.ep[pos] and cube.eo[pos] == self.target.eo[pos]
            for pos in _SB_EDGE_GOALS
        ) and _u_corners_on_u_layer(cube, self.target)

    def _heuristic(self, cube: CubeState, goals: tuple[tuple[int, int], ...]) -> int:
        return max(
            _f2l_pair_heuristic(
                cube,
                self.target.cp[corner],
                self.target.ep[edge],
                corner,
                edge,
                self.target.co[corner],
                self.target.eo[edge],
            )
            for corner, edge in goals
        )

    def _solve_stage(
        self,
        cube: CubeState,
        goals: tuple[tuple[int, int], ...],
        *,
        include_edges: tuple[int, ...] = (),
        preserve_goals: tuple[tuple[int, int], ...] = (),
        max_stage_depth: int | None,
    ) -> tuple[str, ...]:
        def goal(state: CubeState) -> bool:
            if not all(
                state.cp[corner] == self.target.cp[corner]
                and state.co[corner] == self.target.co[corner]
                and state.ep[edge] == self.target.ep[edge]
                and state.eo[edge] == self.target.eo[edge]
                for corner, edge in goals
            ):
                return False
            if not all(
                state.cp[corner] == self.target.cp[corner]
                and state.co[corner] == self.target.co[corner]
                and state.ep[edge] == self.target.ep[edge]
                and state.eo[edge] == self.target.eo[edge]
                for corner, edge in preserve_goals
            ):
                return False
            return all(
                state.ep[edge] == self.target.ep[edge]
                and state.eo[edge] == self.target.eo[edge]
                for edge in include_edges
            )

        if goal(cube):
            return ()
        threshold = self._heuristic(cube, goals)
        while max_stage_depth is None or threshold <= max_stage_depth:
            result = self._dfs(cube, 0, threshold, None, goal, goals)
            if result is not None:
                return result
            threshold += 1
        raise RuntimeError("Roux staged SB stage failed")

    def _solve_stage_candidates(
        self,
        cube: CubeState,
        goals: tuple[tuple[int, int], ...],
        *,
        max_stage_depth: int | None,
        limit: int,
    ) -> list[tuple[str, ...]]:
        """Return a small set of shortest stage candidates.

        This is intentionally bounded. Phase 1 of the human-style SB planner
        must explore alternatives without turning into an unrestricted search.
        Candidates are collected from the first depth thresholds that produce
        solutions, then capped by ``limit``.
        """
        if limit <= 0:
            return []
        heuristic = self._heuristic(cube, goals)
        results: list[tuple[str, ...]] = []
        seen: set[tuple[str, ...]] = set()

        def goal(state: CubeState) -> bool:
            return all(
                state.cp[corner] == self.target.cp[corner]
                and state.co[corner] == self.target.co[corner]
                and state.ep[edge] == self.target.ep[edge]
                and state.eo[edge] == self.target.eo[edge]
                for corner, edge in goals
            )

        def collect(state, depth, threshold, previous_face) -> None:
            if len(results) >= limit:
                return
            self.nodes += 1
            self._check_limits()
            if depth + self._heuristic(state, goals) > threshold:
                return
            if goal(state):
                candidate = tuple(self.path)
                if candidate not in seen:
                    seen.add(candidate)
                    results.append(candidate)
                return
            if depth == threshold:
                return
            for move in _SB_MOVES:
                face = move[0]
                if previous_face is not None and face == previous_face:
                    continue
                self.path.append(move)
                collect(apply_move(state, move), depth + 1, threshold, face)
                self.path.pop()
                if len(results) >= limit:
                    return

        threshold = heuristic
        while max_stage_depth is None or threshold <= max_stage_depth:
            collect(cube, 0, threshold, None)
            if len(results) >= limit:
                break
            threshold += 1
        return results

    def _pair_order_options(
        self,
        dr_state: CubeState,
        dr_moves: tuple[str, ...],
        dr_goal: tuple[int, int],
        *,
        remaining_depth: int | None,
    ) -> list[dict[str, object]]:
        """Phase 2: evaluate both natural pair orders after a fixed DR.

        The first pair is actually solved for the lookahead. The resulting
        state is then scored for the remaining pair. This avoids the classic
        mistake of choosing the shortest DR while ignoring what it leaves
        behind.
        """
        orders = (
            ("FR_FIRST", (4, 8), (7, 11)),
            ("BR_FIRST", (7, 11), (4, 8)),
        )
        evaluated: list[dict[str, object]] = []
        for name, first_pair, final_pair in orders:
            try:
                first_moves = self._solve_stage(
                    dr_state,
                    (first_pair,),
                    include_edges=(first_pair[1],),
                    preserve_goals=(dr_goal,),
                    max_stage_depth=remaining_depth,
                )
            except (RuntimeError, TimeoutError):
                continue
            after_first = apply_moves(dr_state, first_moves)
            final_heuristic = self._heuristic(after_first, (final_pair,))
            opportunity = _SBOpportunityDetector(self.target).detect(after_first)
            opportunity_bonus = 0
            if opportunity["strategy"] == "FREE_SQUARE":
                opportunity_bonus = -2
            elif opportunity["strategy"] == "FREE_PAIR":
                opportunity_bonus = -1
            score = (
                len(dr_moves) + len(first_moves) + final_heuristic + opportunity_bonus,
                final_heuristic,
                len(first_moves),
                len(dr_moves),
            )
            evaluated.append({
                "order": name,
                "first_pair": first_pair,
                "final_pair": final_pair,
                "first_moves": first_moves,
                "after_first": after_first,
                "final_heuristic": final_heuristic,
                "opportunity": opportunity,
                "score": score,
            })
        return evaluated

    def _dfs(self, cube, depth, threshold, previous_face, goal, goals):
        self.nodes += 1
        self._check_limits()
        if depth + self._heuristic(cube, goals) > threshold:
            return None
        if goal(cube):
            return tuple(self.path)
        if depth == threshold:
            return None

        # Roux SB subgroup: U/R/r/M. Prefer quarter turns before double turns
        # for recognition speed; all moves remain equal-cost HTM turns.
        for move in _SB_MOVES:
            face = move[0]
            if previous_face is not None and face == previous_face:
                continue
            self.path.append(move)
            result = self._dfs(apply_move(cube, move), depth + 1, threshold, face, goal, goals)
            self.path.pop()
            if result is not None:
                return result
        return None

    def _solve_final_fr_candidates(
        self,
        cube: CubeState,
        goals: tuple[tuple[int, int], ...],
        *,
        preserve_goals: tuple[tuple[int, int], ...],
        max_depth: int | None,
        limit: int = 6,
    ) -> list[tuple[str, ...]]:
        """Generate bounded final-FR candidates, including penalized exceptions."""
        if limit <= 0:
            return []
        moves = _SB_MOVES + _SB_EXCEPTIONAL_MOVES
        heuristic = self._heuristic(cube, goals)
        results: list[tuple[str, ...]] = []
        seen: set[tuple[str, ...]] = set()

        def goal(state: CubeState) -> bool:
            if not _fb_cubies_goal(state, self.target) or not _centers_ready_for_eo_state(state):
                return False
            if not all(
                state.cp[corner] == self.target.cp[corner]
                and state.co[corner] == self.target.co[corner]
                and state.ep[edge] == self.target.ep[edge]
                and state.eo[edge] == self.target.eo[edge]
                for corner, edge in goals
            ):
                return False
            if not all(
                state.cp[corner] == self.target.cp[corner]
                and state.co[corner] == self.target.co[corner]
                and state.ep[edge] == self.target.ep[edge]
                and state.eo[edge] == self.target.eo[edge]
                for corner, edge in preserve_goals
            ):
                return False
            return all(
                state.ep[edge] == self.target.ep[edge]
                and state.eo[edge] == self.target.eo[edge]
                for edge in (4, 8, 11)
            )

        def collect(state: CubeState, depth: int, threshold: int, previous_face: str | None) -> None:
            if len(results) >= limit:
                return
            self.nodes += 1
            self._check_limits()
            if depth + self._heuristic(state, goals) > threshold:
                return
            if goal(state):
                candidate = tuple(self.path)
                if candidate and candidate[-1] in _SB_FINAL_MOVES and candidate not in seen:
                    seen.add(candidate)
                    results.append(candidate)
                return
            if depth == threshold:
                return
            for move in moves:
                face = move[0]
                if previous_face is not None and face == previous_face:
                    continue
                self.path.append(move)
                collect(apply_move(state, move), depth + 1, threshold, face)
                self.path.pop()
                if len(results) >= limit:
                    return

        threshold = heuristic
        while max_depth is None or threshold <= max_depth:
            collect(cube, 0, threshold, None)
            if len(results) >= limit:
                break
            threshold += 1
        results.sort(key=lambda path: (_sb_move_penalty(path), len(path), path))
        return results

    def solve(self, cube: CubeState) -> tuple[str, ...]:
        # This planner is called with a fixed FB frame. Do not use the
        # frame-agnostic second_block_solved() predicate here: accepting a
        # different y-frame can produce a deceptively short candidate that
        # the fixed-target exact search cannot reproduce.
        if (
            _centers_ready_for_eo_state(cube)
            and all(
                cube.cp[pos] == self.target.cp[pos] and cube.co[pos] == self.target.co[pos]
                for pos in _SB_CORNER_GOALS
            )
            and all(
                cube.ep[pos] == self.target.ep[pos] and cube.eo[pos] == self.target.eo[pos]
                for pos in _SB_EDGE_GOALS
            )
        ):
            self.strategy = "ALREADY_SOLVED"
            self.opportunity = {"strategy": self.strategy, "squares": (), "pairs": ()}
            return ()

        detector = _SBOpportunityDetector(self.target)
        self.opportunity = detector.detect(cube)
        opportunity_result = self._solve_opportunity(cube)
        if opportunity_result is not None:
            return opportunity_result

        self.strategy = "DR_FIRST"

        # Phase 1: generate at most three DR candidates across both natural
        # constructions. We deliberately keep this small so alternatives are
        # considered without turning SB into a broad global search.
        dr_specs = ((4, 4), (7, 4))
        dr_candidates: list[tuple[tuple, tuple[int, int], tuple[str, ...], CubeState]] = []
        per_spec_limit = self.dr_candidate_limit
        for dr in dr_specs:
            try:
                paths = self._solve_stage_candidates(
                    cube,
                    (dr,),
                    max_stage_depth=self.max_depth,
                    limit=per_spec_limit,
                )
            except (RuntimeError, TimeoutError):
                paths = []
            for dr_moves in paths:
                dr_state = apply_moves(cube, dr_moves)
                # Phase-1 ranking is intentionally cheap: evaluate both pair
                # sides without committing to either order yet.
                readiness = min(
                    self._heuristic(dr_state, ((4, 8),)),
                    self._heuristic(dr_state, ((7, 11),)),
                )
                score = (readiness, len(dr_moves), dr_moves)
                dr_candidates.append((score, dr, dr_moves, dr_state))

        dr_candidates.sort(key=lambda item: item[0])
        unique: list[tuple[tuple, tuple[int, int], tuple[str, ...], CubeState]] = []
        seen_dr: set[tuple[str, ...]] = set()
        for item in dr_candidates:
            if item[2] in seen_dr:
                continue
            seen_dr.add(item[2])
            unique.append(item)
            if len(unique) >= self.dr_candidate_limit:
                break
        self.dr_candidates_found = len(unique)

        # Phase 2: for each of the <=3 DR candidates, look ahead through both
        # FR-first and BR-first orders. Phase 3 then chooses the best complete
        # human-style plan and solves only its final pair.
        plans: list[dict[str, object]] = []
        for _, dr, dr_moves, dr_state in unique:
            for option in self._pair_order_options(dr_state, dr_moves, dr, remaining_depth=self.max_depth):
                plans.append({
                    **option,
                    "dr": dr,
                    "dr_moves": dr_moves,
                    "dr_state": dr_state,
                })

        plans.sort(key=lambda item: item["score"])
        completed_plans: list[tuple[tuple, tuple[str, ...], dict[str, object], dict[str, object]]] = []
        for plan in plans:
            dr_moves = plan["dr_moves"]
            first_moves = plan["first_moves"]
            final_pair = plan["final_pair"]
            state = plan["after_first"]
            remaining = self.max_depth
            try:
                if plan["order"] == "FR_FIRST":
                    final_candidates = self._solve_final_fr_candidates(
                        state,
                        (final_pair,),
                        preserve_goals=(plan["first_pair"],),
                        max_depth=remaining,
                    )
                else:
                    final_candidates = [
                        self._solve_stage(
                            state,
                            (final_pair,),
                            include_edges=(4, 8, 11),
                            preserve_goals=(plan["first_pair"],),
                            max_stage_depth=remaining,
                        )
                    ]
            except (RuntimeError, TimeoutError):
                continue

            ranked: list[tuple[tuple, tuple[str, ...], dict[str, object] | None]] = []
            for final_moves in final_candidates:
                candidate = tuple(dr_moves + first_moves + final_moves)
                eo_setup = None
                if plan["order"] == "FR_FIRST":
                    candidate, eo_setup = _optimize_sb_final_move_for_eo(cube, self.target, candidate)
                candidate_state = apply_moves(cube, candidate)
                if not self._goal(candidate_state):
                    continue
                if plan["order"] == "FR_FIRST" and (
                    not _sb_final_move_ok(candidate) or not _centers_ready_for_eo(candidate)
                ):
                    continue
                analysis = (
                    self.corner_orientation_analyzer.analyze(candidate_state)
                    if plan["order"] == "FR_FIRST" and self.use_corner_orientation_analyzer
                    else None
                )
                score = (
                    _sb_move_penalty(candidate),
                    analysis["score"] if analysis else (99, 99, 99),
                    len(candidate),
                    plan["score"],
                    candidate,
                )
                ranked.append((score, candidate, {"eo_setup": eo_setup, "analysis": analysis}))

            if ranked:
                ranked.sort(key=lambda item: item[0])
                final_score, final_candidate, final_metadata = ranked[0]
                # Do not stop at the first successful pair order. FR_FIRST and
                # BR_FIRST are peers: the better human-style choice is the one
                # whose first pair leaves the other pair easier to solve. The
                # actual completion is now known, so use it as the final
                # tie-break instead of trusting a fixed FR->BR order.
                human_score = (
                    plan["score"],
                    final_score[0],
                    final_score[1],
                    len(final_candidate),
                    final_candidate,
                )
                completed_plans.append((human_score, final_candidate, plan, final_metadata))

                self.pair_order_evaluations.append({
                    "order": plan["order"],
                    "dr_moves": len(dr_moves),
                    "first_pair_moves": len(first_moves),
                    "remaining_pair_heuristic": plan["final_heuristic"],
                    "final_moves": len(final_candidate),
                    "score": human_score,
                })

        if not completed_plans:
            raise RuntimeError("Roux staged Second Block search failed")
        _, best, best_plan, best_metadata = min(completed_plans, key=lambda item: item[0])
        self.selected_pair_order = best_plan["order"]
        self.planner_score = best_plan["score"]
        self.corner_orientation_analysis = best_metadata["analysis"]
        self.opportunity = {
            **self.opportunity,
            "dr_candidates": self.dr_candidates_found,
            "selected_pair_order": self.selected_pair_order,
            "planner_score": self.planner_score,
            "lookahead_opportunity": best_plan["opportunity"],
            "pair_order_evaluations": tuple(self.pair_order_evaluations),
            "eo_setup": best_metadata["eo_setup"],
            "move_penalty": _sb_move_penalty(best),
            "final_move": best[-1],
            "corner_orientation_analyzer": self.corner_orientation_analysis,
        }
        return best

    def _solve_opportunity(self, cube: CubeState) -> tuple[str, ...] | None:
        """Exploit an exact free square/pair without abandoning human flow."""
        strategy = self.opportunity.get("strategy")
        if strategy == "FREE_SQUARE":
            for side in self.opportunity.get("squares", ()):
                if side == "FR":
                    square = (4, 4)
                    adjacent_edge = 8
                    final_pair = (7, 11)
                else:
                    square = (7, 4)
                    adjacent_edge = 11
                    final_pair = (4, 8)
                try:
                    remaining = self._solve_stage(
                        cube,
                        (final_pair,),
                        include_edges=(4, 8, 11),
                        preserve_goals=(square,),
                        max_stage_depth=self.max_depth,
                    )
                except (RuntimeError, TimeoutError):
                    continue
                candidate = tuple(remaining)
                solved = apply_moves(cube, candidate)
                if self._goal(solved):
                    self.strategy = "FREE_SQUARE"
                    self.opportunity = {
                        **self.opportunity,
                        "selected_square": side,
                        "adjacent_edge": adjacent_edge,
                    }
                    return candidate

        if strategy == "FREE_PAIR":
            pairs = self.opportunity.get("pairs", ())
            for side in pairs:
                if side == "FR":
                    free_pair = (4, 8)
                    dr_pair = (4, 4)
                    final_pair = (7, 11)
                    include_dr_edge = 4
                elif side == "BR":
                    free_pair = (7, 11)
                    dr_pair = (7, 4)
                    final_pair = (4, 8)
                    include_dr_edge = 4
                else:
                    continue
                try:
                    dr_moves = self._solve_stage(
                        cube,
                        (dr_pair,),
                        include_edges=(include_dr_edge,),
                        preserve_goals=(free_pair,),
                        max_stage_depth=self.max_depth,
                    )
                    after_dr = apply_moves(cube, dr_moves)
                    final_moves = self._solve_stage(
                        after_dr,
                        (final_pair,),
                        include_edges=(4, 8, 11),
                        preserve_goals=(dr_pair, free_pair),
                        max_stage_depth=self.max_depth,
                    )
                except (RuntimeError, TimeoutError):
                    continue
                candidate = tuple(dr_moves + final_moves)
                solved = apply_moves(cube, candidate)
                if self._goal(solved):
                    self.strategy = "FREE_PAIR"
                    self.opportunity = {**self.opportunity, "selected_pair": side}
                    return candidate
        return None


def _center_state_after_moves(moves: tuple[str, ...]) -> tuple[int, ...]:
    init_kociemba_engine()
    cube = EngineCube()
    cube.move(" ".join(moves))
    return tuple(cube.center)


def _centers_ready_for_eo(moves: tuple[str, ...]) -> bool:
    centers = _center_state_after_moves(moves)
    return {centers[0], centers[3]} == {0, 3}


def _optimize_sb_final_move_for_eo(
    cube: CubeState,
    target: CubeState,
    moves: tuple[str, ...],
) -> tuple[tuple[str, ...], dict[str, object]]:
    current_state = apply_moves(cube, moves) if moves else cube
    metadata: dict[str, object] = {
        "applied": False,
        "original_move": moves[-1] if moves else None,
        "replacement_move": None,
        "centers_ready_for_eo": _centers_ready_for_eo_state(current_state) if moves else _centers_ready_for_eo_state(cube),
    }
    if not moves or metadata["centers_ready_for_eo"]:
        return moves, metadata
    replacement = {"R": "r", "R'": "r'"}.get(moves[-1])
    if replacement is None:
        return moves, metadata
    candidate = moves[:-1] + (replacement,)
    candidate_state = apply_moves(cube, candidate)
    if not (
        all(
            candidate_state.cp[pos] == target.cp[pos] and candidate_state.co[pos] == target.co[pos]
            for pos in _SB_CORNER_GOALS
        )
        and all(
            candidate_state.ep[pos] == target.ep[pos] and candidate_state.eo[pos] == target.eo[pos]
            for pos in _SB_EDGE_GOALS
        )
        and _u_corners_on_u_layer(candidate_state, target)
    ):
        return moves, metadata
    if not _centers_ready_for_eo_state(candidate_state):
        return moves, metadata
    metadata.update({"applied": True, "replacement_move": replacement})
    return candidate, metadata


_FRAME_CONJUGATION_CACHE: dict[tuple[str, ...], dict[str, str]] = {}


def _frame_conjugation_map(frame: tuple[str, ...]) -> dict[str, str]:
    """Map face turns through an active x/y frame without emitting rotations."""
    cached = _FRAME_CONJUGATION_CACHE.get(frame)
    if cached is not None:
        return cached
    solved = CubeState.solved()
    inverse_frame = tuple(inverse_move(move) for move in reversed(frame))
    candidates = tuple(MOVES)
    mapping: dict[str, str] = {}
    for move in candidates:
        conjugated = apply_moves(solved, inverse_frame + (move,) + frame)
        matches = [candidate for candidate in candidates if apply_move(solved, candidate) == conjugated]
        if len(matches) != 1:
            raise RuntimeError(f"Unable to conjugate Kociemba move {move!r} through frame {frame!r}")
        mapping[move] = matches[0]
    _FRAME_CONJUGATION_CACHE[frame] = mapping
    return mapping


def _kociemba_frame_fallback(
    cube: CubeState,
    target: CubeState,
    frame: tuple[str, ...],
) -> tuple[str, ...]:
    """Solve the remaining cube as a last-resort oracle in the active frame."""
    inverse_frame = tuple(inverse_move(move) for move in reversed(frame))
    canonical = apply_moves(cube, inverse_frame)
    result = KociembaSolver().solve(canonical)
    if any(move[0] in "xyz" for move in result.moves):
        raise RuntimeError("Kociemba fallback returned an unexpected whole-cube rotation")
    mapping = _frame_conjugation_map(frame)
    moves = tuple(mapping[move] for move in result.moves)
    if apply_moves(cube, moves) != target:
        raise RuntimeError("Kociemba frame fallback failed active-frame verification")
    return moves


def _pair_goal(cube: CubeState, reference: CubeState, corner: int, edge: int) -> bool:
    return (
        cube.cp[corner] == reference.cp[corner]
        and cube.co[corner] == reference.co[corner]
        and cube.ep[edge] == reference.ep[edge]
        and cube.eo[edge] == reference.eo[edge]
    )


def _edge_goal(cube: CubeState, reference: CubeState, edge: int) -> bool:
    return cube.ep[edge] == reference.ep[edge] and cube.eo[edge] == reference.eo[edge]


def _square_goal(cube: CubeState, reference: CubeState, corner: int, edge: int) -> bool:
    return _pair_goal(cube, reference, corner, edge) and (
        cube.ep[6] == reference.ep[6] and cube.eo[6] == reference.eo[6]
    )


def _remaining_pair_goal(cube: CubeState, reference: CubeState, corner: int, edge: int) -> bool:
    return _square_goal(cube, reference, corner, edge) and _pair_goal(
        cube, reference, 6 if corner == 5 else 5, 10 if edge == 9 else 9
    )


@dataclass(slots=True)
class _StagedFBSearch:
    """Small recognition/ranking layer for Roux square+pair FB construction."""

    target: CubeState
    max_depth: int
    max_nodes: int | None
    timeout_seconds: float | None
    nodes: int = field(init=False, default=0)
    started: float = field(init=False, default=0.0)
    path: list[str] = field(init=False, default_factory=list)

    def __post_init__(self) -> None:
        self.started = monotonic()

    def _check_limits(self) -> None:
        if self.max_nodes is not None and self.nodes >= self.max_nodes:
            raise RuntimeError("Roux staged FB search node limit exceeded")
        if self.timeout_seconds is not None and monotonic() - self.started >= self.timeout_seconds:
            raise TimeoutError("Roux staged FB search timeout exceeded")

    def _heuristic(self, cube: CubeState, goals: tuple[tuple[int, int], ...], include_dl: bool) -> int:
        values = [
            _f2l_pair_heuristic(cube, self.target.cp[c], self.target.ep[e], c, e, self.target.co[c], self.target.eo[e])
            for c, e in goals
        ]
        if include_dl and not (cube.ep[6] == self.target.ep[6] and cube.eo[6] == self.target.eo[6]):
            values.append(1)
        return max(values, default=0)

    def solve(self, cube: CubeState, goal_kind: str, first_corner: int, first_edge: int) -> tuple[str, ...]:
        other = (6, 10 if first_edge == 9 else 9)
        if goal_kind == "line":
            goal = lambda state: _pair_goal(state, self.target, first_corner, first_edge)
            goals = ((first_corner, first_edge),)
            include_dl = False
        elif goal_kind == "square":
            goal = lambda state: _square_goal(state, self.target, first_corner, first_edge)
            goals = ((first_corner, first_edge),)
            include_dl = True
        else:
            goal = lambda state: _remaining_pair_goal(state, self.target, first_corner, first_edge)
            goals = ((first_corner, first_edge), other)
            include_dl = True

        heuristic = lambda state: self._heuristic(state, goals, include_dl)
        if goal(cube):
            return ()
        for threshold in range(heuristic(cube), self.max_depth + 1):
            result = self._dfs(cube, 0, threshold, None, goal, heuristic)
            if result is not None:
                return result
        raise RuntimeError(f"Roux staged FB {goal_kind} search failed within depth {self.max_depth}")

    def _dfs(self, cube, depth, threshold, previous_face, goal, heuristic):
        self._check_limits()
        self.nodes += 1
        if depth + heuristic(cube) > threshold:
            return None
        if goal(cube):
            return tuple(self.path)
        if depth == threshold:
            return None
        ordered = sorted(_FB_MOVES, key=lambda m: m.endswith("2"))
        for move in ordered:
            if previous_face is not None and move[0].lower() == previous_face.lower():
                continue
            self.path.append(move)
            result = self._dfs(apply_move(cube, move), depth + 1, threshold, move[0], goal, heuristic)
            self.path.pop()
            if result is not None:
                return result
        return None


def _full_solve_oracle(cube: CubeState, center_tracking_moves: tuple[str, ...]) -> tuple[str, ...]:
    """Full-cube oracle that normalizes Roux M/r center displacement first.

    CubeState omits centers, while M/r legitimately move the M-slice centers.
    Kociemba's fixed-center adapter therefore cannot consume such a state
    directly. Track the center permutation independently, find the required
    M^k normalization (k in 0..3), then run the ordinary Kociemba solver and
    verify the resulting cubie state.
    """
    init_kociemba_engine()
    center_state = EngineCube()
    if center_tracking_moves:
        center_state.move(" ".join(center_tracking_moves))

    normalization: tuple[str, ...] | None = None
    for power in range(4):
        probe = center_state.clone()
        if power:
            probe.move(" ".join("M" for _ in range(power)))
        if list(probe.center) == [0, 1, 2, 3, 4, 5]:
            normalization = tuple("M" for _ in range(power))
            break

    if normalization is None:
        raise RuntimeError("Roux full-solve oracle could not normalize the M-slice centers.")

    normalized_state = apply_moves(cube, normalization)
    full_solution = KociembaSolver().solve(normalized_state)
    if not apply_moves(normalized_state, full_solution.moves).is_solved():
        raise RuntimeError("Roux full-solve oracle failed verification.")
    return normalization + tuple(full_solution.moves)


def _staged_fb_candidate(
    cube: CubeState,
    frame: tuple[str, ...],
    reference: CubeState,
    *,
    max_depth: int,
    max_nodes: int | None,
    timeout_seconds: float | None,
) -> tuple[tuple[str, ...], int] | None:
    """Recognize/rank a likely line, then square, then remaining pair.

    This is deliberately a planner, not the final correctness oracle. A
    later exact FB search can improve the staged candidate or fall back to it.
    """
    framed = apply_moves(cube, frame)
    pair_specs = ((5, 9), (6, 10))
    ranked = sorted(
        pair_specs,
        key=lambda ce: _f2l_pair_heuristic(
            framed,
            reference.cp[ce[0]],
            reference.ep[ce[1]],
            ce[0],
            ce[1],
            reference.co[ce[0]],
            reference.eo[ce[1]],
        ),
    )

    state = framed
    all_moves: list[str] = []
    nodes = 0
    first_corner, first_edge = ranked[0]
    for kind in ("line", "square", "final"):
        search = _StagedFBSearch(
            target=reference,
            max_depth=max_depth,
            max_nodes=max_nodes,
            timeout_seconds=timeout_seconds,
        )
        try:
            stage_moves = search.solve(state, kind, first_corner, first_edge)
        except (RuntimeError, TimeoutError):
            return None
        state = apply_moves(state, stage_moves)
        all_moves.extend(stage_moves)
        nodes += search.nodes

    physical_moves = frame + tuple(all_moves)
    if not _fb_goal(apply_moves(cube, physical_moves), reference):
        return None
    if not _fb_centers_match_frame(physical_moves, frame):
        return None
    return physical_moves, nodes


@dataclass(slots=True)
class _FirstBlockSearch:
    target: CubeState
    max_depth: int = 12
    max_nodes: int | None = 1_000_000
    timeout_seconds: float | None = 10.0
    nodes: int = field(init=False, default=0)
    started: float = field(init=False, default=0.0)
    path: list[str] = field(init=False, default_factory=list)

    def __post_init__(self) -> None:
        self.started = monotonic()

    def _check_limits(self) -> None:
        if self.max_nodes is not None and self.nodes >= self.max_nodes:
            raise RuntimeError("Roux First Block search node limit exceeded")
        if self.timeout_seconds is not None and monotonic() - self.started >= self.timeout_seconds:
            raise TimeoutError("Roux First Block search timeout exceeded")

    def _heuristic(self, cube: CubeState) -> int:
        # Each pair PDB is an admissible lower bound for the whole FB. The
        # maximum of several overlapping subsets remains admissible.
        return max(
            _f2l_pair_heuristic(cube, self.target.cp[5], self.target.ep[6], 5, 6, self.target.co[5], self.target.eo[6]),
            _f2l_pair_heuristic(cube, self.target.cp[6], self.target.ep[9], 6, 9, self.target.co[6], self.target.eo[9]),
            _f2l_pair_heuristic(cube, self.target.cp[5], self.target.ep[10], 5, 10, self.target.co[5], self.target.eo[10]),
        )

    def solve(self, cube: CubeState) -> tuple[str, ...]:
        if _fb_goal(cube, self.target):
            return ()
        for threshold in range(self._heuristic(cube), self.max_depth + 1):
            result = self._dfs(cube, 0, threshold, None)
            if result is not None:
                return result
        raise RuntimeError(f"Roux First Block search failed within depth {self.max_depth}")

    def _dfs(self, cube: CubeState, depth: int, threshold: int, previous_face: str | None) -> tuple[str, ...] | None:
        self._check_limits()
        self.nodes += 1
        if depth + self._heuristic(cube) > threshold:
            return None
        if _fb_goal(cube, self.target):
            return tuple(self.path)
        if depth == threshold:
            return None

        # Keep the full face-turn set. The frame is selected BEFORE the solve;
        # rotations are never allowed inside this search.
        # Roux FB is not constrained by a preserved CFOP-style cross. B/D and
        # r/M are therefore legitimate ergonomic choices. Keep the search
        # HTM-neutral instead of imposing a cost on any face/slice move.
        ordered = sorted(_FB_MOVES, key=lambda m: m.endswith("2"))
        for move in ordered:
            if previous_face is not None and move[0] == previous_face:
                continue
            self.path.append(move)
            result = self._dfs(apply_move(cube, move), depth + 1, threshold, move[0])
            self.path.pop()
            if result is not None:
                return result
        return None



def _solve_l4e_intuitive(cube: CubeState, target: CubeState) -> tuple[str, ...]:
    if _l4e_solved(cube, target):
        return ()
    moves = ("U", "U2", inverse_move("U"), "M", "M2", inverse_move("M"))
    target_edges = tuple(target.ep[pos] for pos in range(12))

    def key(state: CubeState) -> tuple:
        parts = []
        for piece in target_edges:
            pos = state.ep.index(piece)
            parts.extend((pos, state.eo[pos]))
        for piece in tuple(target.cp[pos] for pos in _CMLL_CORNER_GOALS):
            pos = state.cp.index(piece)
            parts.extend((pos, state.co[pos]))
        return tuple(parts)

    queue = deque([(cube, ())])
    seen = {key(cube)}
    while queue:
        state, path = queue.popleft()
        if _l4e_solved(state, target):
            return path
        if len(path) >= 14:
            continue
        previous = path[-1][0] if path else None
        for move in moves:
            if previous is not None and move[0] == previous:
                continue
            nxt = apply_move(state, move)
            state_key = key(nxt)
            if state_key in seen:
                continue
            seen.add(state_key)
            queue.append((nxt, path + (move,)))
    raise RuntimeError("Roux L4E intuitive M/U procedure failed")

class RouxSolver(Solver):
    """Incremental Roux solver; FB + SB + table-driven CMLL."""

    method = "roux"

    def __init__(self, *, fb_max_depth: int = 12, fb_max_nodes: int | None = 1_000_000, fb_timeout_seconds: float | None = 10.0,
                 sb_max_depth: int = 14, sb_max_nodes: int | None = 2_000_000, sb_timeout_seconds: float | None = 10.0) -> None:
        self.fb_max_depth = fb_max_depth
        self.fb_max_nodes = fb_max_nodes
        self.fb_timeout_seconds = fb_timeout_seconds
        self.sb_max_depth = sb_max_depth
        self.sb_max_nodes = sb_max_nodes
        self.sb_timeout_seconds = sb_timeout_seconds

    def solve(self, cube: CubeState) -> Solution:
        if cube.is_solved():
            return Solution(method=self.method, moves=(), verified=True)

        candidates = []
        for frame_index in range(4):
            frame = _fb_frame(frame_index)
            framed = apply_moves(cube, frame)
            reference = apply_moves(CubeState.solved(), frame)

            # Primary planner: recognition/ranking -> 1x1x3 line -> 1x2x2
            # square -> remaining pair. The staged result supplies an upper
            # bound to the exact search; if exact search cannot improve it,
            # the staged construction itself remains a valid candidate.
            staged_candidate = _staged_fb_candidate(
                cube,
                frame,
                reference,
                max_depth=min(self.fb_max_depth, 8),
                max_nodes=self.fb_max_nodes,
                timeout_seconds=(
                    None
                    if self.fb_timeout_seconds is None
                    else min(self.fb_timeout_seconds, 1.0)
                ),
            )

            upper_bound = None if staged_candidate is None else len(staged_candidate[0]) - len(frame)
            search = _FirstBlockSearch(
                target=reference,
                max_depth=(
                    self.fb_max_depth
                    if upper_bound is None
                    else min(self.fb_max_depth, max(0, upper_bound - 1))
                ),
                max_nodes=self.fb_max_nodes,
                timeout_seconds=self.fb_timeout_seconds,
            )
            try:
                inner_moves = search.solve(framed)
            except (RuntimeError, TimeoutError):
                inner_moves = None

            if inner_moves is not None:
                physical_moves = frame + inner_moves
                if _fb_centers_match_frame(physical_moves, frame):
                    candidates.append((len(physical_moves), frame_index, physical_moves, search, "exact"))

            if staged_candidate is not None:
                physical_moves, staged_nodes = staged_candidate
                if _fb_centers_match_frame(physical_moves, frame):
                    candidates.append((len(physical_moves), frame_index, physical_moves, staged_nodes, "staged"))
                continue

            # Roux contract: rotations are a setup prefix only. Never rotate
            # back after the solve, and never rotate between face turns.
            # Do not penalize B/D in Roux FB: a short B/D solution can be
            # preferable to a longer R/U/F/L-only solution. Candidate order
            # is therefore setup length, then HTM length, then frame index.

        if not candidates:
            raise RuntimeError("Roux First Block search failed in all four white-bottom frames")

        # Human-style phase boundary: FB is optimized in isolation. Do not
        # inspect or score SB while selecting the FB. Once the shortest valid
        # FB is chosen, SB starts from exactly that resulting state.
        selected_fb = min(candidates, key=lambda item: (item[0], item[1]))
        _, candidate_frame, candidate_fb, candidate_search, candidate_planner = selected_fb
        candidate_after = apply_moves(cube, candidate_fb)
        candidate_reference = apply_moves(CubeState.solved(), _fb_frame(candidate_frame))
        if not _fb_goal(candidate_after, candidate_reference):
            raise RuntimeError("Roux First Block planner produced an invalid FB candidate")
        if not _fb_centers_match_frame(candidate_fb, _fb_frame(candidate_frame)):
            raise RuntimeError("Roux First Block planner produced a center-misaligned FB candidate")

        # Recognition-first SB candidate: DR-first -> square-first ->
        # opposite pair. This search begins only after FB has been finalized.
        staged_sb = _StagedSBSearch(
            target=candidate_reference,
            max_depth=self.sb_max_depth,
            max_nodes=self.sb_max_nodes,
            timeout_seconds=self.sb_timeout_seconds,
        )
        try:
            staged_sb_moves = staged_sb.solve(candidate_after)
        except (RuntimeError, TimeoutError):
            staged_sb_moves = None

        # Human-style SB has priority. Direct search is deliberately an
        # emergency/oracle fallback, not a competing strategy that can replace
        # a valid human-style plan merely because it is shorter.
        exact_sb_moves = None
        if staged_sb_moves is None:
            candidate_sb = _SecondBlockSearch(
                target=candidate_reference,
                max_depth=self.sb_max_depth,
                max_nodes=self.sb_max_nodes,
                timeout_seconds=self.sb_timeout_seconds,
            )
            try:
                exact_sb_moves = candidate_sb.solve(candidate_after)
            except (RuntimeError, TimeoutError):
                exact_sb_moves = None
        else:
            candidate_sb = _SecondBlockSearch(
                target=candidate_reference,
                max_depth=self.sb_max_depth,
                max_nodes=self.sb_max_nodes,
                timeout_seconds=self.sb_timeout_seconds,
            )

        candidate_sb_moves = (
            staged_sb_moves
            if staged_sb_moves is not None
            else exact_sb_moves
        )
        sb_oracle_fallback = False
        if candidate_sb_moves is None:
            try:
                candidate_sb_moves = _kociemba_frame_fallback(
                    candidate_after,
                    candidate_reference,
                    _fb_frame(candidate_frame),
                )
                sb_oracle_fallback = True
                staged_sb.strategy = "KOCIEMBA_FRAME_FALLBACK"
            except RuntimeError as fallback_exc:
                raise RuntimeError(
                    "Roux Second Block search failed after the optimized First Block: "
                    f"staged={staged_sb_moves is not None}, "
                    f"staged_nodes={staged_sb.nodes}, "
                    f"staged_strategy={staged_sb.strategy}, "
                    f"exact_nodes={candidate_sb.nodes}; "
                    f"oracle={fallback_exc}"
                ) from fallback_exc
        candidate_sb_moves, eo_setup = _optimize_sb_final_move_for_eo(
            candidate_after,
            candidate_reference,
            tuple(candidate_sb_moves),
        )
        staged_sb.opportunity = {
            **staged_sb.opportunity,
            "eo_setup": eo_setup,
        }
        candidate_sb_after = apply_moves(candidate_after, candidate_sb_moves)
        if not second_block_solved(candidate_sb_after):
            raise RuntimeError("Roux Second Block planner produced an invalid SB candidate")

        selected_continuation = (
            len(candidate_fb) + len(candidate_sb_moves),
            candidate_frame,
            candidate_fb,
            candidate_search,
            candidate_planner,
            candidate_sb,
            candidate_sb_moves,
            candidate_sb_after,
            staged_sb,
            exact_sb_moves is not None,
        )

        # A valid FB+SB pair is not necessarily a legal CMLL starting
        # position: the SB projection intentionally does not constrain the
        # four remaining U-layer corners. Select the shortest continuation
        # that is also CMLL-recognizable before entering the LSE phases. If a
        # human-style SB plan cannot support the complete Roux continuation,
        # only then add the direct SB oracle as a fallback candidate.
        selected = None
        continuation_errors: list[str] = []
        lse = _LSEFormulaDatabase()
        continuation_candidates = [selected_continuation]
        for continuation_index, continuation in enumerate(continuation_candidates):
            _, candidate_frame, candidate_fb, candidate_search, candidate_planner, candidate_sb_search, candidate_sb_moves, candidate_sb_after, candidate_staged_sb, candidate_sb_exact = continuation
            candidate_reference = apply_moves(CubeState.solved(), _fb_frame(candidate_frame))
            candidate_lse_state = candidate_sb_after
            candidate_lse_target = candidate_reference
            candidate_cmll = _CMLLDatabase(candidate_reference)
            try:
                candidate_cmll_moves = candidate_cmll.solve(candidate_sb_after)
                candidate_cmll_after = apply_moves(candidate_sb_after, candidate_cmll_moves)
                candidate_lse_state = candidate_cmll_after
                candidate_eo_case, candidate_eo_moves = lse.solve_eo(candidate_lse_state, candidate_lse_target)
                candidate_eo_after = apply_moves(candidate_lse_state, candidate_eo_moves)
                candidate_ulur_search = _ULURIDAStar(target=candidate_lse_target, l4e_database=lse)
                candidate_ulur_moves = candidate_ulur_search.solve(candidate_eo_after)
                candidate_ulur_case = {"id": "IDA_STAR", "family": "M/U", "algorithm": " ".join(candidate_ulur_moves)}
                candidate_ulur_after = apply_moves(candidate_eo_after, candidate_ulur_moves)
                candidate_l4e_formula = lse.solve_l4e(candidate_ulur_after, candidate_lse_target)
                if candidate_l4e_formula is None:
                    raise RuntimeError(
                        "Roux L4E formula recognition found no Roux Method VN case "
                        f"(cp={candidate_ulur_after.cp}, ep={candidate_ulur_after.ep}, eo={candidate_ulur_after.eo}, "
                        f"target_cp={candidate_reference.cp}, target_ep={candidate_reference.ep})"
                    )
                candidate_l4e_case, candidate_l4e_moves = candidate_l4e_formula
                candidate_l4e_after = apply_moves(candidate_ulur_after, candidate_l4e_moves)
            except RuntimeError as exc:
                continuation_errors.append(str(exc))
                if continuation_index == 0 and staged_sb_moves is not None:
                    fallback_search = _SecondBlockSearch(
                        target=candidate_reference,
                        max_depth=self.sb_max_depth,
                        max_nodes=self.sb_max_nodes,
                        timeout_seconds=self.sb_timeout_seconds,
                    )
                    try:
                        fallback_moves = fallback_search.solve(candidate_after)
                    except (RuntimeError, TimeoutError) as fallback_exc:
                        continuation_errors.append(
                            f"direct SB fallback failed: {fallback_exc}"
                        )
                        fallback_moves = None
                    if fallback_moves is not None:
                        fallback_after = apply_moves(candidate_after, fallback_moves)
                        continuation_candidates.append(
                            (
                                len(candidate_fb) + len(fallback_moves),
                                candidate_frame,
                                candidate_fb,
                                candidate_search,
                                candidate_planner,
                                fallback_search,
                                fallback_moves,
                                fallback_after,
                                staged_sb,
                                True,
                            )
                        )
                continue
            selected = continuation + (candidate_reference, candidate_cmll, candidate_cmll_moves, candidate_eo_case, candidate_eo_moves, candidate_ulur_case, candidate_ulur_moves, candidate_l4e_case, candidate_l4e_moves)
            break

        if selected is None:
            detail = continuation_errors[0] if continuation_errors else "unknown continuation failure"
            raise RuntimeError(f"Roux First+Second Block continuation failed: {detail}")

        _, frame_index, fb_moves, search, planner, sb_search, sb_inner, sb_after, staged_sb, sb_exact, reference, cmll, cmll_moves, eo_case, eo_moves, ulur_case, ulur_moves, l4e_case, l4e_moves = selected
        fb_after = apply_moves(cube, fb_moves)
        if not first_block_solved(fb_after, frame_index):
            raise RuntimeError("Roux First Block failed phase-state verification")
        sb_after = apply_moves(fb_after, sb_inner)
        if not second_block_solved(sb_after):
            raise RuntimeError("Roux Second Block failed phase-state verification")
        cmll_after = apply_moves(sb_after, cmll_moves)
        if not _roux_blocks_and_cmll_solved(cmll_after, reference):
            raise RuntimeError("Roux CMLL failed phase-state verification: FB/SB/CMLL invariant broken")

        lse = _LSEFormulaDatabase()
        lse_state = cmll_after
        lse_target = reference
        eo_case, eo_moves = lse.solve_eo(lse_state, lse_target)
        eo_after = apply_moves(lse_state, eo_moves)
        if not _eo_solved(eo_after, lse_target):
            raise RuntimeError("Roux EO failed phase-state verification: prior invariants or edge orientation broken")

        ulur_search = _ULURIDAStar(target=lse_target, l4e_database=lse)
        ulur_moves = ulur_search.solve(eo_after)
        ulur_case = {"id": "IDA_STAR", "family": "M/U", "algorithm": " ".join(ulur_moves), "nodes": ulur_search.nodes}
        ulur_after = apply_moves(eo_after, ulur_moves)
        if not _ulur_solved(ulur_after, lse_target):
            raise RuntimeError("Roux ULUR IDA* failed phase-state verification: U corners or UL/UR goal broken")

        l4e_formula = lse.solve_l4e(ulur_after, lse_target)
        if l4e_formula is None:
            raise RuntimeError("Roux L4E formula recognition found no Roux Method VN case")
        l4e_case, l4e_moves = l4e_formula
        l4e_after = apply_moves(ulur_after, l4e_moves)
        if not _l4e_solved(l4e_after, lse_target):
            raise RuntimeError("Roux L4E algorithm failed edge verification")
        if l4e_after.cp != lse_target.cp or l4e_after.co != lse_target.co or l4e_after.ep != lse_target.ep or l4e_after.eo != lse_target.eo:
            raise RuntimeError("Roux LSE completed but final cubie state does not match the active frame")

        verification_state = l4e_after
        if verification_state != reference:
            raise RuntimeError("Roux construction completed but active-frame LSE state is not solved")
        frame_moves = _fb_frame(frame_index)
        original_frame = tuple(inverse_move(move) for move in reversed(frame_moves))
        construction_moves = (
            tuple(fb_moves[len(frame_moves):])
            + tuple(sb_inner)
            + tuple(cmll_moves)
            + tuple(eo_moves)
            + tuple(ulur_moves)
            + tuple(l4e_moves)
        )
        center_tracking_moves = frame_moves + construction_moves + original_frame
        # Center tracking is part of the state now, so final verification
        # compares both cubies and centers in the active physical frame.
        full_solution_moves: tuple[str, ...] = ()

        all_moves = fb_moves + tuple(sb_inner) + tuple(cmll_moves) + tuple(eo_moves) + tuple(ulur_moves) + tuple(l4e_moves)
        return Solution(
            method=self.method,
            moves=all_moves,
            metric="HTM",
            verified=True,
            phases=(
                SolutionPhase(
                    name="First Block",
                    moves=fb_moves,
                    description=(
                        "Setup rotation comes first (see metadata.fb_setup_moves). "
                        "Physically rotate the cube by that setup, then execute the "
                        "remaining First Block construction moves; do not treat the "
                        "setup rotation as a face turn. Wide turns such as u' are "
                        "literal wide-layer turns."
                    ),
                ),
                SolutionPhase(
                    name="Second Block",
                    moves=tuple(sb_inner),
                    description="Solve the Roux right 1x2x3 Second Block while preserving the First Block.",
                ),
                SolutionPhase(
                    name="CMLL",
                    moves=tuple(cmll_moves),
                    description="Recognize one of 42 CMLL corner cases, apply the selected pre-existing algorithm, and use U as AUF when needed.",
                ),
                SolutionPhase(
                    name="EO",
                    moves=tuple(eo_moves),
                    description="Recognize a published Roux EO case and execute its existing formula with AUF when needed.",
                ),
                SolutionPhase(
                    name="ULUR",
                    moves=tuple(ulur_moves),
                    description="Solve UL/UR using a published simple formula when recognized, otherwise the documented intuitive M/U2 procedure.",
                ),
                SolutionPhase(
                    name="L4E",
                    moves=tuple(l4e_moves),
                    description="Recognize a published Last Four Edges case and execute its existing formula.",
                ),
            ),
            metadata={
                "status": "l4e",
                "search": "recognition-ranked staged FB + exact bidirectional SB + 42-case CMLL + published EO/ULUR/L4E formulas",
                "fb_nodes": search if isinstance(search, int) else search.nodes,
                "sb_nodes": sb_search.nodes,
                "depth": len(all_moves),
                "fb_depth": len(fb_moves),
                "sb_depth": len(sb_inner),
                "sb_search": "bidirectional-bfs",
                "sb_planner": staged_sb.strategy,
                "sb_strategy": staged_sb.strategy,
                "sb_opportunity": staged_sb.opportunity,
                "sb_exact_refinement": sb_exact,
                "sb_fallback": staged_sb_moves is None,
                "sb_oracle_fallback": sb_oracle_fallback,
                "sb_staged_nodes": staged_sb.nodes,
                "sb_dr_candidates": staged_sb.dr_candidates_found,
                "sb_dr_candidate_limit": staged_sb.dr_candidate_limit,
                "sb_pair_order": staged_sb.selected_pair_order,
                "sb_pair_order_evaluations": tuple(staged_sb.pair_order_evaluations),
                "sb_planner_score": staged_sb.planner_score,
                "sb_move_penalty": staged_sb.opportunity.get("move_penalty"),
                "sb_final_move": staged_sb.opportunity.get("final_move"),
                "sb_corner_orientation": staged_sb.opportunity.get("corner_orientation_analyzer"),
                "sb_eo_setup": staged_sb.opportunity.get("eo_setup"),
                "cmll_case": (
                    cmll.recognize(sb_after)[0]["id"]
                    if _cmll_recognized(cmll, sb_after)
                    else "TWO_LOOK"
                ),
                "cmll_family": (
                    cmll.recognize(sb_after)[0]["family"]
                    if _cmll_recognized(cmll, sb_after)
                    else "MU-compatible fallback"
                ),
                "eo_case": eo_case["id"],
                "eo_family": eo_case["family"],
                "ulur_case": ulur_case["id"],
                "ulur_family": ulur_case["family"],
                "l4e_case": l4e_case["id"],
                "l4e_family": l4e_case["family"],
                "frame": frame_index,
                "fb_setup_moves": frame_moves,
                "fb_construction_moves": tuple(fb_moves[len(frame_moves):]),
                "fb_execution_order": "setup_rotation_then_construction",
                "planner": planner,
                "white_bottom": True,
                "rotation_policy": "setup-prefix-only",
                "fb_side": "left",
                "phases": ("First Block", "Second Block", "CMLL", "EO", "ULUR", "L4E"),
                "post_cmll_full_solve_length": len(full_solution_moves),
                "post_lse_full_solve_length": len(full_solution_moves),
            },
        )
