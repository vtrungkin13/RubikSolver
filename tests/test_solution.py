from rubik_solver.model.solution import Solution, SolutionPhase


def test_move_count_excludes_whole_cube_rotations() -> None:
    moves = ("x", "y2", "z'", "R", "U2", "M", "r'", "F2")
    solution = Solution(method="Roux", moves=moves)
    phase = SolutionPhase(name="First Block", moves=moves)

    assert solution.move_count == 5
    assert phase.move_count == 5
    # Rotations stay in the displayed/executable sequence; they just do not
    # contribute to the reported move total.
    assert solution.sequence == "x y2 z' R U2 M r' F2"


def test_move_count_does_not_exclude_wide_or_slice_turns() -> None:
    solution = Solution(method="Roux", moves=("x'", "u", "r2", "M'", "z"))
    assert solution.move_count == 3
