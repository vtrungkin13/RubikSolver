import pytest

from rubik_solver.cube.moves import MOVES, apply_move, apply_moves, inverse_move
from rubik_solver.cube.parser import inverse_sequence, parse_scramble
from rubik_solver.cube.state import CubeState


@pytest.mark.parametrize("face", ["U", "R", "F", "D", "L", "B"])
def test_four_quarter_turns_restore_cube(face: str) -> None:
    cube = CubeState.solved()
    for _ in range(4):
        cube = apply_move(cube, face)
    assert cube.is_solved()


@pytest.mark.parametrize("face", ["U", "R", "F", "D", "L", "B"])
def test_double_turn_equals_two_quarter_turns(face: str) -> None:
    assert apply_move(CubeState.solved(), face + "2") == apply_moves(CubeState.solved(), [face, face])


@pytest.mark.parametrize("move", sorted(MOVES))
def test_move_inverse(move: str) -> None:
    assert apply_moves(CubeState.solved(), [move, inverse_move(move)]).is_solved()


def test_scramble_inverse() -> None:
    scramble = parse_scramble("R U R' F2 D L2 B' U2")
    cube = apply_moves(CubeState.solved(), scramble)
    assert apply_moves(cube, inverse_sequence(scramble)).is_solved()


@pytest.mark.parametrize(
    "algorithm",
    ["r U r' U'", "Rw U Rw' U'", "M2 U M2 U2", "x R x' R'", "y F y' F'", "z U z' U'"],
)
def test_extended_notation_sequence_and_inverse(algorithm: str) -> None:
    moves = parse_scramble(algorithm)
    state = apply_moves(CubeState.solved(), moves)
    assert apply_moves(state, inverse_sequence(moves)).is_solved()


def test_extended_notation_can_be_mixed_with_standard_moves() -> None:
    moves = parse_scramble("r U F2 M' x R2")
    state = apply_moves(CubeState.solved(), moves)
    assert apply_moves(state, inverse_sequence(moves)).is_solved()
