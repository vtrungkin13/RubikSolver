from __future__ import annotations

from .base import Solver


class SolverUnavailableError(RuntimeError):
    pass


def get_solver(method: str) -> Solver:
    raise SolverUnavailableError(
        "Solver '" + method + "' is not implemented yet. The cube engine is being built first."
    )
