from rubik_solver.cube.moves import apply_moves
from rubik_solver.cube.parser import inverse_sequence, parse_scramble
from rubik_solver.cube.state import CubeState
from rubik_solver.solvers.search import DepthSearch, heuristic


def test_solution_verification_pipeline() -> None:
    scramble = parse_scramble("R U R' F2 D")
    cube = apply_moves(CubeState.solved(), scramble)
    assert apply_moves(cube, inverse_sequence(scramble)).is_solved()
