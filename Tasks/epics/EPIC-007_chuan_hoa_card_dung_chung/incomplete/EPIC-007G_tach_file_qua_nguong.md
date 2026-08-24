# EPIC-007G — Elite: tách các file vượt ngưỡng ở tầng UI

**Thuộc:** [`EPIC-007`](../README.md) · **Repo:** `Sagittarius_Elite_Warrior` · **Trạng thái:** 🔵 Chưa làm
**Phụ thuộc:** `007F`

---

## Phạm vi

Làm **sau** migrate, không phải trước: `007E`/`007F` đã rút bớt nội dung ra khỏi các file này,
nên tách trước sẽ phải tách hai lần.

Ngưỡng (`README.md` §3.4): **>400 dòng** hoặc **>15 phương thức công khai**.

| File | Dòng hiện tại | Ghi chú |
| :--- | ---: | :--- |
| `data_management_widgets.py` | 1.156 | 9 lớp; sau `007E` mất `TimeRangeCardWidget`, `LogPanelWidget`, `AppProgressBarWidget`, `SymbolPickerDialog` |
| `backtest_modals.py` | 1.231 | 13 lớp — 11 Overlay + 2 helper |
| `data_management_view.py` | 818 | |
| `backtest_top_panel.py` | 697 | |
| `backtest_trade_logs_panel.py` | 617 | |

## Yêu cầu

1. **1 file 1 lớp** cho mọi lớp công khai còn lại. Lớp private (`_XxxRow`) đi cùng lớp công
   khai duy nhất dùng nó.
2. **Giới hạn bắt buộc — Single-Scope Cohesion** (`code-rule.md`): những định nghĩa thuộc
   **cùng một vòng đời** phải ở chung một file. Cụ thể ở epic này:
   - `backtest_fsm_matrix.py` — State enum + Event enum + ma trận chuyển + ánh xạ UI mode:
     **không tách**, đây là ví dụ mẫu của luật.
   - Một `Overlay` cùng các dataclass payload chỉ nó dùng: để chung.

   Tách một vòng đời ra nhiều file là **vi phạm**, không phải tuân thủ.
3. **Không đổi hành vi, không đổi API công khai.** Chỉ di chuyển. `__init__.py` re-export để
   call-site không phải sửa; nếu phải sửa call-site thì liệt kê hết trong file này.
4. Đo lại sau khi xong: liệt kê file nào còn trên ngưỡng và lý do vì sao được ở lại.

## Bằng chứng phải nộp

- Bảng dòng-trước / dòng-sau cho từng file.
- `git diff --stat` cho thấy phần lớn là di chuyển, không phải viết mới.
- `pwsh -NoProfile -File scripts/ci-local.ps1` — `RESULT: PASS`, số test **không đổi**.

## Rủi ro

Tách file dễ tạo import vòng (`data_management_widgets` đang được import từ nhiều nơi). Nếu
gặp vòng, **không** giải bằng import cục bộ trong hàm — `code-rule.md` cấm tuyệt đối. Giải
bằng cách đặt lại ranh giới module.
