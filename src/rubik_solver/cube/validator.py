from __future__ import annotations

from .state import CubeState


class CubeValidationError(ValueError):
    pass


def _permutation_parity(values: tuple[int, ...]) -> int:
    return sum(values[i] > values[j] for i in range(len(values)) for j in range(i + 1, len(values))) % 2


def validate_cube(cube: CubeState) -> None:
    if set(cube.cp) != set(range(8)):
        raise CubeValidationError("Invalid corner permutation.")
    if set(cube.ep) != set(range(12)):
        raise CubeValidationError("Invalid edge permutation.")
    if any(value not in (0, 1, 2) for value in cube.co):
        raise CubeValidationError("Invalid corner orientation.")
    if any(value not in (0, 1) for value in cube.eo):
        raise CubeValidationError("Invalid edge orientation.")
    if sum(cube.co) % 3:
        raise CubeValidationError("Corner orientation sum is invalid.")
    if sum(cube.eo) % 2:
        raise CubeValidationError("Edge orientation sum is invalid.")
    if _permutation_parity(cube.cp) != _permutation_parity(cube.ep):
        raise CubeValidationError("Corner/edge permutation parity mismatch.")
