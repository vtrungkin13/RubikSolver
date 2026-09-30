"""
SearchState: tracks cube coordinates at each node of the two-phase search tree.
"""

from __future__ import annotations
from typing import Optional, TYPE_CHECKING

from ..constants import N_SLICE1, N_SLICE2, N_PARITY
from ..tables.tables import pruning_get

if TYPE_CHECKING:
    from ..cube import Cube

MOVE_NAMES = [
    'U', 'U2', "U'",
    'R', 'R2', "R'",
    'F', 'F2', "F'",
    'D', 'D2', "D'",
    'L', 'L2', "L'",
    'B', 'B2', "B'",
]


class SearchState:
    __slots__ = (
        'parent', 'last_move', 'depth',
        'flip', 'twist', 'slice',
        'parity', 'URFtoDLF', 'FRtoBR',
        'URtoUL', 'UBtoDF', 'URtoDF',
        '_mt', '_pt',
    )

    def __init__(self) -> None:
        self.parent:   Optional[SearchState] = None
        self.last_move: Optional[int]        = None
        self.depth                           = 0

        self.flip      = 0
        self.twist     = 0
        self.slice     = 0
        self.parity    = 0
        self.URFtoDLF  = 0
        self.FRtoBR    = 0
        self.URtoUL    = 0
        self.UBtoDF    = 0
        self.URtoDF    = 0

        self._mt: dict = {}
        self._pt: dict = {}

    def set_tables(self, mt: dict, pt: dict) -> "SearchState":
        self._mt = mt
        self._pt = pt
        return self

    def init_from_cube(self, c: "Cube") -> "SearchState":
        self.flip      = c.flip()
        self.twist     = c.twist()
        self.slice     = c.FRtoBR() // 24
        self.parity    = c.corner_parity()
        self.URFtoDLF  = c.URFtoDLF()
        self.FRtoBR    = c.FRtoBR()
        self.URtoUL    = c.URtoUL()
        self.UBtoDF    = c.UBtoDF()
        return self

    def solution(self) -> str:
        if self.parent is not None:
            return self.parent.solution() + MOVE_NAMES[self.last_move] + ' '
        return ''

    def min_dist1(self) -> int:
        return max(
            pruning_get(self._pt['sliceFlip'],  N_SLICE1 * self.flip  + self.slice),
            pruning_get(self._pt['sliceTwist'], N_SLICE1 * self.twist + self.slice),
        )

    def min_dist2(self) -> int:
        idx1 = (N_SLICE2 * self.URtoDF   + self.FRtoBR) * N_PARITY + self.parity
        idx2 = (N_SLICE2 * self.URFtoDLF + self.FRtoBR) * N_PARITY + self.parity
        return max(
            pruning_get(self._pt['sliceURtoDFParity'],   idx1),
            pruning_get(self._pt['sliceURFtoDLFParity'], idx2),
        )

    def init2(self, top: bool = True) -> None:
        """Propagate Phase-2 coordinates down the parent chain."""
        if self.parent is None:
            return
        self.parent.init2(False)
        m = self.last_move
        mt = self._mt
        self.URFtoDLF = mt['URFtoDLF'][self.parent.URFtoDLF][m]
        self.FRtoBR   = mt['FRtoBR']  [self.parent.FRtoBR  ][m]
        self.parity   = mt['parity']  [self.parent.parity  ][m]
        self.URtoUL   = mt['URtoUL']  [self.parent.URtoUL  ][m]
        self.UBtoDF   = mt['UBtoDF']  [self.parent.UBtoDF  ][m]
        if top:
            self.URtoDF = mt['mergeURtoDF'][self.URtoUL][self.UBtoDF]
