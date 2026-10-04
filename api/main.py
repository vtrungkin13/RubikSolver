from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from rubik_solver.cube.moves import apply_moves
from rubik_solver.cube.parser import normalize_scramble, parse_scramble
from rubik_solver.cube.state import CubeState
from rubik_solver.cube.validator import CubeValidationError, validate_cube
from rubik_solver.solvers.registry import SolverUnavailableError, get_solver
from rubik_solver.solvers.kociemba import KociembaSolver
from rubik_solver.model.solution import Solution

app = FastAPI(title="RubikSolver API", version="0.1.0")


class SolveRequest(BaseModel):
    scramble: str = Field(min_length=0, max_length=500)
    method: str = Field(default="kociemba")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


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

    try:
        solver = get_solver(request.method.lower())
        solution = solver.solve(cube)
    except SolverUnavailableError as exc:
        raise HTTPException(501, detail={"code": "SOLVER_UNAVAILABLE", "message": str(exc)}) from exc
    except RuntimeError as exc:
        # Roux is a specialized planner and can legitimately exhaust its
        # phase search on a difficult state. Do not turn that into an API 500:
        # use the complete Kociemba solver as a generic, verified safety net.
        # This is deliberately method-transparent in the response: callers
        # can see that the requested Roux solve fell back to Kociemba.
        if request.method.lower() != "roux":
            raise
        fallback = KociembaSolver().solve(cube)
        solution = Solution(
            method=fallback.method,
            moves=fallback.moves,
            metric=fallback.metric,
            verified=fallback.verified,
            phases=fallback.phases,
            metadata={
                **fallback.metadata,
                "fallback_from": "roux",
                "fallback_reason": str(exc),
            },
        )

    return {
        "method": solution.method,
        "scramble": normalize_scramble(request.scramble),
        "moves": solution.sequence,
        "move_count": solution.move_count,
        "metric": solution.metric,
        "verified": solution.verified,
        "phases": [{"name": p.name, "moves": p.sequence, "move_count": p.move_count, "description": p.description} for p in solution.phases],
        "metadata": solution.metadata,
    }
