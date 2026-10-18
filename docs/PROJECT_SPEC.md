# RubikSolver — Đặc tả dự án và kế hoạch phát triển

## 1. Mục tiêu

Xây dựng bộ giải Rubik 3×3×3, trong đó Python là lõi xử lý và backend; HTML/CSS/JavaScript đảm nhiệm giao diện web. Đầu vào chính là chuỗi scramble, không yêu cầu camera, ảnh hoặc nhập 54 sticker.

Luồng xử lý: khởi tạo cube đã giải → phân tích và áp dụng scramble → xác thực trạng thái → chạy phương pháp được chọn → trả về chuỗi move và các phase → phát lại lời giải để xác minh.

## 2. Các phương pháp giải

- **CFOP:** Orientation → Cross → bốn cặp F2L → OLL → PLL.
- **Roux:** FB → SB → CMLL → EO → ULUR → L4E.
- **Kociemba / Two-Phase:** phương pháp giải tổng quát làm baseline.
- **Optimal:** hướng phát triển tìm lời giải ngắn nhất theo metric được cấu hình; không gọi một solver nhanh là optimal nếu chưa có cơ sở chứng minh.

Chi tiết từng bước chỉ được ghi trong [ROUX_STRATEGY.md](ROUX_STRATEGY.md) và [CFOP_STRATEGY.md](CFOP_STRATEGY.md). Hai file đó là tài liệu chuẩn cho các quyết định chiến lược theo từng phase.

## 3. Kiến trúc

Tách lõi solver khỏi tầng web:

```text
Trình duyệt → FastAPI → Lõi solver
                         ├── Cube Engine
                         ├── Kociemba
                         ├── CFOP
                         ├── Roux
                         └── Optimal
```

- Cube engine độc lập với FastAPI và frontend.
- Frontend chỉ nhập liệu, gọi API, hiển thị kết quả và tương tác giao diện; không chứa thuật toán giải.
- API xác thực yêu cầu, gọi solver và trả về kết quả có cấu trúc.
- Các solver dùng chung biểu diễn cube và hợp đồng solution.

## 4. Biểu diễn và phép biến đổi cube

Biểu diễn theo cubie:

- Hoán vị và hướng của 8 góc.
- Hoán vị và hướng của 12 cạnh.
- Trạng thái tâm được giữ khi engine hỗ trợ và cần thiết cho frame/metadata.

Trạng thái đã giải có hoán vị identity và hướng bằng 0. Engine hỗ trợ 18 face turn cơ bản, inverse sequence và parser cho Singmaster mở rộng, gồm M/E/S, x/y/z và lớp rộng.

Các bất biến bắt buộc: một move lặp bốn lần trở về trạng thái ban đầu; move hai lần tương đương move 180°; move và inverse triệt tiêu; scramble cộng inverse scramble đưa cube về solved.

## 5. Xác thực và mô hình lời giải

Bộ xác thực kiểm tra đủ và không trùng cubie, tổng hướng góc/cạnh hợp lệ và parity hoán vị góc/cạnh phù hợp.

Solution có cấu trúc, tối thiểu gồm phương pháp, chuỗi move, số move, metric, trạng thái xác minh, danh sách phase và metadata. Mỗi phase có tên, move, số move và mô tả tùy chọn.

Không chỉ trả về một chuỗi move không có ngữ cảnh. Phase boundaries phải thể hiện rõ solver đang giải phần nào và cho phép xác minh từng giai đoạn.

## 6. Nguyên tắc chiến lược

- Ưu tiên quyết định có thể giải thích và gần với tư duy giải thực tế khi mục tiêu là solver human-style.
- Tách tính đúng đắn khỏi tối ưu hóa: lời giải đúng không đồng nghĩa với lời giải ngắn nhất hoặc dễ thao tác nhất.
- Giữ bất biến của các phase đã giải trong quá trình tìm kiếm phase kế tiếp.
- Không tuyên bố tối ưu toàn cục nếu thuật toán chỉ dùng heuristic, giới hạn độ sâu hoặc giới hạn tài nguyên.
- Không âm thầm thay phương pháp được yêu cầu bằng solver khác khi một phase thất bại.
- Chi tiết của Roux và CFOP phải được cập nhật trong các tài liệu chiến lược riêng mỗi khi hành vi trong code thay đổi.

## 7. API và giao diện

Endpoint chính:

```text
POST /api/solve
```

Yêu cầu gồm scramble và tên phương pháp, ví dụ `cfop`, `roux`, `kociemba` hoặc `optimal`. Phản hồi gồm chuỗi lời giải, metric, cờ xác minh, các phase và metadata. Lỗi đầu vào, trạng thái cube bất khả thi, phương pháp không hỗ trợ, timeout hoặc lỗi phase phải trả về cấu trúc lỗi ổn định.

Giao diện tối thiểu cho phép nhập scramble, chọn phương pháp, chạy solve, xem trạng thái lỗi, tổng số move, metric, trạng thái xác minh, từng phase và toàn bộ chuỗi lời giải.

## 8. Kiểm thử

- **Kiểm thử đơn vị:** parser, move engine, inverse move, trạng thái solved, validator và định dạng solution.
- **Kiểm thử bất biến:** move lặp, move kép, scramble/inverse và chuỗi ngẫu nhiên/inverse.
- **Kiểm thử solver:** lời giải đưa cube về solved; move hợp lệ; bất biến phase không bị phá; API chỉ báo verified khi đã xác minh.
- **Kiểm thử hồi quy:** mọi lỗi về chỉ số cubie, ánh xạ move hoặc ranh giới phase phải có trường hợp tái hiện.

Chạy bộ kiểm thử bằng `pytest`. Trước khi tối ưu, phải giữ được kiểm thử tính đúng đắn và benchmark riêng.

## 9. Quy tắc phát triển

- Python 3.12 trở lên; dùng type hints.
- Không dùng trạng thái cube toàn cục có thể bị sửa ngoài ý muốn.
- Ưu tiên phép biến đổi thuần khi phù hợp.
- Không đưa thuật toán solver vào API hoặc frontend.
- Không hard-code lời giải dành riêng cho scramble cụ thể.
- Core phải chạy độc lập với web server.
- Không tự động commit thay đổi; chỉ commit khi được yêu cầu rõ ràng.

## 10. Cấu trúc tài liệu

- [ROADMAP.md](ROADMAP.md): bảy milestone M1–M7, trạng thái và tiêu chí nghiệm thu.
- Tài liệu này: mục tiêu, kiến trúc và nguyên tắc ở mức tổng thể.
- [ROUX_STRATEGY.md](ROUX_STRATEGY.md): chiến lược Roux theo từng phase.
- [CFOP_STRATEGY.md](CFOP_STRATEGY.md): chiến lược CFOP theo từng phase.
- [DEPLOYMENT.md](DEPLOYMENT.md): cài đặt, chạy, kiểm thử và triển khai.
- [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md): thành phần bên thứ ba và giấy phép.
- `WORKLOG.md` ở thư mục gốc: lịch sử công việc, quyết định, kết quả kiểm thử và bước tiếp theo.
