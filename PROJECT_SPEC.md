# RubikSolver — Project Specification & Development Plan

## 1. Mục tiêu

Xây dựng một Rubik Solver cho Rubik 3×3×3, với **Python là solver/backend chính** và **HTML/CSS/JavaScript là web frontend**.

Đầu vào chính là scramble notation; không yêu cầu camera, hình ảnh hoặc nhập 54 sticker.

Từ scramble, chương trình phải:
1. Khởi tạo cube solved.
2. Parse và apply scramble để tạo chính xác trạng thái cube.
3. Validate trạng thái.
4. Chạy solver theo method được chọn.
5. Trả về sequence move hợp lệ và thông tin theo từng phase/method.
6. Tự verify solution bằng cách apply solution lên trạng thái scramble.

Các hướng solver mục tiêu:
- CFOP
- Roux
- Kociemba / Two-Phase
- Optimal / God's-algorithm-style search

"Optimal" được hiểu là tìm lời giải ngắn nhất theo metric được cấu hình; không coi mọi solver nhanh là God's algorithm.

---

## 2. Phạm vi phiên bản đầu

### In scope
- Rubik 3×3×3 tiêu chuẩn.
- Singmaster notation: U, D, L, R, F, B; suffix 2, '.
- Extended Singmaster notation: M, E, S; x, y, z; lowercase wide turns and Rw/Uw/Fw/Dw/Lw/Bw aliases.
- Scramble parser và normalizer.
- Cube state representation dạng permutation/orientation.
- Move engine chính xác.
- Inverse sequence.
- Cube validation.
- Unit/invariant tests.
- Solver architecture dạng strategy để nhiều method dùng chung cube engine.
- HTTP API bằng FastAPI.
- Web UI bằng HTML/CSS/JavaScript thuần.
- UI cho phép nhập scramble, chọn method và xem solution theo phase.

### Out of scope ban đầu
- Camera/computer vision.
- 2×2, 4×4 hoặc cube khác 3×3.
- Blindfolded solving.
- Nhận dạng scramble từ ảnh.
- 3D animation đầy đủ.

---

## 3. Kiến trúc tổng thể

Tách solver core khỏi web layer:

    Browser
      │
      │ HTTP / JSON
      ▼
    FastAPI
      │
      ├── Request validation
      ├── Solver registry
      │
      ▼
    Solver Core
      ├── Cube Engine
      ├── Kociemba
      ├── CFOP
      ├── Roux
      └── Optimal
      │
      ▼
    Solution model
      │
      └── Verification
      │
      ▼
    JSON response
      │
      ▼
    Browser UI

Nguyên tắc: frontend không chứa logic giải Rubik. JavaScript chỉ chịu trách nhiệm nhập liệu, gọi API, render kết quả và tương tác UI.

Cube engine phải độc lập hoàn toàn với FastAPI và frontend.

---

## 4. Cube representation

Ưu tiên representation theo cubie:
- Corner permutation: 8 phần tử.
- Corner orientation: 8 phần tử.
- Edge permutation: 12 phần tử.
- Edge orientation: 12 phần tử.

Canonical indexing:

Corners:
    0 URF
    1 UFL
    2 ULB
    3 UBR
    4 DFR
    5 DLF
    6 DBL
    7 DRB

Edges:
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

Solved state là permutation identity và orientation bằng 0.

Representation này phải được dùng chung cho tất cả solver.

---

## 5. Move engine

Implement 18 face turns:

    U U' U2
    D D' D2
    L L' L2
    R R' R2
    F F' F2
    B B' B2

Mỗi move là phép biến đổi deterministic trên cubie state.

Invariant bắt buộc:
- move rồi inverse move → trạng thái ban đầu.
- X2 tương đương X + X.
- X lặp 4 lần → trạng thái ban đầu.
- scramble rồi inverse(scramble) → solved.

Các move phải được biểu diễn thành transition tables hoặc cấu trúc tương đương, không hard-code theo từng scramble.

---

## 6. Scramble parser

Input ví dụ:

    R U R' F2 D L2 B' U2

Parser phải:
- Ignore extra whitespace.
- Reject token không hợp lệ.
- Hỗ trợ notation trong scope.
- Preserve move order.
- Có hàm inverse sequence.
- Có normalizer để chuẩn hóa chuỗi move.

Khi đảo sequence phải đảo thứ tự token và lấy inverse từng move.

---

## 7. Validation

Cube validator cần kiểm tra tối thiểu:
- Đủ 8 corner cubies.
- Đủ 12 edge cubies.
- Không duplicate/missing cubie.
- Tổng corner orientation % 3 == 0.
- Tổng edge orientation % 2 == 0.
- Parity corner permutation và edge permutation phải phù hợp.

---

## 8. Solution model

Không trả về raw string duy nhất. Dùng object/model có cấu trúc:

    Solution
      - method
      - moves
      - move_count
      - metric
      - verified
      - phases[]
      - metadata

Phase có:
- name
- moves
- move_count
- optional description

CFOP:
    Cross → F2L → OLL → PLL

Roux:
    First Block → Second Block → CMLL → LSE

Kociemba:
    Phase 1 → Phase 2

Optimal:
    một sequence + metric + verification.

---

## 9. Solver interface

Thiết kế strategy interface:

    Solver.solve(cube) -> Solution

Các implementation dự kiến:
- KociembaSolver
- OptimalSolver
- CFOPSolver
- RouxSolver

Có thể thêm solver khác mà không sửa CubeState.

Solver không được phụ thuộc FastAPI.

---

## 10. Kociemba / Two-Phase

Mục tiêu:
- Solver thực dụng, nhanh.
- Không cam kết optimal.
- Là baseline để benchmark.

Phase 1 đưa state vào subgroup phù hợp.
Phase 2 giải từ subgroup về solved.

Pruning tables và coordinate system phải được tách thành module/cache riêng.

---

## 11. Optimal solver

Mục tiêu cuối:
- Tìm solution ngắn nhất theo metric cấu hình.
- Hỗ trợ HTM trước.
- Có thể mở rộng QTM/STM nếu kiến trúc cho phép.

Kỹ thuật dự kiến:
- IDA*
- Coordinate representation
- Pattern databases / pruning tables
- Symmetry reduction
- Move pruning
- Transposition/pruning khi phù hợp

Không bắt đầu bằng brute force thuần túy.

---

## 12. CFOP solver

CFOP cần được xử lý theo phase:

    Cross → F2L → OLL → PLL

Các module:
- CrossSolver
- F2LSolver
- OLLSolver
- PLLSolver

Ban đầu có thể dùng algorithm libraries cho OLL/PLL sau khi nhận diện case.
F2L sẽ phát triển từ basic case solving → search/optimization.

Phải phân biệt:
- CFOP-compatible solution
- human-style CFOP solution
- optimized CFOP solution

Không tuyên bố solution tối ưu CFOP nếu chưa có objective/search chứng minh.

---

## 13. Roux solver

Các phase mục tiêu:

    First Block → Second Block → CMLL → LSE

Tách phase solver để có thể cải tiến độc lập.

---

## 14. Web API

Backend dùng FastAPI.

### Endpoint

    POST /api/solve

Request:

    {
      "scramble": "R U R' F2 D L2",
      "method": "cfop"
    }

Method hợp lệ ban đầu:

    cfop
    roux
    kociemba
    optimal

Response chuẩn:

    {
      "method": "cfop",
      "scramble": "R U R' F2 D L2",
      "moves": 42,
      "metric": "HTM",
      "verified": true,
      "phases": [
        {
          "name": "Cross",
          "moves": "..."
        },
        {
          "name": "F2L",
          "moves": "..."
        },
        {
          "name": "OLL",
          "moves": "..."
        },
        {
          "name": "PLL",
          "moves": "..."
        }
      ],
      "metadata": {}
    }

Errors phải trả JSON có cấu trúc ổn định, ví dụ:
- invalid scramble
- unsupported method
- impossible cube state
- solver unavailable
- solver timeout/error

---

## 15. Web UI

Frontend dùng HTML/CSS/JavaScript thuần ở giai đoạn đầu để giảm dependency.

UI tối thiểu:
1. Text input cho scramble.
2. Method selector:
   - CFOP
   - Roux
   - Kociemba
   - Optimal
3. Solve button.
4. Loading/error state.
5. Tổng số moves.
6. Metric.
7. Verification status.
8. Danh sách phase.
9. Move sequence cho từng phase.
10. Tổng solution sequence.

Giai đoạn sau có thể thêm:
- click từng move để highlight.
- cube visualization 2D/3D.
- animation.
- compare nhiều methods.
- history.
- copy solution.

---

## 16. Project structure

    RubikSolver/
    ├── README.md
    ├── PROJECT_SPEC.md
    ├── DEPLOYMENT.md
    ├── pyproject.toml
    ├── src/
    │   └── rubik_solver/
    │       ├── __init__.py
    │       ├── __main__.py
    │       ├── cube/
    │       │   ├── __init__.py
    │       │   ├── state.py
    │       │   ├── moves.py
    │       │   ├── parser.py
    │       │   └── validator.py
    │       ├── solvers/
    │       │   ├── __init__.py
    │       │   ├── base.py
    │       │   ├── registry.py
    │       │   ├── kociemba/
    │       │   ├── optimal/
    │       │   ├── cfop/
    │       │   └── roux/
    │       ├── model/
    │       │   └── solution.py
    │       └── cli.py
    ├── api/
    │   └── main.py
    ├── frontend/
    │   ├── index.html
    │   ├── style.css
    │   └── app.js
    └── tests/
        ├── test_parser.py
        ├── test_moves.py
        ├── test_state.py
        ├── test_validator.py
        └── test_solvers.py

Frontend/backend phải chỉ là adapters; solver core không import FastAPI.

---

## 17. Testing strategy

### Unit tests
- Parser.
- Move transformations.
- Inverse moves.
- Cube solved detection.
- Validation.
- Solution formatting.
- API request/response models.

### Property/invariant tests
- Mọi face move 4 lần = identity.
- X2 = X + X.
- scramble + inverse = solved.
- random sequence + inverse = solved.

### Solver tests
- Solution phải đưa cube về solved.
- Không chứa move invalid.
- Không phá vỡ phase invariant.
- API response phải có verified=true khi solver hoàn tất thành công.

### Regression tests
Mọi bug về cube indexing/move mapping phải có test tái hiện.

---

## 18. CLI

Vẫn giữ CLI song song với web UI:

    python -m rubik_solver "R U R' F2 D L2"

    python -m rubik_solver --method kociemba "R U R' F2"

Sau này:
- --method cfop
- --method roux
- --method optimal
- --json
- --verbose

CLI và API phải dùng cùng solver core.

---

## 19. Development plan

### Phase 0 — Bootstrap
- Python package.
- pyproject.toml.
- pytest.
- CLI skeleton.
- FastAPI skeleton.
- Frontend skeleton.
- API smoke tests.

Acceptance: bootstrap artifacts tồn tại và FastAPI health/solve smoke tests pass.

### Phase 1 — Cube core
- Canonical cubie indexing.
- CubeState.
- Solved state.
- 18 moves.
- apply moves.
- inverse moves.
- solved check.
- validator.
- Move invariant/regression tests.

Acceptance: toàn bộ cube invariant tests pass.

### Phase 2 — Scramble pipeline
- Parser.
- Normalizer.
- Scramble → CubeState.
- CubeState → debug representation.
- CLI/API nhận scramble.
- Parser/validator edge-case tests.

Acceptance: scramble + inverse luôn solved và invalid cube/scramble được phát hiện.

### Phase 3 — Search foundation
- Generic search interface.
- Move ordering.
- Depth-limited search.
- IDA* implementation.
- Admissible basic heuristic.
- Same-face pruning.
- Max-depth, max-node và timeout limits.
- Automatic solution verification tests.

Acceptance: giải được các scramble ngắn, solution được apply về solved và resource limits hoạt động đúng.

### Phase 4 — Kociemba
- Coordinates.
- Move tables.
- Pruning tables.
- Phase 1.
- Phase 2.
- Benchmarks.

Acceptance: solve reliably trên arbitrary valid scramble và tự verify solution.

### Phase 5 — CFOP
- Case recognition.
- Cross.
- F2L.
- OLL.
- PLL.
- Phase output.

### Phase 6 — Roux
- FB.
- SB.
- CMLL.
- LSE.

### Phase 7 — Optimal
- Strong pruning.
- Pattern databases.
- Symmetry.
- IDA* optimization.
- HTM optimal search.
- Benchmark against known short solutions.

### Phase 8 — Web UI
- Rich result rendering.
- Step-by-step move interaction.
- Optional cube visualization.
- Method comparison.

---

## 20. Coding rules

- Python 3.12+.
- Type hints.
- Dataclasses/Pydantic khi phù hợp.
- No global mutable cube state.
- Pure transformations where practical.
- Solver không mutate input cube ngoài contract rõ ràng.
- Test trước khi tối ưu.
- Không hard-code scramble-specific solutions.
- Benchmark solver riêng với correctness test.
- Tách correctness khỏi optimization.
- Không để frontend chứa solver algorithm.
- API layer không chứa cube logic.
- Core phải chạy độc lập không cần web server.

---

## 21. Definition of Done cho core

Core hoàn thành khi:
1. Parse được mọi scramble hợp lệ trong scope.
2. 18 move transformations chính xác.
3. Có inverse sequence.
4. Random scramble + inverse luôn về solved.
5. Cube validation phát hiện được các trạng thái impossible cơ bản.
6. Có test suite tự động.
7. Solver interface độc lập với cube representation.
8. Một solver có thể verify solution bằng cách apply solution lên scrambled state.
9. API có thể gọi solver qua JSON.
10. Frontend có thể hiển thị solution trả về từ API.

---

## 22. Quy ước phát triển và handoff

### Project Handoff Rule

- Mọi phiên làm việc mới phải đọc `WORKLOG.md` trước khi tiếp tục phát triển project.
- Sau mỗi thay đổi đối với source code, tests, configuration hoặc architecture, phải cập nhật `WORKLOG.md` trong cùng phiên làm việc.
- `WORKLOG.md` phải ghi nhận tối thiểu: thay đổi đã thực hiện, lý do/decision, kết quả test, bug hoặc vấn đề phát sinh, trạng thái milestone và **NEXT ACTION**.
- Trạng thái thực tế của Git và test được ưu tiên hơn thông tin cũ trong `WORKLOG.md` nếu có mâu thuẫn.
- Khi hoàn thành milestone lớn, phải cập nhật checkpoint và commit khi working tree ổn định.
- Không cần chờ user nhắc việc cập nhật `WORKLOG.md`; đây là quy ước mặc định của project.
- Không tự động commit thay đổi. Chỉ được tạo commit khi user yêu cầu rõ ràng.

### Tài liệu nguồn sự thật

- Thiết kế và kiến trúc → `PROJECT_SPEC.md`
- Deployment → `DEPLOYMENT.md`
- Dependency/license → `THIRD_PARTY_NOTICES.md`
- Tiến độ, bug, decision, test baseline, handoff và next action → `WORKLOG.md`

---

## 23. Quyết định kiến trúc

Giữ Python làm ngôn ngữ chính cho solver:

    Python Core
        ↓
    FastAPI
        ↓
    HTML/CSS/JavaScript

Không chuyển toàn bộ project sang JavaScript.

### Solver philosophy — learning-oriented human solve

RubikSolver không chỉ nhằm tìm một sequence hợp lệ hoặc ngắn nhất. Một mục tiêu
quan trọng của project là giúp cuber **học cách giải hay** bằng cách quan sát,
so sánh và phân tích solution do solver tạo ra.

Vì vậy, khi một method có thể được triển khai theo nhiều cách, ưu tiên kiến
trúc có thể giải thích được và gần với tư duy human solve:

- Solution phải giữ phase boundaries rõ ràng để cuber biết solver đang giải gì.
- Solver nên nhận diện các cơ hội có lợi cho human solving thay vì chỉ tối ưu
  một objective toàn cục.
- Search/optimization được dùng để tìm một continuation tốt trong phase, nhưng
  không được làm mất ý nghĩa học tập của phase đó.
- Metadata nên giải thích strategy/case/opportunity khi có thể, để UI sau này
  có thể trình bày **vì sao** solver chọn cách giải đó.
- Cần phân biệt rõ `human-style`, `optimized` và `fallback/oracle search`; không
  gọi một solution là human-style chỉ vì nó giải đúng phase.

Roux là reference implementation đầu tiên cho philosophy này. Kiến trúc tương
tự phải được tái sử dụng khi tiếp tục xây dựng CFOP đang pending, đặc biệt cho
Cross/F2L lookahead, pair selection, case recognition và giải thích quyết định.

### Roux phase-boundary decision

Roux FB và SB phải được xử lý như hai phase độc lập để giữ planner gần với
cách human solve:

- FB chỉ tối ưu theo mục tiêu FB; không dùng SB continuation/lookahead để
  chấm điểm hoặc chọn FB.
- Hoàn tất và chọn FB tối ưu trước.
- Chỉ sau khi FB được chốt mới bắt đầu tìm kiếm SB từ state sau FB.
- Không quay lại đổi FB chỉ vì một SB continuation khác có vẻ thuận lợi hơn.

### Roux human-style SB strategy

Sau khi FB đã được chốt, SB là một phase độc lập nhưng có thể dùng lookahead
**bên trong SB** để mô phỏng tư duy của cuber:

1. Nhận diện `FREE_SQUARE` / `FREE_PAIR` hoặc cơ hội dễ khai thác nếu state đã
   chứa sẵn một phần SB.
2. Nếu không có cơ hội rõ ràng, dùng DR-first nhưng không greedy theo DR ngắn
   nhất; phải xét ảnh hưởng của DR lên hai pair còn lại và thứ tự pair tiếp theo.
3. Chỉ khi human-style planner không tìm được continuation hợp lệ mới dùng
   direct SB search như **emergency/oracle fallback**.
4. Direct fallback không được quay ngược để thay thế một human-style plan hợp
   lệ chỉ vì nó ngắn hơn. Nếu fallback được dùng, metadata phải nói rõ đây là
   fallback để phục vụ học tập/debugging.

Direct SB hiện có mục tiêu correctness và oracle/debugging hơn là strategy chính.
Mặc định fallback được phép tìm tới 14 HTM moves với node limit riêng; giới hạn
thời gian vẫn được áp dụng. Human-style SB planner và direct fallback cùng tôn
trọng resource budget do caller cấu hình; không có cap thời gian nội bộ thấp hơn
budget đó.

### Future CFOP learning-oriented design

Khi tiếp tục M5/CFOP, không reset philosophy về một shortest-path solver. CFOP
cần giữ phase structure `Cross → F2L → OLL → PLL` và hướng tới các quyết định có
giá trị học tập như cross quality, F2L pair recognition/order, lookahead,
free-pair exploitation và ergonomics. Search có thể làm oracle/benchmark, nhưng
human-style solution và optimized solution phải là hai mục tiêu được phân biệt
trong model/metadata.

Thứ tự triển khai:

    Correct Cube Engine
        ↓
    Scramble + Validator
        ↓
    Search Infrastructure
        ↓
    Kociemba
        ↓
    CFOP / Roux
        ↓
    Optimal
        ↓
    Web UI enhancement

Web skeleton được dựng ngay từ đầu để API contract không phải thiết kế lại sau này, nhưng solver correctness vẫn là ưu tiên trước UI nâng cao.

---

## Milestones

M0: Bootstrap — ✅ Hoàn thành
M1: Cube model + moves — ✅ Hoàn thành
M2: Scramble parser + validator — ✅ Hoàn thành
M3: Search foundation — ✅ Hoàn thành
M4: Kociemba solver — ✅ Hoàn thành
M5: CFOP
M6: Roux
M7: Optimal solver
M8: Web UI

Mỗi milestone phải có automated tests và verification trước khi chuyển sang milestone tiếp theo.
