from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CubeState:
    """3x3 cube in canonical cubie representation.

    Corners: URF, UFL, ULB, UBR, DFR, DLF, DBL, DRB.
    Edges: UR, UF, UL, UB, DR, DF, DL, DB, FR, FL, BL, BR.
    """
    cp: tuple[int, ...] = tuple(range(8))
    co: tuple[int, ...] = (0,) * 8
    ep: tuple[int, ...] = tuple(range(12))
    eo: tuple[int, ...] = (0,) * 12
    # Center permutation uses the same face order as the Kociemba engine:
    # U, R, F, D, L, B. Face turns keep this permutation unchanged; slice,
    # wide, and whole-cube rotations update it.
    center: tuple[int, ...] = tuple(range(6))

    @classmethod
    def solved(cls) -> "CubeState":
        return cls()

    def is_solved(self) -> bool:
        return (
            self.cp == tuple(range(8))
            and self.co == (0,) * 8
            and self.ep == tuple(range(12))
            and self.eo == (0,) * 12
            and self.center == tuple(range(6))
        )
