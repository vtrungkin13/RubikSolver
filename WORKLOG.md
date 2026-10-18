# RubikSolver — Nhật ký phát triển và bàn giao phiên

> Đây là nguồn theo dõi tiến độ, quyết định kỹ thuật, kết quả kiểm thử và việc cần làm tiếp theo. Khi thông tin trong nhật ký khác với mã nguồn, Git hoặc kết quả kiểm thử hiện tại, hãy ưu tiên kiểm tra trạng thái thực tế.

**Workspace:** `D:\Coding\Python\RubikSolver`

**Nhánh Git đã biết:** `main`

**Quy tắc Git:** Không tự ý commit hoặc push nếu chưa được yêu cầu rõ ràng.

## 1. Trạng thái hiện tại

### 2026-10-18 — Chuẩn hóa tài liệu tiếng Việt và đối chiếu chiến lược solver

- Chuyển `README.md` và tài liệu trong `docs/` sang tiếng Việt; giữ nguyên tên API, phase, ký hiệu nước đi, lớp/hàm và thuật ngữ cần thiết để đối chiếu mã nguồn.
- Rút gọn `docs/PROJECT_SPEC.md` thành đặc tả tổng thể về mục tiêu, kiến trúc, nguyên tắc và luồng chiến lược. Quy tắc theo từng phase được ghi trong tài liệu chiến lược riêng.
- Đối chiếu `docs/ROUX_STRATEGY.md` với `src/rubik_solver/solvers/roux.py`: cập nhật thứ tự xếp hạng FB, nhận diện `FREE_SQUARE`/`FREE_PAIR`, phạm vi áp dụng ngưỡng 7 move, giữ cặp có sẵn, giới hạn ba ứng viên DR, đánh giá cả `FR-first`/`BR-first`, bàn giao EO và fallback cục bộ L4E.
- Đối chiếu `docs/CFOP_STRATEGY.md` với `src/rubik_solver/solvers/cfop.py`: Cross được giải trong frame chuẩn trước khi chọn hướng y để trình bày Cross; F2L chọn cặp động; OLL có 57 trường hợp và PLL có 21 trường hợp, bao gồm nhận diện biến thể AUF/y.
- Cập nhật README, đặc tả tổng thể, hướng dẫn triển khai và thông báo giấy phép bên thứ ba bằng tiếng Việt.
- Kiểm tra `git diff --check` và các liên kết Markdown. Không chạy lại bộ kiểm thử solver vì chỉ thay đổi tài liệu.
- **Bước tiếp theo:** dùng hai tài liệu chiến lược làm chuẩn khi phát triển; cập nhật chúng cùng lúc với thay đổi hành vi solver.

## 2. Các quyết định và mốc kỹ thuật gần đây

### 2026-10-10 — Giữ nguyên trạng thái CubeState tại ranh giới FB/SB

- Loại bỏ việc chuẩn hóa `center` làm thay đổi hoán vị tâm thực tế sau FB. SB nhận đúng trạng thái thu được khi áp dụng chuỗi FB lên scramble.
- Lưu trạng thái sau FB vào `metadata.fb_state`, gồm `cp`, `co`, `ep`, `eo` và `center`; giữ `fb_center_state` để quan sát riêng trạng thái tâm.
- Kiểm thử ranh giới phase xác nhận trạng thái tâm thực được giữ nguyên. Tại thời điểm ghi nhận, bộ test Roux đầy đủ vẫn có một số trường hợp thất bại do SB không tìm được phần tiếp nối; không xem đó là bộ test đã đạt hoàn toàn.

### 2026-10-10 — Tâm là dữ liệu quan sát trong mục tiêu FB

- Việc hoàn thành FB dựa trên cubie của FB, không dùng trạng thái tâm để kéo dài hoặc xếp hạng chuỗi FB.
- Ghi lại trạng thái tâm sau FB; không thêm nước đi chỉ để khôi phục tâm.
- Điều chỉnh projection và mục tiêu các phase sau để dùng điều kiện cubie phù hợp; vẫn giữ yêu cầu tương thích giữa FB và phần tiếp nối Roux.

### 2026-10-10 — Nhận diện đồng thời cấu trúc FB

- Bổ sung nhận diện `Ctr-FL`, `Ctr-BL`, `Ctr-DL`, các cặp corner-edge hoàn chỉnh, hình vuông `2x2` và đường `1x3` FL/BL. `Ctr` chỉ center (tâm), không phải corner (góc).
- Xếp hạng ứng viên FB dựa trên các cấu trúc đã nhận diện và kiểm tra trạng thái tâm của ứng viên hoàn chỉnh.
- Khi đã có đường FL/BL, ưu tiên cách dựng bảo toàn đường; nếu tìm kiếm có giới hạn không thành công thì mới thử cách có thể phá đường.
- Bộ test Roux tại thời điểm đó: 26 test đạt.

### 2026-10-05 — CubeState có theo dõi hoán vị tâm

- Bổ sung `center` theo quy ước `U,R,F,D,L,B` của engine Kociemba.
- Các nước đi thường và nước đi mở rộng như `x/y/z`, `M`, `r`, `u` cập nhật hoán vị tâm.
- Kiểm tra FB theo đúng frame tâm đã chọn; các phase LSE được kiểm tra để tránh trạng thái cubie đúng nhưng frame tâm không đúng.
- Engine CFOP và trạng thái mục tiêu Roux được cập nhật để bảo toàn dữ liệu tâm.

### 2026-10-05 — Quy tắc độ sâu SB

- Bỏ giới hạn cứng 14 HTM khỏi tìm kiếm theo giai đoạn của SB; việc tìm kiếm vẫn chịu giới hạn số node và thời gian.
- Ranh giới FB/SB là ranh giới cứng: chính sách độ sâu SB không được tác động đến việc chọn FB.

### 2026-10-04 — Tách biệt FB và SB

- Việc xếp hạng FB không dùng phần tiếp nối SB hoặc lookahead của SB.
- Chốt ứng viên FB trước; chỉ sau đó mới tìm SB từ trạng thái sau FB.
- Không tự động commit khi chưa có yêu cầu rõ ràng.

### 2026-10-04 — Bộ lập kế hoạch SB theo hướng giải của con người

- Bộ nhận diện `SBOpportunityDetector` phát hiện cơ hội `FREE_SQUARE` và `FREE_PAIR` trên trạng thái cố định sau FB.
- DR-first là chiến lược SB thông thường; đánh giá cả hai hướng dựng FR/BR và xếp hạng dựa trên trạng thái sau DR.
- Bổ sung metadata về chiến lược, cơ hội và quá trình lựa chọn để phục vụ chẩn đoán.
- Ở thời điểm ban đầu, luồng SB vẫn có fallback trực tiếp; quyết định ngày 2026-10-10 bên dưới đã loại bỏ fallback trực tiếp SB và Kociemba khỏi luồng Roux.

### 2026-10-03 — Hoàn thiện các phase Roux

- Triển khai CMLL và LSE gồm EO → ULUR → L4E.
- Kiểm tra trạng thái sau từng phase; dùng IDA* cho ULUR và bộ công thức L4E trước, sau đó mới dùng tìm kiếm M/U cục bộ nếu bảng công thức không có trường hợp phù hợp.
- Một số trạng thái cố định sau FB từng không tìm được phần tiếp nối trong giới hạn tìm kiếm. Cần ghi nhận riêng các lỗi này, không xem việc một số scramble chạy được là bằng chứng toàn bộ Roux đã ổn định.

### 2026-10-02 — Phát triển First Block của Roux

- Xây dựng bộ nhận diện cấu trúc và xếp hạng ứng viên FB.
- Điều chỉnh hợp đồng frame và hướng xoay để xác minh FB trong đúng frame đang hoạt động.
- Đánh giá các ứng viên hoàn chỉnh thay vì dựa vào một lựa chọn cặp duy nhất.

### 2026-10-01 — Hoàn thiện CFOP

- Xây dựng Cross bằng IDA* với pattern database chính xác cho bốn cạnh Cross.
- Phát triển F2L theo cặp corner-edge, có bảo toàn Cross và các cặp đã giải, đánh giá tính thuận tiện khi thực hiện và khả năng tạo cơ hội cho cặp tiếp theo.
- Bổ sung nhận diện OLL 57 trường hợp và PLL 21 trường hợp, bao gồm xử lý AUF và hướng xoay tương đương.
- Tích hợp các phase và kiểm tra lại lời giải trên trạng thái scramble. Các lỗi về đổi frame F2L, nhận diện PLL và trường hợp scramble dài được xử lý qua các mốc sửa lỗi trong nhật ký lịch sử.

### 2026-09-30 — Nền tảng cube, tìm kiếm và Kociemba

- Xây dựng mô hình `CubeState`, bộ thực thi nước đi, parser/validator scramble và nền tảng tìm kiếm IDA* có giới hạn độ sâu, số node và thời gian.
- Sửa mapping cạnh của nước đi D; duy trì các kiểm thử bất biến cho nước đi và chuỗi nghịch đảo.
- Tích hợp engine Kociemba Two-Phase thuần Python, kiểm tra lời giải bằng cách áp dụng lên cube đã scramble và xử lý xung đột namespace với package bên ngoài `rubik-solver-py`.
- Thiết lập quy ước bàn giao: cập nhật `WORKLOG.md` cùng phiên khi có thay đổi quan trọng; ưu tiên trạng thái Git và kết quả kiểm thử thực tế khi có mâu thuẫn.

## 3. Quy tắc phát triển và kiểm thử

- Mỗi solver phải xác minh lời giải bằng cách áp dụng chuỗi nước đi lên trạng thái đầu vào; không chỉ dựa vào số move hoặc kết quả heuristic.
- Xác minh trạng thái ở ranh giới từng phase. Không dùng phase sau để thay đổi quyết định của phase trước nếu kiến trúc đã quy định ranh giới độc lập.
- Phân biệt lỗi chiến lược, lỗi tìm kiếm do giới hạn tài nguyên và lỗi xác minh trạng thái.
- Không tuyên bố solver hoặc toàn bộ bộ test đã ổn định nếu vẫn còn trường hợp thất bại chưa được giải thích.
- Sau khi sửa mã nguồn: chạy test tập trung, sau đó chạy bộ test phù hợp với phạm vi ảnh hưởng; kiểm tra `git diff --check` và `git status`.
- Chỉ commit hoặc push khi được yêu cầu rõ ràng.

## 4. Tài liệu chuẩn

- `README.md` — giới thiệu dự án và cách bắt đầu.
- `docs/PROJECT_SPEC.md` — đặc tả và kiến trúc tổng thể.
- `docs/ROUX_STRATEGY.md` — chiến lược Roux theo từng phase; đối chiếu với `src/rubik_solver/solvers/roux.py`.
- `docs/CFOP_STRATEGY.md` — chiến lược CFOP theo từng phase; đối chiếu với `src/rubik_solver/solvers/cfop.py`.
- `docs/DEPLOYMENT.md` — hướng dẫn cài đặt và chạy.
- `docs/THIRD_PARTY_NOTICES.md` — giấy phép và nguồn của thành phần bên thứ ba.

## 5. Quy trình bàn giao cho phiên tiếp theo

1. Đọc `WORKLOG.md` và `docs/PROJECT_SPEC.md`.
2. Đọc tài liệu chiến lược liên quan đến task đang làm.
3. Kiểm tra `git status`, diff hiện tại và mã nguồn thực tế trước khi sửa.
4. Chạy kiểm thử phù hợp với thay đổi; ghi rõ kết quả thực tế, kể cả test thất bại.
5. Cập nhật nhật ký với quyết định, thay đổi, kiểm thử và bước tiếp theo.
6. Không giả định trạng thái ghi trong nhật ký luôn mới hơn Git hoặc mã nguồn hiện tại.
