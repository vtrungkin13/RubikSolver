# RubikSolver — Nhật ký phát triển và bàn giao phiên

> Đây là nguồn theo dõi tiến độ, quyết định kỹ thuật, kết quả kiểm thử và việc cần làm tiếp theo. Khi thông tin trong nhật ký khác với mã nguồn, Git hoặc kết quả kiểm thử hiện tại, hãy ưu tiên kiểm tra trạng thái thực tế.

**Workspace:** `D:\Coding\Python\RubikSolver`

**Nhánh Git đã biết:** `main`

**Quy tắc Git:** Không tự ý commit hoặc push nếu chưa được yêu cầu rõ ràng.

## 1. Trạng thái hiện tại

### 2026-10-18 — Bắt đầu triển khai Cube 3D

- Đọc `docs/THIET_KE_KY_THUAT_CUBE_3D.md` và bắt đầu triển khai theo thứ tự API trạng thái → mô hình Three.js → animation → đồng bộ snapshot.
- Thêm `POST /api/cube/state`, serialize 54 facelet theo thứ tự URFDLB và bổ sung `initial_state`, `step_states`, `final_state` trong phản hồi solve.
- Tạo `frontend/cube/cube-view.js` và `frontend/cube/cube-app.js`: dựng 27 cubie/sticker, OrbitControls, hoạt ảnh mặt, hỗ trợ face/wide/slice/whole-cube moves, Next/Previous/Reset, kiểm tra snapshot.
- Nối panel Cube 3D vào giao diện, đồng bộ scramble và ngôn ngữ EN/VI, highlight move hiện tại; giữ nguyên các thay đổi frontend/API có sẵn trước đó.
- Điều chỉnh kiểm tra parity để tính cả hoán vị tâm — cần thiết cho các trạng thái hợp lệ sinh bởi wide/slice/whole-cube moves. Bổ sung kiểm thử cho API trạng thái và trạng thái mở rộng.
- Kiểm thử đã đạt: `tests/test_api.py` (10 passed) trước cập nhật validator; `tests/test_validator.py` sau cập nhật (11 passed); kiểm thử trình duyệt đã đi qua chuỗi `r U2 M x`, 13 move gồm đủ sáu mặt, move nghịch và `R2`, cùng Previous/Reset; tất cả snapshot khớp.
- Bộ kiểm thử toàn dự án trên trạng thái cuối: `python -m pytest` — **148 passed in 307.81s**. Trước đó, bộ API/validator đạt 21 test và kiểm thử CFOP rotated-frame + validator đạt 12 test. Kiểm tra trình duyệt xác nhận CFOP/Roux/Kociemba đều trả snapshot cuối solved với scramble `R U`; đã chạy từng bước qua đủ sáu mặt, move nghịch, `R2`, wide/slice/rotation và kiểm tra Previous/Reset.
- Đã commit trạng thái này trên nhánh `main`: `444e99f` (`Update solver, frontend, and cube 3D design`). Tại thời điểm commit, working tree sạch; chưa push lên remote.
- Three.js hiện tải từ CDN phiên bản ghim `0.180.0`, nên cần cân nhắc vendoring/offline ở bước hoàn thiện.

### 2026-10-18 — Cập nhật trạng thái M5 và M6

- Đánh dấu M5 (CFOP) và M6 (Roux) là **đã thực hiện; cần tối ưu** trong `docs/ROADMAP.md`.
- Cập nhật README và ưu tiên tiếp theo: tối ưu chất lượng lời giải CFOP; cải thiện độ ổn định SB của Roux và bổ sung kiểm thử hồi quy.
- Chưa chạy kiểm thử trong lần cập nhật tài liệu này; các trường hợp SB thất bại đã ghi nhận vẫn là đầu việc cần xử lý, không che giấu bằng cách hạ trạng thái milestone.

### 2026-10-18 — Chuẩn hóa danh sách milestone thành M1–M7

- Thống nhất thứ tự milestone: M1 Cube model + moves; M2 Scramble parser + validator; M3 Search foundation; M4 Kociemba solver; M5 CFOP; M6 Roux; M7 Web UI.
- Cập nhật `docs/ROADMAP.md`, phần trạng thái dự án trong `README.md` và mục cấu trúc tài liệu của `docs/PROJECT_SPEC.md` để thống nhất với danh sách bảy milestone đã chốt.
- Chưa chạy lại bộ kiểm thử vì thay đổi lần này chỉ điều chỉnh tài liệu.

### 2026-10-18 — Bổ sung roadmap và tiêu chí nghiệm thu milestone

- Tạo `docs/ROADMAP.md` để theo dõi milestone M1–M7, trạng thái, tiêu chí nghiệm thu và ưu tiên tiếp theo.
- Liên kết roadmap từ `README.md` và bổ sung vào danh sách tài liệu chuẩn.
- Trạng thái milestone được ghi thận trọng theo tài liệu hiện có; cần đối chiếu kết quả kiểm thử thực tế trước khi tuyên bố hoàn thành, đặc biệt với Roux/SB.

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

- `docs/ROADMAP.md` — milestone, trạng thái và tiêu chí nghiệm thu.
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
