from __future__ import annotations

import re
from dataclasses import dataclass

from .moves import inverse_move

_MOVE_RE = re.compile(r"^[URFDLB](?:2|')?$")


@dataclass(frozen=True, slots=True)
class Move:
    notation: str

    def inverse(self) -> "Move":
        return Move(inverse_move(self.notation))


def parse_scramble(scramble: str) -> list[str]:
    tokens = scramble.split()
    invalid = [token for token in tokens if not _MOVE_RE.fullmatch(token)]
    if invalid:
        raise ValueError("Invalid move token(s): " + ", ".join(invalid))
    return tokens


def normalize_scramble(scramble: str) -> str:
    return " ".join(parse_scramble(scramble))


def inverse_sequence(moves: list[str] | tuple[str, ...]) -> list[str]:
    return [inverse_move(move) for move in reversed(moves)]
