# Chiến lược giải Roux

> Đây là tài liệu chuẩn mô tả chiến lược Roux hiện được triển khai. Khi có khác biệt, mã nguồn `src/rubik_solver/solvers/roux.py` là căn cứ cuối cùng. Mọi thay đổi chiến lược trong code phải được phản ánh lại tại đây và trong `WORKLOG.md`.

## Luồng giải

`First Block (FB) → Second Block (SB) → CMLL → EO → ULUR → L4E`

Solver chạy đủ sáu phase và kiểm tra trạng thái sau từng phase. Không dừng ở FB/SB, không thay thế lời giải Roux bằng lời giải Kociemba khi một phase thất bại.

## Quy ước chung

- FB và SB là hai ranh giới độc lập. Chọn FB chỉ dựa trên chất lượng FB; không dùng SB, CMLL hoặc LSE để chấm điểm hay chọn lại FB.
- Mỗi phase nhận đúng trạng thái thu được bằng cách áp dụng các move của phase trước. Không tạo trạng thái giả hoặc chuẩn hóa tâm trước khi chuyển phase.
- Toàn bộ 6 center luôn được giữ trong `CubeState` và snapshot metadata sau từng phase. Center chỉ là điều kiện goal khi được nêu rõ; không ép các center U/F/D/B trở về vị trí trước phase. Trong frame Roux đang dùng, L/R là hai center cố định với các tập move của SB/CMLL/LSE; bốn center còn lại được theo dõi theo đúng chuỗi move thực tế.
- Mỗi phase phải kiểm tra điều kiện đích trước khi tiếp tục. Lỗi phải chỉ ra phase thất bại; không âm thầm chuyển sang phương pháp giải khác.
- Giới hạn độ sâu, số node và thời gian là giới hạn tài nguyên; chúng không thay thế bước xác minh trạng thái.

## 1. First Block (FB)

1. Xét bốn frame Roux có trục trắng/vàng ở hướng dự kiến.
2. Với mỗi frame, chạy bộ dựng FB theo kiểu nhận diện cơ hội trước, sau đó chạy tìm kiếm chính xác có giới hạn để tìm cách cải thiện lời giải dựng được.
3. Bộ dựng theo giai đoạn tận dụng cấu trúc đang có: quan hệ cạnh–tâm, cặp góc–cạnh đã ghép, hình vuông (1×2×2), và đường (1×1×3). Trình tự ưu tiên là tạo/giữ đường (1×1×3) khi khả thi, tạo hình vuông (1×2×2), rồi hoàn tất cặp góc–cạnh còn lại. Nếu nhánh giữ đường không phù hợp, có thể xét cách dựng không giữ đường.
4. Chỉ đưa các ứng viên FB hợp lệ vào danh sách. Thứ tự xếp hạng hiện tại ưu tiên: giữ các góc U trên tầng U, điểm nhận diện mẫu của frame, ứng viên từ bộ dựng theo giai đoạn khi các tiêu chí trước ngang nhau, độ thuận tay của chuỗi move, số move và chỉ số frame. Không dùng SB hay các phase sau trong điểm số.
5. Nếu cần đổi hướng toàn khối để thiết lập frame, đưa phép xoay vào đầu lời giải; không xoay trả lại sau khi giải xong. Goal FB gồm các cubie của block và center L đúng màu theo frame. Không yêu cầu F/D/B/U/R khớp frame ở ranh giới FB; phải lưu snapshot đầy đủ của cả 6 center.

Tìm kiếm FB có giới hạn, không đảm bảo lời giải FB ngắn nhất toàn cục. Tham số độ sâu/node/thời gian chỉ giới hạn tài nguyên.

## 2. Second Block (SB)

SB chỉ bắt đầu sau khi ứng viên FB đã được chọn và xác minh. Bộ lập kế hoạch SB dùng nhận diện cơ hội trước rồi mới đến chiến lược DR-first.

### 2.1. Khai thác hình vuông tự do (FREE_SQUARE)

- Nhận diện hình vuông (1×2×2) đã ghép dù nó chưa nằm đúng vị trí đích.
- Nếu cần, dùng các move `R`, `R2` hoặc `R'` để đưa hình vuông về phía FR/BR thích hợp.
- Giữ các quan hệ cubie cần thiết trong khi giải cặp còn lại.
- Nhánh này dùng giới hạn tài nguyên chung; ngưỡng 7 move **không** áp dụng cho nhánh FREE_SQUARE.

### 2.2. Khai thác cặp tự do (FREE_PAIR)

Cặp góc–cạnh đã ghép được nhận diện theo danh tính cubie và quan hệ màu, không yêu cầu cặp đã ở đúng slot cuối cùng. Bộ nhận diện bao gồm các cơ hội liên quan tới cạnh DR ghép với góc SB và các quan hệ cạnh FR/BR với tâm tương ứng.

1. Thử chuyển cặp tự do thành hình vuông FR hoặc BR; trong bước thử này phải giữ nguyên các cặp đã ghép cần bảo toàn.
2. Nhánh square-first chỉ được tìm đến **7 move**. Nếu không tìm được hình vuông trong giới hạn này, bỏ nhánh thử đó và chuyển sang cách dựng DR có bảo toàn cặp hoặc DR-first.
3. Nếu đã có một hoặc hai cặp góc–cạnh ghép sẵn, dựng DR trong khi giữ nguyên các cặp đó; sau đó đưa từng cặp về slot đích, tiếp tục bảo toàn những cặp chưa chèn.
4. Nếu không thể hoàn thành nhánh khai thác cơ hội, tiếp tục sang DR-first.

### 2.3. DR-first và chọn thứ tự FR/BR

1. Tạo một tập nhỏ các ứng viên dựng DR từ hai cách dựng tự nhiên; hiện chỉ giữ tối đa ba ứng viên DR khác nhau.
2. Xếp hạng sơ bộ theo độ sẵn sàng của cặp FR/BR và độ dài đường dựng DR.
3. Với mỗi ứng viên DR, đánh giá **cả FR-first và BR-first**. Giải thử cặp đầu, sau đó tính lại độ khó và cơ hội nhận diện của cặp còn lại từ trạng thái mới.
4. Điểm lookahead xem xét khả năng nhìn thấy góc và cạnh trên U/F, cơ hội FREE_SQUARE/FREE_PAIR, độ khó ước lượng của cặp cuối, độ dài lời giải và tie-break theo move. Không cố định FR-first chỉ vì nó được xét trước.
5. Hoàn tất từng kế hoạch ứng viên và chọn kế hoạch tốt nhất theo điểm số nội bộ SB. Đây là lookahead chỉ trong SB, không dùng CMLL/LSE để xếp hạng.

SB dùng tập move nội bộ ưu tiên `U/R/r/M`; các ứng viên hoàn tất cuối có thể xét thêm một số move ngoại lệ có phạt điểm. Mặc định `sb_max_depth=None), nên không có trần HTM mặc định cho planner theo giai đoạn; node limit và timeout vẫn có hiệu lực.

**Không có direct-SB fallback và không có Kociemba fallback.** Nếu planner SB không tìm được lời giải trong resource budget, phải báo lỗi phase SB.

### 2.4. Chuẩn hóa move bàn giao sang EO

Sau khi chọn xong SB, bộ chuẩn hóa cục bộ có thể đổi move cuối `R/R'` thành `r/r'` nếu các cubie FB/SB vẫn được giải và trạng thái tâm phù hợp hơn cho bước bàn giao EO. Đây chỉ là chuẩn hóa handoff; không được dùng để chấm điểm SB theo CMLL/LSE hay chọn lại FB.

### 2.5. Điều kiện xác minh SB

- SB phải đạt đúng mục tiêu cubie trong frame đã chọn. Center R và L giữ nguyên; bốn center U/F/D/B có thể thay đổi theo các move `M/r` và phải được ghi lại chính xác.
- FB phải tiếp tục được giải sau khi áp dụng SB.
- Kiểm tra trên trạng thái thực sau khi áp dụng toàn bộ chuỗi move, không chỉ dựa vào kết quả tìm kiếm trung gian. Không yêu cầu toàn bộ center permutation sau SB bằng trạng thái sau FB.

## 3. CMLL

1. Nhận trạng thái đã giải FB và SB.
2. Nhận diện và giải bốn góc tầng U bằng bảng thuật toán CMLL 42 trường hợp, có xử lý các biến thể AUF.
3. Nếu không khớp trường hợp một-look trong bộ nhận diện, dùng quy trình CMLL hai-look hiện có.
4. Một số thuật toán có `r`, nên sau khi áp dụng phải tính lại và lưu snapshot của cả 6 center. Xác minh hai block vẫn được giải và cả bốn góc CMLL đã đúng trước khi chuyển sang EO; không yêu cầu bốn center U/F/D/B giữ nguyên.

## 4. LSE: EO → ULUR → L4E

### 4.1. EO — định hướng cạnh

- Dùng bộ nhận diện công thức EO của LSE trên trạng thái sau CMLL.
- Áp dụng công thức được chọn và xác minh mục tiêu EO trước khi tiếp tục. Ghi lại toàn bộ center permutation sau EO; không yêu cầu U/F/D/B giữ nguyên.
- Không thêm move chỉ để làm các tâm trông như đã trở lại vị trí ban đầu.

### 4.2. ULUR

- Dùng bộ tìm kiếm IDA* riêng trên tập move `M/U`.
- Ghi lại chuỗi move, số node đã duyệt và snapshot đầy đủ của center sau ULUR.
- Xác minh mục tiêu UL/UR trước khi chuyển sang L4E; không yêu cầu toàn bộ center permutation giữ nguyên sau ULUR.

### 4.3. L4E

- Ưu tiên bộ nhận diện công thức L4E hiện có.
- Nếu bảng công thức không có trường hợp phù hợp với trạng thái hợp lệ, dùng tìm kiếm trạng thái chính xác cục bộ L4E trên tập `M/U`.
- Nhánh này chỉ hoàn tất L4E trong LSE; không phải fallback của SB và không thay thế toàn bộ Roux bằng Kociemba.
- Xác minh cubie cuối cùng đã giải trong frame đang dùng và ghi lại trạng thái center thực tế sau L4E. Các center U/F/D/B không bị ép về permutation ban đầu nếu thuật toán đã giải đúng mục tiêu cubie; L/R phải giữ nguyên theo quy ước move/frame.

## 5. Trạng thái phase, metadata và lỗi

Lưu snapshot đầy đủ `cp`, `co`, `ep`, `eo`, `center` tại các mốc `fb_state`, `sb_state`, `cmll_state`, `eo_state`, `ulur_state`, `l4e_state`. Mỗi snapshot phải được tính bằng cách áp dụng đúng chuỗi move lên trạng thái đầu vào của phase, không tái dựng hoặc chuẩn hóa center khi bàn giao.

Thành công cuối cùng đòi hỏi cubie được giải trong frame hoạt động. Nếu một phase lỗi, phải giữ thông tin đủ để xác định chính xác phase đó; không trả kết quả thành công chỉ vì một solver khác có thể giải được cube.

## 6. Các điều không được làm

- Không dùng điểm số CMLL/LSE để chọn SB.
- Không đổi lại FB vì một FB khác có thể làm SB dễ hơn.
- Không đưa direct SB hoặc Kociemba vào làm đường dự phòng.
- Không tuyên bố tìm được FB tối ưu toàn cục chỉ từ tìm kiếm có giới hạn.
- Không bỏ qua xác minh trạng thái thực tại ranh giới phase.
