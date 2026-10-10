from __future__ import annotations

from rubik_solver.cube.moves import apply_moves
from rubik_solver.cube.parser import parse_scramble
from rubik_solver.cube.state import CubeState
from rubik_solver.model.solution import Solution
from rubik_solver.solvers.base import Solver

from .kociemba_engine import Cube as EngineCube
from .kociemba_engine import init_solver, solve as engine_solve


class KociembaSolver(Solver):
    """Kociemba Two-Phase solver adapter for the project CubeState model."""

    method = "kociemba"
    _initialized = False

    @classmethod
    def _ensure_initialized(cls) -> None:
        if not cls._initialized:
            init_solver()
            cls._initialized = True

    @staticmethod
    def _to_engine_cube(cube: CubeState) -> EngineCube:
        result = EngineCube()
        result.center[:] = cube.center
        result.cp[:] = cube.cp
        result.co[:] = cube.co
        result.ep[:] = cube.ep
        result.eo[:] = cube.eo
        return result

    def solve(self, cube: CubeState) -> Solution:
        if cube.is_solved():
            return Solution(method=self.method, moves=(), verified=True)

        self._ensure_initialized()
        engine_cube = self._to_engine_cube(cube)
        center_rotation = engine_cube.upright()
        if center_rotation:
            engine_cube.move(center_rotation)
        sequence = engine_solve(engine_cube)
        if center_rotation:
            sequence = f"{center_rotation} {sequence}"
        if not sequence:
            raise RuntimeError("Kociemba did not return a solution.")

        moves = tuple(parse_scramble(sequence))
        verified = apply_moves(cube, moves).is_solved()
        if not verified:
            raise RuntimeError("Kociemba returned a solution that does not solve the project CubeState.")

        return Solution(
            method=self.method,
            moves=moves,
            metric="HTM",
            verified=True,
            metadata={"algorithm": "Kociemba Two-Phase", "engine": "pure-python"},
        )
