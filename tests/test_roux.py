from rubik_solver.cube.moves import apply_moves
from rubik_solver.cube.parser import parse_scramble
from rubik_solver.cube.state import CubeState
from rubik_solver.solvers.roux import (
    _CMLLDatabase,
    _CMLL_CORNER_GOALS,
    _cmll_inverse,
    _cmll_u_turn,
    _cmll_solved,
    RouxSolver,
    _SecondBlockSearch,
    _fb_frame,
    first_block_solved,
    second_block_solved,
)


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


def test_first_block_solves_short_scrambles() -> None:
    for scramble in ("R", "U", "F2", "L'", "B2", "D", "R U R'", "F R U' L"):
        cube = scrambled(scramble)
        result = RouxSolver(fb_timeout_seconds=10).solve(cube)
        after = apply_moves(cube, result.moves)
        assert result.verified is True
        assert first_block_solved(after)
        assert result.phases[0].name == "First Block"
        assert result.metadata["status"] == "cmll"
        assert result.metadata["white_bottom"] is True
        assert result.metadata["rotation_policy"] == "setup-prefix-only"
        assert result.metadata["fb_side"] == "left"
        assert_rotation_prefix_only(result.moves)
        assert result.phases[1].name == "Second Block"
        assert result.phases[2].name == "CMLL"
        after_sb = apply_moves(cube, result.moves)
        assert second_block_solved(after_sb)


def test_first_block_does_not_claim_full_cube_solution() -> None:
    cube = scrambled("R U R' F2 D")
    result = RouxSolver().solve(cube)
    after = apply_moves(cube, result.moves)
    assert first_block_solved(after)
    assert second_block_solved(after)


def test_first_block_accepts_white_bottom_without_fixing_white_center() -> None:
    cube = scrambled("R U R' F2 D L2 B")
    result = RouxSolver(fb_timeout_seconds=10).solve(cube)
    after = apply_moves(cube, result.moves)
    assert first_block_solved(after)
    assert result.metadata["white_bottom"] is True
    assert result.metadata["fb_side"] == "left"
    assert_rotation_prefix_only(result.moves)
    assert second_block_solved(after)


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
