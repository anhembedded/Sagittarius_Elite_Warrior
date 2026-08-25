# EPIC-007D — Elite: gộp ~10 biến thể màu nền card về 1 token

**Thuộc:** [`EPIC-007`](../README.md) · **Repo:** `Sagittarius_Elite_Warrior` · **Trạng thái:** ✅ Xong — 2026-08-25
**Phụ thuộc:** `007A`–`007C` — đã xong

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

## Bằng chứng

### Guard: 130 → 0

```text
TRƯỚC  find_inline_stylesheets(src/presentation/ui)                   130
       trong đó assets/palette.py                                      15   ← xem §Lệch 1
SAU    find_inline_stylesheets(..., colour_source_names=("palette.py",)) 0
```

19 dòng mang marker `token-exempt` kèm lý do, chia 3 nhóm:

| Nhóm | Số | Lý do ghi tại chỗ |
| :--- | ---: | :--- |
| `components/chart_card/**` | 15 | Package này **cố ý** không phụ thuộc `Palette` — quyết định đã ghi trong `theme.py`. Xem §Lệch 2 |
| `strategy_indicator_lines.py` | 8 | Bảng 8 màu chuỗi chỉ báo — màu nghiệp vụ, không phải chrome |
| `sidebar.py` | 1 | Xám tối hơn `MUTED` có chủ đích, quyết định đã ghi từ trước |
| `preview.py` | 2 | Màu nến tăng, khớp `chart_card/theme.py` |

### Ảnh trước/sau — 4 màn

Chụp bằng `tests/integration/presentation/ui/test_capture_screenshots.py` (thêm mới trong
task này; bị skip trừ khi bật `SEW_CAPTURE_SCREENSHOTS`, nên không chạy trong CI).

| Màn | Pixel đổi | Delta trung bình | Delta max |
| :--- | ---: | ---: | ---: |
| `settings` | **0** | 0 | 0 |
| `data_management` | 0,7% | 9,4 / 765 | 452 ⚠️ |
| `dashboard` | 16,0% | 8,7 / 765 | 586 ⚠️ |
| `backtest` | 29,4% | 8,9 / 765 | 78 |

⚠️ **Delta max của 2 màn KHÔNG phải lỗi màu — là đồng hồ.** Ô DATA RANGE và dấu thời gian
trong log hiển thị thời điểm hiện tại; hai lần chụp cách nhau 12 phút (`09:37` vs `09:49`) nên
glyph khác hẳn ở vài trăm pixel. Đã cắt ảnh vùng đó kiểm chứng tận mắt trước khi kết luận.
Cảnh báo này đã ghi vào docstring của harness để người sau khỏi điều tra lại.

Thay đổi màu **thật** là delta trung bình ~9/765 ở cả 3 màn có đổi — một dịch chuyển nhỏ đều
khắp, đúng như §3.1 dự kiến. Không màn nào "trông sai hẳn", nên kill criterion không kích hoạt.

### Test

`1695 passed` (`tests/unit/`), bằng đúng baseline trước task.

## Ba chỗ lệch khỏi đề bài

**1. "0 finding" không đạt được nếu không sửa Engine.** Guard ghi cứng `_STYLE_MODULE_NAME =
"style.py"`, nên `assets/palette.py` — chính file định nghĩa token — bị báo 15 lần vì *chứa
token*. Không app nào về 0 được. Đã thêm tham số `colour_source_names` cho
`find_inline_stylesheets` (commit bên Engine, 3 test mới). Đây là thay đổi **cộng thêm**: gọi
không truyền gì thì hành vi cũ giữ nguyên.

**2. `chart_card/` giữ literal, không dùng `Palette`.** Giữa chừng tôi đã thêm import `Palette`
vào 6 file ở đó — rồi phát hiện `theme.py` có quyết định ghi rõ: *"this package doesn't import
the app's global Palette (**kept portable/standalone**)"*. Đã hoàn tác và dùng `token-exempt`
thay vì tự ý lật quyết định của người khác.

> ⚠️ **Nhưng quyết định đó đã yếu hơn lúc nó được viết.** `indicator_manager.py` giờ import
> `Sagittarius_Elite_Warrior.src.domain.indicator_scripts`, nên `chart_card/` **không còn
> standalone** thật. Cần user quyết: giữ tính khả chuyển (thì nên gỡ cả import domain kia), hay
> thừa nhận nó đã là code của app (thì 15 marker này thành thừa). Chưa làm, ghi làm ứng viên.

**3. `sidebar._SECTION_TITLE_COLOR` giữ nguyên.** Script của tôi đã đổi nó thành `Palette.MUTED`
— và comment ngay trên nó nói *"deliberately not Palette.MUTED"*. Đã hoàn tác. Epic này gộp các
**nền card gần trùng nhau**; đây là một ngoại lệ có chủ đích, có lý do ghi sẵn, không phải trôi dạt.

## Hai thứ chỉ lộ ra khi làm, không có trong đề bài

**1. Gộp màu suýt xoá mất sọc vằn của bảng — `ruff` bắt được, test thì không.**
`_TradeLogRowWidget` tô nền xen kẽ `#12141d` (chẵn) / `#161823` (lẻ). Cả hai đều rơi vào
`BG_CARD`, nên biểu thức thành `BG_CARD if row_number % 2 == 0 else BG_CARD` — **sọc vằn biến
mất**. Đó là mất thông tin cho người đọc bảng, không phải trôi màu.

`RUF034 Useless if-else` là thứ phát hiện ra. 1695 test đều xanh trong khi lỗi này đang tồn
tại — không test nào khẳng định hai hàng liền nhau phải khác màu. Đã sửa: hàng lẻ dùng
`BG_CARD_HEADER`.

Ruff tìm ra 4 ca như vậy. Ba ca còn lại (nền badge long/short, nền banner audit pass/fail,
hover của tab) là **nền đồng nhất có chủ đích** — phân biệt do màu chữ/viền mang, đúng thiết
kế `Banner` của `007B`. Đã bỏ nhánh điều kiện và ghi lý do tại chỗ.

**2. `ruff format` và marker `token-exempt` đánh nhau.** Marker phải nằm **cùng dòng** với hex
(guard đọc theo dòng), nhưng thêm nó vào làm dòng vượt 88 ký tự → formatter ngắt dòng → marker
rơi xuống dòng dưới → guard báo lại. Chạy hai công cụ nối tiếp nhau tạo ra vòng lặp: guard 0 →
format → guard 8 → sửa → format → guard 3 → ...

Cách thoát: rút gọn câu lý do, và với chỗ vẫn dài thì đưa giá trị lên thành hằng cấp module
(`crosshair_controller._LABEL_FILL`) để dòng đủ ngắn. **Luôn chạy guard SAU `ruff format`,
không phải trước** — nếu không, cổng xanh giả.

## Hai ứng viên đã được user chốt và làm ngay sau đó

Cả hai nằm trong commit tiếp theo, không phải trong `007D` — ghi ở đây để nối mạch.

**1. `chart_card/` là code của app.** User chốt 2026-08-25: thừa nhận nó đã phụ thuộc app
(`indicator_manager` import `src.domain`) thay vì giả vờ khả chuyển. 19 marker `token-exempt`
→ **4**, và cả 4 đều là màu nghiệp vụ thật (nến tăng/giảm, 2 màu chỉ báo trong script demo).
Docstring `theme.py` — vốn khẳng định package "doesn't import the app's global Palette" — đã
viết lại theo sự thật, kèm chỉ dẫn phải gỡ gì nếu sau này thật sự muốn làm nó khả chuyển.

**2. Guard đã được nối vào CI.** `tests/unit/presentation/ui/test_widget_guards_hold.py`.
`find_inline_stylesheets` khoá **0 tuyệt đối**; `find_bare_qt_base_widgets` khoá bằng **trần
21 chỉ được giảm**, kèm một test thứ hai báo đỏ khi con số *giảm* mà quên hạ trần — nếu không
trần sẽ phình ra rồi nằm đó vô nghĩa. Có cả test kiểm `_UI_ROOT` trỏ đúng chỗ, vì một đường
dẫn sai sẽ khiến hai guard quét thư mục rỗng và xanh vì không tìm thấy gì.

## Ứng viên ghi lại

| Thứ | Vì sao hoãn |
| :--- | :--- |
| Đóng băng đồng hồ trong harness chụp ảnh | Sẽ làm ảnh so sánh được từng pixel; cần VM nhận thời gian cố định |
| Test khoá sọc vằn | Không test nào bảo vệ nó — xem §1 trên. Ứng viên cho `007F` khi bảng chuyển sang `TableCard` |
| `ruff` `UP017` ở `test_kline_inspector_widget.py` | **Đã đỏ sẵn trước task này** (xác minh bằng `git stash`), ở file `007D` không đụng tới. Không sửa kèm để diff không lẫn |

## Rủi ro

Đây là task **duy nhất trong epic đổi thị giác có chủ đích**. Nếu một màn trông sai hẳn (không
phải "hơi khác"), dừng lại: nhiều khả năng một trong ~10 biến thể mang ý nghĩa thật (ví dụ
phân tầng card lồng trong card) chứ không phải trôi dạt. Ghi lại rồi mới quyết định giữ nó
thành token thứ hai có tên hẳn hoi.
