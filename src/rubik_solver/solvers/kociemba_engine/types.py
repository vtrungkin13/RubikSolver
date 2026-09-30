"""
Enumerations and data types for the Rubik's Cube solver.
"""

from enum import IntEnum
from dataclasses import dataclass
from typing import List


class Center(IntEnum):
    U = 0
    R = 1
    F = 2
    D = 3
    L = 4
    B = 5


class Corner(IntEnum):
    URF = 0
    UFL = 1
    ULB = 2
    UBR = 3
    DFR = 4
    DLF = 5
    DBL = 6
    DRB = 7


class Edge(IntEnum):
    UR = 0
    UF = 1
    UL = 2
    UB = 3
    DR = 4
    DF = 5
    DL = 6
    DB = 7
    FR = 8
    FL = 9
    BL = 10
    BR = 11


@dataclass
class CubeState:
    center: List[int]
    cp: List[int]
    co: List[int]
    ep: List[int]
    eo: List[int]
