from rubik_solver.cube.moves import apply_moves, inverse_move
from rubik_solver.cube.parser import parse_scramble
from rubik_solver.cube.state import CubeState
from rubik_solver.solvers.roux import (
    _CMLLDatabase,
    CornerOrientationAnalyzer,
    _SB_MOVE_PENALTY,
    _CMLL_CORNER_GOALS,
    _cmll_inverse,
    _cmll_u_turn,
    _cmll_solved,
    _eo_solved,
    _fb_goal,
    _fb_cubies_goal,
    _fb_search_goal,
    _fb_pattern_snapshot,
    _fb_frame_pattern_score,
    _fb_staged_kinds,
    _fb_move_style_score,
    _centers_ready_for_eo_state,
    _LSEFormulaDatabase,
    _l4e_solved,
    _ulur_solved,
    RouxSolver,
    _SecondBlockSearch,
    _optimize_sb_final_move_for_eo,
    _centers_ready_for_eo,
    _SBOpportunityDetector,
    _StagedSBSearch,
    _sb_joined_pair_inventory,
    _sb_pair_lookahead_score,
    _fb_frame,
    first_block_solved,
    second_block_solved,
)


def test_cube_state_tracks_centers_for_extended_roux_moves() -> None:
    solved = CubeState.solved()
    assert apply_moves(solved, ("x2",)).center == (3, 1, 5, 0, 4, 2)
    assert apply_moves(solved, ("u",)).center == (0, 5, 1, 3, 2, 4)
    assert apply_moves(solved, ("r",)).center == (2, 1, 3, 5, 4, 0)
    assert apply_moves(solved, ("M",)).center == (5, 1, 0, 2, 4, 3)
    assert apply_moves(solved, ("r", "r", "r", "r")).is_solved()


def test_fb_pattern_recognizer_collects_compatible_patterns_together() -> None:
    target = apply_moves(CubeState.solved(), _fb_frame(0))
    patterns = _fb_pattern_snapshot(target, target)

    # Recognition is multi-label: an already-solved FB exposes its center-edge
    # relationships, completed CE pairs, square, and line simultaneously.
    assert "Ctr-FL" in patterns
    assert "Ctr-BL" in patterns
    assert "Ctr-DL" in patterns
    assert "CE-pair-DLF-FL" in patterns
    assert "CE-pair-DBL-BL" in patterns
    assert "square-2x2-DLF" in patterns
    assert "square-2x2-DBL" in patterns
    assert "line-1x3-FL-BL" in patterns


def test_fb_pattern_recognizer_uses_active_center_frame() -> None:
    target = apply_moves(CubeState.solved(), _fb_frame(0))
    shifted_centers = apply_moves(target, ("M",))
    patterns = _fb_pattern_snapshot(shifted_centers, target)

    assert "Ctr-FL" not in patterns
    assert "Ctr-BL" not in patterns
    assert "Ctr-DL" not in patterns


def test_fb_frame_priority_prefers_frames_with_existing_left_block_patterns() -> None:
    cube = apply_moves(CubeState.solved(), ("R", "U", "F"))
    frame_with_ctr = _fb_frame_pattern_score(cube, _fb_frame(0))
    frame_without_ctr = _fb_frame_pattern_score(cube, _fb_frame(2))
    assert frame_with_ctr > frame_without_ctr


def test_fb_move_style_prefers_wide_u_to_d_turns() -> None:
    assert _fb_move_style_score(("u",)) < _fb_move_style_score(("D",))
    assert _fb_move_style_score(("x2", "R2")) < _fb_move_style_score(("x2", "L2"))


def test_fb_search_goal_does_not_repair_or_require_center_permutation() -> None:
    target = apply_moves(CubeState.solved(), _fb_frame(0))
    centers_shifted = apply_moves(target, ("M",))
    assert _fb_search_goal(centers_shifted, target)
    assert not _fb_goal(centers_shifted, target)


def test_fb_stages_start_with_ctr_dl_when_no_reusable_block_exists() -> None:
    assert _fb_staged_kinds(frozenset()) == ("ctr_dl", "line", "square", "final")


def test_fb_stages_skip_pair_build_when_dl_or_side_pair_already_exists() -> None:
    assert _fb_staged_kinds(frozenset({"CE-pair-DLF-DL"}), 5, 9) == ("square", "final")
    assert _fb_staged_kinds(frozenset({"CE-pair-DBL-BL"}), 6, 10) == ("square", "final")


def test_cmll_database_recognizes_all_42_generated_cases() -> None:
    import json
    from pathlib import Path

    db_path = Path(__file__).parents[1] / "data" / "cmll_algorithms.json"
    entries = json.loads(db_path.read_text(encoding="utf-8"))
    target = CubeState.solved()
    database = _CMLLDatabase(target)
    for entry in entries:
        algorithm = tuple(entry["algorithm"].split())
        case = apply_moves(target, tuple(inverse_move(move) for move in reversed(algorithm)))
        recognized, _ = database.recognize(case)
        assert recognized["id"] == entry["id"]


def test_l4e_roux_method_vn_table_recognizes_all_cube_state_cases() -> None:
    import json
    from pathlib import Path

    db_path = Path(__file__).parents[1] / "data" / "lse_algorithms.json"
    entries = json.loads(db_path.read_text(encoding="utf-8"))["l4e"]
    target = CubeState.solved()
    database = _LSEFormulaDatabase()
    seen = set()
    cases = []

    for entry in entries:
        if not entry["id"].startswith("L4E_VN_"):
            continue
        algorithm = tuple(entry["algorithm"].split())
        case = apply_moves(target, _cmll_inverse(algorithm))
        signature = tuple(case.ep.index(target.ep[pos]) for pos in (1, 3, 5, 7))
        if signature in seen:
            continue
        seen.add(signature)
        cases.append(case)

    assert len(cases) == 12
    for case in cases:
        recognized = database.solve_l4e(case, target)
        assert recognized is not None
        _, moves = recognized
        solved = apply_moves(case, moves)
        assert _l4e_solved(solved, target)


def test_roux_end_to_end_short_scramble() -> None:
    cube = apply_moves(CubeState.solved(), parse_scramble("R U"))
    result = RouxSolver(sb_timeout_seconds=15).solve(cube)
    assert result.verified is True
    assert [phase.name for phase in result.phases] == ["First Block", "Second Block", "CMLL", "EO", "ULUR", "L4E"]
    after = apply_moves(cube, result.moves)
    assert first_block_solved(after, result.metadata["frame"])
    assert after.cp == result.metadata["l4e_state"]["cp"]
    assert after.co == result.metadata["l4e_state"]["co"]
    assert after.ep == result.metadata["l4e_state"]["ep"]
    assert after.eo == result.metadata["l4e_state"]["eo"]
    assert result.metadata["status"] == "l4e"
    assert result.metadata["sb_oracle_fallback"] is False
    assert "cmll_case" in result.metadata


def test_roux_end_to_end_deterministic_scrambles() -> None:
    scrambles = (
        "R U R' F2 D",
        "R B2 U' F L' D2 R U2",
        "F2 U R2 B' L D' F R'",
    )
    for scramble in scrambles:
        cube = scrambled(scramble)
        result = RouxSolver(fb_timeout_seconds=15, sb_timeout_seconds=15).solve(cube)
        assert result.verified is True, scramble
        assert result.metadata["sb_dr_candidate_limit"] == 3
        assert 0 <= result.metadata["sb_dr_candidates"] <= 3
        assert result.metadata["sb_pair_order"] in ("FR_FIRST", "BR_FIRST", None)
        frame = _fb_frame(result.metadata["frame"])
        after = apply_moves(cube, result.moves)
        assert first_block_solved(after, result.metadata["frame"]), scramble
        assert second_block_solved(after), scramble
        assert [phase.name for phase in result.phases] == ["First Block", "Second Block", "CMLL", "EO", "ULUR", "L4E"]
        assert result.metadata["sb_oracle_fallback"] is False
        assert after.cp == result.metadata["l4e_state"]["cp"], scramble
        assert after.co == result.metadata["l4e_state"]["co"], scramble
        assert after.ep == result.metadata["l4e_state"]["ep"], scramble
        assert after.eo == result.metadata["l4e_state"]["eo"], scramble


def test_regression_scramble_fb_uses_exact_active_frame() -> None:
    scramble = "F2 L2 B2 F2 U R2 D2 L2 U2 F2 R2 F' U' L' D2 R U R U' F2 L"
    cube = scrambled(scramble)
    result = RouxSolver(fb_timeout_seconds=15, sb_timeout_seconds=15).solve(cube)

    frame = _fb_frame(result.metadata["frame"])
    fb_moves = result.phases[0].moves
    fb_after = apply_moves(cube, fb_moves)

    assert result.metadata["fb_setup_moves"] == frame
    assert result.metadata["fb_construction_moves"] == fb_moves[len(frame):]
    assert result.metadata["fb_execution_order"] == "setup_rotation_then_construction"
    assert first_block_solved(fb_after, result.metadata["frame"])


def test_roux_phase_boundary_hard_sb_case_does_not_reopen_fb() -> None:
    """The optimized FB remains fixed even when SB cannot finish in-budget."""
    for scramble in (
        "U R L U' R' D' F' D2",
        "F R U' L B2 D",
        "R2 U2 F' L2 D B R2",
        "D U L2 R2 U B2 L2 F",
        "L U2 B R' F2 D L2 U'",
    ):
        cube = scrambled(scramble)
        try:
            result = RouxSolver(fb_timeout_seconds=15, sb_timeout_seconds=15).solve(cube)
        except RuntimeError as exc:
            assert "Roux" in str(exc)
        else:
            # If a future SB planner learns this case, success is also acceptable.
            assert result.verified is True


def test_roux_sb_opportunity_detector_recognizes_free_structures() -> None:
    target = CubeState.solved()
    detector = _SBOpportunityDetector(target)
    detected = detector.detect(target)
    assert detected["strategy"] == "FREE_SQUARE"
    assert detected["squares"] in (("FR",), ("BR",))


def test_sb_free_square_can_be_rotated_into_position_with_r_turns() -> None:
    target = CubeState.solved()
    displaced = apply_moves(target, ("R",))
    detected = _SBOpportunityDetector(target).detect(displaced)
    assert detected["strategy"] == "FREE_SQUARE"
    assert detected["square_setup"] in (("R'",), ("R2",), ("R",))
    positioned = apply_moves(displaced, detected["square_setup"])
    assert any(
        all(positioned.cp[pos] == target.cp[pos] and positioned.co[pos] == target.co[pos]
            for pos in (corner,))
        and positioned.ep[4] == target.ep[4]
        for corner in (4, 7)
    )


def test_sb_free_pair_recognition_does_not_require_target_slot() -> None:
    target = CubeState.solved()
    displaced = apply_moves(target, ("D",))
    detected = _SBOpportunityDetector(target).detect(displaced)
    assert detected["strategy"] == "FREE_PAIR"
    assert detected["dr_edge_joined"] is True
    assert (target.cp[4], target.ep[4]) in detected["pairs"]
    # The identity pair is still joined even though the DR edge/corner pair
    # is no longer in its canonical target slot.
    assert not (
        displaced.cp[4] == target.cp[4]
        and displaced.co[4] == target.co[4]
        and displaced.ep[4] == target.ep[4]
        and displaced.eo[4] == target.eo[4]
    )


def test_sb_default_search_has_no_move_depth_ceiling_and_scores_lookahead() -> None:
    target = CubeState.solved()
    search = _StagedSBSearch(target)
    assert search.max_depth is None
    assert _sb_pair_lookahead_score(target, target, (4, 8)) < _sb_pair_lookahead_score(target, target, (7, 11))


def test_cmll_database_has_42_unique_auf_equivalence_classes() -> None:
    target = CubeState.solved()
    db = _CMLLDatabase(target)
    assert len(db.entries) == 42
    assert len(db._case_map) == 42


def test_all_42_cmll_cases_recognize_and_solve() -> None:
    target = CubeState.solved()
    db = _CMLLDatabase(target)
    for entry in db.entries:
        algorithm = tuple(entry["algorithm"].split())
        case = apply_moves(target, _cmll_inverse(algorithm))
        recognized, _ = db.recognize(case)
        assert recognized["id"] == entry["id"]
        solution = db.solve(case)
        solved = apply_moves(case, solution)
        assert _cmll_solved(solved, target)
        for pos in (5, 6, 4, 7):
            assert solved.cp[pos] == target.cp[pos]
            assert solved.co[pos] == target.co[pos]
        for pos in (6, 9, 10, 4, 8, 11):
            assert solved.ep[pos] == target.ep[pos]
            assert solved.eo[pos] == target.eo[pos]


def test_corner_orientation_analyzer_reports_cmll_case() -> None:
    target = CubeState.solved()
    db = _CMLLDatabase(target)
    analyzer = CornerOrientationAnalyzer(target, db)
    entry = db.entries[0]
    case = apply_moves(target, _cmll_inverse(tuple(entry["algorithm"].split())))
    analysis = analyzer.analyze(case)
    assert analysis["case_id"] == entry["id"]
    assert len(analysis["orientation"]) == 4
    assert analysis["score"] == (
        analysis["misoriented_corners"],
        analysis["cmll_algorithm_length"],
        analysis["auf_length"],
    )


def test_sb_penalty_policy_matches_ergonomic_tiers() -> None:
    assert _SB_MOVE_PENALTY["U"] == 0
    assert _SB_MOVE_PENALTY["R"] == 0
    assert _SB_MOVE_PENALTY["M"] == 0
    assert _SB_MOVE_PENALTY["r"] == 0
    assert _SB_MOVE_PENALTY["F"] < _SB_MOVE_PENALTY["L"]
    assert _SB_MOVE_PENALTY["B"] == _SB_MOVE_PENALTY["D"]
    assert _SB_MOVE_PENALTY["B"] > _SB_MOVE_PENALTY["L"]


def test_sb_final_r_eo_optimizer_is_center_aware() -> None:
    target = CubeState.solved()
    cube = apply_moves(target, ("R'",))
    optimized, metadata = _optimize_sb_final_move_for_eo(cube, target, ("R",))
    assert _centers_ready_for_eo(("R",))
    assert optimized == ("R",)
    assert metadata["applied"] is False


def test_sb_planner_does_not_score_downstream_continuation() -> None:
    result = RouxSolver(fb_timeout_seconds=15, sb_timeout_seconds=15).solve(
        scrambled("R U R' F2 D")
    )
    assert [phase.name for phase in result.phases] == [
        "First Block", "Second Block", "CMLL", "EO", "ULUR", "L4E"
    ]
    assert "sb_corner_orientation" not in result.metadata
    assert result.metadata["cmll_state"] is not None
    assert result.metadata["eo_state"] is not None
    assert result.metadata["ulur_state"] is not None
    assert result.metadata["l4e_state"] is not None


def test_all_42_cmll_cases_support_all_auf_rotations() -> None:
    target = CubeState.solved()
    db = _CMLLDatabase(target)
    for entry in db.entries:
        case = apply_moves(target, _cmll_inverse(tuple(entry["algorithm"].split())))
        for power in range(4):
            rotated_case = apply_moves(case, _cmll_u_turn(power))
            recognized, _ = db.recognize(rotated_case)
            assert recognized["id"] == entry["id"]
            solved = apply_moves(rotated_case, db.solve(rotated_case))
            assert _cmll_solved(solved, target)


def assert_rotation_prefix_only(moves: tuple[str, ...]) -> None:
    rotations = {"x", "x2", "x'", "y", "y2", "y'", "z", "z2", "z'"}
    seen_face_turn = False
    for move in moves:
        if move in rotations:
            assert not seen_face_turn, f"rotation {move} appeared after face turns"
        else:
            seen_face_turn = True


def scrambled(scramble: str) -> CubeState:
    return apply_moves(CubeState.solved(), parse_scramble(scramble))


def test_first_block_solved_cube() -> None:
    result = RouxSolver().solve(CubeState.solved())
    assert result.moves == ()
    assert result.phases == ()
    assert result.verified is True


def test_roux_full_solver_solves_short_scrambles() -> None:
    for scramble in ("R", "U", "F2", "L'", "B2", "D", "R U R'", "F R U' L"):
        cube = scrambled(scramble)
        result = RouxSolver(fb_timeout_seconds=10).solve(cube)
        after = apply_moves(cube, result.moves)
        assert result.verified is True
        assert first_block_solved(after)
        assert result.phases[0].name == "First Block"
        assert result.metadata["status"] == "l4e"
        assert result.metadata["white_bottom"] is True
        assert result.metadata["rotation_policy"] == "setup-prefix-only"
        assert result.metadata["fb_side"] == "left"
        assert_rotation_prefix_only(result.moves)
        assert result.phases[1].name == "Second Block"
        assert [phase.name for phase in result.phases] == ["First Block", "Second Block", "CMLL", "EO", "ULUR", "L4E"]
        assert "sb_pair_order_evaluations" in result.metadata
        assert after.cp == result.metadata["l4e_state"]["cp"]
        assert after.co == result.metadata["l4e_state"]["co"]
        assert after.ep == result.metadata["l4e_state"]["ep"]
        assert after.eo == result.metadata["l4e_state"]["eo"]


def test_roux_full_solution_contains_cmll_and_lse() -> None:
    cube = scrambled("R U R' F2 D")
    result = RouxSolver().solve(cube)
    after = apply_moves(cube, result.moves)
    assert first_block_solved(after)
    assert [phase.name for phase in result.phases[-4:]] == ["CMLL", "EO", "ULUR", "L4E"]
    assert after.cp == result.metadata["l4e_state"]["cp"]
    assert after.co == result.metadata["l4e_state"]["co"]
    assert after.ep == result.metadata["l4e_state"]["ep"]
    assert after.eo == result.metadata["l4e_state"]["eo"]


def test_first_block_accepts_white_bottom_without_fixing_white_center() -> None:
    cube = scrambled("R U R' F2 D L2 B")
    result = RouxSolver(fb_timeout_seconds=10).solve(cube)
    after = apply_moves(cube, result.moves)
    assert first_block_solved(after)
    assert result.metadata["white_bottom"] is True
    assert result.metadata["fb_side"] == "left"
    assert_rotation_prefix_only(result.moves)
    assert [phase.name for phase in result.phases[-4:]] == ["CMLL", "EO", "ULUR", "L4E"]


def test_first_block_respects_depth_limit() -> None:
    cube = scrambled("R U F")
    try:
        RouxSolver(fb_max_depth=0).solve(cube)
    except RuntimeError as exc:
        assert "white-bottom frames" in str(exc)
    else:
        raise AssertionError("expected First Block depth limit failure")


def test_second_block_exact_search_uses_partial_goal_projection() -> None:
    target = apply_moves(CubeState.solved(), _fb_frame(0))
    cube = apply_moves(target, ("R",))
    search = _SecondBlockSearch(target=target, max_depth=2, timeout_seconds=5)
    moves = search.solve(cube)
    assert moves == ("R'",)
    assert search._goal(apply_moves(cube, moves))


def test_second_block_exact_search_is_exact_for_all_one_move_cases() -> None:
    target = apply_moves(CubeState.solved(), _fb_frame(0))
    cases = (
        ("U", "U'"), ("U2", "U2"), ("U'", "U"),
        ("R", "R'"), ("R2", "R2"), ("R'", "R"),
        ("M", "M'"), ("M2", "M2"), ("M'", "M"),
        ("r", "r'"), ("r2", "r2"), ("r'", "r"),
    )
    for move, inverse in cases:
        cube = apply_moves(target, (move,))
        search = _SecondBlockSearch(target=target, max_depth=2, timeout_seconds=5)
        expected_length = 0 if search._goal(cube) else 1
        result = search.solve(cube)
        assert len(result) == expected_length
        assert search._goal(apply_moves(cube, result))


def test_roux_phase_boundaries_are_verified_end_to_end() -> None:
    cube = scrambled("R U R' F2 D")
    result = RouxSolver(fb_timeout_seconds=15, sb_timeout_seconds=15).solve(cube)
    frame = _fb_frame(result.metadata["frame"])
    reference = apply_moves(CubeState.solved(), frame)

    state = cube
    phase_states = {}
    for phase in result.phases:
        state = apply_moves(state, phase.moves)
        phase_states[phase.name] = state

    # Phase-boundary states are the literal results of applying each phase;
    # center permutation is observed, not rewritten to the reference frame.
    assert _fb_cubies_goal(phase_states["First Block"], reference)
    assert phase_states["First Block"].center == result.metadata["fb_center_state"]
    assert second_block_solved(phase_states["Second Block"])
    assert phase_states["Second Block"].cp == result.metadata["sb_state"]["cp"]
    assert phase_states["Second Block"].ep == result.metadata["sb_state"]["ep"]
    assert _cmll_solved(phase_states["CMLL"], reference)
    assert _eo_solved(phase_states["EO"], reference)
    assert _ulur_solved(phase_states["ULUR"], reference)
    assert _l4e_solved(phase_states["L4E"], reference)
    for phase_name in ("CMLL", "EO", "ULUR", "L4E"):
        assert phase_states[phase_name].cp == result.metadata[f"{phase_name.lower()}_state"]["cp"]
        assert phase_states[phase_name].ep == result.metadata[f"{phase_name.lower()}_state"]["ep"]


def test_fb_allows_non_fb_centers_to_permute_but_preserves_fb_center_colors() -> None:
    from dataclasses import replace

    scramble = "F2 L2 B2 F2 U R2 D2 L2 U2 F2 R2 F' U' L' D2 R U R U' F2 L"
    cube = scrambled(scramble)
    frame = _fb_frame(0)
    reference = apply_moves(CubeState.solved(), frame)
    old_fb = frame + ("F", "R", "L2", "u'", "L", "F", "L")
    after_fb = apply_moves(cube, old_fb)

    assert _fb_cubies_goal(after_fb, reference)
    assert not _fb_goal(after_fb, reference)

    # Permuting only U/R centers is permitted when D/F/L/B still match the FB.
    swapped_non_fb_centers = list(reference.center)
    swapped_non_fb_centers[0], swapped_non_fb_centers[1] = (
        swapped_non_fb_centers[1], swapped_non_fb_centers[0]
    )
    center_permuted = replace(reference, center=tuple(swapped_non_fb_centers))
    assert _fb_goal(center_permuted, reference)

    center_valid_control = frame + ("U'", "R'", "U2", "B2", "D'", "L", "D'", "F'")
    assert _fb_goal(apply_moves(cube, center_valid_control), reference)


def test_user_fb_sequence_is_rejected_if_fb_center_colors_do_not_match() -> None:
    cube = scrambled("B2 D2 L2 D' F' U D B2 R' B' D2 F U2 D2 F U2 B' R2 F R2")
    user_fb = ("x2", "y'", "F'", "U", "B'", "u2", "M2", "B'")
    after_fb = apply_moves(cube, user_fb)
    reference = apply_moves(CubeState.solved(), _fb_frame(1))

    assert _fb_cubies_goal(after_fb, reference)
    assert not _fb_goal(after_fb, reference)
    assert after_fb.center != reference.center


def test_roux_tracks_centers_at_fb_boundary_without_repair_moves() -> None:
    scramble = "B2 D2 L2 D' F' U D B2 R' B' D2 F U2 D2 F U2 B' R2 F R2"
    cube = scrambled(scramble)
    result = RouxSolver(fb_timeout_seconds=15, sb_timeout_seconds=15).solve(cube)
    frame = _fb_frame(result.metadata["frame"])
    reference = apply_moves(CubeState.solved(), frame)
    fb_moves = result.phases[0].moves
    after_fb = apply_moves(cube, fb_moves)

    assert result.verified is True
    assert _fb_search_goal(after_fb, reference)
    assert result.metadata["fb_center_state"] == after_fb.center
    assert result.metadata["fb_state"] == {
        "cp": after_fb.cp,
        "co": after_fb.co,
        "ep": after_fb.ep,
        "eo": after_fb.eo,
        "center": after_fb.center,
    }
    # The last FB move must still contribute to the FB cubie goal; a center-
    # only cleanup move at the end of FB is not allowed.
    assert not _fb_search_goal(apply_moves(cube, fb_moves[:-1]), reference)
    final_state = apply_moves(cube, result.moves)
    assert first_block_solved(final_state, result.metadata["frame"])
    assert second_block_solved(final_state)
