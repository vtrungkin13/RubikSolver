# RubikSolver — Session Handoff / Development Trace

> **Mục đích:** Đây là file truy vết chính để tiếp tục project giữa các phiên ChatGPT/PalmBridge.
> Mỗi phiên mới nên **đọc file này trước**, sau đó kiểm tra nhanh Git status + test nếu cần. Không cần dựa vào trí nhớ của phiên trước.
>
> **Project:** `D:\Coding\Python\RubikSolver`
> **Git:** branch `main`, upstream `origin/main`
> **Last known commit:** `b2e6f36 Implement Kociemba two-phase solver`
> **Last verified test result:** `41 passed in 0.18s`
> **Last verified API:** `POST /api/solve` với method `kociemba` hoạt động và trả `verified=true`.

---

## 1. TRẠNG THÁI HIỆN TẠI

### Milestones

| ID | Milestone | Trạng thái | Ghi chú |
|---|---|---|---|
| M0 | Bootstrap | ✅ Hoàn thành | Python package, pytest, CLI skeleton, FastAPI skeleton, frontend skeleton |
| M1 | Cube model + moves | ✅ Hoàn thành | Cubie representation + 18 moves + invariant tests |
| M2 | Scramble parser + validator | 🟡 Cơ bản hoàn thành | Parser/validator/inverse đã có; cần hoàn thiện test/search integration |
| M3 | Search foundation | 🟡 Đang làm | `DepthSearch` đã tồn tại nhưng chưa được test/wire đầy đủ |
| M4 | Kociemba | ✅ Hoàn thành | Pure-Python vendored engine, solution verification |
| M5 | CFOP | ⏳ Chưa làm | Cross → F2L → OLL → PLL |
| M6 | Roux | ⏳ Chưa làm | FB → SB → CMLL → LSE |
| M7 | Optimal | ⏳ Chưa làm | IDA* + pruning/PDB/symmetry |
| M8 | Web UI hoàn chỉnh | ⏳ Chưa làm | Skeleton có sẵn; cần nối/render API đầy đủ |

### Ưu tiên tiếp theo

**Việc nên làm ngay: M3 hoàn thiện trước khi bắt đầu M5.**

1. Viết test trực tiếp cho `DepthSearch`.
2. Kiểm tra search giải được các scramble ngắn.
3. Kiểm tra timeout/max-nodes/max-depth và pruning.
4. Quyết định/wire search foundation vào architecture nếu CFOP/Optimal sẽ dùng chung.
5. Sau khi M3 đạt acceptance, bắt đầu M5 CFOP.

> Không coi M3 đã hoàn thành chỉ vì file `search.py` đã tồn tại.

---

## 2. MỤC TIÊU PROJECT

Xây dựng Rubik Solver 3×3 với:

- Input chính: Singmaster scramble notation.
- Cube core bằng Python.
- Solver backend bằng Python.
- FastAPI làm HTTP API.
- HTML/CSS/JavaScript làm frontend.
- Không dùng camera/ảnh/sticker input ở giai đoạn đầu.
- Mỗi solver phải tự verify solution bằng cách apply solution lên cube đã scramble.

Các solver mục tiêu:

1. CFOP
2. Roux
3. Kociemba / Two-Phase
4. Optimal / God's-algorithm-style search

**Lưu ý:** Optimal nghĩa là tìm solution ngắn nhất theo metric được cấu hình; không được gọi một solver nhanh là "optimal".

---

## 3. KIẾN TRÚC ĐÃ CHỐT

Luồng chính:

```
Scramble
   ↓
Parser
   ↓
CubeState
   ↓
Validator
   ↓
SolverStrategy
   ↓
Solution
   ↓
Verification
   ↓
FastAPI / CLI / Frontend
```

Nguyên tắc:

- Frontend không chứa solver logic.
- FastAPI không chứa cube logic.
- Solver không phụ thuộc FastAPI.
- Cube engine dùng chung cho mọi solver.
- Không hard-code solution theo scramble cụ thể.
- Correctness phải được test trước optimization.
- Solver không mutate input cube ngoài contract rõ ràng.

---

## 4. CẤU TRÚC HIỆN TẠI

```
RubikSolver/
├── PROJECT_SPEC.md
├── DEPLOYMENT.md
├── README.md
├── WORKLOG.md                  ← FILE TRUY VẾT NÀY
├── THIRD_PARTY_NOTICES.md
├── pyproject.toml
├── api/
│   ├── __init__.py
│   └── main.py
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── app.js
├── src/
│   └── rubik_solver/
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli.py
│       ├── cube/
│       │   ├── __init__.py
│       │   ├── state.py
│       │   ├── moves.py
│       │   ├── parser.py
│       │   └── validator.py
│       ├── model/
│       │   ├── __init__.py
│       │   └── solution.py
│       └── solvers/
│           ├── __init__.py
│           ├── base.py
│           ├── registry.py
│           ├── search.py
│           ├── kociemba.py
│           └── kociemba_engine/
│               └── ... vendored Kociemba engine ...
└── tests/
    ├── test_state.py
    ├── test_parser.py
    ├── test_moves.py
    ├── test_validator.py
    ├── test_solvers.py
    └── test_kociemba.py
```

---

## 5. CUBE MODEL — ĐÃ XÁC NHẬN

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

`CubeState` gồm:

- `cp[8]` — corner permutation
- `co[8]` — corner orientation
- `ep[12]` — edge permutation
- `eo[12]` — edge orientation

Solved state = identity permutation + orientation toàn 0.

---

## 6. MOVE ENGINE — ĐÃ HOÀN THÀNH

18 moves:

```
U U' U2
D D' D2
L L' L2
R R' R2
F F' F2
B B' B2
```

Invariant bắt buộc đã được test:

- Move + inverse → state ban đầu.
- `X2 == X + X`.
- `X4 == identity`.
- Scramble + inverse(scramble) → solved.

### Bug quan trọng đã sửa

Trong quá trình tích hợp Kociemba, mapping edge của **D move** bị sai.

Đã sửa từ:

```
(0,1,2,3,7,4,5,6,8,9,10,11)
```

thành:

```
(0,1,2,3,5,6,7,4,8,9,10,11)
```

Corner mapping của D giữ nguyên:

```
(0,1,2,3,5,6,7,4)
```

Bug này phải được coi là regression-sensitive: nếu sửa move engine sau này, phải giữ các invariant tests.

---

## 7. PARSER + VALIDATOR

Parser hỗ trợ:

```
U D L R F B
U' D' L' R' F' B'
U2 D2 L2 R2 F2 B2
```

Parser phải:

- bỏ whitespace thừa;
- reject token không hợp lệ;
- giữ đúng thứ tự move;
- tạo inverse sequence;
- hỗ trợ normalization.

Validator kiểm tra:

- đủ/đúng 8 corners;
- đủ/đúng 12 edges;
- không duplicate/missing cubie;
- `sum(co) % 3 == 0`;
- `sum(eo) % 2 == 0`;
- corner/edge permutation parity phù hợp.

M2 được coi là **đã có chức năng chính**, nhưng cần hoàn thiện test coverage theo acceptance của M2/M3.

---

## 8. SEARCH FOUNDATION — ĐANG DỞ

File:

```
src/rubik_solver/solvers/search.py
```

Hiện có:

- iterative/depth search;
- heuristic dựa trên số cubie sai vị trí;
- max depth;
- timeout;
- max nodes;
- same-face pruning;
- `SearchResult`.

Heuristic hiện tại:

```
max(
    (misplaced_corners + 3) // 4,
    (misplaced_edges + 3) // 4
)
```

### Chưa hoàn thành

- Chưa có test trực tiếp đủ cho `DepthSearch`.
- Chưa xác nhận acceptance "giải được các scramble ngắn và verify solution".
- Chưa quyết định đầy đủ việc expose search foundation cho các solver khác.

### Việc tiếp theo

Tạo tests cho ít nhất:

1. solved cube → empty solution;
2. một move → inverse move;
3. scramble rất ngắn → solution hợp lệ;
4. solution apply vào scramble → solved;
5. max-depth failure;
6. max-nodes failure;
7. timeout;
8. pruning không làm mất solution hợp lệ.

---

## 9. KOCIEMBA — ĐÃ HOÀN THÀNH

### Implementation

File:

```
src/rubik_solver/solvers/kociemba.py
```

Đặc điểm:

- `KociembaSolver(Solver)`
- method = `kociemba`
- lazy initialization của engine tables;
- convert `CubeState` → engine cube;
- gọi vendored pure-Python Kociemba;
- parse solution về move sequence của project;
- apply solution lên scrambled cube để verify;
- trả `Solution`.

Metadata:

```
{
  "algorithm": "Kociemba Two-Phase",
  "engine": "pure-python"
}
```

Metric: **HTM**

### Test đã có

`tests/test_kociemba.py` kiểm tra:

- solved cube;
- `R U R' F2 D`;
- scramble dài hơn;
- solution thực sự đưa cube về solved.

### Kết quả đã xác nhận

Scramble:

```
R U R' F2 D
```

Solution từng chạy thành công:

```
D' L D' L D2 F2 U' R2 U R2 D' F2 L2 U' F2
```

15 moves, `verified=true`.

---

## 10. REGISTRY HIỆN TẠI

Hiện solver registry đã đăng ký:

```
kociemba -> KociembaSolver
```

Các method còn lại chưa implementation:

```
cfop
roux
optimal
```

Không được giả vờ trả solution cho method chưa implement.

---

## 11. API — ĐÃ XÁC NHẬN

Endpoint:

```
POST /api/solve
```

Health:

```
GET /api/health
```

Đã test thực tế bằng Uvicorn.

Request đã test:

```json
{
  "scramble": "R U R' F2 D",
  "method": "kociemba"
}
```

Response thực tế đã xác nhận có:

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

### Lệnh chạy API

```powershell
cd D:\Coding\Python\RubikSolver
uvicorn api.main:app --reload
```

Swagger:

```
http://127.0.0.1:8000/docs
```

---

## 12. MỘT SỰ CỐ MÔI TRƯỜNG ĐÃ XỬ LÝ

Có package ngoài:

```
rubik-solver-py==0.1.1
```

Package này dùng top-level namespace `rubik_solver`, gây conflict với package của project và tạo lỗi:

```
ModuleNotFoundError:
No module named 'rubik_solver.cube.moves';
'rubik_solver.cube' is not a package
```

Đã xử lý bằng cách uninstall package ngoài:

```powershell
python -m pip uninstall -y rubik-solver-py
```

Kociemba engine đã được vendored vào project nên **không cần package ngoài này**.

Sau khi uninstall đã xác nhận:

```
import rubik_solver
→ D:\Coding\Python\RubikSolver\src\rubik_solver\__init__.py

import api.main
→ api import ok

pytest
→ 41 passed in 0.18s
```

**Không cài lại `rubik-solver-py` nếu không có lý do kiến trúc rất rõ ràng.**

---

## 13. THIRD-PARTY / KOCIEMBA

Kociemba engine đã được vendored vào:

```
src/rubik_solver/solvers/kociemba_engine/
```

Thông tin license/source được ghi trong:

```
THIRD_PARTY_NOTICES.md
```

Dependency runtime hiện tại trong `pyproject.toml` gồm:

- FastAPI
- uvicorn
- Pydantic
- NumPy

Không phụ thuộc package `rubik-solver-py` bên ngoài nữa.

---

## 14. TEST BASELINE

Baseline cuối cùng đã xác nhận:

```
41 passed in 0.18s
```

Trước mỗi milestone lớn:

1. chạy toàn bộ pytest;
2. chạy test mới của milestone;
3. test solution verification;
4. nếu API liên quan thì test endpoint;
5. kiểm tra Git diff;
6. chỉ commit khi working tree/code ổn định.

---

## 15. GIT / CHECKPOINT

Trạng thái cuối đã xác nhận:

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

Khi bắt đầu phiên mới, luôn kiểm tra:

```powershell
cd D:\Coding\Python\RubikSolver
git status
pytest
```

Nếu `git status` không clean, **không được giả định code giống checkpoint này**.

---

## 16. KẾ HOẠCH TIẾP THEO

### M3 — Search Foundation

**Trạng thái:** 🟡 In progress

Checklist:

- [ ] Test `DepthSearch` solved state.
- [ ] Test one-move state.
- [ ] Test short scramble.
- [ ] Verify returned solution.
- [ ] Test max depth.
- [ ] Test max nodes.
- [ ] Test timeout.
- [ ] Test pruning.
- [ ] Xác định interface dùng chung cho CFOP/Optimal.
- [ ] Chạy full pytest.
- [ ] Commit milestone.

**Acceptance:**

> Search giải được các scramble ngắn và tự verify solution.

---

### M5 — CFOP

Sau khi M3 pass:

#### Cross
- [ ] Xác định cross target/state.
- [ ] Cross solver.
- [ ] Cross verification.
- [ ] Tests.

#### F2L
- [ ] Pair/case recognition.
- [ ] Basic case solving.
- [ ] Search-assisted solving nếu phù hợp.
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
- [ ] Cross → F2L → OLL → PLL.
- [ ] Phase output.
- [ ] Full solution verification.
- [ ] Registry.
- [ ] API test.

**Không gọi solution là "optimal CFOP" nếu chưa có objective/search chứng minh.**

---

### M6 — Roux

```
First Block
    ↓
Second Block
    ↓
CMLL
    ↓
LSE
```

Tách solver theo phase và verify từng phase.

---

### M7 — Optimal

Mục tiêu:

- HTM trước.
- IDA*.
- Coordinate representation.
- Pattern databases / pruning tables.
- Symmetry reduction.
- Move pruning.
- Benchmark với scramble ngắn đã biết.

**Không bắt đầu bằng brute-force thuần túy.**

---

### M8 — Web UI

Sau khi solver backend ổn định:

- [ ] Connect frontend → `POST /api/solve`.
- [ ] Loading state.
- [ ] Error state.
- [ ] Move count.
- [ ] Metric.
- [ ] Verified status.
- [ ] Phase list.
- [ ] Tổng solution.
- [ ] Copy solution.
- [ ] Step-by-step move interaction.
- [ ] Optional cube visualization.
- [ ] Compare methods.

---

## 17. QUY TẮC CHO PHIÊN CHATGPT MỚI

Khi một phiên mới tiếp quản project:

### Bước 1 — Đọc file này

```
WORKLOG.md
```

### Bước 2 — Kiểm tra trạng thái thực tế

```powershell
cd D:\Coding\Python\RubikSolver
git status
pytest
```

Không tin tuyệt đối trạng thái ghi trong file nếu Git/test hiện tại mâu thuẫn.

### Bước 3 — Xác định task

Lấy **"KẾ HOẠCH TIẾP THEO"** làm source of truth.

Nếu user yêu cầu một việc khác, ưu tiên yêu cầu mới nhưng phải cập nhật file này sau khi hoàn thành.

### Bước 4 — Sau mỗi thay đổi quan trọng

Cập nhật:

- trạng thái milestone;
- việc đã hoàn thành;
- bug/decision mới;
- test result;
- commit hash nếu đã commit;
- **NEXT ACTION**.

### Bước 5 — Kết thúc phiên

Phải để lại một checkpoint đủ để phiên sau có thể tiếp tục mà không cần hỏi lại:

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

### 2026-09-30 — Kociemba/API checkpoint

**Đã làm:**
- Hoàn thiện Kociemba Two-Phase integration.
- Vendored pure-Python Kociemba engine.
- Sửa D-edge mapping bug.
- Thêm Kociemba tests.
- Xử lý namespace conflict với `rubik-solver-py`.
- Uninstall package ngoài gây conflict.
- Xác nhận API import.
- Xác nhận `POST /api/solve` với Kociemba.
- Xác nhận solution verification.
- Push commit M4 lên GitHub.

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
> Hoàn thiện M3 Search Foundation bằng tests + acceptance; sau đó mới bắt đầu CFOP.

---

## 19. NEXT ACTION — LUÔN ĐỌC PHẦN NÀY TRƯỚC

**Task hiện tại: M3 — Search Foundation**

Việc đầu tiên trong phiên tiếp theo:

1. Mở `src/rubik_solver/solvers/search.py`.
2. Mở `tests/test_solvers.py`.
3. Kiểm tra interface `Solver`/registry.
4. Viết test trực tiếp cho `DepthSearch`.
5. Chạy pytest.
6. Nếu fail, sửa implementation/test theo đúng nguyên nhân.
7. Khi acceptance pass, cập nhật section M3 thành ✅.
8. Commit M3.
9. Sau đó mới bắt đầu thiết kế M5 CFOP.

**Không nhảy sang CFOP trước khi xác nhận M3, trừ khi user yêu cầu rõ ràng.**

---

## 20. QUY ƯỚC CẬP NHẬT FILE NÀY

File này là **handoff/checkpoint**, không phải tài liệu thiết kế chi tiết.

- Thiết kế kiến trúc → `PROJECT_SPEC.md`
- Deployment → `DEPLOYMENT.md`
- Dependency/license → `THIRD_PARTY_NOTICES.md`
- Tiến độ, bug, decision, test baseline, việc tiếp theo → **`WORKLOG.md`**

Khi thông tin trong file này thay đổi, ưu tiên cập nhật ngay sau khi task hoàn tất thay vì để cuối nhiều phiên.
