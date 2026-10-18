# RubikSolver

Bộ giải Rubik 3×3 viết bằng Python, kèm giao diện web.

## Trạng thái dự án

Dự án được chia thành bảy milestone: M1 Cube model + moves, M2 Scramble parser + validator, M3 Search foundation, M4 Kociemba solver, M5 CFOP, M6 Roux và M7 Web UI. M5 (CFOP) và M6 (Roux) đã thực hiện; các bước tiếp theo là tối ưu chất lượng lời giải, độ ổn định và kiểm thử hồi quy. Roux có đủ các phase FB, SB, CMLL, EO, ULUR và L4E; riêng SB vẫn còn các trường hợp cần điều tra và tối ưu như ghi trong roadmap.

## Triết lý thiết kế solver

Mục tiêu không chỉ là giải được cube mà còn giúp cuber học cách đưa ra quyết định tốt. Vì vậy, lời giải cần giữ ranh giới phase rõ ràng, cung cấp metadata hữu ích về chiến lược/trường hợp, và phân biệt chiến lược human-style với tìm kiếm tối ưu hoặc tìm kiếm oracle.

## Cài đặt và chạy

Cài đặt package cùng dependency phát triển:

```powershell
pip install -e ".[dev]"
pytest
```

Chạy API:

```powershell
uvicorn api.main:app --reload
```

Chạy frontend tĩnh:

```powershell
python -m http.server 5500 --directory frontend
```

Scramble hỗ trợ Singmaster chuẩn và mở rộng, gồm move lát giữa (`M E S`), xoay toàn khối (`x y z`) và move lớp rộng (`r` hoặc `Rw`, v.v.).

## Tài liệu

- [Lộ trình và milestone](docs/ROADMAP.md)
- [Đặc tả và kiến trúc tổng thể](docs/PROJECT_SPEC.md)
- [Chiến lược Roux từng bước](docs/ROUX_STRATEGY.md)
- [Chiến lược CFOP từng bước](docs/CFOP_STRATEGY.md)
- [Cài đặt, chạy và triển khai](docs/DEPLOYMENT.md)
- [Thông tin giấy phép bên thứ ba](docs/THIRD_PARTY_NOTICES.md)
