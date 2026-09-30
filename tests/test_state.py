from rubik_solver.cube.state import CubeState


def test_solved_cube() -> None:
    assert CubeState.solved().is_solved()
