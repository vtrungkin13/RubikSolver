import pytest

from rubik_solver.cube.state import CubeState
from rubik_solver.cube.validator import CubeValidationError, validate_cube


def test_solved_cube_is_valid() -> None:
    validate_cube(CubeState.solved())


def test_invalid_corner_parity() -> None:
    cube = CubeState(cp=(1, 0, 2, 3, 4, 5, 6, 7))
    with pytest.raises(CubeValidationError, match="parity"):
        validate_cube(cube)


def test_invalid_corner_orientation_sum() -> None:
    cube = CubeState(co=(1, 0, 0, 0, 0, 0, 0, 0))
    with pytest.raises(CubeValidationError, match="orientation sum"):
        validate_cube(cube)


def test_invalid_edge_orientation_sum() -> None:
    cube = CubeState(eo=(1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0))
    with pytest.raises(CubeValidationError, match="orientation sum"):
        validate_cube(cube)


def test_invalid_corner_permutation_values() -> None:
    cube = CubeState(cp=(0, 1, 2, 3, 4, 5, 6, 8))
    with pytest.raises(CubeValidationError, match="corner permutation"):
        validate_cube(cube)


def test_invalid_edge_permutation_values() -> None:
    cube = CubeState(ep=(0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12))
    with pytest.raises(CubeValidationError, match="edge permutation"):
        validate_cube(cube)
