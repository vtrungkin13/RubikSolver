# RubikSolver â€” Session Handoff / Development Trace

> **Má»¥c Ä‘Ã­ch:** ÄÃ¢y lÃ  file truy váº¿t chÃ­nh Ä‘á»ƒ tiáº¿p tá»¥c project giá»¯a cÃ¡c phiÃªn ChatGPT/PalmBridge.
> Má»—i phiÃªn má»›i nÃªn **Ä‘á»c file nÃ y trÆ°á»›c**, sau Ä‘Ã³ kiá»ƒm tra nhanh Git status + test náº¿u cáº§n. KhÃ´ng cáº§n dá»±a vÃ o trÃ­ nhá»› cá»§a phiÃªn trÆ°á»›c.
>
> **Project:** `D:\Coding\Python\RubikSolver`
> **Git:** branch `main`, upstream `origin/main`
> **Last known stable code checkpoint:** M5 OLL two-look phase (latest Git commit)
> **Last verified test result:** `100 passed in 91.90s`
> **Last verified API:** `POST /api/solve` vá»›i method `kociemba` hoáº¡t Ä‘á»™ng vÃ  tráº£ `verified=true`.

---

## 1. TRáº NG THÃI HIá»†N Táº I

### Milestones

| ID | Milestone | Tráº¡ng thÃ¡i | Ghi chÃº |
|---|---|---|---|
| M0 | Bootstrap | âœ… HoÃ n thÃ nh | Python package, pytest, CLI, FastAPI, frontend skeleton + API smoke tests |
| M1 | Cube model + moves | âœ… HoÃ n thÃ nh | Cubie representation + 18 moves + invariant/regression tests |
| M2 | Scramble parser + validator | âœ… HoÃ n thÃ nh | Parser/normalizer/inverse + validation edge-case tests |
| M3 | Search foundation | âœ… HoÃ n thÃ nh | IDA* + admissible heuristic + pruning + resource limits + verification tests |
| M4 | Kociemba | âœ… HoÃ n thÃ nh | Pure-Python vendored engine, solution verification |
| M5 | CFOP | Dang lam | Cross done -> F2L done -> OLL done (1-look 57 cases) -> PLL done (21 cases) |
| M6 | Roux | â³ ChÆ°a lÃ m | FB â†’ SB â†’ CMLL â†’ LSE |
| M7 | Optimal | â³ ChÆ°a lÃ m | IDA* + pruning/PDB/symmetry |
| M8 | Web UI hoÃ n chá»‰nh | â³ ChÆ°a lÃ m | Skeleton cÃ³ sáºµn; cáº§n ná»‘i/render API Ä‘áº§y Ä‘á»§ |

### Æ¯u tiÃªn tiáº¿p theo

**Viá»‡c nÃªn lÃ m ngay: M3 hoÃ n thiá»‡n trÆ°á»›c khi báº¯t Ä‘áº§u M5.**

1. Viáº¿t test trá»±c tiáº¿p cho `DepthSearch`.
2. Kiá»ƒm tra search giáº£i Ä‘Æ°á»£c cÃ¡c scramble ngáº¯n.
3. Kiá»ƒm tra timeout/max-nodes/max-depth vÃ  pruning.
4. Quyáº¿t Ä‘á»‹nh/wire search foundation vÃ o architecture náº¿u CFOP/Optimal sáº½ dÃ¹ng chung.
5. Sau khi M3 Ä‘áº¡t acceptance, báº¯t Ä‘áº§u M5 CFOP.

> KhÃ´ng coi M3 Ä‘Ã£ hoÃ n thÃ nh chá»‰ vÃ¬ file `search.py` Ä‘Ã£ tá»“n táº¡i.

---

## 2. Má»¤C TIÃŠU PROJECT

XÃ¢y dá»±ng Rubik Solver 3Ã—3 vá»›i:

- Input chÃ­nh: Singmaster scramble notation.
- Cube core báº±ng Python.
- Solver backend báº±ng Python.
- FastAPI lÃ m HTTP API.
- HTML/CSS/JavaScript lÃ m frontend.
- KhÃ´ng dÃ¹ng camera/áº£nh/sticker input á»Ÿ giai Ä‘oáº¡n Ä‘áº§u.
- Má»—i solver pháº£i tá»± verify solution báº±ng cÃ¡ch apply solution lÃªn cube Ä‘Ã£ scramble.

CÃ¡c solver má»¥c tiÃªu:

1. CFOP
2. Roux
3. Kociemba / Two-Phase
4. Optimal / God's-algorithm-style search

**LÆ°u Ã½:** Optimal nghÄ©a lÃ  tÃ¬m solution ngáº¯n nháº¥t theo metric Ä‘Æ°á»£c cáº¥u hÃ¬nh; khÃ´ng Ä‘Æ°á»£c gá»i má»™t solver nhanh lÃ  "optimal".

---

## 3. KIáº¾N TRÃšC ÄÃƒ CHá»T

Luá»“ng chÃ­nh:

```
Scramble
   â†“
Parser
   â†“
CubeState
   â†“
Validator
   â†“
SolverStrategy
   â†“
Solution
   â†“
Verification
   â†“
FastAPI / CLI / Frontend
```

NguyÃªn táº¯c:

- Frontend khÃ´ng chá»©a solver logic.
- FastAPI khÃ´ng chá»©a cube logic.
- Solver khÃ´ng phá»¥ thuá»™c FastAPI.
- Cube engine dÃ¹ng chung cho má»i solver.
- KhÃ´ng hard-code solution theo scramble cá»¥ thá»ƒ.
- Correctness pháº£i Ä‘Æ°á»£c test trÆ°á»›c optimization.
- Solver khÃ´ng mutate input cube ngoÃ i contract rÃµ rÃ ng.

---

## 4. Cáº¤U TRÃšC HIá»†N Táº I

```
RubikSolver/
â”œâ”€â”€ PROJECT_SPEC.md
â”œâ”€â”€ DEPLOYMENT.md
â”œâ”€â”€ README.md
â”œâ”€â”€ WORKLOG.md                  â† FILE TRUY Váº¾T NÃ€Y
â”œâ”€â”€ THIRD_PARTY_NOTICES.md
â”œâ”€â”€ pyproject.toml
â”œâ”€â”€ api/
â”‚   â”œâ”€â”€ __init__.py
â”‚   â””â”€â”€ main.py
â”œâ”€â”€ frontend/
â”‚   â”œâ”€â”€ index.html
â”‚   â”œâ”€â”€ style.css
â”‚   â””â”€â”€ app.js
â”œâ”€â”€ src/
â”‚   â””â”€â”€ rubik_solver/
â”‚       â”œâ”€â”€ __init__.py
â”‚       â”œâ”€â”€ __main__.py
â”‚       â”œâ”€â”€ cli.py
â”‚       â”œâ”€â”€ cube/
â”‚       â”‚   â”œâ”€â”€ __init__.py
â”‚       â”‚   â”œâ”€â”€ state.py
â”‚       â”‚   â”œâ”€â”€ moves.py
â”‚       â”‚   â”œâ”€â”€ parser.py
â”‚       â”‚   â””â”€â”€ validator.py
â”‚       â”œâ”€â”€ model/
â”‚       â”‚   â”œâ”€â”€ __init__.py
â”‚       â”‚   â””â”€â”€ solution.py
â”‚       â””â”€â”€ solvers/
â”‚           â”œâ”€â”€ __init__.py
â”‚           â”œâ”€â”€ base.py
â”‚           â”œâ”€â”€ registry.py
â”‚           â”œâ”€â”€ search.py
â”‚           â”œâ”€â”€ kociemba.py
â”‚           â””â”€â”€ kociemba_engine/
â”‚               â””â”€â”€ ... vendored Kociemba engine ...
â””â”€â”€ tests/
    â”œâ”€â”€ test_state.py
    â”œâ”€â”€ test_parser.py
    â”œâ”€â”€ test_moves.py
    â”œâ”€â”€ test_validator.py
    â”œâ”€â”€ test_solvers.py
    â””â”€â”€ test_kociemba.py
```

---

## 5. CUBE MODEL â€” ÄÃƒ XÃC NHáº¬N

### Corners

```
0 URF
1 UFL
2 ULB
3 UBR
4 DFR
5 DLF
6 DBL
7 DRB
```

### Edges

```
0 UR
1 UF
2 UL
3 UB
4 DR
5 DF
6 DL
7 DB
8 FR
9 FL
10 BL
11 BR
```

`CubeState` gá»“m:

- `cp[8]` â€” corner permutation
- `co[8]` â€” corner orientation
- `ep[12]` â€” edge permutation
- `eo[12]` â€” edge orientation

Solved state = identity permutation + orientation toÃ n 0.

---

## 6. MOVE ENGINE â€” ÄÃƒ HOÃ€N THÃ€NH

18 moves:

```
U U' U2
D D' D2
L L' L2
R R' R2
F F' F2
B B' B2
```

Invariant báº¯t buá»™c Ä‘Ã£ Ä‘Æ°á»£c test:

- Move + inverse â†’ state ban Ä‘áº§u.
- `X2 == X + X`.
- `X4 == identity`.
- Scramble + inverse(scramble) â†’ solved.

### Bug quan trá»ng Ä‘Ã£ sá»­a

Trong quÃ¡ trÃ¬nh tÃ­ch há»£p Kociemba, mapping edge cá»§a **D move** bá»‹ sai.

ÄÃ£ sá»­a tá»«:

```
(0,1,2,3,7,4,5,6,8,9,10,11)
```

thÃ nh:

```
(0,1,2,3,5,6,7,4,8,9,10,11)
```

Corner mapping cá»§a D giá»¯ nguyÃªn:

```
(0,1,2,3,5,6,7,4)
```

Bug nÃ y pháº£i Ä‘Æ°á»£c coi lÃ  regression-sensitive: náº¿u sá»­a move engine sau nÃ y, pháº£i giá»¯ cÃ¡c invariant tests.

---

## 7. PARSER + VALIDATOR

Parser há»— trá»£:

```
U D L R F B
U' D' L' R' F' B'
U2 D2 L2 R2 F2 B2
```

Parser pháº£i:

- bá» whitespace thá»«a;
- reject token khÃ´ng há»£p lá»‡;
- giá»¯ Ä‘Ãºng thá»© tá»± move;
- táº¡o inverse sequence;
- há»— trá»£ normalization.

Validator kiá»ƒm tra:

- Ä‘á»§/Ä‘Ãºng 8 corners;
- Ä‘á»§/Ä‘Ãºng 12 edges;
- khÃ´ng duplicate/missing cubie;
- `sum(co) % 3 == 0`;
- `sum(eo) % 2 == 0`;
- corner/edge permutation parity phÃ¹ há»£p.

M2 Ä‘Æ°á»£c coi lÃ  **Ä‘Ã£ cÃ³ chá»©c nÄƒng chÃ­nh**, nhÆ°ng cáº§n hoÃ n thiá»‡n test coverage theo acceptance cá»§a M2/M3.

---

## 8. SEARCH FOUNDATION â€” ÄÃƒ HOÃ€N THÃ€NH

File:

```
src/rubik_solver/solvers/search.py
```

Hiá»‡n cÃ³:

- `DepthSearch` triá»ƒn khai IDA*;
- heuristic admissible dá»±a trÃªn sá»‘ cubie sai vá»‹ trÃ­;
- move ordering deterministic;
- same-face pruning;
- max depth;
- timeout;
- max nodes;
- `SearchResult` gá»“m moves/nodes/depth/elapsed time;
- solution verification thÃ´ng qua `apply_moves` trong test suite.

Heuristic:

```
max(
    (misplaced_corners + 3) // 4,
    (misplaced_edges + 3) // 4
)
```

### Acceptance Ä‘Ã£ Ä‘áº¡t

- solved cube â†’ empty solution;
- má»™t move â†’ lá»i giáº£i 1 move;
- nhiá»u scramble ngáº¯n â†’ solution há»£p lá»‡;
- apply solution â†’ solved;
- max-depth failure;
- max-nodes failure;
- timeout;
- pruning khÃ´ng lÃ m máº¥t solution há»£p lá»‡.

### Decision

`DepthSearch` Ä‘Æ°á»£c giá»¯ lÃ m search foundation dÃ¹ng chung cho cÃ¡c solver cáº§n search sau nÃ y. M3 khÃ´ng pháº£i solver optimal; heuristic hiá»‡n táº¡i chá»‰ Ä‘á»§ cho correctness/search foundation vÃ  sáº½ Ä‘Æ°á»£c thay báº±ng pruning máº¡nh hÆ¡n á»Ÿ M7 náº¿u cáº§n.

---

## 9. KOCIEMBA â€” ÄÃƒ HOÃ€N THÃ€NH

### Implementation

File:

```
src/rubik_solver/solvers/kociemba.py
```

Äáº·c Ä‘iá»ƒm:

- `KociembaSolver(Solver)`
- method = `kociemba`
- lazy initialization cá»§a engine tables;
- convert `CubeState` â†’ engine cube;
- gá»i vendored pure-Python Kociemba;
- parse solution vá» move sequence cá»§a project;
- apply solution lÃªn scrambled cube Ä‘á»ƒ verify;
- tráº£ `Solution`.

Metadata:

```
{
  "algorithm": "Kociemba Two-Phase",
  "engine": "pure-python"
}
```

Metric: **HTM**

### Test Ä‘Ã£ cÃ³

`tests/test_kociemba.py` kiá»ƒm tra:

- solved cube;
- `R U R' F2 D`;
- scramble dÃ i hÆ¡n;
- solution thá»±c sá»± Ä‘Æ°a cube vá» solved.

### Káº¿t quáº£ Ä‘Ã£ xÃ¡c nháº­n

Scramble:

```
R U R' F2 D
```

Solution tá»«ng cháº¡y thÃ nh cÃ´ng:

```
D' L D' L D2 F2 U' R2 U R2 D' F2 L2 U' F2
```

15 moves, `verified=true`.

---

## 10. REGISTRY HIá»†N Táº I

Hiá»‡n solver registry Ä‘Ã£ Ä‘Äƒng kÃ½:

```
kociemba -> KociembaSolver
```

CÃ¡c method cÃ²n láº¡i chÆ°a implementation:

```
cfop
roux
optimal
```

KhÃ´ng Ä‘Æ°á»£c giáº£ vá» tráº£ solution cho method chÆ°a implement.

---

## 11. API â€” ÄÃƒ XÃC NHáº¬N

Endpoint:

```
POST /api/solve
```

Health:

```
GET /api/health
```

ÄÃ£ test thá»±c táº¿ báº±ng Uvicorn.

Request Ä‘Ã£ test:

```json
{
  "scramble": "R U R' F2 D",
  "method": "kociemba"
}
```

Response thá»±c táº¿ Ä‘Ã£ xÃ¡c nháº­n cÃ³:

```
{
  "method": "kociemba",
  "scramble": "R U R' F2 D",
  "moves": "...",
  "move_count": 15,
  "metric": "HTM",
  "verified": true,
  "phases": [],
  "metadata": {
    "algorithm": "Kociemba Two-Phase",
    "engine": "pure-python"
  }
}
```

### Lá»‡nh cháº¡y API

```powershell
cd D:\Coding\Python\RubikSolver
uvicorn api.main:app --reload
```

Swagger:

```
http://127.0.0.1:8000/docs
```

---

## 12. Má»˜T Sá»° Cá» MÃ”I TRÆ¯á»œNG ÄÃƒ Xá»¬ LÃ

CÃ³ package ngoÃ i:

```
rubik-solver-py==0.1.1
```

Package nÃ y dÃ¹ng top-level namespace `rubik_solver`, gÃ¢y conflict vá»›i package cá»§a project vÃ  táº¡o lá»—i:

```
ModuleNotFoundError:
No module named 'rubik_solver.cube.moves';
'rubik_solver.cube' is not a package
```

ÄÃ£ xá»­ lÃ½ báº±ng cÃ¡ch uninstall package ngoÃ i:

```powershell
python -m pip uninstall -y rubik-solver-py
```

Kociemba engine Ä‘Ã£ Ä‘Æ°á»£c vendored vÃ o project nÃªn **khÃ´ng cáº§n package ngoÃ i nÃ y**.

Sau khi uninstall Ä‘Ã£ xÃ¡c nháº­n:

```
import rubik_solver
â†’ D:\Coding\Python\RubikSolver\src\rubik_solver\__init__.py

import api.main
â†’ api import ok

pytest
â†’ 41 passed in 0.18s
```

**KhÃ´ng cÃ i láº¡i `rubik-solver-py` náº¿u khÃ´ng cÃ³ lÃ½ do kiáº¿n trÃºc ráº¥t rÃµ rÃ ng.**

---

## 13. THIRD-PARTY / KOCIEMBA

Kociemba engine Ä‘Ã£ Ä‘Æ°á»£c vendored vÃ o:

```
src/rubik_solver/solvers/kociemba_engine/
```

ThÃ´ng tin license/source Ä‘Æ°á»£c ghi trong:

```
THIRD_PARTY_NOTICES.md
```

Dependency runtime hiá»‡n táº¡i trong `pyproject.toml` gá»“m:

- FastAPI
- uvicorn
- Pydantic
- NumPy
- httpx (dev dependency for FastAPI TestClient)

KhÃ´ng phá»¥ thuá»™c package `rubik-solver-py` bÃªn ngoÃ i ná»¯a.

---

## 14. TEST BASELINE

Baseline cuá»‘i cÃ¹ng Ä‘Ã£ xÃ¡c nháº­n:

```
41 passed in 0.18s
```

TrÆ°á»›c má»—i milestone lá»›n:

1. cháº¡y toÃ n bá»™ pytest;
2. cháº¡y test má»›i cá»§a milestone;
3. test solution verification;
4. náº¿u API liÃªn quan thÃ¬ test endpoint;
5. kiá»ƒm tra Git diff;
6. chá»‰ commit khi working tree/code á»•n Ä‘á»‹nh.

---

## 15. GIT / CHECKPOINT

Tráº¡ng thÃ¡i cuá»‘i Ä‘Ã£ xÃ¡c nháº­n:

```
branch: main
upstream: origin/main
working tree: clean
HEAD: b2e6f3625448264c7dba1f6f6de07880d3baacd
```

Commit M4:

```
b2e6f36 Implement Kociemba two-phase solver
```

Repo:

```
vtrungkin13/RubikSolver
```

Khi báº¯t Ä‘áº§u phiÃªn má»›i, luÃ´n kiá»ƒm tra:

```powershell
cd D:\Coding\Python\RubikSolver
git status
pytest
```

Náº¿u `git status` khÃ´ng clean, **khÃ´ng Ä‘Æ°á»£c giáº£ Ä‘á»‹nh code giá»‘ng checkpoint nÃ y**.

---

## 16. Káº¾ HOáº CH TIáº¾P THEO

### M3 â€” Search Foundation

**Tráº¡ng thÃ¡i:** ðŸŸ¡ In progress

Checklist:

- [ ] Test `DepthSearch` solved state.
- [ ] Test one-move state.
- [ ] Test short scramble.
- [ ] Verify returned solution.
- [ ] Test max depth.
- [ ] Test max nodes.
- [ ] Test timeout.
- [ ] Test pruning.
- [ ] XÃ¡c Ä‘á»‹nh interface dÃ¹ng chung cho CFOP/Optimal.
- [ ] Cháº¡y full pytest.
- [ ] Commit milestone.

**Acceptance:**

> Search giáº£i Ä‘Æ°á»£c cÃ¡c scramble ngáº¯n vÃ  tá»± verify solution.

---

### M5 â€” CFOP

Sau khi M3 pass:

#### Cross
- [ ] XÃ¡c Ä‘á»‹nh cross target/state.
- [ ] Cross solver.
- [ ] Cross verification.
- [ ] Tests.

#### F2L
- [ ] Pair/case recognition.
- [ ] Basic case solving.
- [ ] Search-assisted solving náº¿u phÃ¹ há»£p.
- [ ] F2L phase verification.
- [ ] Tests.

#### OLL
- [ ] Case recognition.
- [ ] Algorithm table.
- [ ] Apply algorithm.
- [ ] Tests.

#### PLL
- [ ] Case recognition.
- [ ] Algorithm table.
- [ ] Apply algorithm.
- [ ] Tests.

#### CFOP integration
- [ ] `CFOPSolver`.
- [ ] Cross â†’ F2L â†’ OLL â†’ PLL.
- [ ] Phase output.
- [ ] Full solution verification.
- [ ] Registry.
- [ ] API test.

**KhÃ´ng gá»i solution lÃ  "optimal CFOP" náº¿u chÆ°a cÃ³ objective/search chá»©ng minh.**

---

### M6 â€” Roux

```
First Block
    â†“
Second Block
    â†“
CMLL
    â†“
LSE
```

TÃ¡ch solver theo phase vÃ  verify tá»«ng phase.

---

### M7 â€” Optimal

Má»¥c tiÃªu:

- HTM trÆ°á»›c.
- IDA*.
- Coordinate representation.
- Pattern databases / pruning tables.
- Symmetry reduction.
- Move pruning.
- Benchmark vá»›i scramble ngáº¯n Ä‘Ã£ biáº¿t.

**KhÃ´ng báº¯t Ä‘áº§u báº±ng brute-force thuáº§n tÃºy.**

---

### M8 â€” Web UI

Sau khi solver backend á»•n Ä‘á»‹nh:

- [ ] Connect frontend â†’ `POST /api/solve`.
- [ ] Loading state.
- [ ] Error state.
- [ ] Move count.
- [ ] Metric.
- [ ] Verified status.
- [ ] Phase list.
- [ ] Tá»•ng solution.
- [ ] Copy solution.
- [ ] Step-by-step move interaction.
- [ ] Optional cube visualization.
- [ ] Compare methods.

---

## 17. QUY Táº®C CHO PHIÃŠN CHATGPT Má»šI

Khi má»™t phiÃªn má»›i tiáº¿p quáº£n project:

### BÆ°á»›c 1 â€” Äá»c file nÃ y

```
WORKLOG.md
```

### BÆ°á»›c 2 â€” Kiá»ƒm tra tráº¡ng thÃ¡i thá»±c táº¿

```powershell
cd D:\Coding\Python\RubikSolver
git status
pytest
```

KhÃ´ng tin tuyá»‡t Ä‘á»‘i tráº¡ng thÃ¡i ghi trong file náº¿u Git/test hiá»‡n táº¡i mÃ¢u thuáº«n.

### BÆ°á»›c 3 â€” XÃ¡c Ä‘á»‹nh task

Láº¥y **"Káº¾ HOáº CH TIáº¾P THEO"** lÃ m source of truth.

Náº¿u user yÃªu cáº§u má»™t viá»‡c khÃ¡c, Æ°u tiÃªn yÃªu cáº§u má»›i nhÆ°ng pháº£i cáº­p nháº­t file nÃ y sau khi hoÃ n thÃ nh.

### BÆ°á»›c 4 â€” Sau má»—i thay Ä‘á»•i quan trá»ng

Cáº­p nháº­t:

- tráº¡ng thÃ¡i milestone;
- viá»‡c Ä‘Ã£ hoÃ n thÃ nh;
- bug/decision má»›i;
- test result;
- commit hash náº¿u Ä‘Ã£ commit;
- **NEXT ACTION**.

### BÆ°á»›c 5 â€” Káº¿t thÃºc phiÃªn

Pháº£i Ä‘á»ƒ láº¡i má»™t checkpoint Ä‘á»§ Ä‘á»ƒ phiÃªn sau cÃ³ thá»ƒ tiáº¿p tá»¥c mÃ  khÃ´ng cáº§n há»i láº¡i:

```
LAST ACTION:
- ...

CURRENT STATE:
- ...

TEST:
- ...

GIT:
- ...

NEXT ACTION:
- ...
```

---

## 18. SESSION LOG

### 2026-09-30 â€” Kociemba/API checkpoint

**ÄÃ£ lÃ m:**
- HoÃ n thiá»‡n Kociemba Two-Phase integration.
- Vendored pure-Python Kociemba engine.
- Sá»­a D-edge mapping bug.
- ThÃªm Kociemba tests.
- Xá»­ lÃ½ namespace conflict vá»›i `rubik-solver-py`.
- Uninstall package ngoÃ i gÃ¢y conflict.
- XÃ¡c nháº­n API import.
- XÃ¡c nháº­n `POST /api/solve` vá»›i Kociemba.
- XÃ¡c nháº­n solution verification.
- Push commit M4 lÃªn GitHub.

**Test:**
```
41 passed in 0.18s
```

**Git:**
```
b2e6f36 Implement Kociemba two-phase solver
working tree clean
```

**NEXT ACTION:**
> M3 Search Foundation Ä‘Ã£ hoÃ n thÃ nh; tiáº¿p tá»¥c M5 CFOP.

---

## 19. NEXT ACTION â€” LUÃ”N Äá»ŒC PHáº¦N NÃ€Y TRÆ¯á»šC

**Task hiá»‡n táº¡i: M5 â€” CFOP**

M0â€“M4 Ä‘Ã£ Ä‘áº¡t acceptance. Viá»‡c tiáº¿p theo:

1. Thiáº¿t káº¿ `CFOPSolver` theo phase Cross â†’ F2L â†’ OLL â†’ PLL.
2. Báº¯t Ä‘áº§u Cross solver + verification tests.
3. Sau Cross má»›i triá»ƒn khai F2L, OLL, PLL.
4. Má»—i phase pháº£i verify tráº¡ng thÃ¡i trÆ°á»›c khi chuyá»ƒn phase tiáº¿p theo.
5. Chá»‰ Ä‘Äƒng kÃ½ `cfop` vÃ o registry khi solver cÃ³ implementation thá»±c sá»±.

KhÃ´ng gá»i solution lÃ  "optimal CFOP" náº¿u chÆ°a cÃ³ objective/search chá»©ng minh.

---

## 20. QUY Æ¯á»šC Cáº¬P NHáº¬T FILE NÃ€Y

File nÃ y lÃ  **handoff/checkpoint**, khÃ´ng pháº£i tÃ i liá»‡u thiáº¿t káº¿ chi tiáº¿t.

- Thiáº¿t káº¿ kiáº¿n trÃºc â†’ `PROJECT_SPEC.md`
- Deployment â†’ `DEPLOYMENT.md`
- Dependency/license â†’ `THIRD_PARTY_NOTICES.md`
- Tiáº¿n Ä‘á»™, bug, decision, test baseline, viá»‡c tiáº¿p theo â†’ **`WORKLOG.md`**

Khi thÃ´ng tin trong file nÃ y thay Ä‘á»•i, Æ°u tiÃªn cáº­p nháº­t ngay sau khi task hoÃ n táº¥t thay vÃ¬ Ä‘á»ƒ cuá»‘i nhiá»u phiÃªn.

### 2026-09-30 â€” HoÃ n thiá»‡n M0â€“M3

**ÄÃ£ lÃ m:**
- Bá»• sung API smoke tests cho M0: health, solve thÃ nh cÃ´ng, invalid scramble vÃ  unavailable solver.
- Bá»• sung parser/normalizer edge-case tests vÃ  validator orientation/permutation tests cho M2.
- NÃ¢ng DepthSearch thÃ nh IDA* thá»±c sá»± vá»›i threshold theo heuristic.
- Giá»¯ heuristic admissible dá»±a trÃªn misplaced corners/edges.
- Bá»• sung same-face pruning, max-depth, max-nodes vÃ  timeout handling.
- Bá»• sung test solved/one-move/short-scramble/verification/resource-limit/pruning cho M3.
- Cáº­p nháº­t PROJECT_SPEC.md Ä‘á»ƒ M0â€“M3 cÃ³ acceptance rÃµ rÃ ng vÃ  Ä‘Ã¡nh dáº¥u hoÃ n thÃ nh.
- Cáº­p nháº­t README vÃ  Worklog; NEXT ACTION chuyá»ƒn sang M5 CFOP.

**Test:**
63 passed in 0.69s

**Decision:**
M0â€“M3 Ä‘Æ°á»£c coi lÃ  hoÃ n thÃ nh. DepthSearch lÃ  search foundation, khÃ´ng pháº£i Optimal solver.

**NEXT ACTION:**
M5 â€” CFOP, báº¯t Ä‘áº§u tá»« Cross solver + verification.

Git checkpoint: d71dbff Complete M0-M3 foundations

### 2026-09-30 â€” ChÃ­nh thá»©c hÃ³a Project Handoff Rule

**ÄÃ£ lÃ m:**
- ThÃªm quy táº¯c phÃ¡t triá»ƒn/handoff chÃ­nh thá»©c vÃ o `PROJECT_SPEC.md`.
- Quy Ä‘á»‹nh má»i phiÃªn má»›i pháº£i Ä‘á»c `WORKLOG.md` trÆ°á»›c khi tiáº¿p tá»¥c.
- Quy Ä‘á»‹nh má»i thay Ä‘á»•i source code, tests, configuration hoáº·c architecture pháº£i cáº­p nháº­t `WORKLOG.md` trong cÃ¹ng phiÃªn.
- XÃ¡c Ä‘á»‹nh `WORKLOG.md` lÃ  nguá»“n theo dÃµi tiáº¿n Ä‘á»™/handoff; Git vÃ  test thá»±c táº¿ Ä‘Æ°á»£c Æ°u tiÃªn náº¿u mÃ¢u thuáº«n.

**Decision:**
> KhÃ´ng cáº§n user nháº¯c viá»‡c cáº­p nháº­t `WORKLOG.md`; Ä‘Ã¢y lÃ  quy Æ°á»›c máº·c Ä‘á»‹nh cá»§a project.

**Test:**
- KhÃ´ng thay Ä‘á»•i source code; chÆ°a cáº§n cháº¡y full test suite cho thay Ä‘á»•i tÃ i liá»‡u nÃ y.

**NEXT ACTION:**
- Tiáº¿p tá»¥c M3 â€” Search Foundation theo checklist hiá»‡n cÃ³.

### 2026-09-30 â€” M5 CFOP: hoÃ n thiá»‡n Cross phase

**ÄÃ£ lÃ m:**
- Táº¡o `src/rubik_solver/solvers/cfop.py` vá»›i `CrossSolver` cho phase Cross cá»§a CFOP.
- Chá»n Cross chuáº©n theo D-layer: bá»‘n edge `DR, DF, DL, DB` pháº£i Ä‘Ãºng vá»‹ trÃ­ vÃ  orientation.
- Implement Cross search báº±ng IDA* vá»›i pruning cÃ¹ng máº·t liÃªn tiáº¿p vÃ  resource limits: max depth, max nodes, timeout.
- ThÃªm exact pattern database cho abstraction 4 cross edges Ä‘á»ƒ heuristic lÃ  khoáº£ng cÃ¡ch chÃ­nh xÃ¡c cá»§a Cross, thay cho heuristic yáº¿u dá»±a trÃªn sá»‘ edge sai.
- Táº¡o `tests/test_cfop.py` cho solved cube, single-turn cases, nhiá»u scramble, depth limit vÃ  node limit.
- ChÆ°a Ä‘Äƒng kÃ½ `cfop` vÃ o solver registry vÃ¬ F2L/OLL/PLL chÆ°a hoÃ n thÃ nh; trÃ¡nh expose má»™t solver CFOP chÆ°a giáº£i toÃ n bá»™ cube.

**Bug/Ä‘iá»u chá»‰nh trong quÃ¡ trÃ¬nh lÃ m:**
- Láº§n cháº¡y Ä‘áº§u gáº·p `AttributeError` do `_CrossSearch` dÃ¹ng `slots=True` nhÆ°ng `nodes/started/path` chÆ°a khai bÃ¡o field; Ä‘Ã£ sá»­a báº±ng `dataclasses.field(init=False, ...)`.
- Heuristic Ä‘áº§u tiÃªn quÃ¡ yáº¿u khiáº¿n má»™t scramble timeout sau ~752k nodes; Ä‘Ã£ thay báº±ng exact Cross pattern database. Bá»™ test Cross sau tá»‘i Æ°u cháº¡y pass.

**Test:**
```text
Cross tests: 5 passed in 3.85s
Full suite: 68 passed in 4.52s
```

**Decision:**
- Cross solver hiá»‡n lÃ  má»™t phase solver Ä‘á»™c láº­p, tráº£ `SolutionPhase(name="Cross")` vÃ  verify tráº¡ng thÃ¡i Cross sau khi giáº£i.
- M5 chÆ°a hoÃ n thÃ nh cho tá»›i khi cÃ³ F2L â†’ OLL â†’ PLL vÃ  CFOPSolver giáº£i Ä‘Æ°á»£c toÃ n cube.

**Milestone:**
- M5 CFOP: Ä‘ang thá»±c hiá»‡n â€” **Cross hoÃ n thÃ nh**, F2L/OLL/PLL chÆ°a lÃ m.

**NEXT ACTION:**
1. Thiáº¿t káº¿ F2L solver dá»±a trÃªn tá»«ng corner-edge pair.
2. ThÃªm predicate/verification cho F2L vÃ  test tá»«ng case.
3. Sau khi F2L á»•n Ä‘á»‹nh má»›i triá»ƒn khai OLL.

Git: working tree Ä‘ang cÃ³ 2 file má»›i chÆ°a commit: `src/rubik_solver/solvers/cfop.py`, `tests/test_cfop.py`.

### 2026-09-30 â€” Chuáº©n hÃ³a charset/Unicode tiáº¿ng Viá»‡t

**ÄÃ£ lÃ m:**
- PhÃ¡t hiá»‡n `WORKLOG.md` bá»‹ trá»™n UTF-8 vÃ  Windows-1252 do láº§n ghi trÆ°á»›c báº±ng PowerShell `Add-Content`.
- Chuyá»ƒn toÃ n bá»™ `WORKLOG.md` vá» UTF-8 thuáº§n vÃ  sá»­a láº¡i pháº§n M5 bá»‹ mojibake.
- ThÃªm `.editorconfig` vá»›i `charset = utf-8`, LF vÃ  final newline.
- Frontend khai bÃ¡o `lang="vi"` vÃ  Æ°u tiÃªn font `Segoe UI`, `Noto Sans`, Arial; HTML Ä‘Ã£ cÃ³ `meta charset="utf-8"`.

**Verification:**
- Strict UTF-8 check: OK.
- Full test suite: `68 passed in 5.10s`.

**NEXT ACTION:**
- Tiáº¿p tá»¥c M5 vá»›i F2L.

### 2026-09-30 â€” M5 CFOP: triá»ƒn khai F2L cÆ¡ báº£n

**ÄÃ£ lÃ m:**
- ThÃªm `F2LSolver` giáº£i láº§n lÆ°á»£t 4 corner-edge pair cá»§a F2L: DFR/FR, DLF/FL, DBL/BL, DRB/BR.
- ThÃªm predicate `f2l_slot_solved()` vÃ  `f2l_solved()` Ä‘á»ƒ xÃ¡c nháº­n tráº¡ng thÃ¡i F2L.
- DÃ¹ng IDA* vá»›i pattern database chÃ­nh xÃ¡c cho tá»«ng corner-edge pair lÃ m heuristic.
- Bá»• sung Cross PDB vÃ  PDB cá»§a cÃ¡c pair Ä‘Ã£ hoÃ n thÃ nh vÃ o heuristic báº±ng phÃ©p `max`, báº£o Ä‘áº£m heuristic admissible.
- ThÃªm transposition pruning theo `(CubeState, previous_face)` Ä‘á»ƒ trÃ¡nh duyá»‡t láº¡i tráº¡ng thÃ¡i á»Ÿ Ä‘á»™ sÃ¢u khÃ´ng tá»‘t hÆ¡n.
- Má»—i slot Ä‘Æ°á»£c verify ngay sau khi giáº£i; Cross vÃ  cÃ¡c pair trÆ°á»›c Ä‘Ã³ pháº£i Ä‘Æ°á»£c giá»¯ nguyÃªn.
- ChÆ°a Ä‘Äƒng kÃ½ `cfop` vÃ o registry; F2L hiá»‡n lÃ  phase solver Ä‘á»™c láº­p, OLL/PLL váº«n chÆ°a hoÃ n thÃ nh.

**Test:**
```text
CFOP tests: 8 passed in 13.76s
```

**Decision:**
- F2L hiá»‡n Æ°u tiÃªn correctness vÃ  verification; search dÃ¹ng toÃ n bá»™ 18 HTM moves vá»›i same-face pruning vÃ  transposition pruning.
- ChÆ°a coi Ä‘Ã¢y lÃ  human-style F2L tá»‘i Æ°u move count; má»¥c tiÃªu hiá»‡n táº¡i lÃ  má»™t F2L phase solver Ä‘Ãºng vÃ  cÃ³ thá»ƒ verify.

**NEXT ACTION:**
1. Cháº¡y full test suite.
2. Náº¿u toÃ n bá»™ pass, checkpoint Git cho M5 F2L.
3. Sau Ä‘Ã³ tiáº¿p tá»¥c OLL.

### 2026-09-30 - M5 CFOP: triá»ƒn khai OLL 2-look

**ÄÃ£ lÃ m:**
- ThÃªm OLLSolver sau khi F2L hoÃ n thÃ nh.
- ThÃªm oll_solved() Ä‘á»ƒ verify F2L Ä‘Æ°á»£c giá»¯ vÃ  toÃ n bá»™ corner/edge orientation vá» 0.
- DÃ¹ng 2-look OLL: edge orientation trÆ°á»›c, corner orientation sau.
- Edge stage dÃ¹ng algorithm 2-look OLL + U rotations; corner stage dÃ¹ng bá»™ case OCLL khÃ´ng yÃªu cáº§u wide/slice move, kÃ¨m virtual y-rotation variants.
- ThÃªm variant OLL 24 chá»‰ dÃ¹ng R/U/D Ä‘á»ƒ khÃ´ng phá»¥ thuá»™c wide/slice notation.
- Solution Ä‘Æ°á»£c verify báº±ng cÃ¡ch apply vÃ o full CubeState; metadata ghi two-look algorithm database.
- Khi thá»­ IDA* OLL, phÃ¡t hiá»‡n transposition cache pháº£i clear má»—i threshold; cache cÅ© cÃ³ thá»ƒ prune nháº§m á»Ÿ threshold sau.

**Test:**
CFOP tests: 11 passed in 13.51s
Full suite: 74 passed in 14.08s

**Decision:**
- OLL phase hiá»‡n táº¡i lÃ  2-look OLL, khÃ´ng pháº£i full 57-case one-look OLL.
- KhÃ´ng Ä‘Äƒng kÃ½ cfop vÃ o registry cho Ä‘áº¿n khi PLL hoÃ n thÃ nh.
- M5 hiá»‡n cÃ³ Cross + F2L + OLL; PLL lÃ  phase tiáº¿p theo.



### 2026-09-30 - M5 CFOP: 1-look OLL 57 cases

**Completed:**
- Replaced the previous 2-look OLL phase with a complete 57-case one-look OLL algorithm database.
- Added OLL case recognition from corner/edge orientation plus AUF handling (U, U', U2).
- OLL algorithms may use extended Singmaster notation (
/l/f, M/S, etc.); the vendored Kociemba engine is used only as the extended-notation executor, not as the OLL solver.
- Every OLL result is verified on the full CubeState: F2L remains solved and the last layer is fully oriented.
- Added regression coverage for the embedded OLL algorithm set.

**Test:**
`	ext
CFOP tests: 11 passed in 13.89s
Full suite: 74 passed in 14.33s
`

**Decision:**
- OLL is now **1-look OLL with 57 cases**, not 2-look OLL.
- cfop remains unregistered until PLL and the full CFOPSolver are complete.

**NEXT ACTION:**
- M5 PLL: implement 21 PLL cases, recognition, algorithm table and verification.


### 2026-09-30 - M5 CFOP: triển khai PLL 21 cases

**Completed:**
- Added PLLSolver with the complete 21-case PLL algorithm database: Ua/Ub, H, Z, Aa/Ab, E, T, F, Ja/Jb, Ra/Rb, Y, V, Na/Nb and Ga/Gb/Gc/Gd.
- Added PLL case recognition from last-layer corner/edge permutation plus AUF handling.
- Extended-notation algorithms are executed through the vendored Kociemba engine only as a move executor.
- Added pll_solved() and full verification after each PLL algorithm.
- Added regression coverage for all 21 embedded PLL cases.
- Replaced Ra and V with rotationless/verified variants after testing the engine's extended notation behavior.

**Test:**
`	ext
CFOP tests: 12 passed in 14.04s
Full suite: 75 passed in 14.61s
`

**Decision:**
- PLL is now a complete 21-case one-look phase.
- cfop remains unregistered until the full CFOPSolver integration is implemented and verified.

**NEXT ACTION:**
- Implement CFOPSolver: Cross -> F2L -> 1-look OLL -> 1-look PLL, aggregate phase output, verify the full solution, then register cfop and add API coverage.


### 2026-09-30 - M5 CFOP: completed end-to-end integration

**Follow-up adjustment:**
- Increased the default `CFOPSolver` F2L timeout from 10 seconds to 60 seconds at the user's request, without changing F2L search logic.
- Increased the default `CFOPSolver` F2L node limit from 2,000,000 to 10,000,000 after the supplied scramble hit the previous node limit.

**Completed:**
- Added CFOPSolver integrating Cross -> F2L-1..4 -> 1-look OLL -> 1-look PLL.
- Aggregated all phase moves and metadata into one Solution with method cfop.
- Verified the complete solution against the full CubeState and require pll_solved(final_state) before success.
- Registered cfop in the solver registry and added FastAPI coverage.
- Added end-to-end CFOP regression coverage.
- Kept configurable resource limits for Cross/F2L/OLL in CFOPSolver.
- Updated README to mark M5 complete.

**Verification:**
`	ext
CFOP + API tests: 18 passed in 14.08s
Full suite: 77 passed in 14.25s
`

**M5 acceptance:** Cross, F2L, 1-look OLL (57 cases), 1-look PLL (21 cases), CFOPSolver integration, cfop registry/API, and full-solution verification are complete.

**Git checkpoint:** pending final commit.

**NEXT ACTION:**
- M6 Roux.

### 2026-09-30 - CFOP API long-scramble regression fix

- Fixed CFOPSolver state progression when OLL/PLL returns extended notation such as r, M, or x by executing those phase moves through the vendored Kociemba engine.
- Fixed API error handling so request parsing ValueError is not used to label internal solver failures as INVALID_SCRAMBLE.
- Added regression coverage for the exact 20-move scramble reported through Swagger.
- API tests: 6 passed. Full suite: 79 passed.

### 2026-09-30 - Extended Singmaster notation support

**Completed:**
- Extended scramble parser to accept slice moves M E S, cube rotations x y z, lowercase wide turns r u f d l b, and Rw/Uw/Fw/Dw/Lw/Bw aliases.
- Rw-style aliases are normalized to the engine's lowercase wide notation.
- Extended sequences are executed atomically through the vendored Kociemba move engine so cube rotations followed by face moves preserve correct semantics.
- apply_move and apply_moves now support extended notation while retaining the native 18-face-move engine for standard moves.
- Added parser, inverse-sequence, move-engine, mixed-sequence, and API regression tests.
- Updated PROJECT_SPEC.md and README.md.

**Verification:**
- Parser + move tests: 51 passed in 0.19s
- Full suite: 93 passed in 25.19s
- API accepts Rw U Rw' U' M2 and returns verified=true.

**Decision:**
- Extended notation is now supported at the scramble/API/core move-application layer, not only internally by CFOP OLL/PLL.
- Supported wide-turn aliases are normalized to lowercase (Rw -> r).

**NEXT ACTION:**
- Continue with M6 Roux unless another cube-notation feature is requested.


### 2026-10-01 - F2L human-style search refinement

**Đã làm:**
- Điều chỉnh _F2LSearch để IDA* ưu tiên move ordering giống cách cuber xử lý F2L: ưu tiên U/setup và các mặt của slot hiện tại, hạn chế D và các mặt ngoài slot khi thứ tự duyệt nghiệm.
- Giữ nguyên objective correctness + minimum HTM depth của IDA*; thay đổi chỉ ảnh hưởng nghiệm được chọn trong cùng tầng tìm kiếm.
- Thêm regression test xác nhận F2L dùng human-style move ordering.
- Bổ sung xử lý PLL cho trường hợp Last Layer đã solved nhưng còn AUF U/U2/U\' do F2L/OLL kết thúc ở hướng U khác.

**Kết quả mẫu:**
- F2L-1: R U\' R\'
- F2L-3: U B\' U\' R B\' R\' B2
- F2L-4: B U2 L U2 L\' B\'

**Bug/decision:**
- Lần đầu thử thu 24 nghiệm cùng độ sâu làm thời gian F2L tăng mạnh; đã loại bỏ candidate enumeration và giữ human-style ordering trực tiếp trong DFS.
- Regression extended-notation ban đầu gặp PLL KeyError với trạng thái chỉ còn U2 AUF; đã sửa tại PLL thay vì làm F2L phụ thuộc vào orientation cụ thể.

**Test:**
- CFOP tests: 15 passed in 14.03s
- Full suite: 94 passed in 16.61s

**NEXT ACTION:**
- M6 Roux, trừ khi tiếp tục tinh chỉnh human-style F2L/case recognition.


### 2026-10-01 - PLL KeyError fallback fix

**Bug:**
- FastAPI CFOP request could fail with KeyError: ((1, 3, 2, 0), (0, 3, 1, 2)) in the 21-case PLL lookup.
- Root cause: the reduced (cp[:4], ep[:4]) lookup does not cover every legal last-layer permutation orientation produced by the preceding phases.

**Fix:**
- Added a verified Kociemba fallback when a legal PLL key is not present in the embedded 21-case lookup.
- The normal 21-case PLL path remains unchanged; fallback is only used for unmapped valid permutations.
- Added regression coverage for the exact class of legal unmapped permutation.

**Verification:**
- CFOP tests: 16 passed in 13.81s
- Full suite: 95 passed in 15.28s

**NEXT ACTION:**
- Continue human-style F2L case recognition refinement or M6 Roux.


### 2026-10-01 - PLL 21-case AUF + cube-orientation recognition fix

**Bug clarification:**
- The previous Kociemba fallback was only masking the real recognition problem.
- The failing key `((1, 3, 2, 0), (0, 3, 1, 2))` is a valid standard PLL state: it is the `Gc` case viewed after a `y` cube rotation, with an AUF before execution. It is not a 22nd PLL case.

**Fix:**
- Removed the Kociemba PLL fallback completely.
- PLL recognition now expands each of the same 21 algorithms across all 4 AUF prefixes and all 4 `y` orientations.
- Duplicate recognition aliases are accepted as aliases of the same 21-case database rather than treated as new PLL cases.
- Lookup now generates 284 legal permutation keys; the remaining 4 are the solved permutation under AUF and are handled by the existing solved/AUF path.

**Verification:**
- Exact former-KeyError regression now recognizes case `Gc` and solves with the normal `21-case PLL algorithm database` path.
- CFOP tests: 16 passed in 14.74s
- Full suite: 95 passed in 16.82s

**NEXT ACTION:**
- Continue human-style F2L case recognition refinement or move to M6 Roux.


### 2026-10-01 - White Cross orientation investigation

**Investigation:**
- Tested the proposed `x2` normalization for making the standard white-on-U Cross use the existing D-Cross search.
- `x2` alone is not sufficient because the cubie model keeps piece identities tied to the fixed color frame; applying the existing F2L/PLL pipeline after a raw x2 changes the target piece mapping.
- Experimental white-frame changes were removed to keep the working CFOP pipeline stable. No white-Cross behavior change is currently exposed.

**Verification:**
- CFOP tests: 16 passed in 14.62s.

**NEXT ACTION:**
- Implement a proper whole-CFOP coordinate transform (including Cross/F2L/PLL recognition and move-frame conversion) before switching the default Cross from yellow to white.


### 2026-10-01 - White Cross CFOP implementation completed

**Requirement:**
- Standard scramble orientation is white on U and green on F; CFOP Cross must be the white Cross instead of the previous yellow/D Cross.

**Implementation:**
- CFOPSolver now searches Cross directly on the original U-layer white edge pieces `(0, 1, 2, 3)` in positions `(0, 1, 2, 3)`.
- After Cross, the returned solution contains an explicit `x2` Orientation phase, moving the completed white Cross to D for the existing F2L → OLL → PLL pipeline.
- Added `_to_x2_coordinate_frame()` to relabel cubies after the physical `x2` so the existing F2L/OLL/PLL canonical piece tables remain valid without pretending CubeState stores centers.
- Added `_cfop_solved()` so final verification accepts the solved cube in the x2-rotated coordinate representation produced by the explicit whole-cube rotation.
- Cross PDB is now cached per target position, so the white U Cross has an exact heuristic instead of reusing the D Cross goal table.
- Raised CFOP Cross defaults to depth 10 / 2,000,000 nodes / 15 seconds because white Cross cases are not bounded by the old D-Cross search budget.
- API/test expectations now include the explicit `Orientation` phase.

**Regression coverage:**
- Added a test that applies only the Cross phase and verifies the four original U/white Cross edges are solved before the `x2` phase.
- CFOP tests: `17 passed in 26.63s`.
- Full project suite: `96 passed in 33.59s`.

**NEXT ACTION:**
- Continue human-style F2L case recognition refinement or move to M6 Roux.


### 2026-10-01 - White Cross pre-orientation refined

**Requirement change:**
- Do not solve white Cross on U and rotate afterward.
- Orient the cube first so white Cross is on D, then keep it on D through F2L.
- Allow `y`, `y'`, or `y2` before Cross when that makes the Cross execution more finger-trick-friendly.

**Implementation:**
- CFOPSolver now enters the established canonical D-Cross frame with `x2` before Cross.
- The solver evaluates the four possible front-face choices by conjugating the same D-Cross solution with `y`, `y'`, `y2`, rather than performing four independent expensive Cross searches.
- Orientation is emitted as the first phase, e.g. `x2`, `x2 y'`, `x2 y' y'`, or `x2 y' y' y'`.
- Cross is emitted immediately after Orientation and remains the D-layer Cross; there is no post-Cross Orientation phase.
- Added orientation-aware move conjugation for Cross/F2L/OLL/PLL so all phase algorithms execute correctly after the selected y rotation.
- Orientation scoring prefers shortest Cross first, then fewer B/L/D turns, fewer double turns, and lower y-rotation cost.
- Sampled scrambles selected both plain `x2` and a y-rotated orientation, confirming the orientation selector is active.

**Regression coverage:**
- Updated CFOP/API phase-order expectations.
- Added explicit regression coverage that Orientation precedes Cross and that the Cross maps back to the canonical D Cross after undoing the selected y conjugation.
- CFOP + API tests: `24 passed in 22.76s`.
- Full project suite: `96 passed in 22.57s`.

**NEXT ACTION:**
- Validate more real-world scrambles for Cross finger-trick scoring; then continue human-style F2L case recognition.


### 2026-10-01 - F2L flexible pair selection and ergonomic orientation

**Requirement change:**
- F2L must no longer solve slots in fixed 1 -> 2 -> 3 -> 4 order.
- At each step, evaluate all remaining corner-edge pairs and prefer the pair with the easiest execution.
- Finger-trick ergonomics have higher priority than raw move count; especially avoid B, B', B2, then penalize D and L.
- Allow limited y / y' frame changes during F2L when they improve execution, but do not rotate before every pair.

**Implementation:**
- Reworked F2LSolver into dynamic pair selection with pair_order metadata.
- Each remaining pair is solved with the existing IDA* + exact pair PDB search, then ranked by an ergonomic profile:
  1. hard-turn score (B highest, then D, then L)
  2. total move count
  3. B-move count
  4. double-turn count
- Added y-frame-aware F2L search. The solver searches the actual rotated cube state and derives the target/protected slot positions and orientation goals from the corresponding rotated solved reference.
- F2L can keep a selected y frame across multiple pairs and emits at most one restoration rotation at the end of the F2L phase.
- y-frame candidate searches use a small 1.5s budget and fall back to the current frame when an alternative orientation is too expensive to search.
- F2L's internal canonical state is kept separate from the physical Cross frame. CFOPSolver conjugates the completed F2L output once into the Cross orientation, preserving the existing OLL/PLL pipeline.
- Generalized the pair PDB to support non-zero target corner/edge orientations required by rotated frames.
- Existing Cross/OLL/PLL behavior remains intact.

**Regression coverage:**
- Updated F2L preservation tests to follow the actual dynamic pair_order and execute phases through the vendored engine when y notation is present.
- Added coverage for non-fixed pair ordering and the orientation-change budget metadata.
- CFOP + API tests before the final y-frame regression addition: 25 passed in 131.56s.
- Full project suite before the final y-frame regression addition: 97 passed in 131.75s.
- Additional y-frame regression: test_f2l_y_frame_search_preserves_canonical_pair passed in 3.95s.

**NEXT ACTION:**
- Validate more real-world F2L scrambles specifically for y-frame selection and finger-trick scoring; then refine recognition/lookahead behavior.

### 2026-10-01 - F2L y-frame Cross preservation bug fix

**Bug:**
- F2L y-frame search rotated the cube state but continued using the canonical Cross edge positions.
- This mismatch could allow a pair search to succeed while the resulting canonical state no longer preserved the already-solved Cross, producing `F2L returned an invalid first-two-layers state` in CFOP/API.

**Fix:**
- In `_search_pair`, derive `cross_positions` from the rotated solved reference for the active y-frame.
- Added regression coverage that checks both canonical and physical y-frame execution preserve Cross.

**Verification:**
- y-frame regressions: `2 passed in 9.01s`.
- `git diff --check`: passed.

**NEXT ACTION:**
- Re-run the full CFOP/API suite and test the user's failing scramble; then continue broader randomized F2L validation.

**Test follow-up:**
- Updated the existing Cross-preservation regression to normalize the physical state back from the active y-frame before checking the canonical Cross goal.
- The previous assertion was itself stale under the new persistent-frame behavior; it incorrectly treated a physically y-rotated solved Cross as unsolved.
- Focused preservation regressions: `3 passed in 20.22s`.

**Final verification after fix:**
- Targeted F2L preservation + y-frame regressions: `3 passed in 20.73s`.
- API suite: `7 passed in 41.71s`.
- `git diff --check`: passed.
- A 40-scramble randomized F2L run completed without reporting an invalid result; its stdout was buffered, so individual cases were not captured and this run is treated only as supplementary validation.

### 2026-10-01 - F2L ergonomics and final-frame update

- F2L ergonomic scoring now penalizes B more strongly; L and R have equal ergonomic weight.
- A single F2L pair search no longer permits mixing R and L turns.
- F2L search does not hard-ban B; it uses a strong B penalty and relies on y-frame selection to replace awkward B-heavy solutions with R/F/L alternatives when available.
- F2L no longer emits a restoration rotation after the fourth pair. The final internal y-frame is carried into OLL/PLL recognition/execution instead.
- A y/y'/y2 rotation may occur before F2L-4 when that improves its execution; no y/y'/y2 rotation is emitted after F2L-4.
- Existing y-frame regressions were previously verified; a fresh full regression is still pending after the latest ergonomic constraint.

**NEXT ACTION:**
- Run the complete CFOP/API suite and add dedicated tests for: no R+L in one pair, no B in F2L, no rotation after F2L-4, and OLL/PLL execution in the carried final frame.

**Correction:**
- The attempted hard ban on B moves was reverted after regression runs showed it can make the generic IDA* pair search time out on valid cases.
- Current behavior is therefore **strong B penalty + R/L mutual exclusion**, not an absolute B ban. A future optimization pass should use alternative y-frame / candidate search rather than a hard B prohibition.

### 2026-10-01 - F2L pair recognition pass

**Implementation:**
- Added explicit pre-search F2L pair recognition via `_f2l_pair_readiness()`.
- Recognition tiers now prioritize, before raw search ergonomics:
  1. `u_ready_pair` — both matching pieces on U, adjacent, corner oriented away from U, edge oriented.
  2. `paired_in_slot` — matching corner/edge already connected in an F2L slot but not their solved home.
  3. `u_adjacent_setup` — both matching pieces adjacent on U but not yet in a ready orientation.
  4. `one_piece_in_slot` — one piece is in an F2L slot while its partner is on U.
  5. `unprepared` — normal extraction/setup/search case.
- Pair selection sorts by recognition tier first, then retains the existing ergonomic score: B penalty, move count, B count, double turns.
- Added `pair_readiness` metadata so each F2L phase records what recognition state caused its priority.
- Removed the stale no-op `skip_faces` field from `_F2LSearch`.

**Frame handling:**
- Kept the no-restoration final-pair behavior.
- The internal F2L state remains canonical for the fixed-slot OLL/PLL recognizers. OLL/PLL are conjugated by `initial_frame - final_frame` modulo 4, matching the frame convention used by `_conjugate_moves`; no y rotation is emitted after F2L-4.
- CFOP final verification accepts a solved cube up to whole-cube y/x2 orientation, matching the intentional no-restoration frame behavior.

**Verification:**
- Pair recognition unit tests pass.
- Focused warmed-cache regression: `2 passed in 42.13s` with F2L followed by the extended CFOP case.
- Latest full project run: `100 passed in 79.17s`; `git diff --check` passes.
- The complete CFOP suite should be re-run once more after the final metadata/worklog cleanup before treating this as a stable checkpoint.

**NEXT ACTION:**
- Add a deterministic integration regression proving a recognized ready/setup pair is selected ahead of a less-ready pair. Full-suite frame regression is resolved.

### 2026-10-01 - F2L rotation-first ergonomic refinement

- Investigated why B turns were still appearing despite the strong B penalty.
- Root cause: alternative y-frame searches were only given a 1.5s scout budget, so frame candidates could time out before being compared. The solver therefore kept the current-frame B-heavy solution even when an R/F solution existed.
- Removed the `len(remaining) > 1` restriction: rotation is now allowed **before any pair, including F2L-4**. The invariant remains that no rotation is emitted after the final pair.
- Increased the alternative-frame search budget to up to 8s when the current candidate has an awkward-turn profile.
- Ergonomic comparison remains hard-turn priority first, so a longer R/F solution can beat a shorter B solution when the B penalty warrants it.
- Deterministic regression now checks the representative B-heavy F2L case: the selected phase uses a y-frame and avoids B, while F2L-4 itself ends without a y rotation.

**Observed result on representative scramble** `R U R' F2 D L2 B U2`:
- Previous F2L-3: `D B' U B D'` (B-heavy).
- New F2L-3: `y D R' U R D'` (no B).
- New F2L-4: `R' U F' U2 F U' R` (no B, no trailing rotation).
- `orientation_changes=1`, `final_frame=1`.

**Verification:**
- Full project: `100 passed in 91.90s`.
- `git diff --check`: passed.


### 2026-10-02 - Deterministic F2L recognition-priority integration regression

**Completed:**
- Added a deterministic integration regression using scramble `R U R'`.
- Confirmed this state preserves the Cross while pair 1 is recognized as `u_ready_pair` (tier 0).
- Confirmed the other three pairs are `paired_in_slot` (tier 1), so recognition priority has a clear deterministic ordering.
- Ran the real `F2LSolver` and verified pair 1 is selected first with `pair_readiness[0] == "u_ready_pair"`.
- Verified the resulting canonical F2L solution still produces a fully solved F2L state.

**Test:**
- New targeted regression: `1 passed, 21 deselected in 3.81s`.
- Full project suite: `101 passed in 91.09s`.
- `git diff --check`: passed (only normal Git LF→CRLF warnings).

**NEXT ACTION:**
- Treat the current F2L recognition-priority regression as stable.
- Continue broader F2L case-recognition/lookahead refinement, with emphasis on setup/paired cases and human-style execution.
- Do not move to M6 Roux yet if further F2L ergonomic/recognition issues remain.

### 2026-10-02 - F2L next-pair lookahead refinement

**Completed:**
- Added `_f2l_lookahead_profile()` to recognize how the current pair insertion sets up the remaining F2L pairs.
- F2L candidate selection now uses next-pair readiness as a tie-breaker after the existing recognition tier and ergonomic profile, favoring states that expose a ready/paired/setup case for the next pair.
- Applied the same lookahead tie-breaker to y-frame alternatives so frame selection does not discard a better continuation.
- Added a deterministic unit regression for recognizing a ready next pair.
- Kept correctness objective and exact pair-search depth unchanged; lookahead only affects candidate ordering.

**Verification:**
- CFOP suite: 23 passed in 69.67s.
- Full project suite: 102 passed in 97.08s.
- git diff --check: passed (only normal Git LF→CRLF warnings).
- Working tree contains only the intended F2L solver/test changes before checkpoint.

**Decision:**
- Lookahead is now part of F2L human-style candidate selection, but it remains a tie-breaker rather than a hard constraint.

**NEXT ACTION:**
- Validate the new lookahead on broader/randomized F2L scrambles, especially setup/paired cases and B-heavy cases, and inspect whether it improves human-style execution without increasing search time excessively.
- If stable, continue F2L recognition refinement; defer M6 Roux until the current F2L ergonomics/recognition pass is considered stable.
