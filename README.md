# RubikSolver

Python 3×3 Rubik's Cube solver with a web interface.

Current stage: M0–M5 complete. CFOP is integrated end-to-end as Cross → F2L → 1-look OLL (57 cases) → 1-look PLL (21 cases), with full-solution verification and API support. Roux and Optimal will be implemented incrementally.

Run tests with `pip install -e ".[dev]"` then `pytest`.

Run API with `uvicorn api.main:app --reload` and frontend with `python -m http.server 5500 --directory frontend`.

See PROJECT_SPEC.md and DEPLOYMENT.md for architecture and deployment details.
