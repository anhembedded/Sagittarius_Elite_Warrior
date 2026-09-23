# Nhiệm vụ: BOT-095G — Bộ nhớ đệm Lịch sử Lần chạy (Session Run History & Quick Comparison Cache)

> Thuộc Epic [`BOT-095`](BOT-095_backtest_signals_fsm_lifecycle_epic.md).
> Phụ thuộc: `BOT-095B` ✅ và [`BOT-095H`](BOT-095H_backtest_action_ownership_and_stale_callback_fencing.md).
> **Trọng tâm**: Xây dựng bộ nhớ đệm lưu vết các lần chạy trong phiên làm việc (`SessionRunHistoryCache` lưu 5–10 kết quả gần nhất), bổ sung dropdown chọn nhanh trên Toolbar để cho phép trader đối chiếu kết quả giữa các lần chạy khác nhau (đa khung thời gian, đa chiến lược) với thời gian tải lại tức thì ($0\text{ms}$).

---

## 1. Vấn đề Hiện tại

- Trong một phiên làm việc, trader thường thử nghiệm nhiều kịch bản:
  - *Lần 1:* Chiến lược EMA trên `1m` (PnL +15%, Winrate 60%)
  - *Lần 2:* Chiến lược EMA trên `5m` (PnL +28%, Winrate 55%)
  - *Lần 3:* Chiến lược MACD trên `5m` (PnL -5%, Winrate 40%)
- Hiện tại, mỗi khi người dùng thay đổi thông số và chạy lại, **kết quả của lần chạy trước đó bị ghi đè và mất vĩnh viễn**.
- Muốn xem lại kết quả cũ, trader buộc phải chỉnh lại từng thông số và chờ tính toán lại từ đầu, làm gián đoạn nghiêm trọng quá trình so sánh và tối ưu hóa chiến lược.

---

## 2. Thiết kế Kỹ thuật (Technical Design)

### 2.1. Lớp `SessionRunHistoryCache` trong Presenter / Domain
Trong `src/presentation/ui/screens/backtest/logic/session_run_history.py`:

```python
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime

@dataclass
class BacktestRunSnapshot:
    run_id: str                      # UUID hoặc index ngắn (#1, #2, #3)
    timestamp: datetime              # Thời điểm chạy
    config: object                   # Immutable config + strategy params copy sâu
    metrics: object                  # BacktestMetrics
    trades: list                     # Danh sách Trade entities
    equity_curve: list               # Điểm đường cong vốn
    provenance: object               # Data window/watermark, strategy version, fee, engine mode
    label: str                       # Nhãn hiển thị ngắn gọn: "#1 - EMA (5m) | PnL +28%"

class SessionRunHistoryCache:
    """
    Bộ nhớ đệm trong phiên lưu tối đa MAX_HISTORY lần chạy gần nhất.
    """
    MAX_HISTORY = 5

    def __init__(self):
        self._history: List[BacktestRunSnapshot] = []

    def push(self, snapshot: BacktestRunSnapshot) -> None:
        self._history.insert(0, snapshot)
        if len(self._history) > self.MAX_HISTORY:
            self._history.pop()

    def get_all(self) -> List[BacktestRunSnapshot]:
        return list(self._history)

    def get_by_id(self, run_id: str) -> Optional[BacktestRunSnapshot]:
        for item in self._history:
            if item.run_id == run_id:
                return item
        return None
```

---

### 2.2. Phục hồi Tức thì ($0\text{ms}$) khi Người dùng Chọn Lại Lần chạy Cũ
1. Thêm dropdown **"Lịch sử lần chạy"** trên `BackTestTopPanel.qml`:
   - Hiển thị danh sách các lần chạy:
     - `#3 — 15:30 — EMA Crossover (5m) — PnL: +28.4%`
     - `#2 — 15:25 — EMA Crossover (1m) — PnL: +15.2%`
     - `#1 — 15:20 — RSI Reversal (1m) — PnL: -4.8%`
2. Khi người dùng click chọn lại một lần chạy cũ:
   - Presenter nạp lại toàn bộ `BacktestRunSnapshot`:
     - Cập nhật lại các thông số trên Toolbar theo cấu hình của lần chạy đó.
     - Cập nhật 4 thẻ chỉ số, 8 thẻ mở rộng, đường cong vốn và bảng 50 lệnh Trade Logs ngay lập tức.
     - Vẽ lại các cờ Buy/Sell trên Chart.
   - Đặt FSM về `BacktestUiState.COMPLETED` trong một restore transaction, suppress dirty tracking trong lúc toolbar được hydrate.
   - Không gọi lại CPU backtest engine. UI có thể render bất đồng bộ; không hứa `$0ms`/`<5ms`.

---

## 3. Danh sách File Cần Chỉnh sửa & Tạo mới

- 🆕 `src/presentation/ui/screens/backtest/logic/session_run_history.py`: Định nghĩa `BacktestRunSnapshot` và `SessionRunHistoryCache`.
- ✏️ `src/presentation/ui/screens/backtest/backtest_view_model.py`: Bổ sung model danh sách lần chạy `sessionRunHistoryList` và signal `restoreRunRequested`.
- ✏️ `src/presentation/ui/screens/backtest/backtest_presenter.py`: Lưu snapshot sau mỗi lần `BACKTEST_SUCCEEDED` và xử lý phục hồi dữ liệu khi nhận `restoreRunRequested`.
- ✏️ `src/presentation/ui/screens/backtest/BackTestTopPanel.qml`: Thêm nút / dropdown "Lịch sử lần chạy" trên thanh công cụ.
- ✏️ `tests/unit/presentation/ui/screens/test_session_run_history.py`: Viết test cases kiểm tra lưu cache, giới hạn 5 lần chạy và phục hồi 100% dữ liệu.

---

## 4. Tiêu chuẩn Nghiệm thu (Acceptance Criteria)

1. **Lưu cache tự động**:
   - Mỗi lần Backtest thành công $\rightarrow$ Tự động thêm 1 snapshot vào dropdown lịch sử.
2. **Khôi phục có provenance**:
   - Chọn snapshot cũ khôi phục đúng Toolbar, Cards, Charts và Trade Logs của snapshot, kèm dữ liệu/provenance đã dùng; dữ liệu không còn tái tạo được phải được nói rõ thay vì giả vờ “hoàn hảo”.
3. **Local CI Verification**:
   - Chạy `.\scripts\ci-local.ps1 -UnitOnly` đạt 100% Passed.

4. **Memory & mutation safety**:
   - Snapshot không giữ tham chiếu mutable; cache có giới hạn theo số entry **và** ngân sách bộ nhớ. Test eviction, restore không kích dirty, và restore snapshot cũ khi run mới đang active.
