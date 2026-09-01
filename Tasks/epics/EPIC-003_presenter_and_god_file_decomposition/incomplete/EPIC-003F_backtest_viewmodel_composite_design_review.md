# EPIC-003F — `BackTestViewModel` → Composite ViewModel: vòng thiết kế trước, CHƯA code

**Thuộc Epic:** [`EPIC-003`](../README.md)
**Trạng thái:** 🟡 **Đã mở khoá 2026-08-27** — vòng thiết kế xong, có quyết định ở §4.
Code vẫn chưa bắt đầu: task con triển khai chưa mở.
**Phụ thuộc:** Không phụ thuộc kỹ thuật task nào, nhưng cố tình tách khỏi `EPIC-003E` — không tự động làm sau khi `E` xong.
**Nguồn vòng đo lại:** [`DOCTOR-002`](../../../completed/DOCTOR-002_epic_003f_blocker_is_dead.md)

---

## 1. Lý do chặn cũ — đã chết, giữ lại để không ai mở lại

> **Bản gốc (21/08) lập luận:** *"mọi file `.qml` đang bind `viewModel.xxx` trực
> tiếp — tách ViewModel gốc thành nhiều `QObject` con nghĩa là mọi điểm bind đó
> phải đổi cách viết […] lan rộng tới gần như mọi `.qml` của màn Backtest cùng
> lúc"*, và bắt trả lời 3 câu hỏi trước khi được code: (1) QML có đọc được
> `viewModel.config.someProp` lồng nhau không, (2) migrate từng `.qml` thế nào,
> (3) cần bao nhiêu test binding QML để không lặp lại `BUG-018`/`BUG-019`.

`EPIC-006` đã gỡ sạch QML khỏi app. Kiểm bằng cây thư mục, không bằng trí nhớ:

```bash
find src -name '*.qml' | wc -l                                    # → 0
grep -rn "setContextProperty\|rootContext" src --include='*.py'   # → không có dòng nào
```

**Câu hỏi 1 và 3 hết đối tượng.** Không còn binding QML nào để hỏng, không còn
`.qml` nào để viết test binding. Đừng trả lời chúng.

**Câu hỏi 2 (chiến lược migrate) sống sót** — nó không phải câu hỏi về QML, nó
là câu hỏi về việc đổi một API mà nhiều nơi đang gọi. Xem §3.

## 2. Rủi ro thật hôm nay — đo lại 27/08, không suy đoán

`BackTestViewModel`: **1.368 dòng, 64 `@Property`, 68 `Signal`.**
*(Đo lại 2026-09-01: **1.435 dòng** — con số trên đã trôi, dùng lệnh đếm thật, xem `003F1` §1.)*

| Đo | Số |
| :--- | ---: |
| File tham chiếu tới nó (`src` + `tests`) | **28** |
| — trong `src` | 18 |
| — riêng `backtest_modals/` | 14 |
| Điểm đọc thuộc tính trong `screens/backtest/` | **344** |
| Test phủ màn Backtest | 40 file / **451 test** |
| Coverage của chính `backtest_view_model.py` | **96%** |

### 2.1. Phát hiện quyết định: 15/18 file chỉ dùng nó để **chú thích kiểu**

Trong 18 file `src` tham chiếu `BackTestViewModel`, **15 file import nó bên
trong `if TYPE_CHECKING:`** — tức chỉ để viết `vm: BackTestViewModel`. Chỉ **3**
file chạm nó lúc chạy thật: `backtest_presenter.py`, `backtest_modals/__init__.py`,
`preview.py`.

Đó là tin tốt về mặt cấu trúc: coupling phần lớn là **kiểu**, không phải khởi tạo.

### 2.2. Và đó cũng chính là rủi ro mới, vì kiểu đó **không ai kiểm**

`[tool.mypy]` trong `pyproject.toml` loại trừ `src/presentation/` **nguyên
khối**. Nghĩa là 15 annotation kia hiện **không được kiểm bởi bất cứ thứ gì**.

Nếu tách ViewModel và một widget còn đọc `vm.someProp` đã dời sang sub-ViewModel,
**không công cụ nào bắt được** — nó nổ lúc chạy, đúng kiểu hỏng mà bản gốc sợ ở
QML. **Chế độ hỏng không biến mất; nó chỉ đổi áo.** Từ "binding QML nổ lúc chạy"
thành "`AttributeError` nổ lúc chạy".

Đo xem bật `mypy` cho riêng màn này tốn bao nhiêu (probe 27/08, dùng bản copy
`pyproject.toml` đã bỏ dòng loại trừ `presentation/`):

```
Found 229 errors in 21 files (checked 56 source files)
  89 [arg-type]   74 [union-attr]   23 [assignment]   22 [attr-defined]  …
  104/229 dòng có nhắc "Property"  ← nhiễu hệ thống @Property đã biết
```

**Bật `mypy` cho màn Backtest không miễn phí** — nó là một việc cỡ `EPIC-002A`
(đo baseline, phân loại nhiễu-vs-thật), không phải một cái công tắc.

## 3. Ba lựa chọn, và cái giá thật của từng cái

| # | Cách chặn lỗi "đọc thuộc tính đã dời" | Cái giá |
| :-- | :--- | :--- |
| A | **Bật `mypy` cho `screens/backtest/` trước** | Phải xử 229 lỗi (≈45% là nhiễu `@Property`). Một task riêng cỡ `EPIC-002A`. Chặn `003F` lại thêm một vòng nữa |
| B | **Dựa vào 451 test hiện có** | Rẻ, nhưng test không phải công cụ chứng minh *vắng mặt*: 96% coverage của ViewModel không nói gì về việc widget nào đọc thuộc tính nào |
| C | **Facade chuyển tiếp** — giữ `BackTestViewModel` forward mỗi `@Property` sang đúng sub-ViewModel, migrate từng call site | Không cần A hay B để an toàn: mỗi bước không đổi hành vi, 344 điểm đọc vẫn chạy nguyên trong lúc chuyển |

**C chính là câu hỏi 2 của bản gốc**, và nó sống sót nguyên vẹn qua đợt QML→QtWidgets
— vì nó chưa bao giờ là câu hỏi về QML.

## 4. Quyết định (27/08)

> **Mở khoá, theo hướng C. Không kèm điều kiện tiên quyết mới.**

Lý do: hướng C làm cho câu hỏi "công cụ nào bắt lỗi" trở nên **không cần trả
lời** — vì không có bước nào trong quá trình chuyển làm hỏng call site nào. Bắt
`003F` chờ hướng A (bật `mypy`) là thay một cánh cổng đã chết bằng một cánh cổng
mới, đắt hơn, cho một rủi ro mà C vốn đã loại bỏ.

**Điều kiện bắt buộc khi mở task con triển khai:**

1. **Facade trước, dời sau.** Bước đầu tiên chỉ được tạo sub-ViewModel và cho
   `BackTestViewModel` forward sang — **không sửa call site nào**. Bước đó phải
   giữ cả 451 test pass **không sửa dòng test nào**; nếu phải sửa test thì facade
   sai, dừng lại.
2. **Không "big bang".** Mỗi lần dời một nhóm thuộc tính, không phải cả 64.
3. **Gỡ facade là bước cuối cùng và là một task riêng** — chỉ khi 344 điểm đọc
   đã dời hết. Nếu dừng giữa chừng, facade ở lại; nó vẫn đúng, chỉ là chưa đẹp.
4. **Ghi lại nếu hướng A về sau vẫn đáng làm.** Bật `mypy` cho `presentation/`
   là việc tốt độc lập với `003F` (thuộc `EPIC-002D`), chỉ là không được phép
   chặn `003F`.

## 5. Việc còn lại ở chính task này

- [x] Đo lại rủi ro thật (§2).
- [x] Chốt hướng và điều kiện (§4).
- [x] Mở task con [`EPIC-003F1`](EPIC-003F1_trade_log_sub_view_model_facade.md) — facade +
      sub-ViewModel đầu tiên, theo §4.1. **User duyệt phạm vi 2026-09-01.**
      Lát cắt đầu: **trade log** (6 property / 6 signal / 56 điểm đọc) — không phải nhóm nhỏ nhất,
      mà là nhóm cohesive nhất và đã có đường nối sẵn ở 3 tầng khác (coordinator, widget VM, module
      logic thuần). Xem `003F1` §2 để biết vì sao nhóm "UI lặt vặt" (38 điểm đọc) bị loại dù nhỏ hơn.
