from __future__ import annotations

import argparse

from .cube.moves import apply_moves
from .cube.parser import normalize_scramble, parse_scramble
from .cube.state import CubeState
from .cube.validator import validate_cube
from .solvers.registry import SolverUnavailableError, get_solver


def main() -> None:
    parser = argparse.ArgumentParser(description="3x3 Rubik's Cube Solver")
    parser.add_argument("scramble", help="Singmaster scramble")
    parser.add_argument("--method", default="kociemba", choices=["cfop", "roux", "kociemba", "optimal"])
    args = parser.parse_args()
    try:
        moves = parse_scramble(args.scramble)
        cube = apply_moves(CubeState.solved(), moves)
        validate_cube(cube)
        solution = get_solver(args.method).solve(cube)
        print("Scramble:", normalize_scramble(args.scramble))
        print("Method:", solution.method)
        print("Solution:", solution.sequence)
        print("Moves:", solution.move_count)
        print("Metric:", solution.metric)
        print("Verification:", "SOLVED" if solution.verified else "NOT VERIFIED")
    except (ValueError, SolverUnavailableError) as exc:
        parser.error(str(exc))
