import pytest

from rubik_solver.cube.moves import apply_moves
from rubik_solver.cube.parser import inverse_sequence, parse_scramble
from rubik_solver.cube.state import CubeState
from rubik_solver.solvers.search import DepthSearch, heuristic


def scrambled(scramble: str) -> CubeState:
    return apply_moves(CubeState.solved(), parse_scramble(scramble))


def test_depth_search_solved_cube() -> None:
    result = DepthSearch().solve(CubeState.solved())
    assert result.moves == ()
    assert result.depth == 0
    assert result.nodes == 0


def test_depth_search_one_move() -> None:
    cube = scrambled("R")
    result = DepthSearch(max_depth=2).solve(cube)

    assert result.depth == 1
    assert apply_moves(cube, result.moves).is_solved()


def test_depth_search_short_scramble() -> None:
    cube = scrambled("R U R'")
    result = DepthSearch(max_depth=5, timeout_seconds=2).solve(cube)

    assert 0 < result.depth <= 5
    assert result.nodes > 0
    assert apply_moves(cube, result.moves).is_solved()


def test_depth_search_returns_valid_solution_for_multiple_short_scrambles() -> None:
    for scramble in ("F2", "R U", "R U F", "R2 F U'"):
        cube = scrambled(scramble)
        result = DepthSearch(max_depth=6, timeout_seconds=2).solve(cube)
        assert apply_moves(cube, result.moves).is_solved()


def test_search_solution_verification_pipeline() -> None:
    scramble = parse_scramble("R U R' F2 D")
    cube = apply_moves(CubeState.solved(), scramble)
    result = DepthSearch(max_depth=6, timeout_seconds=5).solve(cube)

    assert apply_moves(cube, result.moves).is_solved()


def test_depth_search_max_depth_failure() -> None:
    cube = scrambled("R U")
    with pytest.raises(RuntimeError, match="depth 1"):
        DepthSearch(max_depth=1).solve(cube)


def test_depth_search_max_nodes_failure() -> None:
    cube = scrambled("R U")
    with pytest.raises(RuntimeError, match="node limit exceeded"):
        DepthSearch(max_depth=5, max_nodes=1).solve(cube)


def test_depth_search_timeout() -> None:
    cube = scrambled("R U")
    with pytest.raises(TimeoutError, match="timeout exceeded"):
        DepthSearch(max_depth=5, timeout_seconds=0).solve(cube)


def test_depth_search_pruning_preserves_solution() -> None:
    scramble = parse_scramble("R R U")
    cube = apply_moves(CubeState.solved(), scramble)
    result = DepthSearch(max_depth=3, timeout_seconds=2).solve(cube)

    assert result.depth == 2
    assert apply_moves(cube, result.moves).is_solved()


def test_heuristic_is_zero_for_solved_cube() -> None:
    assert heuristic(CubeState.solved()) == 0


def test_inverse_sequence_remains_a_valid_solution() -> None:
    scramble = parse_scramble("R U R' F2")
    cube = apply_moves(CubeState.solved(), scramble)
    assert apply_moves(cube, inverse_sequence(scramble)).is_solved()
