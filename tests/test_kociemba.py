from rubik_solver.cube.moves import apply_moves
from rubik_solver.cube.parser import parse_scramble
from rubik_solver.cube.state import CubeState
from rubik_solver.solvers.kociemba import KociembaSolver


def test_kociemba_solves_solved_cube() -> None:
    result = KociembaSolver().solve(CubeState.solved())
    assert result.moves == ()
    assert result.verified is True


def test_kociemba_solves_short_scramble() -> None:
    scramble = parse_scramble("R U R' F2 D")
    cube = apply_moves(CubeState.solved(), scramble)
    result = KociembaSolver().solve(cube)

    assert result.verified is True
    assert result.move_count > 0
    assert apply_moves(cube, result.moves).is_solved()


def test_kociemba_solves_longer_scramble() -> None:
    scramble = parse_scramble("R U2 F' L2 D B R2 U' F2 D' L B2 U R' D2")
    cube = apply_moves(CubeState.solved(), scramble)
    result = KociembaSolver().solve(cube)

    assert result.verified is True
    assert apply_moves(cube, result.moves).is_solved()
