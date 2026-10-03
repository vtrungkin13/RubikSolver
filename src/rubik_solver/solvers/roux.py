from __future__ import annotations

from dataclasses import dataclass, field
from collections import deque
import json
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
_SB_MOVES = (
    "U", "U2", "U'",
    "R", "R2", "R'",
    "M", "M2", "M'",
    "r", "r2", "r'",
)

# A Roux FB is a 1x2x3 block on the LEFT. Its bottom must be made from the
# white stickers, but the white center does not have to be the physical D
# center. CubeState has no center permutation, so choose a pre-solve frame with
# x2 (white stickers become D-facing), then one of four y orientations, and
# solve the canonical LEFT block there: DLF/DBL + DL/FL/BL.
_FB_CORNER_GOALS = (5, 6)  # DLF, DBL
_FB_EDGE_GOALS = (6, 9, 10)  # DL, FL, BL
_SB_CORNER_GOALS = (4, 7)  # DFR, DBR
_SB_EDGE_GOALS = (4, 8, 11)  # DR, FR, BR
_CMLL_CORNER_GOALS = (0, 1, 2, 3)  # URF, UFL, ULB, UBR
_CMLL_DB_PATH = Path(__file__).resolve().parents[3] / "data" / "cmll_algorithms.json"


def _fb_frame(frame: int) -> tuple[str, ...]:
    frame %= 4
    y = ((), ("y",), ("y2",), ("y'",))[frame]
    return ("x2",) + y


def _fb_goal(cube: CubeState, reference: CubeState) -> bool:
    return (
        all(
            cube.cp[pos] == reference.cp[pos] and cube.co[pos] == reference.co[pos]
            for pos in _FB_CORNER_GOALS
        )
        and all(
            cube.ep[pos] == reference.ep[pos] and cube.eo[pos] == reference.eo[pos]
            for pos in _FB_EDGE_GOALS
        )
    )


def first_block_solved(cube: CubeState) -> bool:
    if cube.is_solved():
        return True
    solved = CubeState.solved()
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
        if _fb_goal(cube, reference) and all(
            cube.cp[pos] == reference.cp[pos] and cube.co[pos] == reference.co[pos]
            for pos in _SB_CORNER_GOALS
        ) and all(
            cube.ep[pos] == reference.ep[pos] and cube.eo[pos] == reference.eo[pos]
            for pos in _SB_EDGE_GOALS
        ):
            return True
    return False


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
        entry, auf = self.recognize(cube)
        return auf + tuple(entry["algorithm"].split())


def _cmll_solved(cube: CubeState, target: CubeState) -> bool:
    return all(
        cube.cp[pos] == target.cp[pos] and cube.co[pos] == target.co[pos]
        for pos in _CMLL_CORNER_GOALS
    )


@dataclass(slots=True)
class _SecondBlockSearch:
    target: CubeState
    max_depth: int = 12
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
        return all(
            cube.cp[pos] == self.target.cp[pos] and cube.co[pos] == self.target.co[pos]
            for pos in _SB_CORNER_GOALS
        ) and all(
            cube.ep[pos] == self.target.ep[pos] and cube.eo[pos] == self.target.eo[pos]
            for pos in _SB_EDGE_GOALS
        )

    def _projection_key(self, cube: CubeState) -> tuple:
        """Project the state onto the six SB cubies.

        SB is a partial-state goal: only DFR/DBR and DR/FR/BR matter. A
        bidirectional search keyed by the complete CubeState is therefore
        incorrect, because a state can satisfy the SB goal while the other
        cubies differ from the canonical target. Encode each target cubie's
        current position and orientation instead; this projection is Markovian
        under the SB move set and is sufficient for goal matching.
        """
        corner_parts = []
        corner_pieces = tuple(self.target.cp[pos] for pos in _SB_CORNER_GOALS)
        for piece in corner_pieces:
            pos = cube.cp.index(piece)
            corner_parts.extend((pos, cube.co[pos]))
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
        # Split so an even depth budget can actually use both halves. With a
        # 12-move limit, each side must be allowed to reach depth 6; using
        # floor(12/2) on the goal side previously capped the combined search
        # at 11 moves.
        half = (self.max_depth + 1) // 2
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
    max_depth: int = 12
    max_nodes: int | None = 500_000
    timeout_seconds: float | None = 2.0
    nodes: int = field(init=False, default=0)
    started: float = field(init=False, default=0.0)
    path: list[str] = field(init=False, default_factory=list)

    def __post_init__(self) -> None:
        self.started = monotonic()

    def _check_limits(self) -> None:
        if self.max_nodes is not None and self.nodes >= self.max_nodes:
            raise RuntimeError("Roux staged SB search node limit exceeded")
        if self.timeout_seconds is not None and monotonic() - self.started >= self.timeout_seconds:
            raise TimeoutError("Roux staged SB search timeout exceeded")

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
        max_stage_depth: int,
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
        for threshold in range(self._heuristic(cube, goals), max_stage_depth + 1):
            result = self._dfs(cube, 0, threshold, None, goal, goals)
            if result is not None:
                return result
        raise RuntimeError("Roux staged SB stage failed")

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

    def solve(self, cube: CubeState) -> tuple[str, ...]:
        # This planner is called with a fixed FB frame. Do not use the
        # frame-agnostic second_block_solved() predicate here: accepting a
        # different y-frame can produce a deceptively short candidate that
        # the fixed-target exact search cannot reproduce.
        if all(
            cube.cp[pos] == self.target.cp[pos] and cube.co[pos] == self.target.co[pos]
            for pos in _SB_CORNER_GOALS
        ) and all(
            cube.ep[pos] == self.target.ep[pos] and cube.eo[pos] == self.target.eo[pos]
            for pos in _SB_EDGE_GOALS
        ):
            return ()

        # There are two natural DR-first constructions:
        #   A: DFR+DR -> FR square -> DBR+BR
        #   B: DBR+DR -> BR square -> DFR+FR
        #
        # Do recognition on the *actual post-DR state*, not the initial cube.
        # The initial heuristic cannot see how the chosen DR solution changes
        # the remaining pair/square relationship.
        plans = (
            ((4, 4), (4, 8), (7, 11)),
            ((7, 4), (7, 11), (4, 8)),
        )

        dr_candidates: list[tuple[int, tuple[int, int], tuple[int, int], tuple[str, ...], CubeState]] = []
        for dr, square, final_pair in plans:
            try:
                dr_moves = self._solve_stage(
                    cube,
                    (dr,),
                    max_stage_depth=min(7, self.max_depth),
                )
            except (RuntimeError, TimeoutError):
                continue
            dr_state = apply_moves(cube, dr_moves)
            # Recognition score after DR: prefer the square/final-pair route
            # whose actual post-DR state is closer to completion.
            score = self._heuristic(dr_state, (square,)) + self._heuristic(dr_state, (final_pair,))
            dr_candidates.append((score, square, final_pair, dr_moves, dr_state))

        dr_candidates.sort(key=lambda item: (item[0], len(item[3])))
        best: tuple[str, ...] | None = None

        for _, square, final_pair, dr_moves, dr_state in dr_candidates:
            moves: list[str] = list(dr_moves)
            state = dr_state
            try:
                # Stage 2: recognize/rank the square from the post-DR state.
                # Only the adjacent FR/BR edge is needed to extend the fixed DR.
                stage = self._solve_stage(
                    state,
                    (square,),
                    include_edges=(4,),
                    preserve_goals=(dr,),
                    max_stage_depth=min(7, self.max_depth - len(moves)),
                )
                state = apply_moves(state, stage)
                moves.extend(stage)

                # Stage 3: evaluate the remaining pair from the *post-square*
                # state. Its score is useful as recognition telemetry and keeps
                # the ranking decision tied to the state actually being solved.
                final_score = self._heuristic(state, (final_pair,))
                _ = final_score

                stage = self._solve_stage(
                    state,
                    (final_pair,),
                    include_edges=(4, 8, 11),
                    preserve_goals=(square,),
                    max_stage_depth=self.max_depth - len(moves),
                )
                moves.extend(stage)
            except (RuntimeError, TimeoutError):
                continue

            candidate = tuple(moves)
            candidate_state = apply_moves(cube, candidate)
            if all(
                candidate_state.cp[pos] == self.target.cp[pos]
                and candidate_state.co[pos] == self.target.co[pos]
                for pos in _SB_CORNER_GOALS
            ) and all(
                candidate_state.ep[pos] == self.target.ep[pos]
                and candidate_state.eo[pos] == self.target.eo[pos]
                for pos in _SB_EDGE_GOALS
            ):
                if best is None or len(candidate) < len(best):
                    best = candidate

        if best is None:
            raise RuntimeError("Roux staged Second Block search failed")
        return best


def _pair_goal(cube: CubeState, reference: CubeState, corner: int, edge: int) -> bool:
    return (
        cube.cp[corner] == reference.cp[corner]
        and cube.co[corner] == reference.co[corner]
        and cube.ep[edge] == reference.ep[edge]
        and cube.eo[edge] == reference.eo[edge]
    )


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
        ordered = sorted(_ROUX_MOVES, key=lambda m: (m.endswith("2"), m[0] in "u"))
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
        ordered = sorted(_ROUX_MOVES, key=lambda m: m.endswith("2"))
        for move in ordered:
            if previous_face is not None and move[0] == previous_face:
                continue
            self.path.append(move)
            result = self._dfs(apply_move(cube, move), depth + 1, threshold, move[0])
            self.path.pop()
            if result is not None:
                return result
        return None


class RouxSolver(Solver):
    """Incremental Roux solver; FB + SB + table-driven CMLL."""

    method = "roux"

    def __init__(self, *, fb_max_depth: int = 12, fb_max_nodes: int | None = 1_000_000, fb_timeout_seconds: float | None = 10.0,
                 sb_max_depth: int = 12, sb_max_nodes: int | None = 2_000_000, sb_timeout_seconds: float | None = 10.0) -> None:
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

        # FB is not an isolated optimization problem: an arbitrary valid FB
        # can leave the remaining cube in a state outside the SB subgroup.
        # Evaluate SB continuation for each FB candidate instead of blindly
        # selecting the shortest FB. This is the first explicit FB->SB
        # lookahead in the Roux planner.
        continuations = []
        for _, candidate_frame, candidate_moves, candidate_search, candidate_planner in sorted(candidates, key=lambda item: item[:2]):
            candidate_after = apply_moves(cube, candidate_moves)
            candidate_reference = apply_moves(CubeState.solved(), _fb_frame(candidate_frame))
            if not _fb_goal(candidate_after, candidate_reference):
                continue
            # Recognition-first SB candidate: DR-first -> square-first ->
            # opposite pair. This gives exact refinement a concrete upper bound.
            staged_sb = _StagedSBSearch(
                target=candidate_reference,
                max_depth=self.sb_max_depth,
                max_nodes=self.sb_max_nodes,
                timeout_seconds=(
                    None
                    if self.sb_timeout_seconds is None
                    else min(self.sb_timeout_seconds, 2.0)
                ),
            )
            try:
                staged_sb_moves = staged_sb.solve(candidate_after)
            except (RuntimeError, TimeoutError):
                staged_sb_moves = None

            upper_bound = None if staged_sb_moves is None else len(staged_sb_moves)
            candidate_sb = _SecondBlockSearch(
                target=candidate_reference,
                max_depth=(
                    self.sb_max_depth
                    if upper_bound is None
                    else min(self.sb_max_depth, max(0, upper_bound - 1))
                ),
                max_nodes=self.sb_max_nodes,
                timeout_seconds=self.sb_timeout_seconds,
            )

            # If the recognition-first staged solution already reaches the
            # admissible SB lower bound, exact refinement cannot improve it.
            # Skip the expensive bidirectional BFS in that case.
            sb_lower_bound = staged_sb._heuristic(
                candidate_after,
                ((4, 8), (7, 11), (4, 4)),
            )
            exact_sb_moves = None
            if staged_sb_moves is None or upper_bound is None or upper_bound > sb_lower_bound:
                try:
                    exact_sb_moves = candidate_sb.solve(candidate_after)
                except (RuntimeError, TimeoutError):
                    exact_sb_moves = None

            candidate_sb_moves = exact_sb_moves or staged_sb_moves
            if candidate_sb_moves is None:
                continue
            candidate_sb_after = apply_moves(candidate_after, candidate_sb_moves)
            if not second_block_solved(candidate_sb_after):
                continue
            continuations.append(
                (
                    len(candidate_moves) + len(candidate_sb_moves),
                    candidate_frame,
                    candidate_moves,
                    candidate_search,
                    candidate_planner,
                    candidate_sb,
                    candidate_sb_moves,
                    candidate_sb_after,
                    staged_sb,
                    exact_sb_moves is not None,
                )
            )

        if not continuations:
            raise RuntimeError("Roux First+Second Block search failed: no FB candidate had a valid SB continuation")

        _, frame_index, fb_moves, search, planner, sb_search, sb_inner, sb_after, staged_sb, sb_exact = min(
            continuations,
            key=lambda item: (item[0], len(item[2]), item[1]),
        )
        reference = apply_moves(CubeState.solved(), _fb_frame(frame_index))
        fb_after = apply_moves(cube, fb_moves)

        cmll = _CMLLDatabase(reference)
        cmll_moves = cmll.solve(sb_after)
        cmll_after = apply_moves(sb_after, cmll_moves)
        if not _cmll_solved(cmll_after, reference):
            raise RuntimeError("Roux CMLL algorithm failed corner verification")

        # Kociemba's engine has no center state, so verify from the original
        # coordinate frame rather than feeding it a state that still contains
        # the Roux setup rotation (x2 + y^k).
        frame_moves = _fb_frame(frame_index)
        original_frame = tuple(inverse_move(move) for move in reversed(frame_moves))
        verification_state = apply_moves(cmll_after, original_frame)
        construction_moves = tuple(fb_moves[len(frame_moves):]) + tuple(sb_inner) + tuple(cmll_moves)
        center_tracking_moves = frame_moves + construction_moves + original_frame
        full_solution_moves = _full_solve_oracle(verification_state, center_tracking_moves)

        all_moves = fb_moves + tuple(sb_inner) + tuple(cmll_moves)
        return Solution(
            method=self.method,
            moves=all_moves,
            metric="HTM",
            verified=True,
            phases=(
                SolutionPhase(
                    name="First Block",
                    moves=fb_moves,
                    description="Solve a Roux 1x2x3 First Block on the left with a white bottom; rotations are setup-only.",
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
            ),
            metadata={
                "status": "cmll",
                "search": "recognition-ranked staged FB + exact bidirectional SB + 42-case CMLL database",
                "fb_nodes": search if isinstance(search, int) else search.nodes,
                "sb_nodes": sb_search.nodes,
                "depth": len(all_moves),
                "fb_depth": len(fb_moves),
                "sb_depth": len(sb_inner),
                "sb_search": "bidirectional-bfs",
                "sb_planner": "dr-first/square-first staged + exact refinement",
                "sb_exact_refinement": sb_exact,
                "sb_staged_nodes": staged_sb.nodes,
                "cmll_case": cmll.recognize(sb_after)[0]["id"],
                "cmll_family": cmll.recognize(sb_after)[0]["family"],
                "frame": frame_index,
                "planner": planner,
                "white_bottom": True,
                "rotation_policy": "setup-prefix-only",
                "fb_side": "left",
                "phases": ("First Block", "Second Block", "CMLL", "LSE"),
                "post_cmll_full_solve_length": len(full_solution_moves),
            },
        )
