# RubikSolver

Python 3×3 Rubik's Cube solver with a web interface.

Current stage: cube-engine bootstrap. The web/API skeleton is present, while Kociemba, CFOP, Roux and Optimal solvers will be implemented incrementally.

Run tests with `pip install -e ".[dev]"` then `pytest`.

Run API with `uvicorn api.main:app --reload` and frontend with `python -m http.server 5500 --directory frontend`.

See PROJECT_SPEC.md and DEPLOYMENT.md for architecture and deployment details.
