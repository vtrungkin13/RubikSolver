# RubikSolver

Python 3×3 Rubik's Cube solver with a web interface.

Current stage: M0–M5 complete. CFOP is integrated end-to-end as Cross → F2L → 1-look OLL (57 cases) → 1-look PLL (21 cases), with full-solution verification and API support. Roux is in active development and is being used as the first **learning-oriented human-style solver** reference; CFOP improvements remain pending.

## Solver philosophy

The project is intended not only to solve cubes, but to help cubers learn better solving decisions. Solutions should therefore preserve meaningful phase boundaries, expose useful strategy/case metadata, and distinguish human-style planning from optimized or emergency/oracle search.

This philosophy is especially important for Roux SB and will be carried forward when the pending CFOP work resumes, including Cross quality, F2L pair choice/order, lookahead, free-pair opportunities, and ergonomics.

Run tests with `pip install -e ".[dev]"` then `pytest`.

Scrambles accept standard and extended Singmaster notation, including slice moves (`M E S`), cube rotations (`x y z`), and wide turns (`r` or `Rw`, etc.).

Run API with `uvicorn api.main:app --reload` and frontend with `python -m http.server 5500 --directory frontend`.

See PROJECT_SPEC.md and DEPLOYMENT.md for architecture and deployment details.
