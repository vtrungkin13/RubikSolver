import pytest

from rubik_solver.cube.state import CubeState
from rubik_solver.cube.validator import CubeValidationError, validate_cube


def test_solved_cube_is_valid() -> None:
    validate_cube(CubeState.solved())


def test_invalid_corner_parity() -> None:
    cube = CubeState(cp=(1, 0, 2, 3, 4, 5, 6, 7))
    with pytest.raises(CubeValidationError):
        validate_cube(cube)
