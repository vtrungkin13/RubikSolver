from __future__ import annotations

import re
from dataclasses import dataclass

from .moves import inverse_move

# Standard face turns plus Singmaster extended notation.
_MOVE_RE = re.compile(r"^(?:[URFDLBMESxyzurfdlb](?:2|')?|[URFDLB](?:w|W)(?:2|')?)$")


def _normalize_token(token: str) -> str:
    if len(token) >= 2 and token[0] in "URFDLB" and token[1] in "wW":
        return token[0].lower() + token[2:]
    return token


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
    return [_normalize_token(token) for token in tokens]


def normalize_scramble(scramble: str) -> str:
    return " ".join(parse_scramble(scramble))


def inverse_sequence(moves: list[str] | tuple[str, ...]) -> list[str]:
    return [inverse_move(move) for move in reversed(moves)]
