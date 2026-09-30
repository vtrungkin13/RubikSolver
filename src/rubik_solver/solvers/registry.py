from __future__ import annotations

from .base import Solver
from .kociemba import KociembaSolver


class SolverUnavailableError(RuntimeError):
    pass


_SOLVERS: dict[str, type[Solver]] = {
    "kociemba": KociembaSolver,
}


def get_solver(method: str) -> Solver:
    solver_type = _SOLVERS.get(method.lower())
    if solver_type is None:
        raise SolverUnavailableError(
            "Solver '" + method + "' is not implemented yet."
        )
    return solver_type()
