from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .state import CubeState


class Face(str, Enum):
    U = "U"
    R = "R"
    F = "F"
    D = "D"
    L = "L"
    B = "B"


@dataclass(frozen=True, slots=True)
class MoveDefinition:
    cp: tuple[int, ...]
    co: tuple[int, ...]
    ep: tuple[int, ...]
    eo: tuple[int, ...]


# Standard cubie move tables used by Kociemba-style representations.
_BASE_MOVES = {
    Face.U: MoveDefinition((3,0,1,2,4,5,6,7), (0,)*8, (3,0,1,2,4,5,6,7,8,9,10,11), (0,)*12),
    Face.R: MoveDefinition((4,1,2,0,7,5,6,3), (2,0,0,1,1,0,0,2), (8,1,2,3,11,5,6,7,4,9,10,0), (0,)*12),
    Face.F: MoveDefinition((1,5,2,3,0,4,6,7), (1,2,0,0,2,1,0,0), (0,9,2,3,4,8,6,7,1,5,10,11), (0,1,0,0,0,1,0,0,1,1,0,0)),
    Face.D: MoveDefinition((0,1,2,3,5,6,7,4), (0,)*8, (0,1,2,3,5,6,7,4,8,9,10,11), (0,)*12),
    Face.L: MoveDefinition((0,2,6,3,4,1,5,7), (0,1,2,0,0,2,1,0), (0,1,10,3,4,5,9,7,8,2,6,11), (0,)*12),
    Face.B: MoveDefinition((0,1,3,7,4,5,2,6), (0,0,1,2,0,0,2,1), (0,1,2,11,4,5,6,10,8,9,3,7), (0,0,0,1,0,0,0,1,0,0,1,1)),
}


def _compose(a: MoveDefinition, b: MoveDefinition) -> MoveDefinition:
    return MoveDefinition(
        tuple(a.cp[b.cp[i]] for i in range(8)),
        tuple((a.co[b.cp[i]] + b.co[i]) % 3 for i in range(8)),
        tuple(a.ep[b.ep[i]] for i in range(12)),
        tuple((a.eo[b.ep[i]] + b.eo[i]) % 2 for i in range(12)),
    )


def _power(base: MoveDefinition, count: int) -> MoveDefinition:
    result = MoveDefinition(tuple(range(8)), (0,)*8, tuple(range(12)), (0,)*12)
    for _ in range(count):
        result = _compose(result, base)
    return result


MOVES: dict[str, MoveDefinition] = {}
for face, base in _BASE_MOVES.items():
    MOVES[face.value] = _power(base, 1)
    MOVES[f"{face.value}2"] = _power(base, 2)
    MOVES[f"{face.value}'"] = _power(base, 3)


def apply_move(cube: CubeState, move: str) -> CubeState:
    definition = MOVES.get(move)
    if definition is None:
        raise ValueError(f"Unknown move: {move}")
    return CubeState(
        cp=tuple(cube.cp[definition.cp[i]] for i in range(8)),
        co=tuple((cube.co[definition.cp[i]] + definition.co[i]) % 3 for i in range(8)),
        ep=tuple(cube.ep[definition.ep[i]] for i in range(12)),
        eo=tuple((cube.eo[definition.ep[i]] + definition.eo[i]) % 2 for i in range(12)),
    )


def apply_moves(cube: CubeState, moves: list[str] | tuple[str, ...]) -> CubeState:
    state = cube
    for move in moves:
        state = apply_move(state, move)
    return state


def inverse_move(move: str) -> str:
    if move.endswith("2"):
        return move
    return move[0] if move.endswith("'") else move + "'"
