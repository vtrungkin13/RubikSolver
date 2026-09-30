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


def test_f2l_solves_already_solved_f2l() -> None:
    from rubik_solver.solvers.cfop import F2LSolver

    result = F2LSolver().solve(CubeState.solved())
    assert result.moves == ()
    assert len(result.phases) == 4
    assert result.verified is True


def test_f2l_solves_scrambles_after_cross() -> None:
    from rubik_solver.solvers.cfop import CrossSolver, F2LSolver, f2l_solved

    scrambles = (
        "R U R' F2 D",
        "R U2 F' L2 D B R2",
        "F R U' L B2 D F2 R' U",
    )
    for scramble in scrambles:
        cube = scrambled(scramble)
        cross = CrossSolver(max_depth=8, timeout_seconds=5).solve(cube)
        after_cross = apply_moves(cube, cross.moves)
        f2l = F2LSolver(max_depth=14, timeout_seconds=10).solve(after_cross)
        after_f2l = apply_moves(after_cross, f2l.moves)
        assert f2l.verified is True
        assert f2l_solved(after_f2l)
        assert len(f2l.phases) == 4


def test_f2l_preserves_cross_and_previous_pairs() -> None:
    from rubik_solver.solvers.cfop import CrossSolver, F2LSolver, f2l_slot_solved

    cube = scrambled("R U R' F2 D L2 B U2")
    cross = CrossSolver(max_depth=8, timeout_seconds=5).solve(cube)
    after_cross = apply_moves(cube, cross.moves)
    solver = F2LSolver(max_depth=14, timeout_seconds=10)
    result = solver.solve(after_cross)
    state = after_cross
    for index, phase in enumerate(result.phases):
        state = apply_moves(state, phase.moves)
        assert cross_solved(state)
        for corner, edge in ((4, 8), (5, 9), (6, 10), (7, 11))[: index + 1]:
            assert f2l_slot_solved(state, corner, edge)
