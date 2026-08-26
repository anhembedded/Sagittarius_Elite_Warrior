# BUG-058 — Mọi nhãn trong app bị vẽ khung riêng, và chữ trong stat tile bị cắt

**Trạng thái:** ✅ Đã sửa — 2026-08-26
**Người báo:** user, kèm ảnh chụp màn Storage Vault
**Nguyên văn:** *"bị che chữ, theme quá nhiều đường viền, bạn xóa bớt đi"*
**Nguồn gốc:** `EPIC-005E`/`EPIC-006` — có từ ngày port sang QtWidgets, không phải regression mới

---

## 1. Triệu chứng

Hai stat tile đầu màn Storage Vault:

- Mỗi nhãn (`Stored KLines Records`, giá trị, dòng gợi ý) **tự có một cái khung bao quanh** — ba
  khung lồng trong một card.
- Dòng gợi ý dưới cùng **bị cắt mất phần dưới**.

Cùng hiện tượng ở `SYNC CONTROLS`, `TARGET & TIMEFRAME`, `ACTIONS`, header cột bảng, và mọi nhãn
trên cả bốn màn.

## 2. Hai lỗi độc lập, không phải một

Ban đầu tôi đoán chữ bị cắt là **hệ quả** của viền thừa. **Sai.** Đo sau khi đã gỡ hết viền vẫn
cắt đúng 5px. Đây là hai lỗi riêng biệt tình cờ nằm cạnh nhau.

### 2a. Chữ bị cắt — số học thuần

```
margins 12+12         = 24
labels  15 + 23 + 13  = 51
spacing 2 × 2         =  4
                       ---
                        79px   vs   tile.setFixedHeight(74)
```

`setFixedHeight` **thấp hơn 5px so với chính nội dung của nó**. Sửa: `setMinimumHeight(74)` —
giữ được sàn để hai tile bằng nhau, nhưng không chặn trần dưới mức nội dung cần.

### 2b. Khung thừa — `BUG-008`, và lần này tìm ra **gốc thật**

Cascade `BUG-008` đã được "sửa" một lần: `_scope_qss()` bọc QSS trong `type(widget).__name__`.
Nó chặn universal selector. Nó **không** chặn thứ tiếp theo:

> **Selector kiểu trong Qt khớp cả lớp con.** `QLabel` kế thừa `QFrame`.

Nên trên một `QFrame` thuần, `QFrame { border: ... }` **vẫn** vẽ khung quanh mọi `QLabel` bên
trong. Đo bằng repro tối giản:

| Selector | `QLabel` con | `QLineEdit` con | `QPushButton` con |
| :--- | :---: | :---: | :---: |
| `QFrame` | **rò** | ok | ok |
| `.QFrame` | ok | ok | ok |

`issubclass(QLabel, QFrame) = True`; hai cái kia `False` — khớp chính xác quan hệ kế thừa.

Docstring của `_scope_qss` đã **lập luận thẳng** vì sao dùng selector trần: *"subclass matching
only ever reaches a further subclass of this same widget — never an unrelated sibling"*. Đúng với
`Card`/`Panel`; **sai** với lớp Qt trần, nơi "a further subclass" là **mọi `QLabel` trên màn**.

### 2c. Và chỗ rò lớn nhất thì guard bỏ sót

`main_window.py:110` — `QStackedWidget` chứa **toàn bộ mọi màn hình**:

```python
_CONTENT_BG_STYLE = f"background-color: {Palette.BG}; color: {Palette.TEXT_PRIMARY};"
self._stacked.setStyleSheet(_CONTENT_BG_STYLE)
```

Guard tôi vừa viết **đi thẳng qua nó**, vì `QStackedWidget` giữ widget con **không qua layout**,
nên phép kiểm "sở hữu layout" không thấy. Báo được 15 chỗ và sót đúng cái quan trọng nhất.

## 3. Ba khuyết tật mà chỗ rò đang **che**, không phải gây ra

Gỡ cascade xong thì ba thứ hoá trắng/nhợt. Không cái nào là regression — chúng là rule **thiếu**,
lâu nay sống nhờ màu đi lạc:

| Widget | Vấn đề thật |
| :--- | :--- |
| `LogPanel.list_view` | Không có styling nào |
| Danh sách gap | Không có styling nào |
| `Sidebar` (`BaseView`) | **Có** rule, chưa bao giờ được áp — `QWidget` subclass bỏ qua nền QSS khi bị lồng, trừ khi bật `WA_StyledBackground`. Đứng một mình thì vẽ, nên không test nào bắt được |

## 4. Sửa ở đâu

**Engine (6 PR):** `#207` guard mới · `#208` guard giải `self` theo class · `#209` selector
exact-class `.ClassName` · `#210` `LIST_SURFACE` cho ba thân cuộn · `#211` `WA_StyledBackground`
trên `BaseView` · `#212` guard hiểu container không-layout.

**Elite:** 16 chỗ rò → **0**; 3 card frame dùng `apply_role(SURFACE)`, 2 header dùng
`TABLE_HEADER`, phần còn lại scope tay kèm lý do; `setFixedHeight` → `setMinimumHeight`.

## 5. Vì sao phải để user báo mới biết

Guard `find_inline_stylesheets` = 0 và `find_bare_qt_base_widgets` = 0 **suốt thời gian đó**.
Không guard nào hỏi *"widget này có sơn đè lên con nó không"*. Test thì assert chuỗi QSS và cấu
trúc — không assert **cái nhìn thấy được**.

Nay `find_unscoped_container_stylesheets` khoá ở **0 tuyệt đối** trong
`test_widget_guards_hold.py`, cùng hạng với guard màu.

**Bài học ghi lại:** `BUG-008` tái phát năm lần vì mỗi lần chỉ sửa *chỗ* bị lộ, không sửa *loại*.
Lần này sửa cả ba tầng — gốc (`.ClassName`), guard (bắt được), và ngưỡng (khoá 0).
