# EPIC-007H — Mang widget kit từ Engine về Elite

**Thuộc:** [`EPIC-007`](../README.md) · **Repo:** `Sagittarius_Engine` (xoá) + `Sagittarius_Elite_Warrior` (nhận) · **Trạng thái:** ✅ Xong 2026-08-26
**Phụ thuộc:** `007F` (phải migrate xong 4 màn trước, nếu không việc đổi import sẽ chạm vào code đang dở)

---

## Vì sao — user đề xuất, và số liệu ủng hộ

> *"may cai card UI o ben engen, tui nghi nen mang het qua day, engin nen it thay doi, con cho
> may card UI vao thay doi hoai. du thu issue het"*

Đo trên Engine trong đúng ngày 2026-08-26:

| | |
| :--- | ---: |
| Commit trên Engine hôm đó | 27 |
| …đụng vào `pyside_mvc/` | **15 (56%)** |
| Consumer thật của kit | **1** (Elite, 15 file) |
| `examples/student_management` import kit | **0** lần |
| Chỗ ngoài `widgets/` import vào `widgets/` | **1** (một dòng re-export) |

Một framework lẽ ra ít đổi thì dành hơn nửa ngày để đổi. Lý do kit nằm ở Engine là lời hứa
*"dùng lại được"*, và **chưa consumer thứ hai nào kiểm chứng lời hứa đó**.
`examples/student_management` là bằng chứng duy nhất cho khả năng đó — nó là app **QML**, dùng
kit **0 lần**.

## Cái giá đã hiện thành một bug file

`BUG-055` chính là khoản thuế viết ra giấy: một call site hỏng vì Engine đã cài chưa mang tham
số được thêm vài giờ trước. Mọi hình dạng trong kit đều **đo từ đúng một app**, mọi khuyết tật
đều **do app đó tìm ra** (xem §5b của README epic — năm khuyết tật, một nguyên nhân), và mọi bản
vá đều phải ship thành một release framework rồi app mới chờ và kéo về.

## Đã làm gì

| Từ (Engine) | Đến (Elite) |
| :--- | :--- |
| `sagittarius_engine/extensions/pyside_mvc/widgets/` (24 file, 4.037 dòng) | `src/presentation/ui/kit/` |
| `tests/extensions/pyside_mvc/widgets/` (3.267 dòng) | `tests/unit/presentation/ui/kit/` |
| `tools/widget_showcase/` | `tools/kit_showcase/` |

- Đổi import ở **18 file** Elite; 3 chỗ dùng kiểu module (`from ... import widgets`) đổi thành
  `from ...ui import kit as widgets`.
- Xoá kit khỏi Engine + gỡ dòng re-export ở `pyside_mvc/__init__.py` (export 63 → 45).
- **Ở lại Engine:** MVC base, từ vựng token, `theme_bridge`, kit QML — những thứ **có** consumer
  thứ hai mà kit widget chưa bao giờ có. Kit mới chỉ còn **một** phụ thuộc hướng ra:
  `pyside_mvc.tokens.theme_bridge`.

## Việc chuyển chỗ tự nó lộ ra 4 lỗ hổng — đây mới là phần đáng giá

1. **`_MonthGrid` chưa từng bị guard soi.** Test guard của Engine chỉ quét
   `widgets/surfaces/`, **không bao giờ quét `overlays/`**. Sang Elite mới lộ. Đã thêm
   `# base-exempt:` có ghi lý do.
2. **8 lỗi lint** mà ruff của Elite bắt còn ruff của Engine cho qua: `DTZ011 date.today()`,
   `PLR2004`, `SIM105`, `FURB192`. Cấu hình chặt hơn tìm ra lỗi thật.
3. **Showcase làm bẩn guard.** 11 hex literal trong demo làm `find_inline_stylesheets` đỏ. Đưa
   showcase ra `tools/` — ngoài cây guard quét — để "cây guard quét" vẫn đúng nghĩa là "UI của
   app". Kèm theo: thêm `tools` vào cổng ruff của CI Elite, vì một thư mục top-level nằm ngoài
   cổng lint là cách cổng lặng lẽ ngừng phủ repo.
4. **Guard `test_card_layer_structure` đỏ.** Luật "Card phải nằm trong `components/`" gặp
   `StatCard`/`TableCard`/`LogPanel` của chính kit. Đã **thu hẹp phạm vi** (kit là nơi *định
   nghĩa* `Card`, luật không thể ràng buộc chính nó) chứ không nới luật: mọi đường dẫn guard
   phủ trước đây vẫn phủ, và thêm `test_the_kit_is_not_a_hiding_place` ghim đúng 3 file được
   miễn — thêm card mới vào kit là đỏ cho tới khi có người ghi tên nó vào.

## Kiểm chứng

- Engine: `pytest` **1221 passed, 20 skipped**; `mypy` sạch **413 file**; `bandit` **0 issue**;
  `ruff check`/`format` sạch trên đúng path CI chạy.
- Elite: `pytest` **2277 passed** + guard card 4/4 sau khi sửa; 3 guard về baseline
  (cascade **0**, hex **0**, bare **2**).
- `ResourceWarning` lúc shutdown có **y hệt** trên `origin/main` (cùng số 45) → không phải của
  thay đổi này.

## Rủi ro đã chấp nhận

User đã được nêu rủi ro và trả lời: *"chuyen nay phai lam cho du co risk nhu nao cung phai lam"*.
Rủi ro lớn nhất là **mất khả năng dùng lại nếu sau này có app thứ hai**. Đánh đổi: khi đó kit đã
được **một** app dùng thật đủ lâu để hình dạng ổn định, nên việc rút ngược lên framework lúc ấy
rẻ hơn và **đúng hơn** so với đoán trước hình dạng bây giờ — đúng quy luật §5b của epic này.
