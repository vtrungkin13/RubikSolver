from __future__ import annotations

from abc import ABC, abstractmethod

from rubik_solver.cube.state import CubeState
from rubik_solver.model.solution import Solution


class Solver(ABC):
    method: str

    @abstractmethod
    def solve(self, cube: CubeState) -> Solution:
        raise NotImplementedError
