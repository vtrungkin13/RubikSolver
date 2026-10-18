# Chiến lược giải CFOP

> Đây là tài liệu chuẩn mô tả chiến lược CFOP hiện được triển khai. Khi có khác biệt, mã nguồn `src/rubik_solver/solvers/cfop.py` là căn cứ cuối cùng. Mọi thay đổi chiến lược trong code phải được phản ánh lại tại đây và trong `WORKLOG.md`.

## Luồng giải

`Orientation → Cross → F2L-1 → F2L-2 → F2L-3 → F2L-4 → OLL → PLL`

Phase `Orientation` là bước thiết lập hướng toàn khối được xuất riêng trong solution. Bốn phase F2L tương ứng với bốn cặp góc–cạnh; chúng không nhất thiết được giải theo thứ tự slot cố định.

## 1. Orientation và Cross

### 1.1. Hệ tọa độ nội bộ

- Chuyển trạng thái đầu vào sang hệ tọa độ nội bộ bằng phép xoay `x2`, đưa mặt trắng xuống D.
- Giải Cross trong hệ tọa độ chuẩn này trước; chưa chọn frame y vật lý ở bước tìm kiếm Cross.
- Bộ tìm Cross dùng IDA* với heuristic chính xác từ pattern database cho abstraction bốn cạnh Cross, cùng quy tắc cắt tỉa các move liên tiếp trên cùng mặt.
- Áp dụng giới hạn độ sâu, node và timeout được cấu hình. Nếu tìm kiếm vượt giới hạn hoặc thất bại, phải báo lỗi phase; không âm thầm thay bằng Kociemba.

### 1.2. Chọn hướng nhìn Cross

Sau khi có lời giải Cross chuẩn, xét bốn hướng xoay quanh trục y. Biến đổi chuỗi Cross tương ứng với từng hướng, rồi chấm điểm theo hồ sơ move/độ thuận tay F2L. Chọn frame có điểm tốt nhất; đây là chọn cách trình bày Cross và hướng nhìn, không thay đổi mục tiêu Cross.

Chuỗi giải xuất ra có phase `Orientation` gồm `x2` và hướng `y` được chọn, tiếp theo là chuỗi Cross đã biến đổi vào frame vật lý đó. Các phép xoay là move tường minh trong solution.

## 2. F2L

F2L được giải từng cặp góc–cạnh, mỗi cặp là một phase riêng. Thứ tự chọn cặp được quyết định lại sau mỗi lần chèn.

Với mỗi cặp chưa giải:

1. Tìm phương án cho từng cặp ứng viên trong frame hiện tại, đồng thời bắt buộc Cross và mọi cặp đã giải trước đó vẫn được giữ nguyên.
2. Dùng IDA* có giới hạn, heuristic/pattern database chính xác cho cặp, giới hạn mặt phù hợp với slot cùng các giới hạn độ sâu, node và thời gian.
3. Ước lượng mức sẵn sàng của cặp, độ thuận tay của chuỗi move và trạng thái còn lại dành cho các cặp chưa giải.
4. Xếp hạng ứng viên và chọn cặp tiếp theo một cách động; không mã hóa cứng thứ tự slot.
5. Nếu phương án tốt nhất có move khó thao tác, thử các frame y lân cận và so sánh điểm số. Giữ frame hiện tại nếu việc đổi hướng không cải thiện điểm.
6. Áp dụng phương án đã chọn lên trạng thái nội bộ, xác minh cặp mới được giải và tiếp tục đánh giá các cặp còn lại.

Điểm ergonomic hiện ưu tiên độ khó thao tác/finger-trick trước số move; độ sẵn sàng của cặp và lookahead cặp tiếp theo cũng tham gia xếp hạng. Solver giữ chuỗi move chuẩn cùng metadata frame, sau đó biến đổi chuỗi sang frame Cross vật lý nhất quán. Không phát thêm phép xoay y sau cặp F2L cuối cùng; frame cuối được mang sang OLL/PLL bằng phép biến đổi công thức.

Đây là bộ lập kế hoạch có heuristic và giới hạn, không chứng minh F2L ngắn nhất toàn cục. Mọi cặp đã giải và Cross phải được giữ nguyên sau từng phase.

## 3. OLL — định hướng tầng cuối

1. Chỉ chạy khi Cross và cả bốn cặp F2L đã được giải.
2. Nếu hướng của mọi góc và cạnh đã đúng, trả phase OLL rỗng.
3. Nếu chưa, nhận diện trường hợp từ bảng thuật toán một-look gồm 57 trường hợp OLL; lookup có xử lý các biến thể AUF.
4. Áp dụng công thức đã nhận diện.
5. Xác minh F2L không bị phá và mọi góc/cạnh đạt mục tiêu định hướng trước khi chuyển sang PLL.

## 4. PLL — hoán vị tầng cuối

1. Chỉ chạy khi F2L và OLL đã được giải.
2. Nếu hoán vị đã đúng, không cần công thức PLL; chỉ thêm AUF nếu cần để căn chỉnh U.
3. Nếu chưa, nhận diện trường hợp trong bảng 21 công thức PLL. Lookup tạo các biểu diễn tương đương theo hướng y và AUF để nhận diện không phụ thuộc mặt nào đang hướng ra trước; các biểu diễn này không làm tăng số trường hợp PLL.
4. Trong frame nội bộ x2, biến đổi công thức phù hợp trước khi áp dụng lên chuỗi move vật lý.
5. Xác minh hoán vị tầng cuối, sau đó kiểm tra toàn bộ trạng thái cube.

## 5. Xác minh, metadata và xử lý lỗi

- Trả về toàn bộ các phase: Orientation, Cross, F2L-1 đến F2L-4, OLL và PLL.
- Metadata ghi lại hướng đã chọn, kết quả tìm Cross, thứ tự cặp F2L, thay đổi frame, thông tin lookahead và trường hợp OLL/PLL.
- Sau mỗi phase, áp dụng move lên trạng thái nội bộ và kiểm tra bất biến trước khi tiếp tục.
- Sau khi tạo xong solution, phát lại toàn bộ chuỗi move trên cube đầu vào ban đầu và xác minh trạng thái cuối.
- Nếu một phase thất bại hoặc hết resource budget, phải báo lỗi rõ ràng; không thay bằng lời giải Kociemba.

## 6. Các điều không được làm

- Không mô tả việc chọn hướng y là một phần của mục tiêu tìm Cross: code giải Cross chuẩn trước rồi mới chấm điểm bốn hướng trình bày.
- Không cố định thứ tự F2L theo slot.
- Không tuyên bố F2L tối ưu toàn cục; search có giới hạn và heuristic.
- Không bỏ qua Cross hoặc các cặp F2L đã giải trong lúc tìm cặp tiếp theo.
- Không thay thế thất bại của CFOP bằng phương pháp giải khác mà không báo lỗi.
