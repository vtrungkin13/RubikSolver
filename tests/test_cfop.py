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


def test_f2l_uses_human_style_move_ordering() -> None:
    from rubik_solver.solvers.cfop import CrossSolver, F2LSolver

    cube = scrambled("R U R' F2 D L2 B U2")
    cross = CrossSolver(max_depth=8, timeout_seconds=5).solve(cube)
    after_cross = apply_moves(cube, cross.moves)
    result = F2LSolver(max_depth=14, timeout_seconds=10).solve(after_cross)

    assert result.metadata["search"] == "IDA* with exact corner-edge pair PDB and human-style move ordering"
    assert all(phase.name.startswith("F2L-") for phase in result.phases)


def test_oll_solves_already_oriented_f2l() -> None:
    from rubik_solver.solvers.cfop import OLLSolver, oll_solved

    result = OLLSolver().solve(CubeState.solved())
    assert result.moves == ()
    assert result.phases[0].name == "OLL"
    assert result.verified is True
    assert oll_solved(CubeState.solved())


def test_oll_solves_sune_and_preserves_f2l() -> None:
    from rubik_solver.solvers.cfop import OLLSolver, f2l_solved, oll_solved

    cube = scrambled("R U R' U R U2 R'")
    assert f2l_solved(cube)
    result = OLLSolver(max_depth=15, timeout_seconds=15).solve(cube)
    after = apply_moves(cube, result.moves)
    assert result.verified is True
    assert oll_solved(after)
    assert f2l_solved(after)


def test_oll_solves_one_look_cases() -> None:
    from rubik_solver.solvers.cfop import (
        OLLSolver,
        _OLL_ALGORITHMS,
        _apply_oll_algorithm,
        _inverse_algorithm,
        f2l_solved,
        oll_solved,
    )

    cases = (
        "F R U R' U' F'",
        "F U R U' R' F'",
        "R U2 R' U' R U R' U' R U' R'",
        "R U2 R2 U' R2 U' R2 U2 R",
        "R2 D R' U2 R D' R' U2 R'",
        "R' F R B' R' F' R B",
        "R U R D R' U' R D' R2",
    )
    solver = OLLSolver()
    for scramble in cases:
        cube = scrambled(scramble)
        result = solver.solve(cube)
        after = _apply_oll_algorithm(cube, " ".join(result.moves))
        assert result.verified is True
        assert oll_solved(after)
        assert f2l_solved(after)

    # Every embedded standard OLL algorithm must be recognized and verified.
    for case_number, algorithm in _OLL_ALGORITHMS:
        cube = _apply_oll_algorithm(CubeState.solved(), _inverse_algorithm(algorithm))
        result = solver.solve(cube)
        after = _apply_oll_algorithm(cube, " ".join(result.moves))
        assert result.verified is True
        assert result.metadata["case"] == case_number
        assert oll_solved(after)
        assert f2l_solved(after)


def test_pll_solves_all_21_cases() -> None:
    from rubik_solver.solvers.cfop import (
        PLLSolver,
        _PLL_ALGORITHMS,
        _apply_oll_algorithm,
        _inverse_algorithm,
        oll_solved,
        pll_solved,
    )

    solver = PLLSolver()
    for case_name, algorithm in _PLL_ALGORITHMS:
        cube = _apply_oll_algorithm(CubeState.solved(), _inverse_algorithm(algorithm))
        result = solver.solve(cube)
        after = _apply_oll_algorithm(cube, " ".join(result.moves))
        assert result.verified is True
        assert result.metadata["case"] == case_name
        assert oll_solved(after)
        assert pll_solved(after)


def test_pll_recognizes_auf_and_y_rotated_case() -> None:
    from rubik_solver.solvers.cfop import PLLSolver, _apply_oll_algorithm, pll_solved

    # This is the exact legal PLL state that previously raised KeyError.
    # It is Gc viewed one y-rotation away, with an AUF before execution.
    cube = CubeState(
        cp=(1, 3, 2, 0, 4, 5, 6, 7),
        co=(0, 0, 0, 0, 0, 0, 0, 0),
        ep=(0, 3, 1, 2, 4, 5, 6, 7, 8, 9, 10, 11),
        eo=(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
    )
    result = PLLSolver().solve(cube)
    after = _apply_oll_algorithm(cube, " ".join(result.moves))

    assert result.verified is True
    assert result.metadata["case"] == "Gc"
    assert result.metadata["search"] == "21-case PLL algorithm database"
    assert pll_solved(after)


def test_cfop_solves_complete_scramble() -> None:
    from rubik_solver.solvers.cfop import CFOPSolver, _apply_oll_algorithm, _cfop_solved

    cube = scrambled("R U R' F2 D")
    result = CFOPSolver(
        cross_timeout_seconds=5,
        f2l_timeout_seconds=10,
        oll_timeout_seconds=10,
    ).solve(cube)
    after = _apply_oll_algorithm(cube, " ".join(result.moves))

    assert result.verified is True
    assert _cfop_solved(after)
    assert [phase.name for phase in result.phases] == [
        "Orientation", "Cross", "F2L-1", "F2L-2", "F2L-3", "F2L-4", "OLL", "PLL"
    ]
    assert result.metadata["algorithm"] == "CFOP"


def test_cfop_orients_before_white_cross_on_d() -> None:
    from rubik_solver.solvers.cfop import (
        CFOPSolver,
        _conjugate_moves,
        _cross_goal,
        _to_x2_coordinate_frame,
    )

    cube = scrambled("R U R' F2 D")
    result = CFOPSolver(
        cross_timeout_seconds=10,
        f2l_timeout_seconds=10,
        oll_timeout_seconds=10,
    ).solve(cube)
    orientation = result.phases[0]
    cross = result.phases[1]
    assert orientation.name == "Orientation"
    assert orientation.moves[0] == "x2"
    assert all(move in {"y", "y'", "y2"} for move in orientation.moves[1:])
    assert cross.name == "Cross"

    y_count = sum(move in {"y", "y'"} for move in orientation.moves[1:])
    inverse_y = " ".join("y'" for _ in range(y_count))
    canonical_cross = _conjugate_moves(inverse_y, cross.moves) if inverse_y else cross.moves
    after_cross = apply_moves(_to_x2_coordinate_frame(cube), canonical_cross)
    assert _cross_goal(after_cross, (4, 5, 6, 7), (4, 5, 6, 7))


def test_cfop_solves_extended_notation_regression_scramble() -> None:
    from rubik_solver.solvers.cfop import CFOPSolver, _apply_oll_algorithm, _cfop_solved

    scramble = "R B2 L2 D L2 D2 B2 L2 D R2 U' B2 L2 F' D' R U R U2 F' R2"
    cube = scrambled(scramble)
    result = CFOPSolver().solve(cube)
    after = _apply_oll_algorithm(cube, " ".join(result.moves))

    assert result.verified is True
    assert _cfop_solved(after)
