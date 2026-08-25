---
name: Onboarding
description: Entry point for any AI agent working on Sagittarius Elite Warrior — repo layout, task/bug workflow, real verification commands, bookkeeping, and the traps that repeatedly produce broken code.
trigger: always_on
---

# ONBOARDING — Đọc file này TRƯỚC KHI viết dòng code đầu tiên

Dự án này đã có 7 file rule chi tiết (đếm thật: `ls .agents/rules/`). Vấn đề không phải thiếu rule — mà là
một agent mới **không biết có những file đó, đọc theo thứ tự nào, và quy
trình thật sự chạy ra sao**. File này là bản đồ đó. Nó không lặp lại nội
dung rule; nó nói *khi nào* đọc rule nào, và mô tả những phần quy trình
chưa được viết ở đâu cả (thao tác 2 repo, lệnh chạy test thật trên Linux,
bookkeeping `ROADMAP.md`).

---

## 1. Bản đồ tài liệu — đọc theo thứ tự này

| Thứ tự | File | Khi nào |
| :--- | :--- | :--- |
| 1 | `.agents/ONBOARDING.md` (file này) | Luôn luôn, đầu tiên |
| 2 | `.agents/AGENTS.md` | Chỉ để điều hướng — nội dung thật nằm ở `rules/code-rule.md` (sửa 21/08: file này trước là bản sao trôi của `code-rule.md`, đã rút gọn) |
| 3 | `.agents/rules/code-rule.md` | Mọi thay đổi code Python |
| 4 | `.agents/rules/ci-rule.md` | Trước khi tuyên bố "xong" bất cứ thứ gì — định nghĩa 4 tầng test |
| 5 | `.agents/rules/commit-rule.md` | Trước mọi commit |
| 6 | `.agents/rules/bug-fix-rule.md` | **Bắt buộc** khi user báo bug |
| 7 | `.agents/rules/logging-rule.md` | Khi thêm/sửa log, và trong mọi bug fix |
| 8 | `.agents/rules/qml-rule.md` | Khi đụng file `.qml` |
| 9 | `.agents/Handover.md` | Khi cần bối cảnh lịch sử của một mảng cụ thể |
| — | `Tasks/ROADMAP.md` | Khi cần biết hệ thống đang ở đâu, task nào tồn tại |
| — | `Tasks/bug_report/README.md` | Bug Board — hệ thống đang gánh lỗi gì (mở/đã sửa) |
| — | `Tasks/epics/README.md` | Danh sách Epic đang có (mỗi Epic có thư mục + README riêng, xem §3) |
| — | **§12 của file này** | **Bắt tay vào việc đang dở** — epic nào đang chạy, task con tiếp theo, cơ chế mới ở Engine phải dùng |

`.agents/rules/install-rule.md` là chuyên đề riêng (cài đặt), đọc khi task
chạm đúng phạm vi đó.

> **Sửa 2026-08-25:** dòng này trước đây còn nhắc
> `.agents/rules/sentinel-rule.md` — **file đó không tồn tại** (và cũng không
> có trong lịch sử `git log`). Quy tắc bảo mật thật sống ở
> `.jules/sentinel.prompt.md` + `Tasks/epics/EPIC-004_static_security_and_quality_analysis/`,
> không phải ở `rules/`.

---

## 2. HAI repo độc lập, không phải submodule — đổi từ 21/08

```
Sagittarius_Engine/                  ← repo framework (sagittarius_engine/), remote riêng
└── Sagittarius_Elite_Warrior/       ← repo app bot Binance, nhánh `master-warrior`, remote riêng
```

**Đổi 21/08 (commit `a1efcd6`, quyết định của user, đọc nguyên văn message
commit đó nếu cần bối cảnh đầy đủ):** trước đây `Sagittarius_Elite_Warrior/`
là **git submodule** của `Sagittarius_Engine` — superproject giữ 1 con trỏ
(gitlink) tới đúng commit của submodule, và mọi lần đổi submodule phải
"bump" con trỏ đó ở superproject rồi commit riêng. **Không còn đúng nữa** —
`a1efcd6` đã xoá hẳn khai báo submodule (`.gitmodules` không còn tồn tại,
`git ls-files -s Sagittarius_Elite_Warrior` từ superproject trả về rỗng).
Hai thư mục giờ chỉ là 2 **repo Git hoàn toàn độc lập**, tình cờ nằm lồng
nhau trên đĩa của máy phát triển này — không có con trỏ nào cần đồng bộ.

**Quy trình commit bây giờ, đơn giản hơn hẳn trước:**

- Việc trong `Sagittarius_Elite_Warrior/` (gần như mọi task nghiệp vụ): vào
  đúng thư mục đó, `git commit`/`git push` — **chỉ 1 repo, không có bước
  "bump" nào ở superproject nữa.**
- Việc trong `sagittarius_engine/` (hiếm — chỉ khi thật sự thiếu cơ chế
  nền): commit/push riêng trong `Sagittarius_Engine`, **hoàn toàn không
  liên quan tới `Sagittarius_Elite_Warrior/`** — không cần bump gì cả vì
  không còn gì để bump.

Nếu thấy tài liệu hoặc thói quen cũ nhắc "bump submodule pointer" /
`chore(submodule): bump to ...` — đó là quy trình **đã hết hiệu lực**, đừng
làm theo mà không kiểm tra lại `git ls-files -s Sagittarius_Elite_Warrior`
từ superproject trước (rỗng = xác nhận đã detach, đừng bump gì cả).

**Không bao giờ `git push` nếu user không yêu cầu rõ ràng.** Commit là
mặc định-hỏi (xem §7); push là mặc định-cấm.

---

## 3. Vòng đời một TASK (tính năng mới)

1. **Task file.** Mọi task đều có file trong `Tasks/backlog/` theo mẫu
   `BOT-XXX_short_description.md` (số kế tiếp số lớn nhất đang tồn tại).
   Nếu user yêu cầu một tính năng chưa có task → tạo file task trước, rồi
   mới code. Epic lớn thì tách task con `BOT-XXXA`, `BOT-XXXB`… và epic
   phải có bảng liệt kê task con.
2. **Nội dung task file** viết bằng tiếng Việt, tối thiểu: Bối cảnh & vấn
   đề thật (không phải mô tả chung chung), Thiết kế + **lý do** cho các
   quyết định không hiển nhiên, Thay đổi theo từng file, Kiểm thử.
3. **Code + test.** Xem §5 để biết tầng test nào là đúng.
4. **Hoàn thành:** `git mv Tasks/backlog/BOT-XXX_*.md Tasks/completed/`,
   đổi trạng thái trong file thành `✅ Hoàn thành (YYYY-MM-DD)`, và thêm
   mục "Ghi chú Triển khai" ghi lại **bug thật đã phát hiện trong lúc
   làm**, quyết định thiết kế, số test. Phần này là giá trị lớn nhất của
   task file đối với người đọc sau — đừng viết cho có.
5. **Bookkeeping `ROADMAP.md`:** xem §6.

Epic **không** chuyển sang `completed/` cho đến khi *tất cả* task con xong;
trong lúc đó cập nhật trạng thái tại chỗ (`1/3 xong`).

---

## 4. Vòng đời một BUG

`.agents/rules/bug-fix-rule.md` là nguồn chuẩn — đọc nguyên văn. Ba điểm
bị vi phạm nhiều nhất:

- **Viết regression test TRƯỚC khi sửa, và chạy nó để xác nhận nó FAIL
  đúng lý do.** Test viết sau khi sửa không chứng minh được gì. Test fail
  vì lý do khác (import sai, fixture thiếu) cũng không chứng minh được gì.
- **Chọn đúng tầng test.** Nếu chỗ crash nằm trong method mà test double
  của bạn thay thế, test đó *không thể* tái hiện bug — `Mock` không chạy
  thân hàm thật. `BUG-013` đã "tái hiện" nhầm kiểu này hai lần liên tiếp
  với `Mock(spec=...)`, pass ngay cả khi chưa sửa gì.
- **Bug report bắt buộc:** `Tasks/bug_report/incomplete/BUG-XXX_mô_tả.md`
  (sửa xong thì `git mv` sang `completed/`), có
  Symptom (bằng chứng thật: traceback/log/ảnh, không diễn giải lại), Root
  cause (cơ chế thật kèm file:line), Fix, Regression test. Lập xong thì
  **thêm dòng vào [Bug Board](../Tasks/bug_report/README.md)** — đó là chỗ
  duy nhất thấy được bug nào đang mở; `ROADMAP.md` chỉ hiện bug đã sửa.

Nếu user dán log/ảnh vào chat, **đọc chúng bằng công cụ thật** (Read ảnh,
đọc file log) trước khi đưa ra giả thuyết. Một chi tiết trong ảnh thường
chỉ thẳng vào nguyên nhân: ở `BUG-018`, việc ô "Database Size" đúng trong
khi ô "Stored Records" sai đã khoanh vùng ngay lỗi nằm ở hàm cộng số liệu
từ bảng chứ không phải ở tầng đọc đĩa.

---

## 5. Chạy verification THẬT

`.agents/rules/ci-rule.md` quy định `scripts/ci-local.ps1 -Full` là cổng
bắt buộc. **Sửa lại (2026-08-21, phát hiện khi làm `EPIC-002B`):** trước
đây mục này ghi "PowerShell không chạy được trên máy Linux hiện tại" —
**sai**, `pwsh` có sẵn qua snap (`which pwsh` → `/snap/powershell/.../pwsh`).
`ci-local.ps1` chạy được thật, đã tự verify bằng cách chạy thẳng:

```bash
pwsh -NoProfile -Command "./scripts/ci-local.ps1 -Full"
# chạy từ thư mục Sagittarius_Elite_Warrior/ (đây là $botRoot, khác mọi lệnh
# bash bên dưới vốn chạy từ superproject)
```

Ưu tiên dùng `pwsh` khi cần đúng cổng CI thật (nó nối dây đúng `mypy`,
coverage, sanity tuần tự — dùng bash tự ráp lại từng phần dễ thiếu bước).
Bộ lệnh bash bên dưới vẫn hữu ích cho kiểm tra nhanh, có chủ đích, không cần
chờ toàn bộ orchestration của script — chạy **từ thư mục superproject**:

```bash
# Unit (~3 phút, hiện 1641 test tại 2026-08-21 — con số này TRÔI liên tục,
# đừng tin tuyệt đối, chỉ để biết cỡ)
PYTHONPATH=. QT_QPA_PLATFORM=offscreen \
  Sagittarius_Elite_Warrior/.venv/bin/python -m pytest Sagittarius_Elite_Warrior/tests/unit/ -q

# Sanity (~35 giây, hiện 41 test)
PYTHONPATH=. QT_QPA_PLATFORM=offscreen \
  Sagittarius_Elite_Warrior/.venv/bin/python -m pytest Sagittarius_Elite_Warrior/tests/sanity/ -q

# Lint (read-only, không bao giờ để CI tự --fix)
Sagittarius_Elite_Warrior/.venv/bin/python -m ruff check  <file...>
Sagittarius_Elite_Warrior/.venv/bin/python -m ruff format --check <file...>

# Mypy (EPIC-002, gate thật — src VÀ scripts PHẢI chung 1 lệnh, xem lý do
# ở ci-rule.md §1 và Tasks/reports/EPIC-002A_mypy_baseline_audit.md §3)
PYTHONPATH=. \
  Sagittarius_Elite_Warrior/.venv/bin/mypy --config-file Sagittarius_Elite_Warrior/pyproject.toml \
  --namespace-packages --explicit-package-bases \
  Sagittarius_Elite_Warrior/src Sagittarius_Elite_Warrior/scripts
```

**Bẫy đọc kết quả — quan trọng:** ở chế độ `offscreen`, QML xả rất nhiều
`TypeError: Cannot read property '...' of null` ra stderr. Chúng **vô
hại** và xuất hiện *sau* dòng tổng kết của pytest, nên `tail` sẽ cho bạn
xem nhầm đống nhiễu đó và tưởng test hỏng. Luôn ghi ra file rồi grep:

```bash
... -q > /tmp/run.log 2>&1; grep -E "^[0-9]+ (passed|failed)|failed," /tmp/run.log | tail -3
```

**Luật này áp dụng cho MỌI lệnh verification, không chỉ pytest — kể cả
chính `ci-local.ps1 -Full`.** Lý do còn nặng hơn "nhiễu": nếu chỉ xem qua
`| tail -N` hay terminal cắt xén, có thể **mất hẳn** đúng dòng lỗi thật,
không phải chỉ bị làm phiền bởi nhiễu. Bằng chứng thật (2026-08-21,
`BUG-029`/`BUG-030`): agent trước đó chỉ chạy `pytest` thô, không bao giờ
chạy `ci-local.ps1 -Full` thật; khi cuối cùng chạy và **redirect toàn bộ ra
file** (`> file 2>&1`, không phải pipe/tail), phát hiện được 2 bug thật
cùng lúc mà cách làm cũ không bao giờ bắt được: (1) `build-native-chart.ps1`
(script này đã bị xoá 2026-08-24 cùng native chart — giữ lại ở đây làm bằng
chứng lịch sử) lỗi `Join-Path` chỉ chạy trên PowerShell 7+, phá cổng CI trên PowerShell
5.1 mà `ci-local.ps1` tự khai hỗ trợ, và (2) `-n 6` (song song) làm 1
worker chết giữa chừng sau `ResourceWarning: unclosed database`, tái hiện
2/2 lần — không phải flaky. Cả hai chỉ lộ ra được vì có file log đầy đủ để
`grep`/đọc lại sau, không phải vì nhìn màn hình lúc chạy. Luôn dùng
`> logfile 2>&1` (không phải `| tail`) cho bất kỳ lệnh verification nào
đủ dài để cần đọc lại — pytest, `ci-local.ps1`, hay build script.

Về lint: repo luôn có sẵn vài lỗi `I001` (import chưa sort) từ phiên khác
không do bạn gây ra (14 lỗi trên `src tests` tại 21/08, con số này cũng
trôi — kiểm tra thật bằng `ruff check src tests` thay vì tin số ở đây). Quy
tắc: chỉ sửa lint trong **file bạn đang sửa cho task hiện tại**, không đi
dọn dẹp file vô can — làm vậy diff bug-fix sẽ lẫn thay đổi không liên quan
và không ai review nổi. Muốn dọn toàn repo thì làm một commit `style:`
riêng, sau khi hỏi user.

---

## 6. Bookkeeping `Tasks/ROADMAP.md` — phần hay bị làm ẩu nhất

Mỗi task/bug hoàn thành phải cập nhật **cả ba** chỗ:

1. **Thêm 1 dòng vào ĐẦU mục `🟢 Completed`** (thứ tự mới-nhất-trước).
   Dòng đó phải tóm tắt được root cause / quyết định thiết kế, không phải
   chỉ nhắc lại tên task.
2. **Tính lại bảng số lượng bằng lệnh thật, không đếm tay:**
   ```bash
   for d in completed in_progress backlog cancelled; do
     printf "%s %s\n" "$d" "$(ls Tasks/$d/*.md 2>/dev/null | wc -l)"
   done
   ```
   Rồi cập nhật cả 4 dòng + tổng + tỷ lệ %. (Bug report trong
   `Tasks/bug_report/` **không** tính vào các con số này.)
3. **Cập nhật dòng epic tại chỗ** trong bảng nhóm tương ứng, và ghi chú
   "Cập nhật <ngày>" ở đầu file.

Sau khi thêm task file mới có link chéo, **kiểm tra link không gãy**:

```bash
cd Tasks/backlog && grep -oh "](\.\./\?[^)]*\.md)" BOT-XXX*.md | tr -d '](' | sed 's/)$//' \
  | sort -u | while read -r l; do [ -f "$l" ] || echo "BROKEN: $l"; done
```

**Epic lớn (nhiều task con, nhiều lần cập nhật trạng thái) dùng
`Tasks/epics/EPIC-XXX_slug/` riêng, không phải 1 dòng trong `ROADMAP.md`**
— quy ước mới từ 20/08 (xem `Tasks/epics/README.md` để biết chi tiết đầy
đủ, đã có 3 epic theo kiểu này: `EPIC-001`/`002`/`003`). Cấu trúc:
`README.md` (tổng quan + bảng task con) + `incomplete/`/`completed/` (y hệt
`Tasks/backlog/`/`completed/` nhưng riêng cho epic đó, mã task con
`EPIC-XXXA`, `EPIC-XXXB`…). `ROADMAP.md` khi đó **chỉ giữ 1 dòng liên kết**
tới `README.md` của epic — không chép nội dung. Nhớ cập nhật cả 3 nơi khi
xong 1 task con: `README.md` của epic, `Tasks/epics/README.md` (đếm lại
X/N), và dòng 1-liên-kết ở `ROADMAP.md`. (Epic kiểu cũ, phẳng trong
`Tasks/backlog/`/`completed/` — ví dụ `BOT-109`, `BOT-112`, `BOT-115` — vẫn
giữ nguyên định dạng cũ, không bị dời ngược sang `epics/`.)

Đề xuất kiến trúc chưa thành task (ai đó viết ra một hướng đi, chưa ai
duyệt) sống ở `Tasks/proposal/PRO-XXX.md` — khác `Tasks/backlog/` (đã là
task được chấp nhận) và khác `Tasks/epics/` (đã tách task con cụ thể). Khi
1 đề xuất được duyệt, chuyển hoá nó thành `BOT-XXX`/`EPIC-XXX` thật — bản
thân `PRO-XXX.md` không tự thực thi được.

---

## 7. Quyền hạn — cái gì được tự làm, cái gì phải hỏi

| Hành động | Quy tắc |
| :--- | :--- |
| Đọc, phân tích, chạy test | Tự do |
| Sửa code trong phạm vi user yêu cầu | Tự do |
| `git commit` | **Hỏi trước.** Không bao giờ commit tự phát |
| `git push` | **Chỉ khi user yêu cầu rõ ràng**, và mỗi repo (app / engine) là 1 lần xác nhận riêng — 2 repo độc lập từ §2, không còn liên đới nhau |
| Sửa file ngoài phạm vi task | Không, trừ khi user yêu cầu |
| Xoá/ghi đè file của user | Đọc nội dung trước, hỏi trước |

**Phản biện là bắt buộc, không phải tuỳ chọn** (`code-rule.md` §5): nếu yêu cầu
của user tạo ra mâu thuẫn kiến trúc, vi phạm ranh giới tầng, hoặc phá
nguyên tắc đã chốt — phải nói ra và đề xuất phương án sạch, không im lặng
làm theo. Nhưng nếu user đã nghe và vẫn quyết định giữ nguyên yêu cầu thì
làm đầy đủ theo họ.

---

## 8. Mười một cái bẫy khiến agent khác tạo ra code lỗi

Tất cả đều là chuyện đã xảy ra thật trong repo này, không phải giả định.

1. **Tự tính giá trị kỳ vọng của test bằng đầu thay vì chạy code thật.**
   Ở `BOT-106A`, một chuỗi return hằng số về mặt toán học vẫn cho
   `statistics.stdev()` ra ~1e-16 chứ không phải `0.0`, khiến Sharpe bung
   ra ~3.2×10¹⁵. Chạy code thật rồi mới chốt số kỳ vọng.
2. **So sánh float bằng `== 0` hoặc `if value:`.** Dùng
   `math.isclose(x, 0.0, abs_tol=1e-9)`. Xem bẫy 1 để biết hậu quả.
3. **Assert số lượng bằng hằng số cứng** (`len(cards) == 9`). Task sau
   thêm 1 card là test vỡ dù không có gì sai. Assert theo *thứ có ý
   nghĩa* (có mặt/không có mặt, thứ tự tương đối), không theo số đếm.
4. **Assert bằng full-dict equality** trên output của `to_dict()`. Một
   phiên khác thêm field hợp lệ là test vỡ. Assert subset đúng field mà
   test thật sự quan tâm.
5. **Thêm field vào dataclass đã đóng băng mà không đặt default.** `Trade`,
   `BacktestMetrics`, `BacktestRunConfig` có hàng trăm call site dựng trực
   tiếp trong test. Field mới **luôn** phải có giá trị mặc định.
6. **Đổi công thức dùng chung mà không rẽ nhánh bảo toàn hành vi cũ.**
   `BOT-114` thêm đòn bẩy vào `PaperExchange`: công thức PnL kiểu "spot"
   của LONG sai hoàn toàn khi `margin != notional`. Cách xử lý đúng là giữ
   **nguyên si** nhánh cũ cho `leverage == 1.0` và chỉ dùng công thức mới
   khi thật sự có đòn bẩy — bằng chứng là 47 test cũ pass không sửa dòng nào.
7. **Gọi `fsm.transition_to(X)` khi đang ở đúng `X`.** Ma trận FSM không có
   cạnh tự thân, sẽ raise; `@safe_ui_action` nuốt lỗi nên app không chết
   nhưng slot **chết giữa chừng**, mọi dòng phía sau không chạy. Đây chính
   là `BUG-018`. Worker nền chưa từng khoá UI thì **không được** phát tín
   hiệu unlock.
8. **Quên rằng `@safe_ui_action` nuốt exception.** Một slot có thể chết im
   lặng ở giữa. Đừng đặt việc quan trọng (refresh dữ liệu) *sau* một lời
   gọi có thể ném lỗi.
9. **Thêm `logger.info()` vào một vòng lặp nóng.** Log **không** miễn phí ở
   app này: `SignalLogHandler` gắn vào logger **gốc** `"App"` ở mức INFO
   (`data_management_presenter.py`), nên **mọi** `App.*` của **mọi**
   subsystem đều bị đẩy qua queued cross-thread signal sang UI thread, rồi
   mỗi dòng chạy trọn một chu kỳ `beginInsertRows`/`endInsertRows`/
   `countChanged` trong `LogListModel`. `BUG-042`: `PaperExchange` log INFO
   mỗi lệnh khớp → 838 trades sinh **5.028 dòng trong 2 giây** → UI đơ cứng,
   đơ tuyến tính theo số trade. Việc log nằm ở màn hình nào **không** quan
   trọng — handler bắt ở logger gốc. Trong vòng lặp chạy nhiều lần (mỗi
   trade, mỗi nến, mỗi tick) thì dùng `logger.debug()`, hoặc gộp/throttle
   trước khi log — xem `ProgressThrottle` (`BUG-033`) làm mẫu cho đúng đường
   signal.
10. **Sửa file `.qml` mà quên logic phải nằm ở Python.** QML chỉ khai báo và
    binding; state machine, validate, tính toán đều thuộc Presenter/ViewModel.
    Và `.qml` > 300 dòng thì tách component.
11. **Thêm `@abstractmethod` mới vào một Port rồi chỉ cập nhật implementer
    "chính".** `ruff` không bắt được thiếu sót này — kiểm tra 1 class có
    implement đủ interface hay không là việc của type checker, ngoài phạm
    vi kiến trúc của linter. `BUG-026`: một script probe implement
    `IExchangeClient` bị bỏ quên khi interface đó có thêm method, crash
    ngay lúc khởi tạo (`TypeError: Can't instantiate abstract class`). Khi
    đổi 1 Port, grep implementer ở **cả `src/`, `scripts/`, VÀ `tests/`**
    — không chỉ `src/`/`tests/` (đây chính là lỗi lúc sửa `BUG-025`: phạm
    vi grep khi đó bỏ sót `scripts/`, để lọt 1 defect sống y hệt, mãi sau
    mới lộ ra qua `EPIC-002A`'s audit). Từ `EPIC-002B`: `mypy` (gate
    `src`+`scripts` chung 1 lệnh, xem §5) là lưới an toàn thứ hai — nhưng
    đừng chỉ dựa vào tool, grep vẫn phải làm khi đổi interface.

---

## 9. Hai bộ `.agents/` — đừng đọc nhầm repo

`Sagittarius_Engine` (framework) và `Sagittarius_Elite_Warrior` (app bot,
thư mục này) đều có `.agents/` riêng, **là 2 repo Git độc lập** (không còn
quan hệ submodule — xem §2), chỉ tình cờ nằm lồng nhau trên đĩa. Nội dung
khác nhau và phục vụ hai dự án khác nhau — đây vẫn là chỗ nhầm lẫn nguy
hiểm nhất với agent mới, càng dễ nhầm hơn từ khi hết còn dấu hiệu "submodule"
rõ ràng để phân biệt:

| | `../.agents/` (`Sagittarius_Engine`) | `.agents/` (`Sagittarius_Elite_Warrior` — thư mục này) |
| :--- | :--- | :--- |
| Phục vụ | framework `sagittarius_engine/` | app bot |
| Bảng task | `../Tasks/README.md` (Kanban, mã `TASK-XXX`) | `Tasks/ROADMAP.md` (mã `BOT-XXX`/`BUG-XXX`/`EPIC-XXX`) |
| Entry point | `PLAYBOOK.md` + `manifest.yml` | `ONBOARDING.md` (file này) + `AGENTS.md` |
| Remote Git | riêng, repo `Sagittarius_Engine` | riêng, repo `Sagittarius_Elite_Warrior` |

Khi làm việc trong app, **luôn ưu tiên rule của repo này**. Rule của
`Sagittarius_Engine` chỉ áp dụng khi bạn thật sự sửa code framework — và khi
đó là 1 commit/push hoàn toàn tách biệt (§2), không có bước đồng bộ nào giữa
2 repo. Hai bảng task không liên quan gì nhau — đừng ghi task app vào
`Tasks/README.md` của engine và ngược lại.

**Đã dọn 2026-08-20:** `../.agents/PLAYBOOK.md` trước đó mô tả cây thư mục
`.ai/` (không tồn tại) và định tuyến sang 8 skill file không có thật;
`../.agents/manifest.yml` khai báo 9 mục không tồn tại đồng thời bỏ sót 5
file có thật. Cả hai đã được sửa — mọi mục trong manifest giờ trỏ đúng file
thật.

**Đã dọn 2026-08-21 (rà soát toàn bộ file này theo yêu cầu user):** toàn bộ
§2 và §9 vẫn mô tả quan hệ **submodule** giữa 2 repo — đã hết đúng từ
`a1efcd6` cùng ngày (xem §2), viết lại hoàn toàn thay vì chỉ sửa câu chữ.
Số "10 file rule" ở đầu file sai (thực tế 9, đếm bằng `ls .agents/rules/`).
Số liệu test/lint ở §5 ("1564 test tại 2026-08-20", "38 lỗi I001") đã trôi
so với thực tế (1641 test, 14 lỗi) — đổi cách viết để không tự tin tuyệt
đối vào con số cố định trong tài liệu nữa, luôn trỏ về lệnh kiểm tra thật.
§1 và §6 thiếu hẳn quy ước `Tasks/epics/` (có từ 20/08, đã có 3 epic) và
`Tasks/proposal/` — bổ sung. **Cùng ngày, phát hiện thêm (user chỉ ra):**
`AGENTS.md` gần như toàn bộ là bản sao trôi độc lập của `code-rule.md` —
xác nhận bằng cách grep 7 cụm từ đặc trưng, cả 7 tồn tại y hệt ở cả hai
file — cộng 1 lỗi thật nguy hiểm: mục Git Commits ghi cứng
`Co-Authored-By: Antigravity <noreply@google.com>`, vi phạm thẳng
`commit-rule.md` tự nói rõ trailer phải khớp đúng AI thực sự tạo commit.
Đã rút gọn `AGENTS.md` thành file điều hướng thuần tuý — xem chính file đó
để biết chi tiết. Cập nhật lại dòng #2 và trích dẫn "Phản biện là bắt buộc"
ở §7 (trước trỏ vào `AGENTS.md`, giờ trỏ đúng `code-rule.md` §5). Nếu phát
hiện thêm chỗ lỗi thời, sửa và ghi lại ở đây thay vì im lặng đi đường vòng.

**Đã dọn 2026-08-25 (rà soát `.agents/` đối chiếu thực tế trên đĩa):** phát
hiện 8 chỗ **sai thật**, không phải chỉ lỗi thời câu chữ — tất cả đã sửa:

1. `AGENTS.md` và §1 của file này cùng trỏ tới `.agents/rules/sentinel-rule.md`
   — **file chưa bao giờ tồn tại**. Đã xoá cả 2 link gãy; nội dung bảo mật
   thật ở `.jules/sentinel.prompt.md` + `Tasks/epics/EPIC-004_.../`.
2. §1 ghi "8 file rule", thực tế **7** (`ls .agents/rules/`). Con số này đã
   sai 3 lần liên tiếp (10 → 9 → 8 → thực tế 7) — đừng chép lại, hãy đếm.
3. `Handover.md` mô tả 2 repo là **superproject/submodule** — sai từ
   2026-08-21 (`a1efcd6`), đúng cái mà §2 file này đã sửa. Đã sửa 4 chỗ.
4. `Handover.md` trỏ tới `.agents/rules/native-chart-rule.md` và
   `Docs/NATIVE_CHART_BUILD_AND_DEPLOY.md` — **cả hai đều không tồn tại**.
   Đã xoá mục đó.
5. `Handover.md` nói `.github/workflows/ci.yml` "chạy đúng lệnh này" và có
   một "discrepancy chưa giải quyết" với `ci-local.ps1` — **repo này không
   có thư mục `.github/` nào cả**, đúng như `ci-rule.md` §7 đã ghi
   (CI local-only). Không có discrepancy nào để đuổi theo.
6. `Handover.md` trỏ tới journal `.jules/bolt.md` / `palette.md` /
   `sentinel.md` — **không tồn tại**, `.jules/` chỉ có 7 file `*.prompt.md`.
7. `BUG-015`/`BUG-016` bị mô tả là "Windows-only, còn mở, chặn `BOT-098F*`"
   — **cả hai đã đóng** (`bug_report/completed/`): `BUG-015` hoá ra là lỗi
   probe script chứ không phải renderer; `BUG-016` đóng dạng *moot* vì
   native chart đã bị xoá hẳn (`36f3a9f`, 2026-08-24). `BUG-017` cũng bị
   ghi "chưa sửa" trong khi đã sửa.
8. 3 link `.md` gãy trong `Handover.md` (`BOT-101`, `BUG-013`, `BUG-017`
   đều đã chuyển sang `completed/`). Đã trỏ lại đúng chỗ.

`Handover.md` giờ có khối `[!IMPORTANT]` ở đầu nói thẳng: các mục theo phiên
bên dưới là **bản ghi lịch sử**, mục mới nhất là 2026-08-20, và trạng thái
hiện tại nằm ở §12 file này. Không xoá phần lịch sử — chỉ đánh dấu chỗ đã
hết đúng.

Lưu ý còn tồn tại: **mọi rule file của cả hai repo chỉ ghi lệnh
PowerShell**. Trên Linux dùng lệnh ở §5.

---

## 10. Ngôn ngữ

- **Trao đổi với user, task file, bug report, ROADMAP:** tiếng Việt.
- **Code, tên biến, docstring, comment, commit subject:** tiếng Anh.
- **Chuỗi hiển thị trên UI:** tiếng Việt (đúng thuật ngữ domain đã chốt,
  ví dụ "Thông số Chiến lược" khác với cài đặt Bot chung).

---

## 11. Báo cáo với user — mức project lead, không phải mức implementation

**Thêm 2026-08-21 (yêu cầu trực tiếp của user).**

- Khi báo cáo tiến độ, trạng thái task/epic, tóm tắt điều tra, hay kết quả
  test cho user trong hội thoại, mặc định viết như đang báo cáo cho một
  **project lead**: kết luận, trạng thái hiện tại, quyết định cần user ra, và
  rủi ro/blocker. **Không** đi vào chi tiết implementation (tên hàm cụ thể,
  dòng code, so sánh kiểu dữ liệu nội bộ, tên biến C++...) trừ khi user hỏi
  thẳng vào đó, hoặc chi tiết đó **quyết định trực tiếp** hành động tiếp theo.
  Ví dụ: báo "F4 đang bị chặn bởi BUG-015 (Windows: geometry bị rebuild khi
  pointer move), giả thuyết root cause đang điều tra" là đủ cho báo cáo tình
  trạng; không cần liệt kê `QSizeF`/tên file `.cpp` trong câu trả lời đó trừ
  khi user muốn đi sâu sửa bug.
- **Không áp dụng cho tài liệu lưu trữ lâu dài** — task file, bug report
  (`Tasks/bug_report/`), báo cáo (`Tasks/reports/`) vẫn phải đầy đủ root
  cause/file:line/bằng chứng theo đúng `bug-fix-rule.md` và §3/§4 ở trên; quy
  tắc "mức project lead" ở đây chỉ áp dụng cho câu trả lời trong hội thoại,
  không áp dụng cho nội dung ghi vào file.

---

## 12. Bắt tay vào việc đang dở — đọc mục này trước khi gõ dòng đầu tiên

**Thêm 2026-08-25.** Mục này tồn tại để một agent mới đọc xong là làm được ngay, không phải
dò lại từ đầu.

### 12.1 Ba lệnh đầu tiên, lần nào cũng vậy

```bash
git -C . status
git -C ../Sagittarius_Engine status
cat Tasks/epics/README.md
```

**Việc ở dự án này thường được để lại chưa commit giữa các phiên** — theo đúng §7, agent không
tự commit. Nên `git status` không phải thủ tục: bảng task trông như chưa ai đụng cộng với cây
làm việc bẩn nghĩa là việc **đã làm rồi**, chỉ chưa được ghi lại. Đọc diff trước khi kết luận
một task còn nguyên.

**Đừng tin con số trạng thái trong chính mục này** — nó trôi nhanh hơn mọi thứ khác trong file.
Bản trước ghi cứng "tính đến 2026-08-25 cả hai repo đều đang có lượng lớn việc chưa commit";
chỉ vài giờ sau **cả hai repo đều đã sạch hoàn toàn**, khiến câu đó thành sai và gây hiểu nhầm
đúng chiều nguy hiểm nhất (tưởng còn việc dang dở trong cây làm việc). Chạy 3 lệnh trên rồi tin
kết quả, không tin đoạn văn này.

### 12.2 Hai epic đang chạy, đều điều phối từ repo này

| Epic | Nội dung | Trạng thái (đọc `README.md` của epic để biết chính xác) |
| :--- | :--- | :--- |
| [`EPIC-007`](../Tasks/epics/EPIC-007_chuan_hoa_card_dung_chung/README.md) | Chuẩn hoá card dùng chung, đưa hình dạng lên Engine | Chưa bắt đầu (0/7). `007A`–`007C` làm ở repo **Engine** trước |
| [`EPIC-008`](../Tasks/epics/EPIC-008_chuan_hoa_luong_event/README.md) | Chuẩn hoá luồng sự kiện | Đang làm (**4/8** — `008A`–`008D` xong ở Engine, tiếp theo `008E`). `008A`–`008E` ở **Engine**, `008F`–`008H` ở repo này |

**`EPIC-006` chưa đóng** dù đã merge vào `master-warrior`: còn `EPIC-006F` (dỡ kit QML bên
Engine) — và task đó **chưa có file**, phải tạo trước khi làm. Kèm theo là 22 file `.qml` chết
còn sót trong `src/` của repo này. Chi tiết ở đầu
[`EPIC-006/README.md`](../Tasks/epics/EPIC-006_drop_qml/README.md).
`EPIC-005` **đã bị `EPIC-006` thay thế** — đừng mở lại nó.

**Bắt buộc: đọc `README.md` của epic + file `DECISION_*.md` (ADR) của nó trước khi làm bất kỳ
task con nào.** ADR ghi lại những quyết định đã tranh luận xong với user — trong đó có vài
quyết định **đảo ngược** phương án trước đó. Tự suy luận lại sẽ tốn một phiên và thường ra kết
quả khác.

`EPIC-007` có thêm 4 sơ đồ PlantUML ở `Tasks/epics/EPIC-007_.../design/` (2 hiện trạng, 2 đề
xuất) — xem trước khi động vào widget.

### 12.3 Task con tiếp theo và thứ tự

Mỗi epic `README.md` có bảng "Thứ tự thực hiện" với cột trạng thái và cột **Repo**. Task ghi
`Engine` phải commit ở repo Engine, không phải repo này (§2, §9). Đừng làm nhảy cóc: bảng đó
xếp theo rủi ro tăng dần và có ghi rõ cái nào chặn cái nào.

Khi làm xong một task con: `git mv incomplete/EPIC-XXXY_*.md completed/`, ghi phần "Xong
<ngày>" vào cuối file đó (root cause, quyết định, bằng chứng verify), cập nhật dòng tương ứng
trong bảng ở `README.md` của epic và số "x/y task con xong" ở đầu file. Đúng quy ước
`Tasks/epics/README.md`.

### 12.4 Cơ chế mới ở Engine — dùng, đừng viết lại

`EPIC-008` đã dựng sẵn các cơ chế sau ở repo Engine (verify 2026-08-25: cả 5 đều tồn tại thật,
Engine gate xanh). Viết cái khác thay thế là tái tạo lại đúng lỗi mà chúng vừa đóng. Chi tiết đầy đủ ở
`Sagittarius_Engine/.agents/context/events.md`:

| Cần gì | Dùng cái gì |
| :--- | :--- |
| Định nghĩa event | kế thừa `BaseEvent` — được `event_id`/`occurred_on`/`event_name` + tự vào catalog |
| Presenter đăng ký nghe event | `self.subscribe(...)`, **không** `self.event_bus.on(...)` — tự nhảy về main thread và tự gỡ khi dispose |
| Dọn dẹp khi tắt presenter | override `shutdown()`, **không bao giờ** override `dispose()` |
| Báo lỗi handler | `report_handler_failure` |
| Logger khi không được inject | `resolve_bus_logger` — **không** `NullLogger` |

### 12.5 Bốn nguyên tắc user đã chốt, áp cho mọi task

1. **Sửa cơ chế, không hot fix.** Cùng một lỗi lặp ở nhiều nơi thì sửa mỗi chỗ được báo là
   không chấp nhận được. Sửa mà không giải thích được *vì sao* triệu chứng biến mất thì không
   tính là sửa (`bug-fix-rule.md`).
2. **Càng nhiều file càng tốt — một abstraction một file, và khác abstraction thì cũng không
   chung thư mục.** Tách là mặc định, **gộp mới là thứ phải có lý do**. Hai ràng buộc cứng:
   (a) hai thứ **khác abstraction level** không được nằm chung một file (Port vs
   implementation, base class vs subclass); (b) các file **khác abstraction level** không được
   nằm chung một `dir` — thư mục là một tầng, không phải cái sọt (`interfaces/` không chứa
   implementation, `widgets/` dùng chung không chứa widget riêng của 1 màn). Đối trọng duy
   nhất là Single-Scope Cohesion trong `code-rule.md`, và nó **chỉ** thắng khi các định nghĩa
   mô tả **cùng một vòng đời** (enum + ma trận của một FSM) — "cùng feature"/"cùng màn hình"
   **không** tính. Ngưỡng buộc tách: **>400 dòng/file** hoặc **>15 method công khai/lớp**.
   Phân xử nhanh: *đổi A có bắt buộc phải sửa B không?* Có → chung file; không → tách.
   Toàn văn ở [`rules/code-rule.md`](rules/code-rule.md) §7 "Abstraction-Level Separation".
3. **Trình design trước khi implement** với mọi việc tái cấu trúc: PlantUML class + component,
   as-is và to-be, chỉ rõ cái gì dùng chung / cái gì riêng từng màn — duyệt xong mới viết task
   file và code.
4. **Không commit, không push nếu user không yêu cầu** (§7).

### 12.6 Bẫy khi chạy gate ở repo Engine

`scripts/ci-local.ps1` bên Engine có thể báo đỏ những test **không liên quan** tới thay đổi của
bạn: `BUG-006` (hai test "no QML runtime warnings" phụ thuộc thứ tự collection — thêm một file
test mới cũng đổi được kết quả) và `tests/test_agents_docs_resolve.py` (không tìm thấy `grep`
trên `PATH` khi chạy qua PowerShell).

**Trước khi kết luận lỗi là do mình gây ra, A/B nó:** `git stash push -u` → chạy → `git stash
pop` → chạy. Mất hai phút, và đó là khác biệt giữa một regression thật với một giờ đuổi theo
môi trường.
