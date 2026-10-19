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
# FB completion requires the left-block cubies and matching L center only.
# All other center positions are tracked in the resulting CubeState, not goals.
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

# A Roux FB is a 1x2x3 block on the LEFT. Only its L center is a center goal;
# the other five center positions are tracked but do not gate FB completion.
# Center tuple order is U, R, F, D, L, B.
_FB_CORNER_GOALS = (5, 6)  # DLF, DBL
_FB_EDGE_GOALS = (6, 9, 10)  # DL, FL, BL
_FB_CENTER_COLOR_POSITIONS = (4,)  # L only
_SB_CORNER_GOALS = (4, 7)  # DFR, DBR
_SB_EDGE_GOALS = (4, 8, 11)  # DR, FR, BR
# Canonical cubie sticker order, in face indices U, R, F, D, L, B.
_CORNER_FACES = ((0, 1, 2), (0, 2, 4), (0, 4, 5), (0, 5, 1),
                 (3, 2, 1), (3, 4, 2), (3, 5, 4), (3, 1, 5))
_EDGE_FACES = ((0, 1), (0, 2), (0, 4), (0, 5), (3, 1), (3, 2),
               (3, 4), (3, 5), (2, 1), (2, 4), (5, 4), (5, 1))
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
    """Return whether FB cubies are solved and the L center matches the block."""
    return _fb_cubies_goal(cube, reference) and all(
        cube.center[pos] == reference.center[pos]
        for pos in _FB_CENTER_COLOR_POSITIONS
    )


def _fb_search_goal(cube: CubeState, reference: CubeState) -> bool:
    """Require the FB cubies and L center only; track all centers separately."""
    return _fb_goal(cube, reference)


def _fb_centers_match_frame(moves: tuple[str, ...], frame: tuple[str, ...]) -> bool:
    """Return whether the physical FB sequence leaves the L center in-frame."""
    actual = apply_moves(CubeState.solved(), moves)
    expected = apply_moves(CubeState.solved(), frame)
    return actual.center[4] == expected.center[4]


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
        # This predicate is also used after later Roux phases, whose slice
        # moves may permute modeled centers while preserving the FB cubies.
        return _fb_cubies_goal(cube, reference)
    for frame_index in range(4):
        frame = _fb_frame(frame_index)
        reference = apply_moves(solved, frame)
        if _fb_cubies_goal(cube, reference):
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
        if _fb_cubies_goal(cube, reference) and all(
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
    parts: list[int] = []
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
    """Solve EO with M/U while retaining the actual center state after moves."""
    moves = (("M",), ("M2",), ("M'",), ("U",), ("U2",), ("U'",))

    def goal(state: CubeState) -> bool:
        return _eo_solved(state, target) and all(
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


def _solve_l4e_mu(
    cube: CubeState,
    target: CubeState,
) -> tuple[str, ...]:
    """Exact M/U completion for a legal L4E state not covered by the formula table.

    The published Roux Method VN recognizer remains the primary path. This
    finite-state fallback is local to L4E (never an SB/direct-cube fallback)
    and uses the tracked edge/corner projection. Center permutations are
    retained in the state but do not constrain the L4E cubie goal.
    """
    moves = ("M", "M2", "M'", "U", "U2", "U'")

    def key(state: CubeState) -> tuple[int, ...]:
        return _lse_key(state, target)

    def goal(state: CubeState) -> bool:
        return _l4e_solved(state, target)

    queue = deque([(cube, ())])
    seen = {key(cube)}
    while queue:
        state, path = queue.popleft()
        if goal(state):
            return path
        previous_face = path[-1][0] if path else None
        for move in moves:
            if previous_face is not None and move[0] == previous_face:
                continue
            nxt = apply_move(state, move)
            state_key = key(nxt)
            if state_key in seen:
                continue
            seen.add(state_key)
            queue.append((nxt, path + (move,)))
    raise RuntimeError("Roux exact M/U L4E completion failed")


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
        parts: list[int] = []
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
        return _ulur_solved(cube, self.target)

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

    def _try_phase(
        self, cube, target, entries, goal, auf_powers=(0, 1, 2, 3),
    ):
        for power in auf_powers:
            auf = _lse_u_turn(power)
            rotated = apply_moves(cube, auf)
            for entry in entries:
                moves = self._moves(entry)
                result = apply_moves(rotated, moves)
                if goal(result, target):
                    return entry, auf + moves
        return None

    def solve_eo(self, cube: CubeState, target: CubeState):
        centered_goal = lambda state, goal_target: _eo_solved(state, goal_target)
        if centered_goal(cube, target):
            return {"id": "SOLVED", "family": "SOLVED", "algorithm": ""}, ()
        result = self._try_phase(cube, target, self.eo, centered_goal)
        if result is None:
            return {"id": "INTUITIVE_MU", "family": "MU-only", "algorithm": ""}, _solve_eo_intuitive(cube, target)
        return result

    def solve_ulur_formula(self, cube: CubeState, target: CubeState):
        centered_goal = lambda state, goal_target: _ulur_solved(state, goal_target)
        if centered_goal(cube, target):
            return {"id": "SOLVED", "family": "SOLVED", "algorithm": ""}, ()
        return self._try_phase(cube, target, self.ulur, centered_goal)

    def solve_l4e(
        self, cube: CubeState, target: CubeState,
    ):
        centered_goal = lambda state, goal_target: _l4e_solved(state, goal_target)
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
        # A square may already be assembled but rotated out of its target
        # slot. R turns move it around the right block without disturbing FB.
        square_setup: tuple[str, ...] | None = None
        square_side: str | None = None
        rotation_options = ((), ("R",), ("R2",), ("R'",))
        for setup in rotation_options:
            positioned = apply_moves(cube, setup)
            if _pair_goal(positioned, self.target, 4, 4) and _edge_goal(positioned, self.target, 8):
                square_setup, square_side = setup, "FR"
                break
            if _pair_goal(positioned, self.target, 7, 4) and _edge_goal(positioned, self.target, 11):
                square_setup, square_side = setup, "BR"
                break
        if square_setup is not None:
            return {
                "strategy": "FREE_SQUARE",
                "squares": (square_side,),
                "square_setup": square_setup,
                "pairs": _sb_joined_pair_inventory(cube, self.target),
            }

        # Free-pair recognition is positional-independent. Case A is the DR
        # edge joined to either SB corner; case B is FR/BR edge material whose
        # sticker is correctly aligned to a matching center.
        joined = _sb_joined_pair_inventory(cube, self.target)
        dr_edge_piece = self.target.ep[4]
        dr_corner_pieces = {self.target.cp[pos] for pos in _SB_CORNER_GOALS}
        dr_joined = any(corner in dr_corner_pieces and edge == dr_edge_piece for corner, edge in joined)
        center_joined = _sb_side_edge_center_opportunity(cube, self.target)
        if dr_joined or center_joined or joined:
            return {
                "strategy": "FREE_PAIR",
                "squares": (),
                "pairs": joined,
                "dr_edge_joined": dr_joined,
                "side_edge_center_joined": center_joined,
            }
        return {"strategy": "DR_FIRST", "squares": (), "pairs": ()}


def _corner_stickers(cube: CubeState, position: int) -> dict[int, int]:
    """Map each face touching a corner slot to the color on that sticker."""
    faces = _CORNER_FACES[position]
    piece_faces = _CORNER_FACES[cube.cp[position]]
    orientation = cube.co[position]
    return {face: piece_faces[(index - orientation) % 3] for index, face in enumerate(faces)}


def _edge_stickers(cube: CubeState, position: int) -> dict[int, int]:
    """Map each face touching an edge slot to the color on that sticker."""
    faces = _EDGE_FACES[position]
    piece_faces = _EDGE_FACES[cube.ep[position]]
    orientation = cube.eo[position]
    return {face: piece_faces[(index - orientation) % 2] for index, face in enumerate(faces)}


def _sb_pair_joined(cube: CubeState, target: CubeState, corner_piece: int, edge_piece: int) -> bool:
    """Whether these exact corner/edge pieces are physically paired in any slot."""
    corner_pos = cube.cp.index(corner_piece)
    edge_pos = cube.ep.index(edge_piece)
    corner_faces = _corner_stickers(cube, corner_pos)
    edge_faces = _edge_stickers(cube, edge_pos)
    if not set(edge_faces).issubset(corner_faces):
        return False
    return all(corner_faces[face] == edge_faces[face] for face in edge_faces)


def _sb_joined_pair_inventory(cube: CubeState, target: CubeState) -> tuple[tuple[int, int], ...]:
    """Return SB corner/edge piece identities already joined, regardless of slot."""
    corners = tuple(target.cp[pos] for pos in _SB_CORNER_GOALS)
    edges = tuple(target.ep[pos] for pos in _SB_EDGE_GOALS)
    return tuple((corner, edge) for corner in corners for edge in edges
                 if _sb_pair_joined(cube, target, corner, edge))


def _sb_side_edge_center_opportunity(cube: CubeState, target: CubeState) -> tuple[int, ...]:
    """Return FR/BR edge identities with at least one sticker matched to its center."""
    matches = []
    for edge_goal in (8, 11):
        piece = target.ep[edge_goal]
        pos = cube.ep.index(piece)
        stickers = _edge_stickers(cube, pos)
        if any(stickers[face] == cube.center[face] for face in stickers):
            matches.append(piece)
    return tuple(matches)


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
        return _fb_cubies_goal(cube, self.target) and all(
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
        # Center state is observational metadata, not an SB goal dimension.
        # It does not affect the transition of the projected cubies.
        edge_parts = []
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
    expected_centers: tuple[int, ...] | None = field(init=False, default=None)
    # None means iterative deepening continues until a strategy finds a goal;
    # node/time budgets remain independent safety controls.
    max_depth: int | None = None
    max_nodes: int | None = 2_000_000
    timeout_seconds: float | None = 10.0
    nodes: int = field(init=False, default=0)
    started: float = field(init=False, default=0.0)
    path: list[str] = field(init=False, default_factory=list)
    strategy: str = field(init=False, default="DR_FIRST")
    opportunity: dict[str, object] = field(init=False, default_factory=dict)
    dr_candidate_limit: int = 3
    dr_candidates_found: int = field(init=False, default=0)
    selected_pair_order: str | None = field(init=False, default=None)
    planner_score: tuple | None = field(init=False, default=None)
    pair_order_evaluations: list[dict[str, object]] = field(init=False, default_factory=list)
    def __post_init__(self) -> None:
        self.started = monotonic()

    def _check_limits(self) -> None:
        if self.max_nodes is not None and self.nodes >= self.max_nodes:
            raise RuntimeError("Roux staged SB search node limit exceeded")
        if self.timeout_seconds is not None and monotonic() - self.started >= self.timeout_seconds:
            raise TimeoutError("Roux staged SB search timeout exceeded")

    def _goal(self, cube: CubeState) -> bool:
        return _fb_cubies_goal(cube, self.target) and all(
            cube.cp[pos] == self.target.cp[pos] and cube.co[pos] == self.target.co[pos]
            for pos in _SB_CORNER_GOALS
        ) and all(
            cube.ep[pos] == self.target.ep[pos] and cube.eo[pos] == self.target.eo[pos]
            for pos in _SB_EDGE_GOALS
        ) and _u_corners_on_u_layer(cube, self.target) and (
            self.expected_centers is None
            or (cube.center[1] == self.expected_centers[1] and cube.center[4] == self.expected_centers[4])
        )

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
        preserve_pairs: tuple[tuple[int, int], ...] = (),
        max_stage_depth: int | None,
        center_target: tuple[int, ...] | None = None,
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
            if not all(_sb_pair_joined(state, self.target, corner_piece, edge_piece)
                       for corner_piece, edge_piece in preserve_pairs):
                return False
            if not all(
                state.cp[corner] == self.target.cp[corner]
                and state.co[corner] == self.target.co[corner]
                and state.ep[edge] == self.target.ep[edge]
                and state.eo[edge] == self.target.eo[edge]
                for corner, edge in preserve_goals
            ):
                return False
            cubies_solved = all(
                state.ep[edge] == self.target.ep[edge]
                and state.eo[edge] == self.target.eo[edge]
                for edge in include_edges
            )
            return cubies_solved and (
                center_target is None
                or (state.center[1] == center_target[1] and state.center[4] == center_target[4])
            )

        if goal(cube):
            return ()
        threshold = max(
            self._heuristic(cube, goals),
            int(center_target is not None and (cube.center[1] != center_target[1] or cube.center[4] != center_target[4])),
        )
        while max_stage_depth is None or threshold <= max_stage_depth:
            result = self._dfs(
                cube, 0, threshold, None, goal, goals, preserve_pairs, center_target
            )
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
            first_lookahead = _sb_pair_lookahead_score(dr_state, self.target, first_pair)
            final_lookahead = _sb_pair_lookahead_score(after_first, self.target, final_pair)
            score = (
                first_lookahead,
                len(dr_moves) + len(first_moves) + final_heuristic + opportunity_bonus,
                final_lookahead,
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

    def _dfs(
        self, cube, depth, threshold, previous_face, goal, goals,
        preserve_pairs=(), center_target: tuple[int, ...] | None = None,
    ):
        self.nodes += 1
        self._check_limits()
        if not all(_sb_pair_joined(cube, self.target, corner_piece, edge_piece)
                   for corner_piece, edge_piece in preserve_pairs):
            return None
        heuristic = max(
            self._heuristic(cube, goals),
            int(center_target is not None and (cube.center[1] != center_target[1] or cube.center[4] != center_target[4])),
        )
        if depth + heuristic > threshold:
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
            result = self._dfs(
                apply_move(cube, move), depth + 1, threshold, face, goal, goals,
                preserve_pairs, center_target,
            )
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
            if not _fb_cubies_goal(state, self.target):
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
        self.expected_centers = cube.center
        # This planner is called with a fixed FB frame. Do not use the
        # frame-agnostic second_block_solved() predicate here: accepting a
        # different y-frame can produce a deceptively short candidate that
        # the fixed-target exact search cannot reproduce.
        if (
            cube.center[1] == self.expected_centers[1]
            and cube.center[4] == self.expected_centers[4]
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

        # Evaluate both pair orders after each DR candidate. FR/BR order is
        # chosen by U/F visibility, solution length and the remaining-pair lookahead.
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
                final_candidates = [
                    self._solve_stage(
                        state,
                        (final_pair,),
                        include_edges=(4, 8, 11),
                        preserve_goals=(plan["first_pair"],),
                        center_target=self.expected_centers,
                        max_stage_depth=remaining,
                    )
                ]
            except (RuntimeError, TimeoutError):
                continue

            ranked: list[tuple[tuple, tuple[str, ...], dict[str, object] | None]] = []
            for final_moves in final_candidates:
                candidate = tuple(dr_moves + first_moves + final_moves)
                candidate_state = apply_moves(cube, candidate)
                if not self._goal(candidate_state):
                    continue
                score = (
                    _sb_pair_lookahead_score(state, self.target, final_pair),
                    len(candidate),
                    plan["score"],
                    candidate,
                )
                ranked.append((score, candidate, None))

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
        self.opportunity = {
            **self.opportunity,
            "dr_candidates": self.dr_candidates_found,
            "selected_pair_order": self.selected_pair_order,
            "planner_score": self.planner_score,
            "lookahead_opportunity": best_plan["opportunity"],
            "pair_order_evaluations": tuple(self.pair_order_evaluations),
            "move_count": len(best),
        }
        return best

    def _solve_opportunity(self, cube: CubeState) -> tuple[str, ...] | None:
        """Exploit movable squares and already-joined pairs before DR-first."""
        strategy = self.opportunity.get("strategy")
        if strategy == "FREE_SQUARE":
            setup = tuple(self.opportunity.get("square_setup", ()))
            side = self.opportunity.get("squares", ("FR",))[0]
            positioned = apply_moves(cube, setup)
            if side == "FR":
                square_pair, square_edge, final_pair = (4, 4), 8, (7, 11)
                square_identity_pairs = ((self.target.cp[4], self.target.ep[4]),
                                         (self.target.cp[4], self.target.ep[8]))
            else:
                square_pair, square_edge, final_pair = (7, 4), 11, (4, 8)
                square_identity_pairs = ((self.target.cp[7], self.target.ep[4]),
                                         (self.target.cp[7], self.target.ep[11]))
            try:
                remaining = self._solve_stage(
                    positioned,
                    (final_pair,),
                    include_edges=(4, 8, 11),
                    preserve_pairs=square_identity_pairs,
                    center_target=self.expected_centers,
                    max_stage_depth=None,
                )
            except (RuntimeError, TimeoutError):
                return None
            candidate = setup + tuple(remaining)
            if self._goal(apply_moves(cube, candidate)):
                self.strategy = "FREE_SQUARE"
                self.opportunity = {**self.opportunity, "selected_square": side,
                                    "square_setup": setup, "square_pair": square_pair,
                                    "square_edge": square_edge}
                return candidate

        if strategy == "FREE_PAIR":
            joined_pairs = tuple(self.opportunity.get("pairs", ()))
            square_candidates: list[tuple[int, tuple[str, ...], str, tuple[int, int], int]] = []
            # First try converting the useful free-pair structure into either
            # canonical square. This is the only place the 7-move threshold applies.
            for side, dr_pair, side_edge in (
                ("FR", (4, 4), 8),
                ("BR", (7, 4), 11),
            ):
                try:
                    moves = self._solve_stage(
                        cube, (dr_pair,), include_edges=(side_edge,),
                        preserve_pairs=joined_pairs, max_stage_depth=7,
                    )
                except (RuntimeError, TimeoutError):
                    continue
                square_candidates.append((len(moves), moves, side, dr_pair, side_edge))
            if square_candidates:
                _, square_moves, side, square_pair, square_edge = min(
                    square_candidates, key=lambda item: (item[0], item[1])
                )
                after_square = apply_moves(cube, square_moves)
                if side == "FR":
                    final_pair = (7, 11)
                    square_identity_pairs = ((self.target.cp[4], self.target.ep[4]),
                                             (self.target.cp[4], self.target.ep[8]))
                else:
                    final_pair = (4, 8)
                    square_identity_pairs = ((self.target.cp[7], self.target.ep[4]),
                                             (self.target.cp[7], self.target.ep[11]))
                try:
                    final_moves = self._solve_stage(
                        after_square, (final_pair,), include_edges=(4, 8, 11),
                        preserve_pairs=square_identity_pairs,
                        center_target=self.expected_centers,
                        max_stage_depth=None,
                    )
                except (RuntimeError, TimeoutError):
                    final_moves = ()
                candidate = square_moves + final_moves
                if final_moves or self._goal(after_square):
                    if self._goal(apply_moves(cube, candidate)):
                        self.strategy = "FREE_PAIR_TO_SQUARE"
                        self.opportunity = {**self.opportunity, "selected_square": side,
                                            "square_moves": len(square_moves)}
                        return candidate

            # No square found in <=7 moves: if one or two pairs were already
            # joined, build DR without ever separating them, then insert each.
            dr_edge_piece = self.target.ep[4]
            insertable_pairs = tuple(pair for pair in joined_pairs if pair[1] != dr_edge_piece)
            if insertable_pairs:
                dr_specs = ((4, 4), (7, 4))
                for dr_pair in dr_specs:
                    try:
                        dr_moves = self._solve_stage(
                            cube, (dr_pair,), include_edges=(4,),
                            preserve_pairs=insertable_pairs, max_stage_depth=None,
                        )
                    except (RuntimeError, TimeoutError):
                        continue
                    state = apply_moves(cube, dr_moves)
                    inserted: list[str] = []
                    remaining_pairs = list(insertable_pairs)
                    failed = False
                    # Insert the joined pairs one at a time, preserving the
                    # remaining ones until their own insertion.
                    for corner_piece, edge_piece in tuple(remaining_pairs):
                        corner_goal = next((pos for pos in _SB_CORNER_GOALS
                                            if self.target.cp[pos] == corner_piece), None)
                        edge_goal = next((pos for pos in _SB_EDGE_GOALS
                                          if self.target.ep[pos] == edge_piece), None)
                        if corner_goal is None or edge_goal is None:
                            continue
                        try:
                            pair_moves = self._solve_stage(
                                state, ((corner_goal, edge_goal),),
                                include_edges=(4, 8, 11),
                                preserve_goals=(dr_pair,),
                                preserve_pairs=tuple(pair for pair in remaining_pairs
                                                     if pair != (corner_piece, edge_piece)),
                                center_target=(
                                    self.expected_centers if len(remaining_pairs) == 1 else None
                                ),
                                max_stage_depth=None,
                            )
                        except (RuntimeError, TimeoutError):
                            failed = True
                            break
                        state = apply_moves(state, pair_moves)
                        inserted.extend(pair_moves)
                        remaining_pairs.remove((corner_piece, edge_piece))
                    if failed:
                        continue
                    candidate = tuple(dr_moves + tuple(inserted))
                    if self._goal(apply_moves(cube, candidate)):
                        self.strategy = "FREE_PAIR_PRESERVE"
                        self.opportunity = {**self.opportunity, "preserved_pairs": joined_pairs,
                                            "dr_goal": dr_pair}
                        return candidate
        return None


def _sb_pair_lookahead_score(cube: CubeState, target: CubeState, pair: tuple[int, int]) -> int:
    """Lower is better: reward a pair whose corner and edge are visible on U/F."""
    corner_pos = cube.cp.index(target.cp[pair[0]])
    edge_pos = cube.ep.index(target.ep[pair[1]])
    visible_faces = {0, 2}  # U and F in canonical face indexing
    corner_visible = bool(set(_CORNER_FACES[corner_pos]) & visible_faces)
    edge_visible = bool(set(_EDGE_FACES[edge_pos]) & visible_faces)
    return int(not corner_visible) + int(not edge_visible)


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
    if not moves:
        return moves, metadata
    centers_preserved = (
        current_state.center[1] == cube.center[1]
        and current_state.center[4] == cube.center[4]
    )
    if centers_preserved and metadata["centers_ready_for_eo"]:
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
    if (candidate_state.center[1], candidate_state.center[4]) != (cube.center[1], cube.center[4]):
        return moves, metadata
    metadata.update({"applied": True, "replacement_move": replacement})
    return candidate, metadata


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


def _fb_pattern_snapshot(cube: CubeState, reference: CubeState) -> frozenset[str]:
    """Recognize reusable FB structures without forcing a single strategy.

    ``Ctr`` means a center in its active-frame position. The Ctr-edge patterns
    below identify an already-correct edge between the corresponding centers;
    CE-pair recognition additionally checks corner/edge identity and orientation.
    All matches are collected so the planner can exploit compatible patterns
    together rather than stopping at the first match.
    """
    patterns: set[str] = set()
    center_ok = {
        face: cube.center[face] == reference.center[face]
        for face in range(6)
    }

    for corner, edge, name in (
        (5, 9, "CE-pair-DLF-FL"),
        (5, 6, "CE-pair-DLF-DL"),
        (6, 10, "CE-pair-DBL-BL"),
        (6, 6, "CE-pair-DBL-DL"),
    ):
        if _pair_goal(cube, reference, corner, edge):
            patterns.add(name)

    # A 2x2 square is the DL edge plus either corner/side-edge pair.
    for corner, edge, name in (
        (5, 9, "square-2x2-DLF"),
        (6, 10, "square-2x2-DBL"),
    ):
        if _square_goal(cube, reference, corner, edge):
            patterns.add(name)

    if all((cube.ep[pos], cube.eo[pos]) == (reference.ep[pos], reference.eo[pos])
           for pos in (9, 10)):
        patterns.add("line-1x3-FL-BL")

    # Center-edge relations are geometric slot relationships. Require the
    # adjacent centers and the edge itself to match the active FB reference.
    if center_ok[4] and center_ok[2] and _edge_goal(cube, reference, 9):
        patterns.add("Ctr-FL")
    if center_ok[4] and center_ok[5] and _edge_goal(cube, reference, 10):
        patterns.add("Ctr-BL")
    if center_ok[4] and center_ok[3] and _edge_goal(cube, reference, 6):
        patterns.add("Ctr-DL")
    return frozenset(patterns)


def _fb_frame_pattern_score(cube: CubeState, frame: tuple[str, ...]) -> tuple[int, int, int, int]:
    """Rank setup frames by reusable left-side FB structures.

    Existing DL-corner pairs and correctly colored Ctr-FL/BL relationships
    are the most useful human-style starts. A 1x3 line is the next preference;
    this score is deliberately evaluated before solution length.
    """
    reference = apply_moves(CubeState.solved(), frame)
    patterns = _fb_pattern_snapshot(apply_moves(cube, frame), reference)
    dl_pairs = sum(name in patterns for name in ("CE-pair-DLF-DL", "CE-pair-DBL-DL"))
    side_ctrs = sum(name in patterns for name in ("Ctr-FL", "Ctr-BL"))
    side_pairs = sum(name in patterns for name in ("CE-pair-DLF-FL", "CE-pair-DBL-BL"))
    ctr_dl = int("Ctr-DL" in patterns)
    line = int("line-1x3-FL-BL" in patterns)
    return (dl_pairs, side_ctrs, side_pairs, ctr_dl + line)


def _fb_staged_kinds(
    patterns: frozenset[str], first_corner: int | None = None, first_edge: int | None = None,
) -> tuple[str, ...]:
    """Choose a human-style FB stage order from currently reusable material."""
    if first_corner is not None and first_edge is not None:
        dl_pair = "CE-pair-DLF-DL" if first_corner == 5 else "CE-pair-DBL-DL"
        side_pair = "CE-pair-DLF-FL" if first_corner == 5 else "CE-pair-DBL-BL"
        if dl_pair in patterns or side_pair in patterns:
            # The corner already has one of the two required edges; go directly
            # to completing its square rather than rebuilding the pair.
            return ("square", "final")
    reusable_block = any(name in patterns for name in (
        "CE-pair-DLF-DL", "CE-pair-DBL-DL",
        "CE-pair-DLF-FL", "CE-pair-DBL-BL",
        "square-2x2-DLF", "square-2x2-DBL",
        "Ctr-FL", "Ctr-BL", "line-1x3-FL-BL",
    ))
    if reusable_block:
        return ("line", "square", "final")
    # With no useful FB material already present, first solve DL edge + its
    # matching D/L centers using the shortest bounded stage search. Then build
    # each corner/side-edge pair while preserving that Ctr-DL relationship.
    return ("ctr_dl", "line", "square", "final")


def _fb_move_style_score(moves: tuple[str, ...]) -> tuple[int, int, int, int]:
    """Prefer ergonomic setup: R2/r2 over opening with L2, and wide-u over D."""
    wide_u = sum(move[0] == "u" for move in moves)
    d_turns = sum(move[0] == "D" for move in moves)
    construction = tuple(move for move in moves if move not in ("x", "x'", "x2", "y", "y'", "y2", "z", "z'", "z2"))
    first = construction[0] if construction else ""
    first_move_penalty = 0 if first in ("R2", "r2") else 2 if first == "L2" else 1
    return (first_move_penalty, d_turns, -wide_u, len(moves))


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

    def solve(
        self,
        cube: CubeState,
        goal_kind: str,
        first_corner: int,
        first_edge: int,
        *,
        preserve_edges: tuple[int, ...] = (),
        preserve_centers: tuple[int, ...] = (),
    ) -> tuple[str, ...]:
        other = (6, 10 if first_edge == 9 else 9)
        if goal_kind == "ctr_dl":
            # This stage is only an optional ergonomic way to start FB; center
            # alignment is metadata, never part of its goal.
            base_goal = lambda state: _edge_goal(state, self.target, 6)
            goals = ()
            include_dl = False
        elif goal_kind == "line":
            base_goal = lambda state: _pair_goal(state, self.target, first_corner, first_edge)
            goals = ((first_corner, first_edge),)
            include_dl = False
        elif goal_kind == "square":
            base_goal = lambda state: _square_goal(state, self.target, first_corner, first_edge)
            goals = ((first_corner, first_edge),)
            include_dl = True
        else:
            base_goal = lambda state: _remaining_pair_goal(state, self.target, first_corner, first_edge)
            goals = ((first_corner, first_edge), other)
            include_dl = True

        goal = lambda state: base_goal(state) and all(
            _edge_goal(state, self.target, edge) for edge in preserve_edges
        ) and all(state.center[pos] == self.target.center[pos] for pos in preserve_centers)

        heuristic = lambda state: max(
            self._heuristic(state, goals, include_dl),
            int(any(state.center[pos] != self.target.center[pos] for pos in preserve_centers)),
            int(goal_kind == "ctr_dl" and not _edge_goal(state, self.target, 6)),
        )
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
        ordered = sorted(
            _FB_MOVES,
            key=lambda move: (
                0 if move in ("R2", "r2") else 1,
                move.endswith("2"),
            ),
        )
        for move in ordered:
            if previous_face is not None and move[0].lower() == previous_face.lower():
                continue
            self.path.append(move)
            result = self._dfs(apply_move(cube, move), depth + 1, threshold, move[0], goal, heuristic)
            self.path.pop()
            if result is not None:
                return result
        return None


def _staged_fb_candidate(
    cube: CubeState,
    frame: tuple[str, ...],
    reference: CubeState,
    *,
    max_depth: int,
    max_nodes: int | None,
    timeout_seconds: float | None,
) -> tuple[tuple[str, ...], int] | None:
    """Compare pattern-aware line -> square -> pair plans for the same FB.

    Every currently available pattern is recognized together. Compatible
    structures are used as a starting point, and both side-pair orders are
    evaluated; the shortest verified complete FB wins. Search remains bounded,
    so this is the shortest candidate found within the configured budgets, not
    a claim of global optimality.
    """
    framed = apply_moves(cube, frame)
    pair_specs = ((5, 9), (6, 10))
    patterns = _fb_pattern_snapshot(framed, reference)

    def rank(ce: tuple[int, int]) -> tuple[int, int, int, int, int]:
        corner, edge = ce
        pair_pattern = "CE-pair-DLF-FL" if ce == (5, 9) else "CE-pair-DBL-BL"
        square_pattern = "square-2x2-DLF" if ce == (5, 9) else "square-2x2-DBL"
        center_edge_pattern = "Ctr-FL" if ce == (5, 9) else "Ctr-BL"
        return (
            0 if any(name in patterns for name in (pair_pattern, "CE-pair-DLF-DL" if ce == (5, 9) else "CE-pair-DBL-DL")) else 1,
            0 if square_pattern in patterns else 1,
            0 if center_edge_pattern in patterns or "Ctr-DL" in patterns else 1,
            _f2l_pair_heuristic(
                framed, reference.cp[corner], reference.ep[edge], corner, edge,
                reference.co[corner], reference.eo[edge],
            ),
            pair_specs.index(ce),
        )

    ranked = sorted(pair_specs, key=rank)
    # If a complete pair/square is already present, keep that side first; then
    # compare the opposite order too, since it can preserve other free pieces.
    candidates: list[tuple[tuple[str, ...], int, tuple[int, int, int, int, int], int]] = []
    for first_corner, first_edge in ranked:
        other_edge = 10 if first_edge == 9 else 9
        strategies = (True, False) if "line-1x3-FL-BL" in patterns else (False,)
        for preserve_line in strategies:
            state = framed
            all_moves: list[str] = []
            nodes = 0
            square_moves_count = 0
            failed = False
            stage_kinds = _fb_staged_kinds(patterns, first_corner, first_edge)
            for kind in stage_kinds:
                search = _StagedFBSearch(
                    target=reference,
                    max_depth=max_depth,
                    max_nodes=max_nodes,
                    timeout_seconds=timeout_seconds,
                )
                preserve_edges = (
                    (other_edge,)
                    if preserve_line and kind in ("line", "square")
                    else ()
                )
                if kind == "ctr_dl":
                    preserve_edges = ()
                elif "Ctr-DL" in patterns or "ctr_dl" in stage_kinds:
                    preserve_edges = tuple(sorted(set(preserve_edges + (6,))))
                side_edge = 9 if first_corner == 5 else 10
                side_ctr = "Ctr-FL" if first_corner == 5 else "Ctr-BL"
                if kind == "line" and side_ctr in patterns:
                    preserve_edges = tuple(sorted(set(preserve_edges + (side_edge,))))
                # Earlier stages may temporarily move centers, but the final
                # FB stage must restore the L center that anchors the block.
                preserve_centers = _FB_CENTER_COLOR_POSITIONS if kind == "final" else ()
                try:
                    stage_moves = search.solve(
                        state, kind, first_corner, first_edge,
                        preserve_edges=preserve_edges,
                        preserve_centers=preserve_centers,
                    )
                except (RuntimeError, TimeoutError):
                    failed = True
                    break
                state = apply_moves(state, stage_moves)
                all_moves.extend(stage_moves)
                nodes += search.nodes
                if kind == "square":
                    square_moves_count = len(stage_moves)
            if failed:
                continue

            physical_moves = frame + tuple(all_moves)
            if not _fb_search_goal(apply_moves(cube, physical_moves), reference):
                continue
            candidates.append((physical_moves, nodes, rank((first_corner, first_edge)), square_moves_count))
            # The line-preserving route succeeded; do not spend the same
            # bounded budget on a line-breaking alternative for this pair.
            if preserve_line:
                break

    if not candidates:
        return None
    selected_moves, selected_nodes, _, _ = min(
        candidates,
        key=lambda item: (
            _fb_move_style_score(item[0]),
            item[2][:3], item[3], item[2][3:], len(item[0]), item[0],
        ),
    )
    return selected_moves, selected_nodes


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
            int(any(cube.center[pos] != self.target.center[pos] for pos in _FB_CENTER_COLOR_POSITIONS)),
        )

    def solve(self, cube: CubeState) -> tuple[str, ...]:
        if _fb_search_goal(cube, self.target):
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
        if _fb_search_goal(cube, self.target):
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
    """Roux solver using staged FB/SB followed by the existing CMLL and LSE pipeline."""

    method = "roux"

    def __init__(self, *, fb_max_depth: int = 12, fb_max_nodes: int | None = 1_000_000, fb_timeout_seconds: float | None = 10.0,
                 sb_max_depth: int | None = None, sb_max_nodes: int | None = 2_000_000, sb_timeout_seconds: float | None = 10.0) -> None:
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
                candidates.append((len(physical_moves), frame_index, physical_moves, search, "exact"))

            if staged_candidate is not None:
                physical_moves, staged_nodes = staged_candidate
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
        # Rank only valid FB candidates. Preserve the actual center state at
        # the boundary; do not normalize or synthesize it for downstream phases.
        selected_fb = min(
            candidates,
            key=lambda item: (
                not _u_corners_on_u_layer(
                    apply_moves(cube, item[2]),
                    apply_moves(CubeState.solved(), _fb_frame(item[1])),
                ),
                tuple(-value for value in _fb_frame_pattern_score(cube, _fb_frame(item[1]))),
                item[4] != "staged",
                _fb_move_style_score(item[2]),
                item[0],
                item[1],
            ),
        )
        _, candidate_frame, candidate_fb, candidate_search, candidate_planner = selected_fb
        candidate_reference = apply_moves(CubeState.solved(), _fb_frame(candidate_frame))
        candidate_after = apply_moves(cube, candidate_fb)
        # This is the real post-FB state. Keep its center permutation as well
        # as its cubies; downstream phases must receive the state produced by
        # applying the emitted moves, not a normalized/synthetic substitute.
        fb_center_state = tuple(candidate_after.center)
        if not _fb_search_goal(candidate_after, candidate_reference):
            raise RuntimeError("Roux First Block planner produced an invalid FB candidate")
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

        if staged_sb_moves is None:
            raise RuntimeError(
                "Roux staged Second Block strategy failed without direct fallback: "
                f"strategy={staged_sb.strategy}, nodes={staged_sb.nodes}, "
                f"opportunity={staged_sb.opportunity}"
            )
        # Preserve the existing Roux SB handoff normalization: where the
        # final R/R' can be replaced by r/r' without changing FB/SB cubies,
        # prefer the variant that leaves the center/EO handoff in its expected
        # state. This does not rank SB by CMLL cases or reopen FB selection.
        candidate_sb_moves, eo_setup = _optimize_sb_final_move_for_eo(
            candidate_after, candidate_reference, tuple(staged_sb_moves)
        )
        staged_sb.opportunity = {**staged_sb.opportunity, "eo_setup": eo_setup}
        candidate_sb_after = apply_moves(candidate_after, candidate_sb_moves)
        if not second_block_solved(candidate_sb_after):
            raise RuntimeError("Roux Second Block planner produced an invalid SB candidate")
        if (candidate_sb_after.center[1], candidate_sb_after.center[4]) != (candidate_after.center[1], candidate_after.center[4]):
            raise RuntimeError("Roux Second Block changed the fixed R/L centers")

        fb_after = apply_moves(cube, candidate_fb)
        if not first_block_solved(fb_after, candidate_frame):
            raise RuntimeError("Roux First Block failed phase-state verification")
        verified_sb_after = apply_moves(fb_after, candidate_sb_moves)
        if not second_block_solved(verified_sb_after):
            raise RuntimeError("Roux Second Block failed phase-state verification")
        if not _fb_cubies_goal(verified_sb_after, candidate_reference):
            raise RuntimeError("Roux Second Block changed the First Block")

        # SB is now a hard phase boundary: once its actual state has been
        # validated, continue with the existing CMLL and LSE solvers. These
        # later phases do not influence FB/SB candidate selection.
        cmll = _CMLLDatabase(candidate_reference)
        cmll_moves = cmll.solve(verified_sb_after)
        cmll_after = apply_moves(verified_sb_after, cmll_moves)
        if (
            not _roux_blocks_and_cmll_solved(cmll_after, candidate_reference)
            or (cmll_after.center[1], cmll_after.center[4]) != (verified_sb_after.center[1], verified_sb_after.center[4])
        ):
            raise RuntimeError("Roux CMLL failed corner or fixed R/L center verification")

        lse = _LSEFormulaDatabase()
        eo_case, eo_moves = lse.solve_eo(cmll_after, candidate_reference)
        eo_after = apply_moves(cmll_after, eo_moves)
        if (
            not _roux_blocks_and_cmll_solved(eo_after, candidate_reference)
            or not _eo_solved(eo_after, candidate_reference)
            or (eo_after.center[1], eo_after.center[4]) != (cmll_after.center[1], cmll_after.center[4])
        ):
            raise RuntimeError("Roux EO failed block/CMLL preservation, edge orientation, or fixed R/L center verification")

        ulur_search = _ULURIDAStar(target=candidate_reference, l4e_database=lse)
        ulur_moves = ulur_search.solve(eo_after)
        ulur_case = {
            "id": "IDA_STAR",
            "family": "M/U",
            "algorithm": " ".join(ulur_moves),
            "nodes": ulur_search.nodes,
        }
        ulur_after = apply_moves(eo_after, ulur_moves)
        if not _ulur_solved(ulur_after, candidate_reference) or (ulur_after.center[1], ulur_after.center[4]) != (eo_after.center[1], eo_after.center[4]):
            raise RuntimeError("Roux ULUR failed UL/UR or fixed R/L center verification")

        l4e_formula = lse.solve_l4e(ulur_after, candidate_reference)
        if l4e_formula is None:
            # Keep the published formula recognizer as the primary path. If
            # its finite table cannot represent this valid L4E state, finish
            # within LSE using exact M/U search rather than reopening SB or
            # replacing the requested Roux solution with Kociemba.
            l4e_moves = _solve_l4e_mu(ulur_after, candidate_reference)
            l4e_case = {
                "id": "EXACT_MU_FALLBACK",
                "family": "M/U exact state search",
                "algorithm": " ".join(l4e_moves),
            }
        else:
            l4e_case, l4e_moves = l4e_formula
        l4e_after = apply_moves(ulur_after, l4e_moves)
        if not _l4e_solved(l4e_after, candidate_reference) or (l4e_after.center[1], l4e_after.center[4]) != (candidate_after.center[1], candidate_after.center[4]):
            raise RuntimeError("Roux L4E failed cubie or fixed R/L center verification")
        if (l4e_after.cp, l4e_after.co, l4e_after.ep, l4e_after.eo) != (
            candidate_reference.cp, candidate_reference.co,
            candidate_reference.ep, candidate_reference.eo,
        ):
            raise RuntimeError("Roux LSE completed but cubies do not match the active frame")
        # M/r moves may permute the four middle-layer centers. The R/L centers
        # remain fixed, while each full center permutation is recorded below.

        all_moves = (
            tuple(candidate_fb) + candidate_sb_moves + tuple(cmll_moves)
            + tuple(eo_moves) + tuple(ulur_moves) + tuple(l4e_moves)
        )
        return Solution(
            method=self.method,
            moves=all_moves,
            metric="HTM",
            verified=True,
            phases=(
                SolutionPhase(
                    name="First Block",
                    moves=tuple(candidate_fb),
                    description=(
                        "Setup rotation comes first (see metadata.fb_setup_moves). "
                        "Physically rotate the cube by that setup, then execute the "
                        "remaining First Block construction moves."
                    ),
                ),
                SolutionPhase(
                    name="Second Block",
                    moves=candidate_sb_moves,
                    description=(
                        "Solve the Roux right 1x2x3 Second Block while preserving "
                        "the First Block. The resulting cube state is validated before CMLL."
                    ),
                ),
                SolutionPhase(
                    name="CMLL",
                    moves=tuple(cmll_moves),
                    description="Solve the last-layer corners using the existing CMLL recognizer and algorithm database.",
                ),
                SolutionPhase(
                    name="EO",
                    moves=tuple(eo_moves),
                    description="Orient the remaining last-layer edges using the existing Roux EO solver.",
                ),
                SolutionPhase(
                    name="ULUR",
                    moves=tuple(ulur_moves),
                    description="Solve UL/UR with the existing M/U search after EO state validation.",
                ),
                SolutionPhase(
                    name="L4E",
                    moves=tuple(l4e_moves),
                    description="Solve the final four edges using the existing L4E formula database.",
                ),
            ),
            metadata={
                "status": "l4e",
                "verification_scope": "first_block+second_block+cmll+eo+ulur+l4e",
                "center_verification": "exact-phase-snapshots; FB-L; later-phases-preserve-RL",
                "search": "recognition-first staged FB/SB followed by existing CMLL and LSE solvers; no direct SB fallback",
                "fb_nodes": candidate_search if isinstance(candidate_search, int) else candidate_search.nodes,
                "sb_nodes": staged_sb.nodes,
                "depth": len(all_moves),
                "fb_depth": len(candidate_fb),
                "sb_depth": len(candidate_sb_moves),
                "fb_center_state": tuple(fb_after.center),
                "fb_state": {
                    "cp": fb_after.cp, "co": fb_after.co,
                    "ep": fb_after.ep, "eo": fb_after.eo,
                    "center": fb_after.center,
                },
                "sb_state": {
                    "cp": verified_sb_after.cp, "co": verified_sb_after.co,
                    "ep": verified_sb_after.ep, "eo": verified_sb_after.eo,
                    "center": verified_sb_after.center,
                },
                "cmll_state": {
                    "cp": cmll_after.cp, "co": cmll_after.co,
                    "ep": cmll_after.ep, "eo": cmll_after.eo,
                    "center": cmll_after.center,
                },
                "eo_state": {
                    "cp": eo_after.cp, "co": eo_after.co,
                    "ep": eo_after.ep, "eo": eo_after.eo,
                    "center": eo_after.center,
                },
                "ulur_state": {
                    "cp": ulur_after.cp, "co": ulur_after.co,
                    "ep": ulur_after.ep, "eo": ulur_after.eo,
                    "center": ulur_after.center,
                },
                "l4e_state": {
                    "cp": l4e_after.cp, "co": l4e_after.co,
                    "ep": l4e_after.ep, "eo": l4e_after.eo,
                    "center": l4e_after.center,
                },
                "sb_search": "staged-iterative-deepening",
                "sb_planner": staged_sb.strategy,
                "sb_strategy": staged_sb.strategy,
                "sb_opportunity": staged_sb.opportunity,
                "sb_fallback": False,
                "sb_oracle_fallback": False,
                "sb_staged_nodes": staged_sb.nodes,
                "sb_dr_candidates": staged_sb.dr_candidates_found,
                "sb_dr_candidate_limit": staged_sb.dr_candidate_limit,
                "sb_pair_order": staged_sb.selected_pair_order,
                "sb_pair_order_evaluations": tuple(staged_sb.pair_order_evaluations),
                "sb_planner_score": staged_sb.planner_score,
                "cmll_case": (
                    cmll.recognize(verified_sb_after)[0]["id"]
                    if _cmll_recognized(cmll, verified_sb_after) else "TWO_LOOK"
                ),
                "cmll_family": (
                    cmll.recognize(verified_sb_after)[0]["family"]
                    if _cmll_recognized(cmll, verified_sb_after) else "MU-compatible fallback"
                ),
                "eo_case": eo_case["id"],
                "eo_family": eo_case["family"],
                "ulur_case": ulur_case["id"],
                "ulur_family": ulur_case["family"],
                "l4e_case": l4e_case["id"],
                "l4e_family": l4e_case["family"],
                "frame": candidate_frame,
                "fb_setup_moves": _fb_frame(candidate_frame),
                "fb_construction_moves": tuple(candidate_fb[len(_fb_frame(candidate_frame)):]),
                "fb_execution_order": "setup_rotation_then_construction",
                "planner": candidate_planner,
                "white_bottom": True,
                "rotation_policy": "setup-prefix-only",
                "fb_side": "left",
                "phases": ("First Block", "Second Block", "CMLL", "EO", "ULUR", "L4E"),
            },
        )
