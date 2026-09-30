# RubikSolver

Python 3×3 Rubik's Cube solver with a web interface.

Current stage: M0–M4 complete; M5 CFOP is in progress. Cross, F2L, full 1-look OLL (57 cases), and full PLL (21 cases) are implemented and tested; CFOP integration remains the next CFOP phase. Roux and Optimal will be implemented incrementally.

Run tests with `pip install -e ".[dev]"` then `pytest`.

Run API with `uvicorn api.main:app --reload` and frontend with `python -m http.server 5500 --directory frontend`.

See PROJECT_SPEC.md and DEPLOYMENT.md for architecture and deployment details.
