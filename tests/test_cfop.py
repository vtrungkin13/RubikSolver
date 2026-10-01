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
        # F2L.moves is the physical, possibly y-rotated sequence. The solver's
        # canonical_moves is the equivalent sequence used to verify the fixed
        # D-Cross coordinate frame.
        from rubik_solver.solvers.cfop import _apply_oll_algorithm
        after_f2l = _apply_oll_algorithm(after_cross, " ".join(f2l.metadata["canonical_moves"]))
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
    from rubik_solver.solvers.cfop import _apply_oll_algorithm

    state = after_cross
    frame = 0
    for index, phase in enumerate(result.phases):
        state = _apply_oll_algorithm(state, " ".join(phase.moves))
        for move in phase.moves:
            if move == "y":
                frame = (frame + 1) % 4
            elif move == "y'":
                frame = (frame - 1) % 4
            elif move == "y2":
                frame = (frame + 2) % 4
        canonical_state = _apply_oll_algorithm(
            state,
            " ".join(("y'",) * frame),
        ) if frame else state
        assert cross_solved(canonical_state)
        solved_order = result.metadata["pair_order"][: index + 1]
        for pair_number in solved_order:
            corner, edge = ((4, 8), (5, 9), (6, 10), (7, 11))[pair_number - 1]
            assert f2l_slot_solved(canonical_state, corner, edge)


def test_f2l_uses_human_style_move_ordering() -> None:
    from rubik_solver.solvers.cfop import CrossSolver, F2LSolver

    cube = scrambled("R U R' F2 D L2 B U2")
    cross = CrossSolver(max_depth=8, timeout_seconds=5).solve(cube)
    after_cross = apply_moves(cube, cross.moves)
    result = F2LSolver(max_depth=14, timeout_seconds=10).solve(after_cross)

    assert result.metadata["search"] == "IDA* with exact pair PDB; dynamic pair ordering and ergonomic scoring"
    assert sorted(result.metadata["pair_order"]) == [1, 2, 3, 4]
    assert len(result.metadata["pair_readiness"]) == 4
    assert all(phase.name.startswith("F2L-") for phase in result.phases)
    # A B-heavy candidate should be replaceable by a y-frame with a more
    # ergonomic R/F execution. The rotation is before the pair, not after it.
    assert "B" not in {move[0] for move in result.phases[2].moves}
    assert any(move in {"y", "y'", "y2"} for move in result.phases[2].moves)
    assert all(move not in {"y", "y'", "y2"} for move in result.phases[-1].moves)


def test_f2l_can_change_pair_order_and_tracks_orientation_budget() -> None:
    from rubik_solver.solvers.cfop import CrossSolver, F2LSolver

    cube = scrambled("R U R' F2 D")
    cross = CrossSolver(max_depth=8, timeout_seconds=5).solve(cube)
    after_cross = apply_moves(cube, cross.moves)
    result = F2LSolver(max_depth=14, timeout_seconds=10).solve(after_cross)

    assert sorted(result.metadata["pair_order"]) == [1, 2, 3, 4]
    assert len(result.metadata["pair_readiness"]) == 4
    assert result.metadata["orientation_changes"] >= 0
    assert result.metadata["orientation_changes"] <= 3


def test_f2l_pair_recognition_prioritizes_ready_and_setup_pairs() -> None:
    from rubik_solver.solvers.cfop import _f2l_pair_readiness

    # A top-layer corner/edge in an adjacent, oriented relationship is a
    # recognized ready pair; an adjacent but non-ready orientation is setup.
    ready = CubeState(
        cp=(4, 1, 2, 3, 0, 5, 6, 7),
        co=(1, 0, 0, 0, 0, 0, 0, 0),
        ep=(8, 1, 2, 3, 4, 5, 6, 7, 0, 9, 10, 11),
        eo=(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
    )
    assert _f2l_pair_readiness(ready, 4, 8) == (0, "u_ready_pair")

    setup = CubeState(
        cp=(4, 1, 2, 3, 0, 5, 6, 7),
        co=(0, 0, 0, 0, 0, 0, 0, 0),
        ep=(8, 1, 2, 3, 4, 5, 6, 7, 0, 9, 10, 11),
        eo=(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
    )
    assert _f2l_pair_readiness(setup, 4, 8) == (2, "u_adjacent_setup")


def test_f2l_integration_selects_ready_pair_before_less_ready_pair() -> None:
    from rubik_solver.solvers.cfop import (
        F2LSolver,
        _apply_oll_algorithm,
        _f2l_pair_readiness,
        f2l_solved,
    )

    # R U R' preserves the solved Cross while putting pair 1 into a
    # recognized ready state. The other three pairs are already in their
    # slots, which is a lower-priority recognition tier (paired_in_slot).
    cube = scrambled("R U R'")
    readiness = [
        _f2l_pair_readiness(cube, corner, edge)
        for corner, edge in ((4, 8), (5, 9), (6, 10), (7, 11))
    ]
    assert readiness[0] == (0, "u_ready_pair")
    assert all(tier == 1 for tier, _ in readiness[1:])

    result = F2LSolver(max_depth=14, timeout_seconds=10).solve(cube)

    assert result.verified is True
    assert result.metadata["pair_order"][0] == 1
    assert result.metadata["pair_readiness"][0] == "u_ready_pair"
    after = _apply_oll_algorithm(cube, " ".join(result.metadata["canonical_moves"]))
    assert f2l_solved(after)


def test_f2l_y_frame_search_preserves_canonical_pair() -> None:
    from rubik_solver.solvers.cfop import (
        CrossSolver,
        F2LSolver,
        _apply_oll_algorithm,
        f2l_slot_solved,
    )

    cube = scrambled("R U2 F2 D")
    cross = CrossSolver(max_depth=8, timeout_seconds=5).solve(cube)
    after_cross = apply_moves(cube, cross.moves)
    solver = F2LSolver(max_depth=14, timeout_seconds=5)
    frame_moves, canonical_moves, _ = solver._search_pair(
        after_cross,
        0,
        (),
        1,
    )

    canonical_after = _apply_oll_algorithm(after_cross, " ".join(canonical_moves))
    assert f2l_slot_solved(canonical_after, 4, 8)

    physical_after = _apply_oll_algorithm(
        after_cross,
        " ".join(("y", *frame_moves, "y'")),
    )
    assert f2l_slot_solved(physical_after, 4, 8)


def test_f2l_y_frame_search_preserves_cross() -> None:
    from rubik_solver.solvers.cfop import CrossSolver, F2LSolver, _apply_oll_algorithm, cross_solved

    cube = scrambled("R U2 F2 D")
    cross = CrossSolver(max_depth=8, timeout_seconds=5).solve(cube)
    after_cross = apply_moves(cube, cross.moves)
    solver = F2LSolver(max_depth=14, timeout_seconds=5)
    frame_moves, canonical_moves, _ = solver._search_pair(
        after_cross,
        0,
        (),
        1,
    )

    canonical_after = _apply_oll_algorithm(after_cross, " ".join(canonical_moves))
    assert cross_solved(canonical_after)

    physical_after = _apply_oll_algorithm(
        after_cross,
        " ".join(("y", *frame_moves, "y'")),
    )
    assert cross_solved(physical_after)


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
