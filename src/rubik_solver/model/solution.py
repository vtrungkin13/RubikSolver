from __future__ import annotations

from dataclasses import dataclass, field


_ROTATION_MOVES = frozenset({"x", "x2", "x'", "y", "y2", "y'", "z", "z2", "z'"})


def _count_moves(moves: tuple[str, ...]) -> int:
    """Count face/slice/wide turns, excluding whole-cube rotations x/y/z."""
    return sum(move not in _ROTATION_MOVES for move in moves)


@dataclass(frozen=True, slots=True)
class SolutionPhase:
    name: str
    moves: tuple[str, ...]
    description: str | None = None

    @property
    def move_count(self) -> int:
        return _count_moves(self.moves)

    @property
    def sequence(self) -> str:
        return " ".join(self.moves)


@dataclass(frozen=True, slots=True)
class Solution:
    method: str
    moves: tuple[str, ...]
    metric: str = "HTM"
    verified: bool = False
    phases: tuple[SolutionPhase, ...] = ()
    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def move_count(self) -> int:
        return _count_moves(self.moves)

    @property
    def sequence(self) -> str:
        return " ".join(self.moves)
