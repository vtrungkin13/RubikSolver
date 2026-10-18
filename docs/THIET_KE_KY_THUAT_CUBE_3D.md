# RubikSolver — Thiết kế kỹ thuật Cube 3D

> **Trạng thái:** Đang triển khai — API trạng thái, mô hình Three.js và điều khiển từng bước đã được tích hợp bước đầu  
> **Phạm vi:** Mô hình cube 3D, hoạt ảnh xoay mặt thật và đồng bộ từng bước lời giải  
> **Nguyên tắc cốt lõi:** Backend Python là nguồn sự thật cho trạng thái logic; frontend chịu trách nhiệm hiển thị và hoạt ảnh.

## 1. Mục tiêu và phạm vi

Bổ sung một khung Rubik 3D vào giao diện web RubikSolver. Khối lập phương khởi đầu ở trạng thái đã giải; khi người dùng nhập scramble hợp lệ, mô hình chuyển sang trạng thái tương ứng. Sau khi bộ giải trả về lời giải, người dùng có thể áp dụng từng move bằng các nút điều khiển; mỗi lần bấm chỉ thực hiện đúng một move và khối lập phương xoay bằng hoạt ảnh mặt thật.

Đặc tả này là căn cứ triển khai và nghiệm thu. Tiến độ thực tế được cập nhật ở mục 14; các phần chưa được kiểm thử đầy đủ vẫn được ghi là đang thực hiện.

### 1.1. Mục tiêu chức năng

- Hiển thị cube 3D có thể xoay góc nhìn bằng chuột hoặc thao tác tương đương.

- Khởi tạo ở trạng thái solved; cập nhật chính xác theo scramble đầu vào.

- Hiển thị lời giải và cho phép tiến/lùi từng move, đồng bộ vị trí move hiện tại với giao diện kết quả.

- Dùng hoạt ảnh xoay lớp cubie thực sự, không thay cube bằng ảnh tĩnh hoặc chỉ đổi màu sticker.

- Đảm bảo trạng thái sau hoạt ảnh khớp với trạng thái do engine Python tính toán.

- Giữ tương thích với CFOP, Roux và Kociemba; không đưa logic tìm lời giải sang JavaScript.

- Giữ quy tắc giao diện hiện có: không cuộn toàn trang; vùng Result là nơi cuộn nội dung lời giải.

### 1.2. Ngoài phạm vi ban đầu

- Không viết lại thuật toán giải hoặc mô hình trạng thái cốt lõi trong Python.

- Không bắt buộc autoplay ở phiên bản đầu; có thể bổ sung sau khi điều khiển từng bước ổn định.

- Không yêu cầu mô phỏng vật lý, va chạm hoặc chuyển động quán tính phức tạp.

- Không cho phép nhiều hoạt ảnh xoay mặt chồng lấn trong phiên bản đầu.

## 2. Kiến trúc tổng thể

Backend Python tiếp tục là nguồn dữ liệu chuẩn (source of truth) cho trạng thái logic của cube. Frontend dùng Three.js để dựng hình, hoạt ảnh và quản lý tương tác. Frontend không tự suy đoán trạng thái solver; backend cung cấp trạng thái sticker chuẩn hóa ở trạng thái ban đầu và sau từng bước.

| Thành phần | Trách nhiệm |
| --- | --- |
| Python cube engine (src/rubik_solver/cube/) | Phân tích move, áp dụng move, xác thực scramble, tính trạng thái logic. |
| API (api/main.py) | Nhận scramble, trả trạng thái cube chuẩn hóa; trả lời giải cùng snapshot trạng thái từng bước. |
| frontend/app.js | Điều phối giao diện, gọi API, chọn phương pháp giải, xử lý ngôn ngữ và kết nối panel. |
| frontend/cube/cube-view.js | Khởi tạo Three.js scene/camera/renderer, dựng cubie và sticker, resize và dispose. |
| frontend/cube/cube-animation.js | Chọn lớp cubie theo move, chạy hoạt ảnh, snap về lưới chính xác, khóa animation. |
| frontend/cube/cube-controller.js | Quản lý snapshot hiện tại, chỉ số move, reset/undo/redo và đồng bộ Result. |
| frontend/cube/cube-api.js | Gọi API, chuẩn hóa dữ liệu phản hồi, kiểm tra lỗi và định dạng snapshot. |

### 2.1. Luồng dữ liệu

1. Người dùng nhập hoặc sửa scramble.

1. Frontend đánh dấu lời giải cũ không còn hợp lệ và gửi scramble tới endpoint trạng thái.

1. Backend phân tích/kiểm tra scramble và trả về trạng thái 54 sticker chuẩn hóa.

1. Cube controller đặt mô hình 3D về trạng thái scramble đã xác nhận.

1. Khi người dùng yêu cầu giải, API trả danh sách move, metadata/phase và snapshot sau mỗi move.

1. Người dùng bấm Next: controller yêu cầu animation engine thực hiện đúng move kế tiếp.

1. Hoàn tất animation thì đối chiếu trạng thái hiển thị với snapshot backend; chỉ sau đó cập nhật move index và highlight Result.

1. Khi tới cuối lời giải, kiểm tra trạng thái logic cuối thực sự solved; không chỉ dựa vào việc đã đi hết danh sách move.

## 3. Mô hình cube 3D

### 3.1. Hình học

Mô hình dự kiến gồm 27 vị trí cubie theo lưới 3×3×3: 8 góc, 12 cạnh, 6 tâm và 1 lõi trung tâm không nhìn thấy. Các cubie là những khối hình học riêng. Sticker màu được gắn vào mặt ngoài của cubie và di chuyển cùng cubie; không được tô màu lại chỉ dựa trên vị trí hiện thời vì như vậy có thể làm sai hướng sticker.

- Dùng một scene Three.js, camera phối cảnh, ánh sáng môi trường và ánh sáng định hướng vừa phải.

- Mỗi cubie có tọa độ lưới logic (x, y, z) và orientation; tọa độ hiển thị có thể là số thực trong animation nhưng phải snap về lưới sau khi hoàn tất.

- Mỗi sticker là mặt phẳng/miếng dán có màu, đặt hơi nhô khỏi mặt cubie để tránh z-fighting.

- Lõi trung tâm có thể không render hoặc dùng mesh ẩn để thuận tiện tổ chức pivot.

- Camera orbit cho phép quan sát cube từ các hướng khác nhau; camera orbit không được thay đổi trạng thái logic hoặc thứ tự sticker.

### 3.2. Quy ước mặt và sticker

Đề xuất thứ tự mặt chuẩn trong dữ liệu là URFDLB, mỗi mặt có 9 sticker. Khi nhìn trực diện vào một mặt, thứ tự đọc là từ hàng trên xuống hàng dưới, trong mỗi hàng từ trái sang phải. Chỉ nêu thứ tự mặt là chưa đủ: cần đặc tả rõ hướng nhìn và chiều hàng/cột của cả sáu mặt.

| Mặt | Tên | Màu hiển thị mặc định (đề xuất) |
| --- | --- | --- |
| U | Up / trên | Trắng |
| R | Right / phải | Đỏ |
| F | Front / trước | Xanh lá |
| D | Down / dưới | Vàng |
| L | Left / trái | Cam |
| B | Back / sau | Xanh dương |

Màu sắc chỉ là cấu hình hiển thị, không phải quy tắc của solver. Nếu cần hỗ trợ scheme khác, hãy tách mapping màu khỏi thứ tự sticker logic.

### 3.3. Hợp đồng tọa độ

Trước khi triển khai cần chốt một hệ tọa độ duy nhất, ví dụ x tăng sang phải, y tăng lên trên, z tăng về phía người quan sát. Cần ghi lại ánh xạ giữa tọa độ lưới, pháp tuyến mặt sticker và thứ tự 9 ô của từng mặt. Quy ước này là hợp đồng kỹ thuật giữa engine Python, dữ liệu API và Three.js.

- Định nghĩa tọa độ của 6 mặt và vector pháp tuyến tương ứng.

- Định nghĩa thứ tự hàng/cột cho U, R, F, D, L, B theo góc nhìn trực diện từng mặt.

- Định nghĩa phép biến đổi tọa độ và hướng sticker sau mỗi phép quay 90°.

- Viết test ánh xạ sticker trước khi dựng animation; không suy luận hướng mặt theo cảm tính khi code.

## 4. Hợp đồng API và snapshot trạng thái

### 4.1. Endpoint trạng thái

Đã bổ sung `POST /api/cube/state`. Endpoint nhận scramble, dùng parser và cube engine hiện có để tính trạng thái, rồi trả về chuỗi 54 facelet chuẩn hóa cùng cờ solved. Đây là nguồn trạng thái dùng để cập nhật cube khi scramble thay đổi.

~~~text
Request (minh họa):
{
  "scramble": "R U R' U'"
}

Response (minh họa):
{
  "valid": true,
  "stickers": "UUUUUUUUURRRRRRRRRFFFFFFFFFDDDDDDDDDLLLLLLLLLBBBBBBBBB",
  "is_solved": false
}
~~~

Cấu trúc response hiện tại trả `stickers` dưới dạng chuỗi 54 ký tự theo thứ tự mặt URFDLB. Với scramble sai, API trả lỗi có cấu trúc và thông điệp có thể hiển thị trên UI, không trả về trạng thái giả.

### 4.2. Mở rộng response giải

Đã mở rộng `POST /api/solve` để cung cấp trạng thái ban đầu và snapshot sau mỗi move. Snapshot được tạo bằng cube engine Python khi áp dụng lần lượt các move, không suy ra bằng cách đảo ngược lời giải trong frontend.

~~~text
S0 = trạng thái sau scramble
S1 = applyMove(S0, move[0])
S2 = applyMove(S1, move[1])
...
Sn = applyMove(Sn-1, move[n-1])

Bất biến: S(i+1) = applyMove(Si, move[i])
Nếu lời giải hợp lệ: Sn phải là trạng thái solved.
~~~

| Trường dữ liệu đề xuất | Ý nghĩa |
| --- | --- |
| moves | Danh sách move theo đúng thứ tự thực thi. |
| initial_state | S0, trạng thái sau scramble và trước move đầu tiên. |
| step_states | Snapshot theo chỉ số; nên gồm S0 và mỗi trạng thái sau move: N+1 snapshot cho N move. |
| final_state | Snapshot cuối sau khi áp dụng toàn bộ chuỗi move. |
| final_is_solved | Xác nhận sáu mặt đều đồng nhất màu; cho phép toàn bộ cube ở frame xoay bởi `x/y/z`. |
| verified | Kết quả kiểm chứng lời giải do backend cung cấp. |
| phases / metadata | Thông tin phase và metadata solver hiện có. |
| phase_ranges (nếu cần) | Khoảng chỉ số move của từng phase nếu frontend không thể suy ra chắc chắn. |

Nếu payload snapshot quá lớn, có thể chuyển sang endpoint truy xuất snapshot theo chỉ số hoặc chỉ gửi snapshot tại ranh giới phase. Tuy nhiên, gửi toàn bộ snapshot là lựa chọn khởi đầu đơn giản, dễ kiểm thử và đáng tin cậy.

### 4.3. Quy tắc đồng bộ

- Snapshot S0 phải khớp trạng thái scramble đang hiển thị.

- Sau khi áp dụng move i, cube phải khớp chính xác snapshot tương ứng S(i+1).

- Undo/Previous có thể đặt lại theo snapshot trước đó; nếu cần animation ngược, dùng inverse move nhưng vẫn đối chiếu snapshot đích.

- Reset luôn trở về S0 (trạng thái sau scramble), không phải trạng thái solved.

- Khi dữ liệu backend và trạng thái hiển thị không khớp, dừng tiến trình và báo lỗi; không âm thầm tiếp tục.

## 5. Bộ phân tích move và animation engine

### 5.1. Các loại move

| Nhóm | Ví dụ | Yêu cầu |
| --- | --- | --- |
| Xoay mặt ngoài | R, U, F, L, D, B | Chọn 9 cubie thuộc lớp mặt tương ứng. |
| Xoay ngược | R', U' | Đảo dấu góc quay so với move thuận theo quy ước trục. |
| Xoay 180° | R2, F2 | Xoay đủ 180°; không thay bằng một move 90°. |
| Wide moves | r, u, f... | Chọn lớp ngoài cộng lớp kế cận theo định nghĩa chuẩn. |
| Slice moves | M, E, S | Chọn lớp giữa tương ứng. |
| Xoay toàn cube | x, y, z | Xoay toàn bộ cube; cần xác định rõ solver dùng như move hay chỉ thay đổi frame. |

Phải hỗ trợ tất cả ký hiệu move mà backend thực tế có thể xuất ra. Nếu gặp move chưa hỗ trợ, cần dừng và báo lỗi rõ ràng; tuyệt đối không bỏ qua move hoặc thay bằng một move khác.

### 5.2. Chu trình hoạt ảnh

1. Phân tích token move thành loại phép quay, trục, lớp cubie và góc đích.

1. Xác định chính xác các cubie thuộc lớp cần xoay theo tọa độ logic hiện tại.

1. Gắn tạm các cubie đó vào một pivot/object group chung.

1. Animate pivot từ góc 0 tới ±90° hoặc ±180° theo thời lượng/easing đã chọn.

1. Khi animation kết thúc, cập nhật tọa độ logic và orientation; snap vị trí về lưới và orientation về các góc chính xác.

1. Tháo cubie khỏi pivot tạm, bảo đảm hierarchy không tích lũy transform.

1. Đối chiếu trạng thái kết quả với snapshot backend; chỉ sau khi hợp lệ mới cập nhật move index và mở khóa nút.

### 5.3. Độ chính xác số học

Không được giữ các góc quay số thực tích lũy vô hạn sau nhiều move. Sau mỗi animation, cubie phải được snap về tọa độ lưới và orientation chuẩn để tránh hiện tượng trôi, lệch cạnh hoặc sai trạng thái sau chuỗi dài. Hướng quay thuận/ngược cần được xác định bằng test, không chỉ bằng quan sát một trường hợp.

### 5.4. Khóa hoạt ảnh và lỗi

- Phiên bản đầu chỉ cho phép một animation tại một thời điểm.

- Trong lúc animation chạy, vô hiệu hóa Next/Previous/Reset hoặc định nghĩa rõ cách Reset hủy animation an toàn.

- Nếu có reset hoặc scramble mới trong lúc animation, dừng hoặc hoàn tất animation theo chính sách nhất quán rồi dựng lại từ snapshot mới.

- Nếu kiểm tra trạng thái thất bại, khóa thao tác tiếp theo và hiện lỗi có thể chẩn đoán.

- Hàng đợi move có thể thêm về sau; không cần triển khai trước khi chế độ từng bước ổn định.

## 6. Module frontend đề xuất

| Module | Phạm vi trách nhiệm | Không nên làm |
| --- | --- | --- |
| cube-view.js | Khởi tạo renderer/scene/camera/lighting; dựng cubie/sticker; camera control; resize/dispose. | Không tự gọi solver hoặc quyết định trạng thái chuẩn. |
| cube-animation.js | Phân tích move cho animation, chọn lớp, animate pivot, snap transform, báo hoàn tất/lỗi. | Không tự thay đổi dữ liệu API hoặc bỏ qua move không hỗ trợ. |
| cube-controller.js | Quản lý S0, snapshots, move index, reset/undo/redo, khóa điều khiển, đồng bộ highlight. | Không tái triển khai thuật toán cube của Python. |
| cube-api.js | Gọi endpoint trạng thái/solve, chuẩn hóa response, xử lý lỗi mạng/schema. | Không dựng trạng thái bằng cách đoán từ chuỗi scramble. |
| app.js | Điều phối Input, Cube, Result; chọn phương pháp giải; ngôn ngữ; trạng thái yêu cầu. | Không chứa toàn bộ chi tiết Three.js và animation trong một file. |

Đây là cấu trúc đề xuất; trước khi tạo file cần kiểm tra cách frontend đang được phục vụ, khả năng dùng ES modules và cấu hình static hiện tại. Nếu dùng Three.js qua CDN, cần cân nhắc độ ổn định và khả năng chạy offline; ưu tiên ghim phiên bản và vendoring thư viện cục bộ khi phù hợp.

## 7. Máy trạng thái giao diện

| Trạng thái | Ý nghĩa / hành vi chính |
| --- | --- |
| Solved | Cube đang solved; chưa có scramble khác hoặc scramble rỗng. |
| ScramblePending | Đang chờ debounce hoặc phản hồi kiểm tra trạng thái. |
| Scrambled | Scramble hợp lệ; cube hiển thị trạng thái ban đầu S0. |
| Invalid | Scramble không hợp lệ; giữ thông báo lỗi và không cho dùng lời giải cũ. |
| Solving | Đang chờ API giải. |
| Ready | Có lời giải và snapshot; chưa áp dụng move nào hoặc đang đứng tại một bước hợp lệ. |
| Animating | Một move đang chạy; không nhận lệnh tiến/lùi mới. |
| Completed | Đã đi hết lời giải và trạng thái cuối được xác nhận solved. |

### 7.1. Quy tắc chuyển trạng thái

- Mỗi lần scramble thay đổi, vô hiệu hóa lời giải cũ ngay lập tức.

- Mỗi lần phương pháp giải thay đổi, vô hiệu hóa kết quả cũ nhưng giữ trạng thái scramble hiện tại.

- Nếu người dùng thay scramble trong khi API đang chạy, response cũ không được phép ghi đè dữ liệu mới; dùng request/version token.

- Debounce kiểm tra scramble khoảng 250–350 ms khi người dùng đang gõ.

- Scramble rỗng được hiểu là trạng thái solved.

- Đổi ngôn ngữ không được reset cube, chỉ số move hoặc kết quả.

- Khi hoàn thành, xác nhận trạng thái cuối bằng snapshot/kiểm chứng backend thay vì chỉ kiểm tra move index.

## 8. Tích hợp UI và responsive

### 8.1. Bố cục desktop

Bố cục mục tiêu gồm ba panel: Input, Cube 3D và Result. Panel cube phải đủ không gian cho mô hình và các nút điều khiển cơ bản. Result giữ danh sách move/phase và highlight move đang áp dụng.

### 8.2. Tablet và mobile

Không nên chỉ thêm cột CSS thứ ba rồi để nguyên layout cũ. Ở màn hình nhỏ, có thể dùng tab/chuyển panel hoặc bố cục ưu tiên Cube với khả năng chuyển giữa Input và Result. Cần bảo đảm người dùng vẫn truy cập được scramble và kết quả.

- Giữ yêu cầu không cuộn toàn trang; chỉ Result panel cuộn nếu đó là hành vi UX hiện hành.

- Kiểm tra breakpoint mobile, nhất là khi workspace chuyển thành một cột nhưng body vẫn overflow:hidden, vì Input/Result có thể bị cắt.

- Kích thước canvas phải dựa vào kích thước container, không chỉ kích thước cửa sổ.

- Dùng ResizeObserver để cập nhật camera aspect và renderer size; nếu panel khởi tạo khi đang ẩn, resize lại khi panel hiện.

- Giải phóng renderer, geometry, material và event listener khi view bị tháo hoặc khởi tạo lại.

### 8.3. Điều khiển người dùng

| Điều khiển | Hành vi |
| --- | --- |
| Reset | Trở về S0 — trạng thái sau scramble. |
| Previous | Lùi về snapshot trước đó; có thể dùng inverse animation hoặc dựng trực tiếp snapshot. |
| Next / Apply move | Thực hiện chính xác một move kế tiếp bằng animation. |
| Move list | Nếu nhấn move để seek, phải định nghĩa rõ chạy từng move hay chuyển thẳng tới snapshot. |
| Autoplay (để sau) | Tự chạy chuỗi move với tốc độ điều chỉnh; chỉ triển khai sau khi từng bước ổn định. |

## 9. Kiểm thử và tiêu chí nghiệm thu

### 9.1. Quy ước trạng thái

- Cube solved phải ánh xạ đúng 54 sticker theo scheme màu đã cấu hình.

- Scramble hợp lệ phải cho trạng thái khớp engine Python.

- Scramble + chuỗi inverse phải quay về trạng thái solved.

- Mỗi move được hỗ trợ phải tạo snapshot; move rồi inverse phải khôi phục đúng trạng thái trước đó.

- R2 phải tương đương hai lần R theo cùng quy ước.

- Thứ tự hàng/cột của cả sáu mặt phải được kiểm thử độc lập.

### 9.2. Hoạt ảnh và điều khiển

- Mỗi lần bấm Next chỉ tăng đúng một move.

- Previous, Next và Reset luôn trỏ tới đúng snapshot.

- Chỉ đúng lớp cubie được phép xoay; các cubie ngoài lớp không dịch chuyển.

- Góc quay cuối đạt chính xác 90° hoặc 180° theo move.

- Sau mỗi animation, trạng thái hiển thị khớp snapshot backend.

- Reset giữa animation không để lại pivot, cubie hoặc trạng thái khóa bị kẹt.

- Không có hai animation chồng lấn khi người dùng bấm nhanh.

### 9.3. Tích hợp solver và độ bền

- Chạy thử với lời giải CFOP, Roux và Kociemba.

- Giữ đúng thứ tự move và ranh giới phase nếu có hiển thị phase.

- Trạng thái cuối phải solved và phù hợp cờ verified từ backend.

- Scramble sai hoặc lỗi solver không được để lại kết quả cũ trông như kết quả mới.

- Nếu đổi scramble khi API đang chạy, response cũ phải bị bỏ qua.

- Move không hỗ trợ phải gây lỗi tường minh; không được âm thầm bỏ qua.

- Không cuộn toàn trang, Result cuộn đúng vùng và không có nội dung bị cắt trên màn hình nhỏ.

- Renderer chạy mượt hợp lý, không tạo vòng lặp render thừa hoặc rò rỉ tài nguyên.

Một hoạt ảnh trông đúng nhưng trạng thái logic sai vẫn được xem là lỗi. Kiểm thử snapshot là điều kiện nghiệm thu bắt buộc.

## 10. Kế hoạch triển khai theo giai đoạn

| Giai đoạn | Công việc | Kết quả cần đạt |
| --- | --- | --- |
| T1 — Hợp đồng trạng thái | Chốt thứ tự 54 sticker, hệ tọa độ, hướng mặt, quy ước màu và test mapping. | Đặc tả ổn định và test mapping trạng thái solved. |
| T2 — API trạng thái | Thêm endpoint tính trạng thái từ scramble và kiểm thử lỗi. | Frontend nhận trạng thái chuẩn hóa sau scramble. |
| T3 — Dựng cube 3D | Tích hợp Three.js, dựng 27 cubie và 54 sticker, camera/resize. | Cube solved hiển thị đúng, camera hoạt động. |
| T4 — Animation engine | Chọn lớp cubie, pivot animation, snap transform, test move. | Các move cơ bản hoạt động chính xác. |
| T5 — Snapshot/controller | Trả step_states từ backend, triển khai reset/next/previous và kiểm tra đồng bộ. | Mỗi bước khớp trạng thái backend. |
| T6 — Tích hợp Result | Nối nút từng move và highlight chỉ số move. | Cube và danh sách move đồng bộ. |
| T7 — Phủ move và solver | Hỗ trợ toàn bộ ký hiệu backend có thể xuất, kiểm thử CFOP/Roux/Kociemba. | Không có move bị bỏ qua hoặc diễn giải sai. |
| T8 — Responsive và tối ưu | Hoàn thiện tablet/mobile, quản lý tài nguyên, đo hiệu năng. | Không cắt nội dung, không rò rỉ tài nguyên. |

Thứ tự ưu tiên: hoàn thành T1 trước khi bắt đầu animation. Sai quy ước tọa độ/sticker sẽ làm sai mọi phần phía sau và khó phát hiện nếu chỉ kiểm tra hình ảnh.

## 11. Rủi ro và cách giảm thiểu

| Rủi ro | Hệ quả | Biện pháp |
| --- | --- | --- |
| Quy ước sticker không rõ | Màu hoặc hướng mặt sai dù cube trông gần đúng. | Định nghĩa mapping 54 ô và test riêng từng mặt. |
| Dấu góc quay sai | Move thuận/ngược bị đảo hoặc sai mặt. | Test từng move và inverse; đối chiếu snapshot. |
| Transform tích lũy | Cubie lệch lưới sau nhiều move. | Snap position/orientation sau mỗi animation. |
| Backend và frontend cùng tính trạng thái | Hai implementation lệch nhau theo thời gian. | Backend là nguồn sự thật; frontend chỉ animate và đối chiếu. |
| Move solver chưa được hỗ trợ | Chuỗi lời giải bị sai nếu bỏ qua move. | Kiểm kê ký hiệu move thực tế và fail-fast. |
| Response API cũ ghi đè | Cube hiển thị trạng thái không khớp scramble mới. | Dùng request/version token và vô hiệu hóa lời giải cũ. |
| Layout mobile bị cắt | Không thao tác được Input/Result. | Thiết kế responsive thực chất, kiểm thử breakpoint. |
| Tải Three.js từ CDN | Không chạy offline hoặc khi CDN lỗi. | Ghim phiên bản, cân nhắc đóng gói thư viện cục bộ. |

## 12. Các quyết định cần chốt trước khi code

- Schema chính thức cho mảng 54 sticker và hướng hàng/cột của từng mặt.

- Hệ tọa độ 3D và ánh xạ ký hiệu move sang trục, lớp và dấu góc.

- Danh sách move mà từng solver thực tế có thể trả về, gồm wide/slice/rotation nếu có.

- Tên field API cuối cùng cho initial_state, step_states và phase_ranges.

- Chính sách Reset/Previous khi animation đang chạy.

- Phương án phân phối Three.js: CDN hay thư viện cục bộ, cùng phiên bản cụ thể.

- Chiến lược responsive mobile: tab panel hay bố cục thay thế.

## 13. Kết luận

Phương án khả thi và phù hợp với kiến trúc hiện tại là dùng Three.js cho cube 3D, Python cube engine làm nguồn trạng thái chuẩn, và cung cấp snapshot backend sau mỗi move. Mấu chốt kỹ thuật không phải chỉ dựng hình mà là thống nhất quy ước 54 sticker/tọa độ, đảm bảo mọi animation kết thúc ở trạng thái chính xác và đồng bộ với danh sách lời giải.

Bắt đầu bằng T1 — đặc tả và kiểm thử quy ước trạng thái. Chỉ sau khi mapping được chứng minh bằng test mới triển khai dựng cube, animation và tích hợp UI.

## 14. Tiến độ triển khai thực tế

- **Đã triển khai bước đầu:** endpoint `POST /api/cube/state`; snapshot `initial_state`, `step_states`, `final_state`; mô hình 27 cubie và sticker bằng Three.js; camera orbit; animation cho face/wide/slice/whole-cube moves; Next/Previous/Reset; đồng bộ highlight move và ngôn ngữ.
- **Đã kiểm thử trên trình duyệt:** chuỗi `r U2 M x` khớp từng snapshot; Previous và Reset đưa cube về đúng chỉ số/trạng thái.
- **Đã kiểm thử backend:** bộ test toàn dự án trên trạng thái cuối đạt **148 passed**; bộ API/validator đạt 21 test sau cập nhật parity; bộ CFOP rotated-frame + validator đạt 12 test trong lần kiểm tra mục tiêu. Kiểm tra trình duyệt xác nhận CFOP, Roux và Kociemba đều có snapshot cuối solved với scramble `R U`.
- **Lưu ý triển khai:** Three.js `0.180.0` và OrbitControls hiện tải từ CDN qua import map. Chưa có gói thư viện cục bộ/offline.
- **Còn cần hoàn thiện:** kiểm tra sâu UI ở các breakpoint nhỏ; xử lý tình huống CDN không khả dụng; cân nhắc đóng gói Three.js cục bộ.

## Phụ lục A — Bất biến cần giữ

- Backend là nguồn sự thật của trạng thái logic.

- Mỗi move tương ứng đúng một thao tác người dùng và một chuyển trạng thái.

- N move cần N+1 snapshot nếu có cả trạng thái ban đầu.

- Reset quay về trạng thái sau scramble, không phải solved.

- Không bỏ qua move chưa hỗ trợ.

- Không cho trạng thái cũ ghi đè response mới.

- Mọi animation kết thúc bằng snap chính xác và đối chiếu snapshot.

- Trạng thái cuối phải được xác nhận solved.
