from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from rubik_solver.cube.moves import apply_moves
from rubik_solver.cube.parser import normalize_scramble, parse_scramble
from rubik_solver.cube.state import CubeState
from rubik_solver.cube.validator import CubeValidationError, validate_cube
from rubik_solver.solvers.registry import SolverUnavailableError, get_solver
from rubik_solver.solvers.kociemba_engine.cube import Cube as FaceletCube

app = FastAPI(title="RubikSolver API", version="0.1.0")

# Allow the local frontend development servers to call the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SolveRequest(BaseModel):
    scramble: str = Field(min_length=0, max_length=500)
    method: str = Field(default="kociemba")


class CubeStateRequest(BaseModel):
    scramble: str = Field(default="", max_length=500)


def _facelets(cube: CubeState) -> str:
    """Serialize the canonical cubie state using the engine's URFDLB order."""
    facelet_cube = FaceletCube()
    facelet_cube.center[:] = cube.center
    facelet_cube.cp[:] = cube.cp
    facelet_cube.co[:] = cube.co
    facelet_cube.ep[:] = cube.ep
    facelet_cube.eo[:] = cube.eo
    return facelet_cube.as_string()


def _is_facelet_solved(facelets: str) -> bool:
    """A visually solved cube may have a rotated whole-cube frame (x/y/z)."""
    return len(facelets) == 54 and all(
        len(set(facelets[offset:offset + 9])) == 1 for offset in range(0, 54, 9)
    )


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/cube/state")
def cube_state(request: CubeStateRequest) -> dict[str, object]:
    """Return the authoritative sticker state for a scramble."""
    try:
        moves = parse_scramble(request.scramble)
        cube = apply_moves(CubeState.solved(), moves)
        validate_cube(cube)
    except CubeValidationError as exc:
        raise HTTPException(422, detail={"code": "INVALID_CUBE", "message": str(exc)}) from exc
    except ValueError as exc:
        raise HTTPException(422, detail={"code": "INVALID_SCRAMBLE", "message": str(exc)}) from exc
    stickers = _facelets(cube)
    return {
        "valid": True,
        "scramble": normalize_scramble(request.scramble),
        "stickers": stickers,
        "is_solved": cube.is_solved(),
    }


@app.post("/api/solve")
def solve(request: SolveRequest) -> dict[str, object]:
    try:
        moves = parse_scramble(request.scramble)
        cube = apply_moves(CubeState.solved(), moves)
        validate_cube(cube)
    except CubeValidationError as exc:
        raise HTTPException(422, detail={"code": "INVALID_CUBE", "message": str(exc)}) from exc
    except ValueError as exc:
        raise HTTPException(422, detail={"code": "INVALID_SCRAMBLE", "message": str(exc)}) from exc

    initial_state = _facelets(cube)

    try:
        solver = get_solver(request.method.lower())
        solution = solver.solve(cube)
    except SolverUnavailableError as exc:
        raise HTTPException(501, detail={"code": "SOLVER_UNAVAILABLE", "message": str(exc)}) from exc
    except RuntimeError as exc:
        # A failed Roux phase search is surfaced directly. Never replace the
        # requested human-style SB strategy with a complete Kociemba solution.
        if request.method.lower() == "roux":
            raise HTTPException(
                422,
                detail={"code": "ROUX_PHASE_FAILED", "message": str(exc)},
            ) from exc
        raise

    solution_moves = parse_scramble(solution.sequence)
    step_states = [initial_state]
    state = cube
    try:
        for move in solution_moves:
            state = apply_moves(state, [move])
            step_states.append(_facelets(state))
    except ValueError as exc:
        raise HTTPException(500, detail={"code": "UNSUPPORTED_SOLUTION_MOVE", "message": str(exc)}) from exc

    return {
        "method": solution.method,
        "scramble": normalize_scramble(request.scramble),
        "moves": " ".join(solution_moves),
        "move_count": len(solution_moves),
        "metric": solution.metric,
        "verified": solution.verified,
        "initial_state": initial_state,
        "step_states": step_states,
        "final_state": step_states[-1],
        "final_is_solved": _is_facelet_solved(step_states[-1]),
        "phases": [{"name": p.name, "moves": p.sequence, "move_count": p.move_count, "description": p.description} for p in solution.phases],
        "metadata": solution.metadata,
    }
