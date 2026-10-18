# RubikSolver

Bộ giải Rubik 3×3 viết bằng Python, kèm giao diện web.

## Trạng thái dự án

Các mốc M0–M5 đã hoàn thành. CFOP được tích hợp từ đầu đến cuối với Cross, bốn cặp F2L, OLL một-look (57 trường hợp), PLL một-look (21 trường hợp), xác minh toàn bộ lời giải và hỗ trợ API. Roux có đủ các phase FB, SB, CMLL, EO, ULUR và L4E; chiến lược được mô tả riêng để phục vụ phát triển theo hướng giải thích được và gần với cách cuber giải thực tế.

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

- [Đặc tả và kiến trúc tổng thể](docs/PROJECT_SPEC.md)
- [Chiến lược Roux từng bước](docs/ROUX_STRATEGY.md)
- [Chiến lược CFOP từng bước](docs/CFOP_STRATEGY.md)
- [Cài đặt, chạy và triển khai](docs/DEPLOYMENT.md)
- [Thông tin giấy phép bên thứ ba](docs/THIRD_PARTY_NOTICES.md)
