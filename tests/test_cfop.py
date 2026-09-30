from rubik_solver.cube.moves import apply_moves
from rubik_solver.cube.parser import parse_scramble
from rubik_solver.cube.state import CubeState
from rubik_solver.solvers.cfop import CrossSolver, cross_solved


def scrambled(scramble: str) -> CubeState:
    return apply_moves(CubeState.solved(), parse_scramble(scramble))


def test_cross_solved_cube() -> None:
    result = CrossSolver().solve(CubeState.solved())
    assert result.moves == ()
    assert result.phases[0].name == "Cross"
    assert result.verified is True


def test_cross_solves_single_face_turns() -> None:
    for scramble in ("R", "U", "F2", "L'", "B2", "D"):
        cube = scrambled(scramble)
        result = CrossSolver(max_depth=8).solve(cube)
        assert cross_solved(apply_moves(cube, result.moves))
        assert result.move_count == len(result.phases[0].moves)


def test_cross_solves_multiple_scrambles() -> None:
    scrambles = (
        "R U R' F2 D",
        "R U2 F' L2 D B R2",
        "F R U' L B2 D F2 R' U",
    )
    for scramble in scrambles:
        cube = scrambled(scramble)
        result = CrossSolver(max_depth=8, timeout_seconds=5).solve(cube)
        assert result.verified is True
        assert cross_solved(apply_moves(cube, result.moves))


def test_cross_respects_depth_limit() -> None:
    cube = scrambled("R U F")
    try:
        CrossSolver(max_depth=0).solve(cube)
    except RuntimeError as exc:
        assert "depth 0" in str(exc)
    else:
        raise AssertionError("expected Cross depth limit failure")


def test_cross_respects_node_limit() -> None:
    cube = scrambled("R U F")
    try:
        CrossSolver(max_depth=8, max_nodes=1).solve(cube)
    except RuntimeError as exc:
        assert "node limit" in str(exc)
    else:
        raise AssertionError("expected Cross node limit failure")
