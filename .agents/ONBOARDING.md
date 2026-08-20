---
name: Onboarding
description: Entry point for any AI agent working on Sagittarius Elite Warrior — repo layout, task/bug workflow, real verification commands, bookkeeping, and the traps that repeatedly produce broken code.
trigger: always_on
---

# ONBOARDING — Đọc file này TRƯỚC KHI viết dòng code đầu tiên

Dự án này đã có 10 file rule chi tiết. Vấn đề không phải thiếu rule — mà là
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
| 2 | `.agents/AGENTS.md` | Luôn luôn — nguyên tắc kiến trúc/SOLID/QML/typing |
| 3 | `.agents/rules/code-rule.md` | Mọi thay đổi code Python |
| 4 | `.agents/rules/ci-rule.md` | Trước khi tuyên bố "xong" bất cứ thứ gì — định nghĩa 4 tầng test |
| 5 | `.agents/rules/commit-rule.md` | Trước mọi commit |
| 6 | `.agents/rules/bug-fix-rule.md` | **Bắt buộc** khi user báo bug |
| 7 | `.agents/rules/logging-rule.md` | Khi thêm/sửa log, và trong mọi bug fix |
| 8 | `.agents/rules/qml-rule.md` | Khi đụng file `.qml` |
| 9 | `.agents/rules/native-chart-rule.md` | Khi đụng chart/native renderer |
| 10 | `.agents/Handover.md` | Khi cần bối cảnh lịch sử của một mảng cụ thể |
| — | `Tasks/ROADMAP.md` | Khi cần biết hệ thống đang ở đâu, task nào tồn tại |
| — | `Tasks/bug_report/README.md` | Bug Board — hệ thống đang gánh lỗi gì (mở/đã sửa) |

`.agents/rules/sentinel-rule.md` và `install-rule.md` là chuyên đề riêng
(bảo mật / cài đặt), đọc khi task chạm đúng phạm vi đó.

---

## 2. Đây là HAI repo, không phải một

```
Sagittarius-Engine/                  ← superproject: framework (sagittarius_engine/)
└── Sagittarius_Elite_Warrior/       ← submodule, nhánh `master-warrior`: app bot Binance
```

Gần như mọi task nghiệp vụ nằm trong **submodule**. Framework
(`sagittarius_engine/`) chỉ sửa khi thật sự thiếu cơ chế nền — và khi đó
phải commit ở cả hai repo.

**Quy trình commit bắt buộc, đúng thứ tự:**

1. Commit trong submodule (`Sagittarius_Elite_Warrior/`) với message
   Conventional Commits đầy đủ, mô tả *tại sao*, không chỉ *cái gì*.
2. Quay ra superproject, `git add Sagittarius_Elite_Warrior` rồi commit
   `chore(submodule): bump to <mô tả ngắn>`.

Bỏ bước 2 = con trỏ submodule của superproject vẫn trỏ commit cũ, người
khác clone về sẽ không thấy thay đổi của bạn. Đây là lỗi im lặng, không
có thông báo nào cảnh báo.

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
- **Bug report bắt buộc:** `Tasks/bug_report/BUG-XXX_mô_tả.md`, có
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
bắt buộc. **Nhưng script đó là PowerShell** — trên máy Linux hiện tại nó
không chạy được, và mọi rule file đều chỉ ghi lệnh Windows. Lệnh tương
đương thật sự đang dùng, chạy **từ thư mục superproject**:

```bash
# Unit (~3 phút, hiện 1564 test tại 2026-08-20)
PYTHONPATH=. QT_QPA_PLATFORM=offscreen \
  Sagittarius_Elite_Warrior/.venv/bin/python -m pytest Sagittarius_Elite_Warrior/tests/unit/ -q

# Sanity (~35 giây, hiện 41 test)
PYTHONPATH=. QT_QPA_PLATFORM=offscreen \
  Sagittarius_Elite_Warrior/.venv/bin/python -m pytest Sagittarius_Elite_Warrior/tests/sanity/ -q

# Lint (read-only, không bao giờ để CI tự --fix)
Sagittarius_Elite_Warrior/.venv/bin/python -m ruff check  <file...>
Sagittarius_Elite_Warrior/.venv/bin/python -m ruff format --check <file...>
```

**Bẫy đọc kết quả — quan trọng:** ở chế độ `offscreen`, QML xả rất nhiều
`TypeError: Cannot read property '...' of null` ra stderr. Chúng **vô
hại** và xuất hiện *sau* dòng tổng kết của pytest, nên `tail` sẽ cho bạn
xem nhầm đống nhiễu đó và tưởng test hỏng. Luôn ghi ra file rồi grep:

```bash
... -q > /tmp/run.log 2>&1; grep -E "^[0-9]+ (passed|failed)|failed," /tmp/run.log | tail -3
```

Về lint: repo hiện có **38 lỗi `I001` (import chưa sort) tồn tại sẵn** trên
`src/`, không do bạn gây ra. Quy tắc: chỉ sửa lint trong **file bạn đang
sửa cho task hiện tại**, không đi dọn dẹp file vô can — làm vậy diff bug-fix
sẽ lẫn thay đổi không liên quan và không ai review nổi. Muốn dọn toàn repo
thì làm một commit `style:` riêng, sau khi hỏi user.

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

---

## 7. Quyền hạn — cái gì được tự làm, cái gì phải hỏi

| Hành động | Quy tắc |
| :--- | :--- |
| Đọc, phân tích, chạy test | Tự do |
| Sửa code trong phạm vi user yêu cầu | Tự do |
| `git commit` | **Hỏi trước.** Không bao giờ commit tự phát |
| `git push` | **Chỉ khi user yêu cầu rõ ràng**, và submodule/superproject là 2 lần xác nhận riêng |
| Sửa file ngoài phạm vi task | Không, trừ khi user yêu cầu |
| Xoá/ghi đè file của user | Đọc nội dung trước, hỏi trước |

**Phản biện là bắt buộc, không phải tuỳ chọn** (`AGENTS.md`): nếu yêu cầu
của user tạo ra mâu thuẫn kiến trúc, vi phạm ranh giới tầng, hoặc phá
nguyên tắc đã chốt — phải nói ra và đề xuất phương án sạch, không im lặng
làm theo. Nhưng nếu user đã nghe và vẫn quyết định giữ nguyên yêu cầu thì
làm đầy đủ theo họ.

---

## 8. Mười cái bẫy khiến agent khác tạo ra code lỗi

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
9. **Đưa tính năng mới vào chart mà quên đường native.**
   `NativeBacktestChartHostAdapter` ném `NativeUnsupportedFeatureError` cho
   mọi thứ ngoài phạm vi nó hỗ trợ, và `BackTestPresenter` phải bắt để
   rebuild host Python. Thêm lời gọi chart mới thì phải có test cho nhánh
   fallback đó. Không cần sửa C++ cho tính năng phía Python.
10. **Sửa file `.qml` mà quên logic phải nằm ở Python.** QML chỉ khai báo và
    binding; state machine, validate, tính toán đều thuộc Presenter/ViewModel.
    Và `.qml` > 300 dòng thì tách component.

---

## 9. Hai bộ `.agents/` — đừng đọc nhầm repo

Cả superproject lẫn submodule đều có thư mục `.agents/`, **nội dung khác
nhau và phục vụ hai dự án khác nhau**. Đây là chỗ nhầm lẫn nguy hiểm nhất
với agent mới:

| | `../.agents/` (superproject) | `.agents/` (submodule — thư mục này) |
| :--- | :--- | :--- |
| Phục vụ | framework `sagittarius_engine/` | app bot `Sagittarius_Elite_Warrior/` |
| Bảng task | `../Tasks/README.md` (Kanban, mã `TASK-XXX`) | `Tasks/ROADMAP.md` (mã `BOT-XXX`/`BUG-XXX`) |
| Entry point | `PLAYBOOK.md` + `manifest.yml` | `ONBOARDING.md` (file này) + `AGENTS.md` |

Khi làm việc trong app, **luôn ưu tiên rule của submodule**. Rule của
superproject chỉ áp dụng khi bạn thật sự sửa code framework. Hai bảng task
không liên quan gì nhau — đừng ghi task app vào `Tasks/README.md` của
engine và ngược lại.

**Đã dọn 2026-08-20:** `../.agents/PLAYBOOK.md` trước đó mô tả cây thư mục
`.ai/` (không tồn tại) và định tuyến sang 8 skill file không có thật;
`../.agents/manifest.yml` khai báo 9 mục không tồn tại đồng thời bỏ sót 5
file có thật. Cả hai đã được sửa — mọi mục trong manifest giờ trỏ đúng file
thật. Nếu phát hiện thêm chỗ lỗi thời, sửa và ghi lại ở đây thay vì im lặng
đi đường vòng.

Lưu ý còn tồn tại: **mọi rule file của cả hai repo chỉ ghi lệnh
PowerShell**. Trên Linux dùng lệnh ở §5.

---

## 10. Ngôn ngữ

- **Trao đổi với user, task file, bug report, ROADMAP:** tiếng Việt.
- **Code, tên biến, docstring, comment, commit subject:** tiếng Anh.
- **Chuỗi hiển thị trên UI:** tiếng Việt (đúng thuật ngữ domain đã chốt,
  ví dụ "Thông số Chiến lược" khác với cài đặt Bot chung).
