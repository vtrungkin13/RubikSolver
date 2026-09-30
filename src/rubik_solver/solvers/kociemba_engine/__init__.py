"""
rubik-solver-py
===============
A Python implementation of Kociemba's two-phase algorithm for solving the Rubik's Cube.

Quick start::

    from rubik_solver import Cube, init_solver, solve, scramble

    init_solver()                          # one-time table build (~30-60 s first time)
    cube = Cube().move("R U R' U'")
    print(solve(cube))                     # e.g. "U R U' R'"
    print(scramble())                      # random scramble sequence
"""

from .cube import Cube
from .types import Center, Corner, Edge, CubeState
from .solver.solver import init_solver, solve, scramble

__all__ = [
    "Cube",
    "Center",
    "Corner",
    "Edge",
    "CubeState",
    "init_solver",
    "solve",
    "scramble",
]

__version__ = "0.1.1"
__author__  = "Tmob"
__license__ = "MIT"
