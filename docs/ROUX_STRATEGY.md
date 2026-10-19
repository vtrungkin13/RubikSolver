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

## Quyết định thiết kế: FB xét đủ 24 frame, đáy trắng theo sticker của cubie

Phần này mô tả hợp đồng triển khai cho cơ chế frame FB và tiêu chí cần giữ khi phát triển tiếp.

### Mục tiêu và phạm vi

- Solver xét đủ 24 hướng xoay toàn khối; không loại frame theo vị trí tâm trắng hoặc màu của bất kỳ tâm nào.
- Mỗi frame là một phép xoay setup vật lý ở đầu lời giải; trạng thái sau setup được giải về cùng target chuẩn, không phải target solved xoay theo frame.
- Target cubie của FB luôn là `_FB_TARGET`. Màu trắng ở đáy được xác định bởi sticker mặt D của các viên DL, DFL và DBL; không phải bởi vị trí tâm trắng. Frame tìm kiếm không được phép đổi định nghĩa màu đáy hoặc thay đổi target dùng bởi các phase sau.
- Goal FB gồm góc DLF, DBL; cạnh DL, FL, BL; và tâm L đúng màu với block. Hướng cubie trong target bảo đảm sticker mặt D của DL, DFL và DBL đều màu trắng. Vị trí tâm trắng không phải điều kiện goal; các tâm khác vẫn được theo dõi.
- Xét đủ 24 hướng xoay của khối lập phương: 6 lựa chọn hướng cho trục D nhân 4 hướng xoay quanh trục đó. Setup rotation được đưa vào đầu lời giải; không dùng frame để thay đổi target vật lý.
- Không suy luận vị trí tâm trắng từ chỉ số frame. Frame mô tả ánh xạ vị trí/mặt; `CubeState.center` vẫn là trạng thái tâm thực tế sau các move đã thực thi.

### Tách ba khái niệm

Khi triển khai, phải tách riêng ba khái niệm hiện đang gắn với nhau trong luồng FB:

1. **Frame tìm kiếm (`search_frame`)**: một trong 24 setup rotation; mọi frame đều được xét, bất kể vị trí tâm trắng ban đầu.
2. **Goal FB (`fb_goal`)**: các góc/cạnh và hướng sticker của block trái, bảo đảm mặt đáy của DL/DFL/DBL màu trắng, cùng tâm L đúng màu. Không áp đặt vị trí tâm trắng.
3. **Target hoàn chỉnh (`completion_target`)**: là target toàn khối được giữ nguyên xuyên suốt SB, CMLL, EO, ULUR, L4E. Target cuối có thể ràng buộc cả sáu tâm; điều đó không biến vị trí tâm trắng thành điều kiện hoàn thành FB.

Sau khi chọn frame, target cố định phải được truyền xuyên suốt SB, CMLL, EO, ULUR, L4E. Không được để mỗi phase tự chọn một frame/target khác.

### Hợp đồng giữa các phase

- **FB:** xét đủ 24 frame, hoàn thành block với sticker mặt D của DL/DFL/DBL màu trắng và tâm L đúng màu. Không yêu cầu tâm trắng ở D. Setup rotation được đưa vào đầu lời giải; các tâm vẫn được theo dõi theo trạng thái thực. Việc kiểm tra/điều chỉnh tâm cho EO diễn ra sau SB, ngay trước EO. Lưu trạng thái thực của cubie và cả sáu tâm.
- **SB:** slot của block phải được ánh xạ theo frame FB đã chọn. Điều kiện giữ nguyên FB và kiểm tra SB phải dùng cùng frame, không mặc định chỉ có bốn frame trắng-ở-D của cách triển khai cũ.
- **CMLL:** tập góc tầng U và cách nhận diện AUF phải được diễn giải theo frame hoạt động. Không được dùng target được tạo từ frame khác với target SB.
- **EO:** điều kiện tâm U/D và định hướng cạnh phải được xác định theo frame hoạt động. Quy tắc hiện tại chèn `M'` khi tâm U không phải trắng/vàng không được giữ nguyên một cách máy móc nếu frame mới khiến quy ước U/D khác đi; phải chứng minh và kiểm thử invariant trước khi dùng.
- **ULUR/L4E:** IDA* phải nhận cùng target hoạt động. L4E chỉ thành công khi toàn bộ cubie và sáu tâm khớp target đó; không được chấp nhận trạng thái cubie đúng nhưng tâm sai.

### Tránh duyệt trùng và giới hạn tài nguyên

- Sinh 24 phép quay hợp lệ, kiểm tra chúng là các hướng khác nhau và có ánh xạ thuận/nghịch nhất quán. Chuẩn hóa/deduplicate các frame nếu cách biểu diễn tạo ra cùng một ánh xạ.
- Tất cả 24 frame đều được đưa vào planner. Theo dõi số frame, node và thời gian; giới hạn tài nguyên không chứng minh tối ưu toàn cục.

### Tiêu chí nghiệm thu

1. Có unit test cho tập frame: đủ 24 hướng phân biệt, mọi frame ánh xạ đúng các mặt và có nghịch đảo hợp lệ.
2. Có test FB cho các trạng thái mà tâm trắng ban đầu nằm lần lượt trên U/R/F/D/L/B; frame không bị lọc theo vị trí tâm trắng.
3. Sau FB, xác minh các góc/cạnh và hướng sticker theo target chuẩn, bảo đảm mặt đáy của DL/DFL/DBL màu trắng, tâm L đúng màu block; vị trí tâm trắng không phải điều kiện FB.
4. Chạy regression toàn pipeline trên scramble chuẩn và kiểm tra trạng thái thực sau từng phase, đặc biệt SB không phá FB và L4E giải đúng toàn bộ cubie cùng sáu tâm.
5. Nếu một frame chưa được các phase sau hỗ trợ đầy đủ, solver phải từ chối frame đó một cách tường minh hoặc báo lỗi phase có nguyên nhân; không được trả lời thành công giả.

**Lưu ý:** việc mở rộng sang 24 frame cần đồng bộ target, metadata, xác minh từng phase và target L4E; chỉ tăng số frame mà giữ target cũ là không đủ.

## 1. First Block (FB)

1. Sinh đủ 24 frame và thử setup rotation tương ứng. Với mỗi frame, tìm lời giải từ trạng thái sau setup về target cubie Roux chuẩn có sticker đáy trắng; không tạo target bằng cách xoay trạng thái solved theo frame.
2. Với mỗi frame, chạy bộ dựng FB theo kiểu nhận diện cơ hội trước, sau đó chạy tìm kiếm chính xác có giới hạn để tìm cách cải thiện lời giải dựng được.
3. Bộ dựng theo giai đoạn tận dụng cấu trúc đang có: quan hệ cạnh–tâm, cặp góc–cạnh đã ghép, hình vuông (1×2×2), và đường (1×1×3). Trình tự ưu tiên là tạo/giữ đường (1×1×3) khi khả thi, tạo hình vuông (1×2×2), rồi hoàn tất cặp góc–cạnh còn lại. Nếu nhánh giữ đường không phù hợp, có thể xét cách dựng không giữ đường.
4. Chỉ đưa các ứng viên FB hợp lệ vào danh sách. Thứ tự xếp hạng ưu tiên điểm nhận diện cấu trúc FB có sẵn của frame, giữ các góc U trên tầng U, ứng viên staged khi các tiêu chí trước ngang nhau, số move, độ thuận tay và chỉ số frame. Không dùng vị trí cặp tâm trắng/vàng để ưu tiên frame; bước kiểm tra tâm sau SB chịu trách nhiệm chuẩn bị trục cho EO. Không dùng SB, CMLL hay LSE để chấm điểm chất lượng FB.
5. Đưa setup rotation được chọn vào đầu lời giải. Goal FB yêu cầu sticker mặt D của DL/DFL/DBL màu trắng và tâm L đúng màu theo target chuẩn; không yêu cầu tâm trắng ở D. Phải lưu snapshot đầy đủ của cả 6 center.

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

1. Nhận trạng thái đã giải FB và SB; không thay đổi hoặc dựng lại lời giải SB trong phase CMLL.
2. Nhận diện CMLL 1-look bằng bảng 42 thuật toán. Với mỗi thuật toán, database bao phủ đủ 4 AUF trước thuật toán và 4 AUF sau thuật toán, nhằm nhận diện các trạng thái góc tương ứng mà không cần xoay toàn khối bằng `y`, `y'` hoặc `y2`.
3. AUF trước được chọn có thể cần thiết để đưa trạng thái vào đúng biến thể công thức; nếu có, lời giải CMLL gồm AUF trước đó rồi đến thuật toán CMLL. AUF sau chỉ dùng để mở rộng khả năng nhận diện trạng thái, **không được nối vào lời giải** để căn góc theo tâm.
4. Điều kiện hoàn thành CMLL là bốn góc tầng U được định hướng đúng và có thứ tự tương đối đúng, cho phép bốn trạng thái tương đương AUF. Không thêm move `U` chỉ nhằm căn góc với tâm hoặc ép trạng thái về một AUF duy nhất. Nếu góc đã ở trạng thái CMLL hoàn chỉnh theo điều kiện này, trả về chuỗi move rỗng.
5. Nếu không khớp trường hợp một-look trong bộ nhận diện, dùng quy trình CMLL hai-look hiện có.
6. Một số thuật toán có `r`, nên sau khi áp dụng phải tính lại và lưu snapshot của cả 6 center. Xác minh hai block vẫn được giải và bốn góc CMLL đạt mục tiêu modulo AUF trước khi chuyển sang EO; không yêu cầu bốn center U/F/D/B giữ nguyên.

## 4. LSE: EO → ULUR → L4E

### 4.1. EO — định hướng cạnh

- Trước khi nhận diện EO, kiểm tra tâm U. Nếu tâm U không phải trắng hoặc vàng, áp dụng `M'` một lần, rồi nhận diện EO lại trên trạng thái cube mới sau move này.
- Nếu có `M'`, move này là phần đầu của phase EO và được nối ngay trước công thức EO trong chuỗi move; không tách thành phase riêng.
- Dùng bộ nhận diện công thức EO của LSE trên trạng thái sau bước kiểm tra/hiệu chỉnh tâm.
- Áp dụng công thức được chọn và xác minh mục tiêu EO trước khi tiếp tục. Ghi lại toàn bộ center permutation sau EO; không yêu cầu U/F/D/B giữ nguyên.
- Điều kiện hoàn thành EO chỉ xét 6 cạnh `UR/UF/UL/UB/DF/DB`: hướng của mặt U/D trên mỗi cạnh phải đúng theo màu trắng/vàng (trong mô hình cubie là hướng cạnh khớp với trạng thái đích). Không yêu cầu đủ cả 12 cạnh được định hướng. Đồng thời, hai tâm U/D phải là trắng và vàng, tức `center[0]` và `center[3]` là cặp màu `{0, 3}`.
- ULUR bắt buộc giữ nguyên điều kiện EO đã đạt được: sau ULUR, 6 cạnh `UR/UF/UL/UB/DF/DB` vẫn phải đúng hướng và tâm U/D vẫn phải là cặp trắng/vàng. Trạng thái này là một phần của goal và khóa trạng thái tìm kiếm, không chỉ là kiểm tra sau khi đã tìm được lời giải.
- Không thêm move chỉ để làm các tâm trông như đã trở lại vị trí ban đầu.

### 4.2. ULUR

- Dùng bộ tìm kiếm IDA* riêng trên tập move `M/U`; không nhận diện hoặc thực thi công thức ULUR từ database.
- Heuristic dùng pattern database nội bộ và handoff projection để hướng tìm kiếm tới trạng thái UL/UR hợp lệ.
- Ghi lại chuỗi move, số node đã duyệt (`ulur_nodes`) và snapshot đầy đủ của center sau ULUR.
- Xác minh mục tiêu UL/UR trước khi chuyển sang L4E; không yêu cầu toàn bộ center permutation giữ nguyên sau ULUR.

### 4.3. L4E

- Dùng bộ tìm kiếm IDA* riêng trên tập move `M/U`; không sử dụng công thức L4E từ database hoặc đường tìm kiếm BFS dự phòng.
- Heuristic sử dụng pattern database của bốn cạnh tầng giữa; goal cuối bắt buộc toàn bộ 12 cạnh, 8 góc và cả 6 tâm khớp chính xác trạng thái đích của frame đang dùng.
- Ghi lại chuỗi move, số node đã duyệt (`l4e_nodes`) và snapshot đầy đủ của center sau L4E.
- Nhánh này chỉ hoàn tất L4E trong LSE; không phải fallback của SB và không thay thế toàn bộ Roux bằng Kociemba.
- Vì L4E là phase cuối, không chấp nhận trạng thái chỉ giải xong cubie: mọi center phải trở về đúng vị trí theo trạng thái đích của frame đang dùng. Trạng thái có cubie đúng nhưng tâm sai không được coi là nghiệm.
- Khóa transposition của IDA* phải bao gồm cả permutation tâm, để không gộp hai trạng thái có cubie giống nhau nhưng khả năng hoàn thành tâm khác nhau.

`data/lse_algorithms.json` chỉ còn giữ nhóm công thức EO; các nhóm `ulur` và `l4e` đã bị loại bỏ vì hai phase này do IDA* xử lý trực tiếp.

## 5. Trạng thái phase, metadata và lỗi

Lưu snapshot đầy đủ `cp`, `co`, `ep`, `eo`, `center` tại các mốc `fb_state`, `sb_state`, `cmll_state`, `eo_state`, `ulur_state`, `l4e_state`. Mỗi snapshot phải được tính bằng cách áp dụng đúng chuỗi move lên trạng thái đầu vào của phase, không tái dựng hoặc chuẩn hóa center khi bàn giao.

Thành công cuối cùng đòi hỏi toàn bộ cubie và cả sáu tâm được giải đúng theo frame hoạt động. Nếu một phase lỗi, phải giữ thông tin đủ để xác định chính xác phase đó; không trả kết quả thành công chỉ vì một solver khác có thể giải được cube.

## 6. Các điều không được làm

- Không dùng điểm số CMLL/LSE để chọn SB.
- Không đổi lại FB vì một FB khác có thể làm SB dễ hơn.
- Không đưa direct SB hoặc Kociemba vào làm đường dự phòng.
- Không tuyên bố tìm được FB tối ưu toàn cục chỉ từ tìm kiếm có giới hạn.
- Không bỏ qua xác minh trạng thái thực tại ranh giới phase.

### Chuẩn hóa chuỗi move

- Mọi phase phải được chuẩn hóa sau khi ghép các đoạn tìm kiếm/công thức; các lượt liên tiếp cùng mặt được cộng số mũ modulo 4 (`F2 F'` → `F`, `R R'` → bỏ cả hai).
- Chuỗi lời giải công khai cũng được chuẩn hóa toàn cục để không còn lượt cùng mặt đứng cạnh nhau, kể cả khi ranh giới phase chia cắt cặp lượt đó.
- Chuẩn hóa không đổi thứ tự các mặt khác nhau. Trạng thái cuối sau khi áp dụng chuỗi chuẩn hóa phải vẫn khớp target và được kiểm chứng như trước.
