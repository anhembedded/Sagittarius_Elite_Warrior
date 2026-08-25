# BOT-120: Màn Backtest phụ thuộc màn Dashboard cho 3 thứ phi-UI

## 1. Bối cảnh & vấn đề thật

Phát hiện 2026-08-25 khi `EPIC-007E` dựng guard chặn import chéo giữa các gói
`screens/*`. Guard tìm được **6** vi phạm; 3 cái là widget và đã bị cắt trong
chính epic đó. **Ba cái còn lại không phải widget**, nên nằm ngoài phạm vi một
epic về chuẩn hoá card — chúng được cho vào danh sách miễn trừ của guard, trỏ
tới file này:

| Nơi | Lấy gì từ `dashboard` |
| :--- | :--- |
| `screens/backtest/backtest_presenter.py:98` | `IndicatorScriptRunner`, `qualified_line_name` |
| `screens/backtest/backtest_presenter.py:102` | `map_klines`, `map_volume` |
| `screens/backtest/backtest_view_model.py:29` | `IndicatorScriptListModel` |

Không có cái nào thuộc về màn Dashboard. Chúng ở đó vì Dashboard là nơi chúng
được viết ra trước.

## 2. Vì sao đáng sửa

Ba import này nói rằng **Backtest không chạy được nếu không có Dashboard**.
Điều đó không đúng về mặt nghiệp vụ: chạy chỉ báo trên một chuỗi nến và ánh xạ
nến sang dạng vẽ được là việc của cả hai màn, không của riêng màn nào.

Hệ quả cụ thể, không phải lý thuyết:

- Xoá hoặc đổi tên màn Dashboard sẽ làm hỏng màn Backtest, và không có gì
  trong tên file nói lên điều đó.
- Guard mới của `EPIC-007E` phải mang một danh sách miễn trừ 3 dòng. Miễn trừ
  không có hạn dùng thì thành vĩnh viễn.
- `qualified_line_name` và `map_klines` là hàm thuần — chúng không có lý do gì
  để sống trong một gói màn hình.

## 3. Đề xuất

Chuyển cả ba lên tầng dùng chung. Chỗ tự nhiên là `presentation/ui/components/`
(nếu còn dính Qt) hoặc `application/` (nếu thuần logic) — cần đọc mới quyết
được, đừng chốt trước:

- `map_klines`/`map_volume` gần như chắc chắn là hàm thuần chuyển đổi dữ liệu.
- `IndicatorScriptRunner`/`IndicatorScriptListModel` cần kiểm xem có phụ thuộc
  Qt không (`ListModel` thì gần như chắc là có).

Xong thì **xoá 3 dòng miễn trừ** khỏi
`tests/unit/presentation/ui/test_no_cross_screen_imports.py` — đó là tín hiệu
task này hoàn tất.

## 4. Ngoài phạm vi

Ba import widget mà `EPIC-007E` đã cắt. Chúng đã xong.
