"""
Kociemba two-phase solver: init_solver(), solve(), scramble().

Tables are cached to disk after first build, so:
  - First call to init_solver(): ~5-10 s (builds + saves cache)
  - Subsequent calls:            ~0.1 s  (loads from cache)
"""

from __future__ import annotations
import os
import numpy as np
from typing import Optional

from ..cube import Cube
from ..constants import FACE_NAMES, FACE_NUMS, BASE_MOVE_DATA, COMPOUND_MOVES
from ..tables.tables import build_move_tables, build_pruning_tables
from .search_state import SearchState

# ── Cache location ────────────────────────────────────────────────
_CACHE_VERSION = "v1"
_CACHE_DIR = os.environ.get(
    "RUBIK_SOLVER_CACHE_DIR",
    os.path.join(os.path.expanduser("~"), ".cache", "rubik_solver"),
)

# ── Singleton table store ─────────────────────────────────────────
_move_tables    = None
_pruning_tables = None
_solver_ready   = False

_MOVE_TABLE_KEYS    = ['parity', 'twist', 'flip', 'FRtoBR', 'URFtoDLF',
                       'URtoDF', 'URtoUL', 'UBtoDF', 'mergeURtoDF']
_PRUNING_TABLE_KEYS = ['sliceTwist', 'sliceFlip',
                       'sliceURFtoDLFParity', 'sliceURtoDFParity']


def _cache_path(name):
    return os.path.join(_CACHE_DIR, f"{_CACHE_VERSION}_{name}.npy")


def _try_load_cache():
    try:
        mt, pt = {}, {}
        for key in _MOVE_TABLE_KEYS:
            p = _cache_path(f"mt_{key}")
            if not os.path.exists(p):
                return None
            mt[key] = np.load(p)
        for key in _PRUNING_TABLE_KEYS:
            p = _cache_path(f"pt_{key}")
            if not os.path.exists(p):
                return None
            pt[key] = np.load(p)
        return mt, pt
    except Exception:
        return None


def _save_cache(mt, pt):
    try:
        os.makedirs(_CACHE_DIR, exist_ok=True)
        for key in _MOVE_TABLE_KEYS:
            np.save(_cache_path(f"mt_{key}"), mt[key])
        for key in _PRUNING_TABLE_KEYS:
            np.save(_cache_path(f"pt_{key}"), pt[key])
    except Exception:
        pass


def clear_cache():
    """Delete cached table files, forcing a full rebuild on next init_solver()."""
    import shutil
    if os.path.isdir(_CACHE_DIR):
        shutil.rmtree(_CACHE_DIR)


def _init_moves():
    Cube.moves = [Cube().from_raw(raw) for raw in BASE_MOVE_DATA]
    for alg in COMPOUND_MOVES:
        c = Cube()
        for m in alg.strip().split():
            if not m:
                continue
            face = FACE_NUMS[m[0]]
            power = (2 if (len(m) > 1 and m[1] == '2')
                     else 3 if (len(m) > 1 and m[1] == "'")
                     else 1)
            for _ in range(power):
                c.multiply(Cube.moves[face])
        Cube.moves.append(c)


def init_solver(verbose=False):
    """
    Pre-compute all move and pruning tables required by the solver.

    First call: ~5-10 s (builds tables, writes cache to ~/.cache/rubik_solver/).
    Subsequent calls: ~0.1 s (loads from cache).
    Safe to call multiple times -- no-op once ready.

    Args:
        verbose: If True, print timing/progress information.
    """
    global _move_tables, _pruning_tables, _solver_ready
    if _solver_ready:
        return

    _init_moves()

    cached = _try_load_cache()
    if cached is not None:
        _move_tables, _pruning_tables = cached
        _solver_ready = True
        if verbose:
            print("rubik_solver: tables loaded from cache.")
        return

    if verbose:
        import time as _time
        print("rubik_solver: building tables (first run, ~5-10 s)...")
        _t0 = _time.time()

    _move_tables = build_move_tables()

    if verbose:
        print(f"  move tables done ({_time.time()-_t0:.1f}s)")

    _pruning_tables = build_pruning_tables(_move_tables)

    if verbose:
        print(f"  pruning tables done ({_time.time()-_t0:.1f}s)")

    _save_cache(_move_tables, _pruning_tables)
    _solver_ready = True

    if verbose:
        print(f"  cache saved to {_CACHE_DIR}")
        print(f"rubik_solver: ready in {_time.time()-_t0:.1f}s total")


def solve(cube, max_depth=22):
    """
    Solve the given Cube using Kociemba's two-phase algorithm.
    Returns a move string or None if no solution found within max_depth.
    """
    init_solver()

    clone = cube.clone()
    upright_alg = clone.upright()
    clone.move(upright_alg)

    rotation = list(clone.center)
    upright_solution = _solve_upright(clone, max_depth)
    if upright_solution is None:
        return None

    result_moves = []
    for m in upright_solution.strip().split():
        if not m:
            continue
        original_face = rotation[FACE_NUMS[m[0]]]
        suffix = m[1] if len(m) > 1 else ''
        result_moves.append(FACE_NAMES[original_face] + suffix)
    return ' '.join(result_moves)


def scramble():
    """Return a random scramble sequence as a move string."""
    init_solver()
    solution = solve(Cube.random())
    return Cube.inverse(solution) if solution else ''


# ── Internal two-phase search ──────────────────────────────────────

def _solve_upright(cube, max_depth):
    mt = _move_tables
    pt = _pruning_tables

    all_moves1 = list(range(18))
    all_moves2 = [0, 1, 2, 4, 7, 9, 10, 11, 13, 16]

    next_moves1 = []
    next_moves2 = []
    for last_face in range(6):
        n1, n2 = [], []
        for face in range(6):
            if face != last_face and face != last_face - 3:
                for p in range(3):
                    n1.append(face * 3 + p)
                for p in ([0, 1, 2] if face in (0, 3) else [1]):
                    n2.append(face * 3 + p)
        next_moves1.append(n1)
        next_moves2.append(n2)

    found = {'solution': None}
    free_states = [SearchState().set_tables(mt, pt) for _ in range(max_depth + 1)]

    def phase1(ss, depth):
        if found['solution'] is not None:
            return
        if depth == 0:
            if ss.min_dist1() == 0 and (
                ss.last_move is None or ss.last_move not in all_moves2
            ):
                phase2_search(ss)
        elif ss.min_dist1() <= depth:
            candidates = (
                next_moves1[ss.last_move // 3]
                if ss.last_move is not None else all_moves1
            )
            for move in candidates:
                if not free_states:
                    return
                nxt = free_states.pop()
                nxt.parent    = ss
                nxt.last_move = move
                nxt.depth     = ss.depth + 1
                nxt.flip      = int(mt['flip'] [ss.flip,        move])
                nxt.twist     = int(mt['twist'][ss.twist,       move])
                nxt.slice     = int(mt['FRtoBR'][ss.slice * 24, move]) // 24
                phase1(nxt, depth - 1)
                free_states.append(nxt)
                if found['solution'] is not None:
                    return

    def phase2_search(ss):
        ss.init2()
        for depth in range(1, max_depth - ss.depth + 1):
            phase2(ss, depth)
            if found['solution'] is not None:
                return

    def phase2(ss, depth):
        if found['solution'] is not None:
            return
        if depth == 0:
            if ss.min_dist2() == 0:
                found['solution'] = ss.solution()
        elif ss.min_dist2() <= depth:
            candidates = (
                next_moves2[ss.last_move // 3]
                if ss.last_move is not None else all_moves2
            )
            for move in candidates:
                if not free_states:
                    return
                nxt = free_states.pop()
                nxt.parent    = ss
                nxt.last_move = move
                nxt.depth     = ss.depth + 1
                nxt.URFtoDLF  = int(mt['URFtoDLF'][ss.URFtoDLF, move])
                nxt.FRtoBR    = int(mt['FRtoBR']  [ss.FRtoBR,   move])
                nxt.parity    = int(mt['parity']  [ss.parity,   move])
                nxt.URtoDF    = int(mt['URtoDF']  [ss.URtoDF,   move])
                phase2(nxt, depth - 1)
                free_states.append(nxt)
                if found['solution'] is not None:
                    return

    root = free_states.pop().set_tables(mt, pt).init_from_cube(cube)
    for depth in range(1, max_depth + 1):
        phase1(root, depth)
        if found['solution'] is not None:
            break

    return found['solution'].strip() if found['solution'] is not None else None