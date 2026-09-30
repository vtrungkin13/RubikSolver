from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class SolutionPhase:
    name: str
    moves: tuple[str, ...]
    description: str | None = None

    @property
    def move_count(self) -> int:
        return len(self.moves)

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
        return len(self.moves)

    @property
    def sequence(self) -> str:
        return " ".join(self.moves)
