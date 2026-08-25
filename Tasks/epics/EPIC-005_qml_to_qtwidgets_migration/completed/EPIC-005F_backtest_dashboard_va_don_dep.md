# EPIC-005F — `backtest` (trừ chart) + `dashboard` + dọn dẹp

**Thuộc Epic:** [`EPIC-005`](../README.md)
**Trạng thái:** ✅ **Xong — do [`EPIC-006D`/`EPIC-006E`](../../EPIC-006_drop_qml/README.md) thực hiện** (2026-08-25)

> **Không phải task này tự làm.** Nó bị hoãn vô thời hạn ngày 2026-08-23 vì lý do ghi ở dưới.
> `EPIC-006` sau đó **đảo ngược ADR của `EPIC-005`** và làm luôn phạm vi này theo con đường triệt
> để hơn (bỏ hẳn QML thay vì "trừ chart"): `EPIC-006D` làm Dev Board, `EPIC-006E` làm Backtest.
>
> Kiểm chứng 2026-08-25: `find src/presentation/ui/screens/backtest src/presentation/ui/screens/dashboard -name '*.qml'`
> → **0 file**. Toàn bộ `src/` cũng đã hết `.qml` sau `EPIC-006F`.
>
> Giữ nguyên phần lý do hoãn bên dưới làm hồ sơ lịch sử — nó ghi lại một phán đoán *đã được
> kiểm chứng là sai*, và đó là thứ đáng đọc hơn cả kết luận.
**Phụ thuộc:** [`EPIC-005E`](EPIC-005E_data_management.md)

---

## ⏸️ Vì sao hoãn — không phải huỷ, không phải "làm sau theo lịch"

[`DECISION_2026-08-23.md`](../DECISION_2026-08-23.md) (§2, §4): lý do gốc chọn QML —
*"AI dịch mockup sang code trực tiếp hơn ở QML"* (`BOT-030`) — vẫn đúng và vẫn đang hoạt
động. `backtest`/`dashboard` chính là nơi bằng chứng đó rõ nhất: 7+ task riêng
(`BOT-040`..`BOT-104`) theo mockup mới trong `backtest` chỉ trong vài tuần gần đây, commit
tính năng gần nhất cách hôm nay 1-10 ngày. Migrate ở đây đổi lấy chi phí thật (mất tốc độ
dịch mockup) lấy lợi ích không rõ ràng bằng, vì đây không phải nơi QtWidgets thắng rõ như
form/bảng tra cứu (`EPIC-005D`/`E`).

**Điều kiện xem lại** (không phải ngày cụ thể): `backtest`/`dashboard` ngừng nhận mockup mới
liên tục trong một khoảng thời gian đáng kể — tức chuyển từ "phát triển tính năng" sang "bảo
trì". Khi đó phần dưới đây vẫn còn giá trị tham khảo, đọc lại trước khi bắt đầu.

---

## 0. Phạm vi

Phần QML còn lại **trừ chart**:

| Nhóm | Ghi chú |
| :--- | :--- |
| `screens/backtest/` (6 file, 1.811 LOC) | **Trừ `NativeBacktestChart.qml`** — ranh giới cứng |
| `screens/dashboard/DevBoardPanel.qml` (385 LOC) | Nhúng trong `QQuickWidget` của `dashboard_view.py` |
| `components/` (16 file, 2.783 LOC) | Chỉ những cái chưa bị các task trước nuốt |

`BackTestTopPanel.qml` (866 LOC) là file lớn thứ hai repo — cân nhắc tách thành commit riêng.

## 1. Việc khó riêng: `backtest` sống chung với chart

Sau task này, `backtest_view.py` sẽ là **QWidget chứa QtWidgets thuần + một `QQuickWidget`
cho chart**. Đây là trạng thái cuối cùng, vĩnh viễn, của app — không phải trạng thái tạm.

Cần kiểm kỹ:
- Chart vẫn nhận đúng theme qua Theme bridge (bridge **không được gỡ**, chart cần nó).
- Tương tác widget ↔ chart (chọn timeframe, khoảng thời gian, crosshair) vẫn thông suốt qua
  ranh giới QtWidgets/QQuickWidget.
- Benchmark contract của chart vẫn xanh — lưu ý nó **từng flaky** (BUG-036), fail thì chạy lại
  trước khi kết luận.

## 2. Dọn dẹp — commit riêng, làm cuối cùng

Chỉ khi **toàn bộ** phần trên đã chạy thật và ổn định:

1. Xoá các file `.qml` không còn được nạp. **Một commit riêng, không trộn với commit migrate**
   — đây là điều giữ cho rollback rẻ suốt cả epic.
2. Gỡ các guard QML nay không còn đối tượng (`gallery-coverage`…) — hoặc thu hẹp phạm vi
   chúng về đúng phần QML còn sống (chart). **Không xoá guard mà không thay bằng gì** cho
   phần QtWidgets: đó là lý do `EPIC-005B` yêu cầu test tĩnh chặn hex trong QSS.
3. Cập nhật `.agents/rules/qml-rule.md` lần cuối cho khớp thực tế còn lại.
4. Cập nhật `Tasks/ROADMAP.md` và trạng thái epic.
5. Mở lại `EPIC-003D` nếu vẫn còn gì đáng dọn trong `components/` — nhiều khả năng lúc này
   nó đã tự tiêu biến phần lớn.

## 3. Không nằm trong phạm vi

11 component QML của engine `pyside_mvc` (1.722 LOC). Chỉ tính đến sau khi app này chứng minh
hướng đi là đúng — và khi đó là epic bên **engine**, không phải ở đây.
