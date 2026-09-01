# BUG-080 — Thư viện widget dùng chung `ui/qml/` phụ thuộc ngược vào `ui/screens/`

- **Trạng thái:** 🔴 Chưa sửa
- **Mức độ:** 🟡 **P3** — chưa gây triệu chứng cho người dùng; là lỗi cấu trúc sẽ tính tiền vào màn hình thứ ba
- **Ngày báo:** 2026-09-01
- **Phát hiện khi:** khảo sát khả năng tái dùng màn Backtest cho màn Giao dịch (`EPIC-021I`)
- **Đóng bởi:** [`EPIC-021L`](../../epics/EPIC-021_ket_noi_binance_futures_testnet/incomplete/EPIC-021L_dao_chieu_phu_thuoc_qml_screens.md)

---

## 1. Symptom — luật do chính repo phát biểu, và code vi phạm nó

Repo đã phát biểu luật này bằng văn bản, trong docstring của
[`qml/StatCardRow/stat_card_row_widget.py:25`](../../../src/presentation/ui/qml/StatCardRow/stat_card_row_widget.py):

> *"…so this widget stays testable and reusable without importing anything from `screens/backtest/`
> (**`qml/` must not depend on `screens/`** — the reverse dependency `backtest_top_panel.py`
> already has is the one direction this rollout uses throughout)."*

Bốn file **production** trong `ui/qml/` vi phạm đúng luật đó. Không có gì bắt được — không lint,
không test, và `mypy` thì loại trừ `src/presentation/` nguyên khối (`pyproject.toml`, `EPIC-002A`).

```bash
grep -rn "screens\." --include=*.py src/presentation/ui/qml/ | grep import
```

| File trong `qml/` (dùng chung) | Import từ |
| :--- | :--- |
| `TradeLogTable/trade_log_vm.py` | `screens.backtest.logic.trade_log_row`, `screens.backtest.logic.trade_log_filter` |
| `MetricsDetailPanel/metrics_detail_vm.py` | `screens.backtest.logic.performance_metrics_view` |
| `DatabaseStatusTable/database_status_vm.py` | `screens.data_management.database_status_table_model` |
| `KlineInspectorTable/kline_inspector_vm.py` | `screens.data_management.kline_inspector_table_model` |

(Cộng 5 hit nữa ở `preview.py`/`tests/` của cùng các widget đó — cùng một defect, cùng phải sửa.)

**Vì sao chưa ai thấy:** app hiện có đúng **hai** consumer cho mỗi widget, và cả hai đều là chính
màn sở hữu module bị import. Vòng phụ thuộc vì thế chưa bao giờ khép lại thành một triệu chứng.

## 2. Root cause — widget đã được trích xuất, model của nó thì chưa

`EPIC-015` chuyển từng widget sang QML và đặt chúng đúng chỗ: `ui/qml/<Widget>/` với `*.qml`,
`*_vm.py`, `preview.py`, `tests/`. Nhưng **model/logic thuần** mà mỗi ViewModel cần thì được để
nguyên tại chỗ cũ trong `screens/<màn>/`:

| Module còn kẹt trong `screens/` | Dòng | Qt? | Thực chất là gì |
| :--- | ---: | :---: | :--- |
| `screens/backtest/logic/trade_log_row.py` | 185 | không | Model thuần, chỉ phụ thuộc `domain.backtesting.Trade`/`ExitReason` |
| `screens/backtest/logic/trade_log_filter.py` | 60 | không | Hàm lọc thuần |
| `screens/backtest/logic/performance_metrics_view.py` | 359 | không | Chuẩn hoá metrics để hiển thị |
| `screens/data_management/database_status_table_model.py` | 230 | có | `QAbstractTableModel` + filter proxy |
| `screens/data_management/kline_inspector_table_model.py` | 278 | có | `QAbstractTableModel` |

Không module nào trong 5 cái này chứa thứ gì **riêng của một màn**. Chúng screen-agnostic thật —
chỉ là đang nằm sai thư mục, và vì nằm sai nên thư viện dùng chung buộc phải với tay vào `screens/`
để lấy.

Đây đúng lớp lỗi mà [`EPIC-007`](../../epics/EPIC-007_chuan_hoa_card_dung_chung/README.md) §1 đã
ghi lại một lần: `data_management_widgets.py` (1.156 dòng) vô tình thành thư viện widget chung của
cả app vì trộn nguyên thuỷ dùng chung với widget riêng của một màn, khiến 3 file ở 2 màn khác phải
import chéo vào nó. Lần này tinh vi hơn: **widget đã ở đúng chỗ, model thì chưa** — nên nhìn cây
thư mục thấy sạch, chỉ `grep` import mới lộ.

## 3. Vì sao là BUG chứ không phải "nợ kỹ thuật để đó"

Theo luật repo, code phát biểu sai về chính nó là BUG. Ở đây phát biểu sai nằm ngay trong docstring
của một file cạnh bên: nó mô tả một bất biến ("`qml/` must not depend on `screens/`") như thể đang
được giữ, trong khi 4 file cùng thư mục đang phá. Một agent đọc docstring đó sẽ tin là mình đang
làm việc trong một thư viện độc lập, và thiết kế dựa trên điều không đúng.

Chi phí sẽ hiện ra ở **màn hình thứ ba**: `EPIC-021I` (màn Giao dịch) cần dùng lại `TradeLogTable`
cho sổ lệnh. Ở trạng thái hôm nay, làm vậy sẽ kéo `screens/backtest/` vào một màn không liên quan
gì tới backtest — một import mà không ai đọc code màn Giao dịch giải thích nổi.

## 4. Fix

Đảo chiều, không cắt: dời 5 module về đúng thư mục widget sở hữu chúng, để chiều phụ thuộc thành
`screens/ → qml/` — đúng chiều mà `stat_card_row_widget.py` gọi là *"the one direction this rollout
uses throughout"*. Chi tiết thiết kế, chỗ đến của từng file, và phương án bị bác bỏ: xem
[`EPIC-021L`](../../epics/EPIC-021_ket_noi_binance_futures_testnet/incomplete/EPIC-021L_dao_chieu_phu_thuoc_qml_screens.md).

## 5. Regression test

Guard `ast` quét toàn `src/presentation/ui/qml/` (kể cả `preview.py` và `tests/` của từng widget),
đỏ khi có bất kỳ import nào tới `presentation.ui.screens`. Verify **hai chiều**, theo đúng khuôn
`test_backtest_view_contract.py` (`EPIC-013B`): chạy sạch sau khi sửa, **và** đỏ khi cố tình chèn
lại một import vi phạm.

Viết guard **trước** khi dời file, và xác nhận nó đỏ với đúng 4 file production + 5 hit phụ ở
`preview`/`tests` — đó là bằng chứng nó thật sự bắt được defect này, không phải một test luôn xanh.
