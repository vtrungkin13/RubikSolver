# RubikSolver — Lộ trình và milestone

> Đây là nguồn chuẩn để theo dõi phạm vi, tiêu chí nghiệm thu và trạng thái của bảy milestone dự án. `WORKLOG.md` lưu nhật ký công việc theo phiên. Trạng thái cần dựa trên mã nguồn và kết quả kiểm thử thực tế, không chỉ dựa trên ghi chép lịch sử.

## 1. Quy ước trạng thái

- **Hoàn thành:** các tiêu chí nghiệm thu đã được kiểm chứng bằng code và kiểm thử phù hợp.
- **Đang thực hiện:** đã có triển khai nhưng còn tiêu chí hoặc lỗi cần xử lý.
- **Chưa bắt đầu:** chưa có triển khai đáng kể cho mục tiêu đó.
- **Cần xác minh:** tài liệu lịch sử cho biết đã làm, nhưng chưa có đủ bằng chứng hiện tại để xác nhận.

## 2. Danh sách milestone

| Mã | Milestone | Trạng thái ghi nhận | Phạm vi |
|---|---|---|---|
| M1 | Cube model + moves | Đã triển khai; cần xác nhận bằng kiểm thử hiện tại | Mô hình trạng thái cube và thực thi nước đi |
| M2 | Scramble parser + validator | Đã triển khai; cần xác nhận bằng kiểm thử hiện tại | Phân tích scramble và xác thực trạng thái |
| M3 | Search foundation | Đã triển khai; cần xác nhận bằng kiểm thử hiện tại | Nền tảng tìm kiếm dùng chung và giới hạn tài nguyên |
| M4 | Kociemba solver | Đã triển khai; cần xác nhận bằng kiểm thử hiện tại | Solver tổng quát Two-Phase |
| M5 | CFOP | Đã thực hiện; cần tối ưu | Cross → F2L → OLL → PLL |
| M6 | Roux | Đã thực hiện; cần tối ưu | FB → SB → CMLL → EO → ULUR → L4E |
| M7 | Web UI | Đã triển khai; cần xác nhận bằng kiểm thử hiện tại | Giao diện web kết nối với API |

> Trạng thái M5 và M6 được ghi nhận là đã thực hiện, với công việc tiếp theo tập trung vào tối ưu chất lượng và độ ổn định. Chưa chạy lại toàn bộ bộ kiểm thử trong lần cập nhật roadmap này; nhật ký vẫn ghi nhận một số trường hợp SB không tìm được phần tiếp nối trong giới hạn tài nguyên, cần giữ làm đầu việc tối ưu và kiểm thử hồi quy.

## 3. Tiêu chí nghiệm thu

### M1 — Cube model + moves

**Mục tiêu:** Có mô hình cube nhất quán và bộ thực thi nước đi làm nền cho các thành phần còn lại.

- [ ] Biểu diễn trạng thái cubie nhất quán, bao gồm hoán vị/hướng góc và cạnh; lưu trạng thái tâm khi cần cho frame/metadata.
- [ ] Các nước đi được hỗ trợ cập nhật trạng thái chính xác.
- [ ] Move lặp bốn lần trở về trạng thái ban đầu; move và inverse triệt tiêu; move kép tương đương phép quay 180°.
- [ ] Có kiểm thử đơn vị và kiểm thử bất biến cho move engine.

### M2 — Scramble parser + validator

**Mục tiêu:** Phân tích chuỗi scramble và từ chối đầu vào/trạng thái không hợp lệ.

- [ ] Parser hỗ trợ cú pháp Singmaster được dự án công bố, bao gồm các dạng mở rộng đã triển khai.
- [ ] Lỗi cú pháp được báo rõ ràng.
- [ ] Validator phát hiện cubie thiếu/trùng, tổng hướng không hợp lệ và parity không hợp lệ.
- [ ] Scramble cộng chuỗi nghịch đảo đưa cube về trạng thái ban đầu.
- [ ] Có kiểm thử cho đầu vào hợp lệ, đầu vào lỗi và bất biến trạng thái.

### M3 — Search foundation

**Mục tiêu:** Cung cấp nền tảng tìm kiếm dùng chung với giới hạn tài nguyên rõ ràng.

- [ ] Thuật toán tìm kiếm trả về chuỗi move có thể áp dụng lên trạng thái.
- [ ] Giới hạn độ sâu, số node và thời gian được xử lý rõ ràng.
- [ ] Phân biệt không tìm thấy lời giải trong giới hạn tài nguyên với lỗi logic hoặc trạng thái không hợp lệ.
- [ ] Có kiểm thử cho mục tiêu tìm kiếm, giới hạn tài nguyên và xác minh lời giải.
- [ ] Không tuyên bố lời giải tối ưu nếu chưa có bảo đảm thuật toán phù hợp.

### M4 — Kociemba solver

**Mục tiêu:** Có solver tổng quát Two-Phase làm baseline.

- [ ] Giải được các trạng thái hợp lệ trong phạm vi kiểm thử.
- [ ] Áp dụng lời giải lên trạng thái đầu vào xác minh cube đã giải.
- [ ] Xử lý rõ ràng đầu vào lỗi và trường hợp không giải được trong giới hạn cho phép.
- [ ] Bộ kiểm thử Kociemba và kiểm thử tích hợp liên quan chạy đạt.

### M5 — CFOP

**Mục tiêu:** Tạo lời giải có ranh giới phase rõ ràng theo Cross → F2L → OLL → PLL.

- [ ] Cross được giải và xác minh trước F2L.
- [ ] Bốn cặp F2L được hoàn thành mà không phá Cross hoặc các cặp đã giải.
- [ ] OLL nhận diện và xử lý 57 trường hợp theo triển khai; PLL nhận diện và xử lý 21 trường hợp, gồm các biến thể AUF/hướng xoay được hỗ trợ.
- [ ] Trạng thái được xác minh sau từng phase và sau toàn bộ lời giải.
- [ ] Bộ kiểm thử CFOP và kiểm thử hồi quy liên quan chạy đạt.

Tài liệu chiến lược chuẩn: [CFOP_STRATEGY.md](CFOP_STRATEGY.md).

### M6 — Roux

**Mục tiêu:** Giải theo luồng FB → SB → CMLL → EO → ULUR → L4E, không âm thầm thay bằng solver khác khi một phase thất bại.

- [ ] FB được chọn dựa trên chất lượng FB; không dùng phase sau để chấm điểm hoặc chọn lại FB.
- [ ] SB bắt đầu từ trạng thái thực sau FB và giữ nguyên ranh giới trạng thái giữa các phase.
- [ ] SB thực hiện chiến lược khai thác cơ hội/DR-first như tài liệu; nếu thất bại thì báo lỗi đúng phase, không dùng direct-SB hoặc Kociemba fallback.
- [ ] CMLL, EO, ULUR và L4E xác minh mục tiêu phase trước khi tiếp tục.
- [ ] Lời giải cuối cùng đưa cube về solved và metadata phản ánh đúng các phase đã thực thi.
- [ ] Các trường hợp SB từng thất bại được tái hiện, phân loại nguyên nhân và bổ sung kiểm thử hồi quy.
- [ ] Bộ kiểm thử Roux đầy đủ chạy đạt; giới hạn tài nguyên và các trường hợp thất bại còn lại được ghi rõ.

Tài liệu chiến lược chuẩn: [ROUX_STRATEGY.md](ROUX_STRATEGY.md).

### M7 — Web UI

**Mục tiêu:** Cho phép người dùng nhập scramble, chọn phương pháp giải và xem lời giải có cấu trúc qua giao diện web.

- [ ] Người dùng có thể nhập scramble và chọn solver được API hỗ trợ.
- [ ] Giao diện gọi API và hiển thị kết quả hoặc lỗi rõ ràng.
- [ ] Hiển thị chuỗi move, metric, trạng thái xác minh và các phase khi có trong phản hồi.
- [ ] Frontend không chứa logic thuật toán solver; core có thể chạy độc lập với web server.
- [ ] Kiểm thử API và kiểm tra tích hợp phù hợp chạy đạt.

## 4. Ưu tiên tiếp theo

1. **M6 — Roux/SB:** tối ưu độ ổn định; tái hiện các trường hợp thất bại đã ghi nhận và xác định nguyên nhân là chiến lược, giới hạn tìm kiếm hay xác minh trạng thái.
2. **M5 — CFOP:** tối ưu chất lượng lời giải và kiểm thử hồi quy cho Cross, F2L, OLL, PLL.
3. **M1–M4 và M7:** tiếp tục xác nhận trạng thái bằng các bộ kiểm thử tương ứng.
4. Cập nhật roadmap và `WORKLOG.md` cùng lúc khi có thay đổi trạng thái hoặc tiêu chí nghiệm thu.

## 5. Quy tắc cập nhật

- Giữ nguyên thứ tự và tên bảy milestone M1–M7 đã thống nhất.
- Chỉ đánh dấu hoàn thành sau khi đối chiếu code và bằng chứng kiểm thử.
- Nếu còn lỗi quan trọng hoặc tiêu chí chưa kiểm chứng, dùng trạng thái **Đang thực hiện** hoặc **Cần xác minh**.
- Phân biệt lỗi chiến lược, lỗi tìm kiếm do giới hạn tài nguyên và lỗi xác minh trạng thái.
- Không tự động commit hoặc push nếu chưa được yêu cầu rõ ràng.
- Khi bắt đầu phiên mới, đọc `WORKLOG.md`, tài liệu này và tài liệu chiến lược liên quan; sau đó kiểm tra Git và code thực tế.
