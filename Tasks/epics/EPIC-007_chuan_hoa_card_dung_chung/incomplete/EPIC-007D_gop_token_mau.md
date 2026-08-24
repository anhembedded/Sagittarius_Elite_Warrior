# EPIC-007D — Elite: gộp ~10 biến thể màu nền card về 1 token

**Thuộc:** [`EPIC-007`](../README.md) · **Repo:** `Sagittarius_Elite_Warrior` · **Trạng thái:** 🔵 Chưa làm
**Phụ thuộc:** `007A`–`007C`

---

## Phạm vi

18 hằng màu cấp module + ~112 hex literal rải rác trong 4 màn hình. User đã chốt: **gộp về 1
token, chấp nhận đổi pixel.**

Hiện trạng đo được:

```text
backtest_top_panel.py : _PANEL_BG #0d0e14  _CARD_BG #12141d  _CARD_BORDER #222533
                        _FIELD_BG #181a24  _FIELD_BORDER #2a2d3d  _FIELD_HOVER_BG #222536
dev_board_panel.py    : _ROOT_BG  #0d0e14  _CARD_BG #12141d  _CARD_BORDER #222533
                        _FIELD_BG #181a24  _FIELD_BORDER #2a2d3d  _BADGE_BG #181a26
                        _BADGE_BORDER #282b3d  _ROW_HOVER_BG #181b27
backtest_widgets.py   : _CARD_BG  #14161f  _CARD_BORDER #232634
                        _CARD_HOVER_BG #1a1d29  _CARD_HOVER_BORDER #363a4d
data_management       : inline, không đặt tên — #131418 #131822 #141620 #15171e
                        #171922 #1b1d28 #1e1e24 ...
Palette.BG_CARD       : #111318   ← KHÔNG màn nào đang dùng
```

## Yêu cầu

1. **Mọi card đọc `Palette.BG_CARD` qua `apply_role()`.** Sau task này, `find_inline_stylesheets`
   chạy trên `src/presentation/ui` phải về **0 finding** ngoài các dòng có `token-exempt` kèm
   lý do (chart pyqtgraph có màu domain thật — nến xanh/đỏ, crosshair — không phải màu card).
2. **Xoá 18 hằng cấp module.** Không đổi tên, không chuyển sang `Palette` — xoá.
3. **Sửa docstring sai của `dev_board_panel.py`** (dòng 6–13). Nó khẳng định bộ màu riêng là
   "bản sắc testbed cố ý, đã kiểm chứng không trùng token nào". Khẳng định đó **không còn
   đúng**: `backtest_top_panel.py:38-43` chép y hệt 5/8 giá trị. Viết lại theo sự thật, dẫn
   quyết định gộp token ở `README.md` §3.1. Đây là nghĩa vụ của `doc-code-sync.md` — sửa trong
   cùng change, không file task để sau.
4. **Token thiếu thì bổ sung vào `Palette`, không tự chế tại chỗ.** `apply_role()` đọc
   `radiusMd`/`radiusSm`/`spaceXs`/`spaceSm`/`spaceMd` — hiện `Palette.as_ui_dict()` chỉ cấp
   màu, phần còn lại rơi vào default của engine (`tokens/defaults.py`). Nếu default không khớp
   thị giác hiện tại thì thêm key vào `as_ui_dict()`, đừng hardcode trong QSS.

## Bằng chứng phải nộp

- Ảnh chụp **trước/sau** của cả 4 màn. Đây là task **cố ý đổi pixel** — phải nhìn thấy được
  đổi cái gì, không được để review đoán.
- `find_inline_stylesheets` trước (130 finding) và sau (kỳ vọng ~0 + danh sách miễn trừ có lý do).
- `pwsh -NoProfile -File scripts/ci-local.ps1` — `RESULT: PASS`, so khớp baseline test.

## Rủi ro

Đây là task **duy nhất trong epic đổi thị giác có chủ đích**. Nếu một màn trông sai hẳn (không
phải "hơi khác"), dừng lại: nhiều khả năng một trong ~10 biến thể mang ý nghĩa thật (ví dụ
phân tầng card lồng trong card) chứ không phải trôi dạt. Ghi lại rồi mới quyết định giữ nó
thành token thứ hai có tên hẳn hoi.
