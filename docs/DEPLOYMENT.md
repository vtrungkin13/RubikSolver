# RubikSolver — Hướng dẫn cài đặt, chạy và triển khai

## 1. Mục đích

Tài liệu này hướng dẫn cài đặt, chạy, kiểm thử và triển khai RubikSolver theo kiến trúc:

```text
Trình duyệt → FastAPI → Lõi solver
```

Python xử lý cube engine và solver. Frontend gọi HTTP API và hiển thị kết quả.

## 2. Yêu cầu môi trường

Khuyến nghị:
- Windows 10/11 hoặc Linux.
- Python 3.12 trở lên.
- pip và môi trường ảo Python.
- Git nếu quản lý mã nguồn bằng Git.

Không cần Node.js ở phiên bản frontend hiện tại vì giao diện dùng HTML/CSS/JavaScript thuần.

## 3. Cài đặt trên máy phát triển

Từ thư mục dự án:

```powershell
cd D:\Coding\Python\RubikSolver
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

Kiểm tra cài đặt:

```powershell
python --version
pytest
```

## 4. Chạy kiểm thử

Chạy toàn bộ bộ kiểm thử:

```powershell
pytest
```

Khi phát triển, có thể chạy riêng file kiểm thử liên quan, ví dụ:

```powershell
pytest tests/test_roux.py
pytest tests/test_cfop.py
pytest tests/test_api.py
```

Nếu tên file kiểm thử thay đổi, hãy kiểm tra thư mục `tests/` trước khi dùng lệnh.

## 5. Chạy giao diện dòng lệnh

Ví dụ:

```powershell
python -m rubik_solver "R U R' F2 D L2"
python -m rubik_solver --method kociemba "R U R' F2"
```

CLI và API phải sử dụng cùng lõi solver; không được triển khai thuật toán cube riêng trong từng adapter.

## 6. Chạy API

Tại thư mục gốc dự án:

```powershell
uvicorn api.main:app --reload
```

API phát triển mặc định ở `http://127.0.0.1:8000`. Có thể kiểm tra endpoint health nếu được cấu hình và gửi yêu cầu solve theo hợp đồng API trong mã nguồn.

Để chạy không bật tự tải lại:

```powershell
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

Chỉ mở host công khai khi đã cấu hình môi trường triển khai phù hợp.

## 7. Chạy frontend

Mở một terminal khác tại thư mục gốc dự án:

```powershell
python -m http.server 5500 --directory frontend
```

Sau đó truy cập `http://127.0.0.1:5500`. Nếu frontend cần gọi API ở địa chỉ khác, hãy cấu hình URL API tương ứng; tránh hard-code địa chỉ máy phát triển cho môi trường production.

## 8. Kiến trúc production

Có thể chạy API và frontend tĩnh như hai dịch vụ riêng:

```text
Trình duyệt
  ├── Frontend tĩnh :5500 hoặc máy chủ web
  └── API qua reverse proxy :80/:443
          └── FastAPI :8000
                  └── Lõi solver
```

Với nhiều worker Uvicorn:

```powershell
uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 2
```

Cần benchmark theo tải thực tế vì solver tìm kiếm có thể tiêu tốn CPU/RAM đáng kể; tăng worker không phải lúc nào cũng tăng thông lượng.

## 9. Cấu hình production

Không hard-code URL API, timeout, số worker, giới hạn solver hoặc đường dẫn bảng pruning. Chuyển các giá trị này sang biến môi trường hoặc tệp cấu hình.

Ví dụ tên cấu hình:

```text
RUBIK_API_HOST=0.0.0.0
RUBIK_API_PORT=8000
RUBIK_SOLVER_TIMEOUT=30
RUBIK_TABLE_DIR=./data/tables
```

Đây là ví dụ tên/giá trị; chỉ các biến đã được đọc bởi code mới có hiệu lực. Không commit secret hoặc thông tin xác thực riêng của máy.

## 10. Quản lý tài nguyên solver

- Engine Kociemba thuần Python có thể tạo và cache bảng move/pruning; lần khởi tạo đầu tiên có thể chậm hơn các lần sau.
- Kociemba không đảm bảo lời giải ngắn nhất tuyệt đối.
- Solver tìm kiếm tối ưu có thể tiêu tốn nhiều CPU và RAM.
- Cấu hình timeout và giới hạn đồng thời phù hợp.
- Tránh khởi tạo lại bảng pruning cho từng yêu cầu nếu có thể tái sử dụng.
- Không chặn event loop bằng tác vụ CPU-bound kéo dài; cân nhắc worker, thread hoặc process phù hợp.
- Ghi nhận thời gian solve, số move và nguyên nhân thất bại để theo dõi hiệu năng.

## 11. Xử lý lỗi API

Lỗi phía client nên trả mã HTTP 4xx cùng JSON ổn định. Lỗi solver/server dùng mã 5xx hoặc mã lỗi miền phù hợp.

Ví dụ cấu trúc:

```json
{
  "error": {
    "code": "INVALID_SCRAMBLE",
    "message": "Invalid move token: X"
  }
}
```

Không trả stack trace cho client trong môi trường production. Lỗi phase phải đủ rõ để phân biệt dữ liệu đầu vào không hợp lệ, hết tài nguyên tìm kiếm và lỗi xác minh.

## 12. Nhật ký

Mỗi yêu cầu solve nên ghi tối thiểu:
- Phương pháp được chọn.
- Scramble đã chuẩn hóa.
- Số move.
- Kết quả xác minh.
- Thời gian xử lý.
- Mã lỗi nếu thất bại.

Không ghi dữ liệu nhạy cảm hoặc thông tin không cần thiết.

## 13. Danh sách kiểm tra trước/sau triển khai

Trước triển khai:
- [ ] Bộ kiểm thử `pytest` đạt.
- [ ] Kiểm thử bất biến cube đạt.
- [ ] Lời giải của solver được xác minh.
- [ ] API xác thực yêu cầu đúng.
- [ ] Frontend gọi API thành công.
- [ ] Timeout và giới hạn tài nguyên đã cấu hình.
- [ ] Nhật ký hoạt động.
- [ ] CORS và reverse proxy đã kiểm tra.
- [ ] Máy chủ production không bật chế độ debug/tự tải lại.

Sau triển khai:
- [ ] Endpoint health trả trạng thái khỏe nếu được bật.
- [ ] Giải được một scramble đã biết.
- [ ] Kết quả báo xác minh thành công.
- [ ] Đã kiểm tra độ trễ và mức sử dụng CPU/RAM.
- [ ] Đã kiểm tra log khi timeout hoặc solver lỗi.

## 14. Quy trình phát triển

Thứ tự khuyến nghị: CubeState và move engine → kiểm thử bất biến → parser/validator → giao diện solver → Kociemba baseline → CFOP/Roux → Optimal → hoàn thiện API → cải tiến UI → triển khai production.

Có thể dựng frontend sớm để kiểm tra hợp đồng API, nhưng không được để việc đó làm chậm xác minh cube engine.

## 15. Cổng phát triển cục bộ

Mặc định:
- FastAPI: cổng 8000.
- Máy chủ frontend tĩnh: cổng 5500.

Có thể thay đổi bằng tham số dòng lệnh hoặc biến môi trường nếu ứng dụng hỗ trợ.

## 16. Lộ trình triển khai

Giai đoạn đầu: chạy API và frontend tĩnh trên máy phát triển Windows. Giai đoạn máy chủ: đặt reverse proxy trước FastAPI và frontend. Giai đoạn tối ưu: tách worker solver và dùng chung các bảng pruning chỉ đọc.

Chưa cần container hóa khi cube engine còn đang phát triển; có thể bổ sung Docker sau khi API và solver ổn định.
