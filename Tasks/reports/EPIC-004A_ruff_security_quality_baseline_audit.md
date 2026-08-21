# EPIC-004A — Baseline thật: Ruff's security (Bandit) + quality rule categories bắt bao nhiêu lỗi trên codebase hiện tại

**Ngày đo:** 2026-08-22
**Công cụ:** Ruff (đã cài sẵn trong venv, không cần thêm binary — `S` là toàn
bộ rule của Bandit đã được port vào Ruff).
**Lệnh dùng để đo:** `ruff check --select S,PLR2004,B,SIM,ERA,N --statistics <path>`
**Cấu hình hiện tại:** `pyproject.toml` **không có** mục `[tool.ruff]` nào —
Ruff đang chạy hoàn toàn ở rule set mặc định (chỉ nhóm `E`/`F` cơ bản). Không
có rule an toàn/bảo mật/magic-number nào đang được enforce.

---

## 1. Vì Sao Đo Baseline Này

`mypy` (đã nối vào CI qua `EPIC-002`) chỉ bắt lỗi *kiểu dữ liệu*. Nó không
bắt được: hardcoded secret, `subprocess`/`pickle` không an toàn, magic number
không đặt tên hằng số (vi phạm rule đã có sẵn trong `code-rule.md` §2.7 nhưng
chưa từng được máy verify), code chết, exception bị nuốt im lặng, v.v.
Không có "MISRA cho Python" 1-1 (Python không có lớp rủi ro undefined-behavior/
con trỏ mà MISRA nhắm tới), nhưng **Bandit** (đã có sẵn trong Ruff qua prefix
`S`) là tương đương gần nhất cho lớp rủi ro bảo mật, và các nhóm rule khác của
Ruff (`PLR2004`, `B`, `SIM`, `ERA`, `N`) phủ được phần "chất lượng code" còn
lại. Đúng phương pháp `EPIC-002A`: đo thật trước, không đoán, không bật gate
ngay khi chưa biết con số.

## 2. Số Liệu Thật

### 2a. Toàn bộ `src` + `scripts` + `tests` (4491 lỗi)

| Rule | Số lượng | Ý nghĩa |
| :--- | ---: | :--- |
| `S101` | 3588 | `assert` trần — Bandit coi là rủi ro vì `assert` bị strip khi chạy `python -O` |
| `PLR2004` | 533 | So sánh với giá trị số/chuỗi chưa đặt tên hằng số (magic number/string) |
| `N815` | 226 | Biến class-scope không phải `snake_case` |
| `N802` | 102 | Tên hàm/method không phải `snake_case` |
| `ERA001` | 9 | Code bị comment out còn sót |
| `S311` | 7 | Dùng `random` (không phải `secrets`) cho việc có thể nhạy cảm |
| `SIM105` | 5 | Nên dùng `contextlib.suppress` thay `try/except/pass` |
| `B007`/`B905` | 3+3 | Biến loop không dùng / `zip()` thiếu `strict=` |
| `N813`/`N999`/`S603` | 2 mỗi loại | Naming lạ / import camelCase / gọi `subprocess` |
| Còn lại (7 rule) | 1 mỗi loại | Lặt vặt |

### 2b. Chỉ `src` + `scripts` (379 lỗi) — loại `tests/` để tách nhiễu

| Rule | Số lượng |
| :--- | ---: |
| `N815` | 226 |
| `N802` | 102 |
| `PLR2004` | 26 |
| `S311` | 7 |
| `SIM105` | 4 |
| `B905` | 3 |
| `ERA001`/`N999` | 2 mỗi loại |
| Còn lại (6 rule) | 1 mỗi loại |

## 3. Phân Loại: Nhiễu Hệ Thống vs. Tín Hiệu Thật

Đúng lớp phát hiện `EPIC-002A` đã gặp với mypy/`@Property` — phần lớn con số
thô là **nhiễu hệ thống có giải thích rõ ràng**, không phải bug thật:

- **`S101` (3588) — 100% nhiễu.** Biến mất hoàn toàn khi loại `tests/`
  (verify: chạy lại chỉ `src`+`scripts`, `S101` không xuất hiện). `assert` là
  idiom bắt buộc của pytest trong mọi test — Bandit's lo ngại (`assert` bị
  strip ở `python -O`) không áp dụng cho code test không bao giờ chạy dưới
  `-O`. **Khuyến nghị: per-file-ignore `S101` cho `tests/`, không cần sửa gì.**
- **`N802`/`N815` (102+226=328) — xác nhận thật 100% là override method/property
  bắt buộc của Qt.** Kiểm tra trực tiếp: `paintEvent`, `eventFilter` trong
  `chart_card/cached_frame_interaction.py` — đây là **virtual method override
  từ `QWidget`/`QObject`**, Qt dispatch theo đúng tên C++ (camelCase), đổi
  sang `snake_case` sẽ **phá vỡ override thật**, không phải vi phạm quy ước
  đặt tên. **Khuyến nghị: ignore `N802`/`N815` toàn cục hoặc chỉ trong
  `src/presentation/ui/`** (nơi duy nhất chạm Qt trực tiếp).
- **`S603`/`S106`/`S108` (2+1+1=4, chỉ ở `tests/`) — xác nhận thật 100% false
  positive.** Đọc từng dòng: `S603` cả 2 chỗ gọi `subprocess.run([sys.executable, ...])`
  — interpreter path tin cậy, không phải "untrusted input". `S106` là chuỗi
  `"s"` gán cho tham số mock `api_secret` trong 1 test — không phải secret
  thật. `S108` **trớ trêu nhất**: báo "insecure temp file" ngay trong chính
  `test_security.py::test_database_manager_path_traversal` — file test **viết
  ra để kiểm tra path traversal**, đường dẫn `/tmp/valid_dir` là fixture, không
  phải lỗ hổng. **Khuyến nghị: per-file-ignore cho `tests/`, không sửa.**

**Tín hiệu thật, đáng làm gate:**

- **`PLR2004` (26 trong `src`/`scripts`, 533 nếu tính cả `tests`) — đúng magic
  number user hỏi, và đúng vi phạm rule đã ghi sẵn trong `code-rule.md` §2.7
  ("Strictly avoid using raw numbers or magic strings in code") nhưng **chưa
  từng có máy verify**. Đáng làm gate + dọn dần.
- **`S311` (7, toàn bộ ở `src/presentation/ui/components/chart_card/__main__.py`)**
  — đọc code xác nhận: đây là **script demo/preview** tự sinh dữ liệu nến giả
  để xem UI (`__main__.py`, không phải đường chạy production/backtest thật —
  domain/application logic dùng nguồn dữ liệu khác hẳn, không đụng `random`
  cho quyết định tài chính nào). Không phải rủi ro bảo mật thật, nhưng đáng
  giữ rule bật để **tự động canh** trường hợp sau này có ai vô tình dùng
  `random` cho logic tài chính thật — false positive hôm nay, canh gác thật
  cho tương lai.
- Còn lại (`SIM105`, `B905`, `B007`, `ERA001`, `N999`, `B027`, `N803`, `N806`,
  `N812`, `N818`, `SIM102`, `SIM108` — tổng ~20 lỗi rải rác) — nhỏ, thật,
  đáng dọn nhưng không cấp thiết.

## 4. Kết Luận Cho `EPIC-004B`

Tín hiệu thật trong `src`+`scripts` sau khi loại nhiễu đã xác nhận: **~48 lỗi**
(26 `PLR2004` + 7 `S311` + ~15 lặt vặt) — hoàn toàn khả thi để làm gate ngay,
không cần baseline-suppression phức tạp như `mypy` (183 lỗi, phải đóng băng
allowlist). Đề xuất cấu hình khởi điểm cho `EPIC-004B`:

```toml
[tool.ruff.lint]
extend-select = ["S", "PLR2004", "B", "SIM", "ERA", "N"]

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101", "S603", "S106", "S108"]  # assert idiom + fixture, không phải rủi ro thật
"src/presentation/ui/**" = ["N802", "N815"]     # Qt virtual-method override bắt buộc camelCase
```

Không bật `--strict`/toàn bộ `PLR`/`C901` (complexity) ngay — theo đúng tiền
lệ rollout từng bước của `EPIC-002`/`BOT-098F`, không "bật hết 1 lần".
