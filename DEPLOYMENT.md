# RubikSolver — Deployment & Runbook

## 1. Mục đích

Tài liệu này mô tả cách cài đặt, chạy, kiểm thử và triển khai RubikSolver theo kiến trúc:

    Browser → FastAPI → Solver Core

Python chịu trách nhiệm toàn bộ cube engine và solver. Frontend chỉ gọi HTTP API và render kết quả.

## 2. Yêu cầu môi trường

Khuyến nghị:
- Windows 10/11 hoặc Linux.
- Python 3.12+.
- pip.
- virtual environment.
- Git nếu quản lý source bằng Git.

Không yêu cầu Node.js ở phiên bản frontend hiện tại vì frontend dùng HTML/CSS/JavaScript thuần.

## 3. Cài đặt local

Từ thư mục project:

    cd D:\Coding\Python\RubikSolver

Tạo virtual environment:

    py -3.12 -m venv .venv

Kích hoạt trên PowerShell:

    .\.venv\Scripts\Activate.ps1

Cài package:

    python -m pip install --upgrade pip
    pip install -e ".[dev]"

Kiểm tra:

    python --version
    pytest

## 4. Chạy test

Toàn bộ test:

    pytest

Bộ test hiện bao gồm cube invariants, parser/validator và Kociemba verification. Kociemba test sẽ kiểm tra solution trả về có thực sự đưa CubeState về solved hay không.

Test verbose:

    pytest -v

Test một module:

    pytest tests/test_moves.py -v

Không triển khai solver mới nếu cube invariant tests chưa pass.

## 5. Chạy CLI

Ví dụ:

    python -m rubik_solver "R U R' F2 D L2"

Chọn method:

    python -m rubik_solver --method kociemba "R U R' F2"

Kociemba hiện đã được đăng ký trong solver registry và có thể giải scramble thực tế. CFOP, Roux và Optimal vẫn báo solver unavailable cho tới khi các phase tương ứng được triển khai.

## 6. Chạy API

Development server:

    uvicorn api.main:app --reload

Mặc định:

    http://127.0.0.1:8000

Swagger/OpenAPI:

    http://127.0.0.1:8000/docs

Health check:

    GET /api/health

Solve:

    POST /api/solve

Request:

    {
      "scramble": "R U R' F2",
      "method": "kociemba"
    }

## 7. Chạy frontend

Frontend hiện tại là static files.

Có thể mở frontend/index.html trực tiếp trong browser cho mục đích UI tĩnh, nhưng khi test API nên dùng một static server để tránh vấn đề origin/CORS.

Ví dụ:

    python -m http.server 5500 --directory frontend

Sau đó mở:

    http://127.0.0.1:5500

Frontend gọi API tại:

    http://127.0.0.1:8000/api/solve

Khi deploy thật, nên serve frontend và API qua cùng domain/reverse proxy để giảm CORS và đơn giản hóa cấu hình.

## 8. Production architecture

Khuyến nghị:

    Internet
       ↓
    Reverse Proxy (Nginx/Caddy)
       ├── /        → static frontend
       └── /api/    → FastAPI
                         ↓
                      Solver Core

FastAPI chạy bằng production ASGI server.

Ví dụ:

    uvicorn api.main:app --host 0.0.0.0 --port 8000

Khi cần nhiều worker:

    uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 2

Số worker phải được benchmark với solver thực tế vì optimal search có thể tiêu tốn CPU/RAM lớn.

## 9. Cấu hình production

Không hard-code:
- API URL.
- timeout.
- worker count.
- solver limits.
- pruning-table paths.

Các giá trị này nên chuyển thành environment variables/config.

Ví dụ:

    RUBIK_API_HOST=0.0.0.0
    RUBIK_API_PORT=8000
    RUBIK_SOLVER_TIMEOUT=30
    RUBIK_TABLE_DIR=./data/tables

Không commit secret hoặc machine-specific credential.

## 10. Solver resource management

Kociemba hiện dùng engine pure-Python vendored và có pruning/move tables được cache. Lần khởi tạo đầu tiên có thể chậm hơn các lần solve sau. Kociemba không đảm bảo lời giải ngắn nhất tuyệt đối.

Đặc biệt Optimal có thể tiêu tốn CPU/RAM đáng kể.

Production cần:
- timeout cho request.
- giới hạn concurrency nếu cần.
- cache pruning tables.
- tránh khởi tạo pruning table lặp lại cho mỗi request.
- không block event loop bằng CPU-bound solver; dùng worker/thread/process phù hợp.
- log thời gian solve và số moves.

Optimal solver phải có giới hạn rõ ràng để một request không giữ server vô thời hạn.

## 11. API error handling

Các lỗi client nên trả HTTP 4xx với JSON ổn định.

Ví dụ:

    {
      "error": {
        "code": "INVALID_SCRAMBLE",
        "message": "Invalid move token: X"
      }
    }

Các lỗi solver/server nên trả HTTP 5xx hoặc mã lỗi domain phù hợp.

Không expose stack trace trong production response.

## 12. Logging

Mỗi request solve nên có tối thiểu:
- method.
- scramble đã normalize.
- move count.
- verified.
- elapsed time.
- error code nếu thất bại.

Không log dữ liệu không cần thiết.

## 13. Deployment checklist

### Before deployment
- [ ] pytest pass.
- [ ] Cube invariant tests pass.
- [ ] Solver verification pass.
- [ ] API validation pass.
- [ ] Frontend gọi API thành công.
- [ ] Timeout được cấu hình.
- [ ] Logging hoạt động.
- [ ] CORS/reverse proxy được kiểm tra.
- [ ] Production server không chạy với debug/reload.

### After deployment
- [ ] /api/health trả healthy.
- [ ] Solve một scramble known-state.
- [ ] verified=true.
- [ ] Kiểm tra latency.
- [ ] Kiểm tra CPU/RAM.
- [ ] Kiểm tra log khi solver timeout/error.

## 14. Development workflow

Khuyến nghị thứ tự:
1. CubeState + move engine.
2. Unit/invariant tests.
3. Scramble parser + validator.
4. Solver interface.
5. Kociemba baseline.
6. CFOP/Roux.
7. Optimal.
8. API hardening.
9. UI enhancement.
10. Production deployment.

Frontend có thể được dựng sớm để kiểm tra API contract, nhưng không được làm chậm việc xác minh cube engine.

## 15. Local development ports

Mặc định:
- FastAPI: 8000
- Frontend static server: 5500

Có thể thay đổi bằng command line hoặc environment variables.

## 16. Deployment strategy

Giai đoạn đầu:

    Local Windows
    ├── FastAPI :8000
    └── Static frontend :5500

Giai đoạn server:

    VPS/Cloud
    ├── Reverse Proxy :80/:443
    ├── FastAPI :8000
    └── Static frontend

Giai đoạn tối ưu:

    Reverse Proxy
         ↓
    API service
         ↓
    Solver workers
         ↓
    Shared/read-only pruning tables

Không cần container hóa ngay ở giai đoạn cube-engine development. Docker có thể thêm sau khi API và solver ổn định.
