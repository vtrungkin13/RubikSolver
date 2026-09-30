"""
Cube class: core logic, coordinates, serialization, move application.
"""

from __future__ import annotations

import random
from typing import Optional, List, Union

from .types import Center, Corner, Edge, CubeState
from .constants import (
    CENTER_COLOR, CORNER_COLOR, CORNER_FACELET,
    EDGE_COLOR, EDGE_FACELET, FACE_NAMES, FACE_NUMS,
)
from .math_utils import cnk, factorial, rotate_left, rotate_right


class Cube:
    """
    Represents a Rubik's Cube state using corner/edge permutation
    and orientation arrays, plus a center permutation for rotation tracking.
    """

    # Populated by initSolver() before solving
    moves: List["Cube"] = []

    def __init__(self) -> None:
        self.center = bytearray([0, 1, 2, 3, 4, 5])
        self.cp     = bytearray([0, 1, 2, 3, 4, 5, 6, 7])
        self.co     = bytearray(8)
        self.ep     = bytearray([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11])
        self.eo     = bytearray(12)

    # ── Construction ────────────────────────────────────────────────

    def clone(self) -> "Cube":
        c = Cube()
        c.center[:] = self.center
        c.cp[:]     = self.cp
        c.co[:]     = self.co
        c.ep[:]     = self.ep
        c.eo[:]     = self.eo
        return c

    def from_raw(self, raw: CubeState) -> "Cube":
        self.center[:] = raw.center
        self.cp[:]     = raw.cp
        self.co[:]     = raw.co
        self.ep[:]     = raw.ep
        self.eo[:]     = raw.eo
        return self

    def to_dict(self) -> dict:
        return {
            "center": list(self.center),
            "cp":     list(self.cp),
            "co":     list(self.co),
            "ep":     list(self.ep),
            "eo":     list(self.eo),
        }

    # ── String serialization ────────────────────────────────────────

    def as_string(self) -> str:
        """Returns the 54-character facelet string (U face first, then R F D L B)."""
        result = [''] * 54
        for i in range(6):
            result[9 * i + 4] = CENTER_COLOR[self.center[i]]
        for i in range(8):
            corner, ori = self.cp[i], self.co[i]
            for n in range(3):
                result[CORNER_FACELET[i][(n + ori) % 3]] = CORNER_COLOR[corner][n]
        for i in range(12):
            edge, ori = self.ep[i], self.eo[i]
            for n in range(2):
                result[EDGE_FACELET[i][(n + ori) % 2]] = EDGE_COLOR[edge][n]
        return ''.join(result)

    @classmethod
    def from_string(cls, s: str) -> "Cube":
        """Parse a cube from a 54-character facelet string."""
        cube = cls()
        for i in range(6):
            for j in range(6):
                if s[9 * i + 4] == CENTER_COLOR[j]:
                    cube.center[i] = j

        for i in range(8):
            ori = 0
            while ori < 3:
                if s[CORNER_FACELET[i][ori]] in ('U', 'D'):
                    break
                ori += 1
            col1 = s[CORNER_FACELET[i][(ori + 1) % 3]]
            col2 = s[CORNER_FACELET[i][(ori + 2) % 3]]
            for j in range(8):
                if col1 == CORNER_COLOR[j][1] and col2 == CORNER_COLOR[j][2]:
                    cube.cp[i] = j
                    cube.co[i] = ori % 3

        for i in range(12):
            for j in range(12):
                if (s[EDGE_FACELET[i][0]] == EDGE_COLOR[j][0] and
                        s[EDGE_FACELET[i][1]] == EDGE_COLOR[j][1]):
                    cube.ep[i] = j
                    cube.eo[i] = 0
                    break
                if (s[EDGE_FACELET[i][0]] == EDGE_COLOR[j][1] and
                        s[EDGE_FACELET[i][1]] == EDGE_COLOR[j][0]):
                    cube.ep[i] = j
                    cube.eo[i] = 1
                    break
        return cube

    # ── Multiplication ──────────────────────────────────────────────

    def center_multiply(self, other: "Cube") -> None:
        new_center = bytearray(6)
        for to in range(6):
            new_center[to] = self.center[other.center[to]]
        self.center[:] = new_center

    def corner_multiply(self, other: "Cube") -> None:
        new_cp = bytearray(8)
        new_co = bytearray(8)
        for to in range(8):
            frm = other.cp[to]
            new_cp[to] = self.cp[frm]
            new_co[to] = (self.co[frm] + other.co[to]) % 3
        self.cp[:] = new_cp
        self.co[:] = new_co

    def edge_multiply(self, other: "Cube") -> None:
        new_ep = bytearray(12)
        new_eo = bytearray(12)
        for to in range(12):
            frm = other.ep[to]
            new_ep[to] = self.ep[frm]
            new_eo[to] = (self.eo[frm] + other.eo[to]) % 2
        self.ep[:] = new_ep
        self.eo[:] = new_eo

    def multiply(self, other: "Cube") -> None:
        self.center_multiply(other)
        self.corner_multiply(other)
        self.edge_multiply(other)

    # ── Move application ────────────────────────────────────────────

    def move(self, alg: str) -> "Cube":
        """Apply an algorithm string, e.g. 'R U R\\' U\\''."""
        for m in alg.strip().split():
            if not m:
                continue
            face = FACE_NUMS.get(m[0])
            if face is None:
                raise ValueError(f"Invalid move: {m}")
            if len(m) == 1:
                power = 0
            elif m[1] == '2':
                power = 1
            elif m[1] == "'":
                power = 2
            else:
                raise ValueError(f"Invalid move: {m}")
            for _ in range(power + 1):
                self.multiply(Cube.moves[face])
        return self

    # ── Upright rotation ────────────────────────────────────────────

    def upright(self) -> str:
        """
        Returns a rotation sequence (x/y/z) that puts the cube in standard
        orientation (F center facing front, U center on top).
        """
        clone = self.clone()
        result: List[str] = []

        i = next(j for j in range(6) if clone.center[j] == Center.F)
        rot1 = (
            'x'  if i == Center.D else
            "x'" if i == Center.U else
            'x2' if i == Center.B else
            'y'  if i == Center.R else
            "y'" if i == Center.L else ''
        )
        if rot1:
            result.append(rot1)
            clone.move(rot1)

        j = next(k for k in range(6) if clone.center[k] == Center.U)
        rot2 = (
            'z'  if j == Center.L else
            "z'" if j == Center.R else
            'z2' if j == Center.D else ''
        )
        if rot2:
            result.append(rot2)

        return ' '.join(result)

    # ── Solved check ────────────────────────────────────────────────

    def verify(self) -> Union[bool, str]:
        """
        Verifies the cube state is mathematically valid.
        Returns True if valid, or an error message string if not.
        """
        corner_count = [0] * 8
        for i in range(8):
            if self.cp[i] == 255:  # -1 as unsigned byte
                return 'Invalid cube: Unrecognized or missing corners.'
            corner_count[self.cp[i]] += 1
        if any(c != 1 for c in corner_count):
            return 'Invalid cube: Duplicate corner detected.'

        edge_count = [0] * 12
        for i in range(12):
            if self.ep[i] == 255:
                return 'Invalid cube: Unrecognized or missing edges.'
            edge_count[self.ep[i]] += 1
        if any(c != 1 for c in edge_count):
            return 'Invalid cube: Duplicate edge detected.'

        if sum(self.co) % 3 != 0:
            return 'Invalid cube: Corner twist error (1 corner needs twisting).'

        if sum(self.eo) % 2 != 0:
            return 'Invalid cube: Edge flip error (1 edge needs flipping).'

        if self.corner_parity() != self.edge_parity():
            return 'Invalid cube: Parity error (2 edges or 2 corners need swapping).'

        return True

    def is_solved(self) -> bool:
        clone = self.clone()
        clone.move(clone.upright())
        for i in range(6):
            if clone.center[i] != i:
                return False
        for i in range(8):
            if clone.cp[i] != i or clone.co[i] != 0:
                return False
        for i in range(12):
            if clone.ep[i] != i or clone.eo[i] != 0:
                return False
        return True

    # ── Randomization ──────────────────────────────────────────────

    def randomize(self) -> "Cube":
        def _shuffle(arr: bytearray) -> None:
            cur = len(arr)
            while cur > 0:
                cur -= 1
                r = random.randint(0, cur)
                arr[cur], arr[r] = arr[r], arr[cur]

        def _swap_count(arr: bytearray) -> int:
            n = 0
            seen = [False] * len(arr)
            while True:
                cur = next((i for i in range(len(arr)) if not seen[i]), -1)
                if cur == -1:
                    break
                length = 0
                while not seen[cur]:
                    seen[cur] = True
                    length += 1
                    cur = arr[cur]
                n += length + 1
            return n

        def _rand_ori(arr: bytearray, mod: int) -> None:
            for i in range(len(arr)):
                arr[i] = random.randint(0, mod - 1)

        _shuffle(self.ep)
        _shuffle(self.cp)
        while (_swap_count(self.ep) + _swap_count(self.cp)) % 2 != 0:
            _shuffle(self.ep)
            _shuffle(self.cp)

        _rand_ori(self.co, 3)
        while sum(self.co) % 3 != 0:
            _rand_ori(self.co, 3)

        _rand_ori(self.eo, 2)
        while sum(self.eo) % 2 != 0:
            _rand_ori(self.eo, 2)

        return self

    @classmethod
    def random(cls) -> "Cube":
        return cls().randomize()

    # ── Algorithm helpers ───────────────────────────────────────────

    @staticmethod
    def inverse(alg: str) -> str:
        """Invert an algorithm string."""
        moves = alg.strip().split()
        result = []
        for m in reversed(moves):
            if not m:
                continue
            f = m[0]
            if len(m) == 1:
                result.append(f + "'")
            elif m[1] == '2':
                result.append(f + '2')
            elif m[1] == "'":
                result.append(f)
            else:
                raise ValueError(f"Invalid move: {m}")
        return ' '.join(result)

    # ── Coordinates (Phase 1 & 2) ───────────────────────────────────

    def twist(self, val: Optional[int] = None) -> Optional[int]:
        if val is not None:
            parity = 0
            for i in range(6, -1, -1):
                ori = val % 3
                val //= 3
                self.co[i] = ori
                parity += ori
            self.co[7] = (3 - parity % 3) % 3
            return None
        else:
            v = 0
            for i in range(7):
                v = 3 * v + self.co[i]
            return v

    def flip(self, val: Optional[int] = None) -> Optional[int]:
        if val is not None:
            parity = 0
            for i in range(10, -1, -1):
                ori = val % 2
                val //= 2
                self.eo[i] = ori
                parity += ori
            self.eo[11] = (2 - parity % 2) % 2
            return None
        else:
            v = 0
            for i in range(11):
                v = 2 * v + self.eo[i]
            return v

    def corner_parity(self) -> int:
        s = 0
        for i in range(Corner.DRB, Corner.URF, -1):
            for j in range(i - 1, Corner.URF - 1, -1):
                if self.cp[j] > self.cp[i]:
                    s += 1
        return s % 2

    def edge_parity(self) -> int:
        s = 0
        for i in range(Edge.BR, Edge.UR, -1):
            for j in range(i - 1, Edge.UR - 1, -1):
                if self.ep[j] > self.ep[i]:
                    s += 1
        return s % 2

    def permutation_index(
        self,
        context: str,
        start: int,
        end: int,
        from_end: bool,
        index: Optional[int] = None,
    ) -> int:
        max_our = end - start
        max_b   = factorial(max_our + 1)
        max_all = 7 if context == 'corners' else 11
        perm_array = self.cp if context == 'corners' else self.ep
        our = bytearray([255] * (max_our + 1))  # -1 as 255

        if index is not None:
            for i in range(max_our + 1):
                our[i] = i + start
            b = index % max_b
            a = index // max_b
            for i in range(len(perm_array)):
                perm_array[i] = 255  # -1

            for j in range(1, max_our + 1):
                k = b % (j + 1)
                b //= (j + 1)
                while k > 0:
                    rotate_right(our, 0, j)
                    k -= 1

            x = max_our
            if from_end:
                for j in range(max_all + 1):
                    c = cnk(max_all - j, x + 1)
                    if a - c >= 0:
                        perm_array[j] = our[max_our - x]
                        a -= c
                        x -= 1
            else:
                for j in range(max_all, -1, -1):
                    c = cnk(j, x + 1)
                    if a - c >= 0:
                        perm_array[j] = our[x]
                        a -= c
                        x -= 1
            return index
        else:
            our = bytearray([255] * (max_our + 1))
            a, b, x = 0, 0, 0
            if from_end:
                for j in range(max_all, -1, -1):
                    if start <= perm_array[j] <= end:
                        a += cnk(max_all - j, x + 1)
                        our[max_our - x] = perm_array[j]
                        x += 1
            else:
                for j in range(max_all + 1):
                    if start <= perm_array[j] <= end:
                        a += cnk(j, x + 1)
                        our[x] = perm_array[j]
                        x += 1

            for j in range(max_our, -1, -1):
                k = 0
                while our[j] != start + j:
                    rotate_left(our, 0, j)
                    k += 1
                b = (j + 1) * b + k

            return a * max_b + b

    def URFtoDLF(self, idx: Optional[int] = None) -> int:
        return self.permutation_index('corners', Corner.URF, Corner.DLF, False, idx)

    def URtoUL(self, idx: Optional[int] = None) -> int:
        return self.permutation_index('edges', Edge.UR, Edge.UL, False, idx)

    def UBtoDF(self, idx: Optional[int] = None) -> int:
        return self.permutation_index('edges', Edge.UB, Edge.DF, False, idx)

    def URtoDF(self, idx: Optional[int] = None) -> int:
        return self.permutation_index('edges', Edge.UR, Edge.DF, False, idx)

    def FRtoBR(self, idx: Optional[int] = None) -> int:
        return self.permutation_index('edges', Edge.FR, Edge.BR, True, idx)
