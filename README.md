# RubikSolver

Python 3×3 Rubik's Cube solver with a web interface.

Current stage: M0–M4 complete. The cube engine, scramble/validation pipeline, IDA* search foundation, FastAPI API, web skeleton and Kociemba Two-Phase solver are available. CFOP, Roux and Optimal will be implemented incrementally.

Run tests with `pip install -e ".[dev]"` then `pytest`.

Run API with `uvicorn api.main:app --reload` and frontend with `python -m http.server 5500 --directory frontend`.

See PROJECT_SPEC.md and DEPLOYMENT.md for architecture and deployment details.
