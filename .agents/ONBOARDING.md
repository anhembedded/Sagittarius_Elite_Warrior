---
name: Onboarding
description: Entry point cho mọi AI agent làm việc trên repo này — bản đồ tài liệu, vòng đời task/bug, lệnh verification thật, bookkeeping, quyền hạn, và các bẫy đã thật sự gây ra code lỗi.
trigger: always_on
---

# ONBOARDING — đọc file này TRƯỚC KHI viết dòng code đầu tiên

Bộ `.agents/` này có nhiều file rule — **đừng nạp hết**. Mỗi file có `trigger`
riêng; đọc đúng cái việc bạn đang làm cần.

Vấn đề của một agent mới không phải là thiếu luật. Là **không biết có những
file đó, đọc theo thứ tự nào, và quy trình thật sự chạy ra sao**. File này là
bản đồ đó. Nó không lặp lại nội dung rule; nó nói *khi nào* đọc rule nào, và
mô tả những phần quy trình không được viết ở đâu khác.

---

## 1. Bản đồ tài liệu — đọc theo thứ tự này

| Thứ tự | File | Khi nào |
| :--- | :--- | :--- |
| 1 | `.agents/ONBOARDING.md` (file này) | Luôn luôn, đầu tiên |
| 2 | `.agents/Handover.md` | **Ngay sau file này** — phiên trước dừng ở đâu, quyết định nào đừng suy luận lại |
| 3 | `.agents/AGENTS.md` | Chỉ để điều hướng — bảng chủ đề → file rule |

Rồi mở **đúng 1-2 file** trong `rules/` theo việc đang làm — không nạp cả bộ:

| Đang làm gì | Đọc |
| :--- | :--- |
| Sửa code bất kỳ | `code-quality-rule.md` |
| Đụng kiến trúc: interface, tầng, tách file | `architecture-rule.md` |
| Phân vân signal nội bộ hay event bus | `event-rule.md` |
| Hoãn một việc, hoặc chấp nhận một đánh đổi | `design-intent-rule.md` |
| Sắp nói "xong" | `ci-rule.md` |
| Sắp commit | `commit-rule.md` |
| User báo bug (**bắt buộc**) | `bug-fix-rule.md` |
| Thêm/sửa log | `logging-rule.md` |
| Viết test | `testing-rule.md` |
| Tác vụ nền do user khởi tạo | `async-action-rule.md` |
| Logic nghiệp vụ | `domain-truth-rule.md` |
| Tầng presentation | `ui-rule.md` |
| Thiếu công cụ để verify | `environment-rule.md` |
| Cần biết hệ thống đang ở đâu | `<TASKS_DIR>` |

**Đừng tin con số nào viết trong tài liệu** (số file rule, số test, số lỗi
lint). Chúng trôi nhanh hơn mọi thứ khác. Ở repo gốc của bộ rule này, câu "có
N file rule" đã sai **ba lần liên tiếp** (10 → 9 → 8, thực tế 7). Đếm bằng
lệnh: `ls .agents/rules/`.

---

## 2. Vòng đời một TASK (tính năng mới)

1. **Task file trước, code sau.** Mọi task có file trong `<TASKS_DIR>` theo
   mẫu `<TASK_ID>-XXX_mo_ta_ngan.md` (số kế tiếp số lớn nhất đang tồn tại).
   User yêu cầu một tính năng chưa có task → tạo file task trước.
   Việc lớn thì tách task con `<TASK_ID>-XXXA`, `-XXXB`… và phải có bảng liệt
   kê task con kèm **thứ tự thực hiện** (xếp theo rủi ro tăng dần, ghi rõ cái
   nào chặn cái nào).
2. **Nội dung task file**, tối thiểu: bối cảnh & vấn đề **thật** (không phải
   mô tả chung chung), thiết kế + **lý do** cho mọi quyết định không hiển
   nhiên, thay đổi theo từng file, cách kiểm thử.
3. **Việc tái cấu trúc: trình design trước khi implement.** Sơ đồ class +
   component, as-is và to-be, chỉ rõ cái gì dùng chung / cái gì riêng. Duyệt
   xong mới viết code.
4. **Code + test.** Tầng test nào là đúng: `rules/ci-rule.md` §6.
5. **Hoàn thành:** chuyển task file sang thư mục `completed/`
   (`git mv`, đừng copy-rồi-xoá — mất lịch sử), đổi trạng thái thành
   `✅ Hoàn thành (YYYY-MM-DD)`, và thêm mục **"Ghi chú triển khai"**: bug
   thật đã phát hiện trong lúc làm, quyết định thiết kế, số test. Phần này là
   giá trị lớn nhất của task file với người đọc sau — đừng viết cho có.
6. **Bookkeeping:** §4.

Một task lớn **không** chuyển sang `completed/` cho tới khi *tất cả* task con
xong; trong lúc đó cập nhật trạng thái tại chỗ (`1/3 xong`).

**Trạng thái ghi trong task file có thể cũ hơn code.** Trước khi tin "task này
chưa làm", kiểm bằng chính code (`grep`, chạy test). Chuyện task đã được làm
xong bởi một việc khác — hoặc đã **hết đối tượng** để làm — xảy ra thường
xuyên hơn bạn nghĩ.

---

## 3. Vòng đời một BUG

`rules/bug-fix-rule.md` là nguồn chuẩn — đọc nguyên văn. Ba điểm bị vi phạm
nhiều nhất:

- **Viết regression test TRƯỚC khi sửa, và chạy nó để xác nhận nó FAIL đúng
  lý do.** Test viết sau khi sửa không chứng minh được gì. Test fail vì lý do
  khác (import sai, thiếu fixture) cũng không chứng minh được gì.
- **Chọn đúng tầng test.** Nếu chỗ crash nằm trong hàm mà test double của bạn
  thay thế, test đó *không thể* tái hiện bug — một mock không chạy thân hàm
  thật. Chuyện "tái hiện" bằng `Mock(spec=...)` rồi thấy nó pass ngay cả khi
  chưa sửa gì đã xảy ra hai lần liên tiếp trong một bug thật.
- **Bug report bắt buộc**, có: Symptom (bằng chứng thật — traceback/log/ảnh,
  không diễn giải lại), Root cause (cơ chế thật kèm `file:line`), Fix,
  Regression test. Lập xong thì thêm dòng vào bảng bug đang mở — đó là chỗ
  duy nhất thấy được bug nào chưa sửa.

Nếu user dán log/ảnh vào chat, **đọc chúng bằng công cụ thật** trước khi đưa
ra giả thuyết. Một chi tiết trong ảnh thường chỉ thẳng vào nguyên nhân: một ô
số liệu đúng nằm cạnh một ô sai đã khoanh vùng ngay lỗi nằm ở hàm tổng hợp
chứ không phải ở tầng đọc dữ liệu.

---

## 4. Bookkeeping — phần hay bị làm ẩu nhất

Mỗi task/bug hoàn thành phải cập nhật **cả ba** chỗ:

1. **Thêm dòng vào đầu mục "đã xong"** (mới nhất trước). Dòng đó phải tóm tắt
   được root cause / quyết định thiết kế, không phải chỉ nhắc lại tên task.
2. **Tính lại bảng số lượng bằng lệnh, không đếm tay:**
   ```bash
   for d in completed in_progress backlog cancelled; do
     printf "%s %s\n" "$d" "$(ls <TASKS_DIR>/$d/*.md 2>/dev/null | wc -l)"
   done
   ```
3. **Cập nhật dòng trạng thái tại chỗ** trong bảng tổng quan, kèm ngày cập
   nhật.

Sau khi thêm file có link chéo, **kiểm link không gãy**:

```bash
grep -oh "](\.\{1,2\}/[^)]*\.md)" <file>.md | tr -d '](' | sed 's/)$//' \
  | sort -u | while read -r l; do [ -f "$l" ] || echo "BROKEN: $l"; done
```

---

## 5. Chạy verification THẬT

Lệnh gate đầy đủ và cách xử lý khi đỏ: `rules/ci-rule.md`. Ở đây chỉ hai điều
mà agent hay làm sai **trước khi kịp đọc file đó**:

### 5.1 Không tin console — ghi ra file rồi grep

```bash
<CI_CMD> > /tmp/ci.log 2>&1
grep -nE "FAILED|ERROR|Traceback|WARNING" /tmp/ci.log
```

**Luôn `> logfile 2>&1`, đừng `| tail`.** Hai lý do, lý do thứ hai nặng hơn:

- Nhiều framework (nhất là GUI ở chế độ headless) xả lỗi **vô hại** ra stderr
  *sau* dòng tổng kết của test runner, nên `tail` cho bạn xem nhầm đống nhiễu
  đó và tưởng test hỏng.
- Nghiêm trọng hơn: `| tail -N` hoặc terminal bị cắt xén có thể làm **mất
  hẳn** đúng dòng lỗi thật. Bằng chứng thật: một agent chạy test thô suốt
  nhiều phiên và không bao giờ chạy cổng đầy đủ; lần đầu chạy đủ **và
  redirect toàn bộ ra file**, hai bug thật lộ ra cùng lúc — một lỗi script chỉ
  xảy ra trên phiên bản shell cũ, và một worker chết giữa chừng sau
  `ResourceWarning: unclosed database`, tái hiện 2/2 lần chứ không hề flaky.
  Cả hai chỉ lộ ra vì có file log đầy đủ để đọc lại.

Áp cho **mọi** lệnh verification, kể cả chính lệnh gate. Mục này nói về việc
**bạn** gõ một lệnh bằng tay; việc **script gate phải tự** ghi log và tự quét
nó là một luật riêng — `rules/ci-rule.md` §5.

### 5.2 Chỉ sửa lint trong file bạn đang sửa

Repo luôn có sẵn vài lỗi lint từ phiên khác không do bạn gây ra. Dọn dẹp file
vô can làm diff bug-fix lẫn thay đổi không liên quan và không ai review nổi.
Muốn dọn toàn repo thì làm một commit `style:` riêng, sau khi hỏi user.

---

## 6. Quyền hạn — cái gì được tự làm, cái gì phải hỏi

| Hành động | Quy tắc |
| :--- | :--- |
| Đọc, phân tích, chạy test | Tự do |
| Sửa code trong phạm vi user yêu cầu | Tự do |
| Quyết định thiết kế trong phạm vi đó | Tự do — xem `architecture-rule.md`, phương châm quyết định |
| Cài công cụ/thư viện **đã khai báo** vào môi trường hiện tại | Tự do — `environment-rule.md` |
| Thêm dependency **mới** vào manifest | **Hỏi trước** |
| `git commit` | **Hỏi trước.** Không bao giờ commit tự phát |
| `git push` | **Chỉ khi user yêu cầu rõ ràng**; mỗi repo là một lần xác nhận riêng |
| Sửa file ngoài phạm vi task | Không, trừ khi user yêu cầu |
| Xoá/ghi đè file của user | Đọc nội dung trước, hỏi trước |

### Phản biện là bắt buộc, không phải tuỳ chọn

- Agent **phải** phản biện yêu cầu của user nếu nó tạo ra mâu thuẫn, vi phạm
  ranh giới tầng, hay phá nguyên tắc đã chốt. Nói ra vấn đề gốc và đề xuất
  phương án sạch — không im lặng làm theo.
- Nhưng nếu user đã nghe và vẫn giữ nguyên yêu cầu thì **làm đầy đủ theo họ**,
  không làm nửa vời để chứng minh mình đúng.

---

## 7. Chín cái bẫy đã thật sự tạo ra code lỗi

Tất cả đều đã xảy ra thật, không phải giả định. **Mỗi cái có đúng một chủ sở
hữu** trong `rules/` — mô tả đầy đủ và bằng chứng nằm ở đó, không chép lại ở
đây. Bảng này chỉ để bạn nhận ra mình đang đứng trước cái bẫy nào.

| # | Bẫy | Luật sở hữu nó |
| :-: | :--- | :--- |
| 1 | Tự tính giá trị kỳ vọng của test bằng đầu thay vì chạy code thật | `testing-rule.md` §4 |
| 2 | So sánh float bằng `==` / `if value:` | `testing-rule.md` §6 |
| 3 | Assert số lượng bằng hằng số cứng (`len(x) == 9`) | `testing-rule.md` §6 |
| 4 | Assert full-object equality trên output serialize | `testing-rule.md` §6 |
| 5 | Thêm field vào kiểu dùng chung mà không đặt default | `code-quality-rule.md` §7 |
| 6 | Đổi công thức dùng chung mà không rẽ nhánh giữ hành vi cũ | `code-quality-rule.md` §7 |
| 7 | Chuyển FSM sang đúng state nó đang đứng; và việc quan trọng đặt sau một lời gọi có thể ném lỗi trong handler nuốt exception | `async-action-rule.md` §3 |
| 8 | Thêm log vào một vòng lặp nóng | `logging-rule.md` §4 |
| 9 | Thêm method vào interface rồi chỉ cập nhật implementer "chính" | `architecture-rule.md` §2 |

Hai cái không có chủ sở hữu ở `rules/` vì chúng là **thói quen làm việc**, không
phải luật về code — nên chúng ở đây:

- **Đọc bằng chứng bằng công cụ thật.** User dán log/ảnh vào chat thì mở chúng
  ra đọc trước khi đưa giả thuyết (§3).
- **A/B trước khi nhận lỗi về mình** khi gate đỏ ở chỗ bạn không đụng (§10.4).

## 8. Ngôn ngữ

- **Trao đổi với user, task file, bug report, tài liệu:** `<DOC_LANG>`.
- **Code, tên biến, docstring, comment, commit subject:** tiếng Anh.
- **Chuỗi hiển thị trên UI:** `<UI_LANG>` — đúng thuật ngữ domain đã chốt.

---

## 9. Báo cáo với user — mức project lead, không phải mức implementation

- Khi báo tiến độ, trạng thái, tóm tắt điều tra hay kết quả test **trong hội
  thoại**, viết như đang báo cáo cho một **project lead**: kết luận, trạng
  thái, quyết định cần user ra, rủi ro/blocker. **Không** đi vào chi tiết
  implementation (tên hàm, dòng code, tên biến) trừ khi user hỏi thẳng vào đó,
  hoặc chi tiết đó **quyết định trực tiếp** hành động tiếp theo.
- **Không áp dụng cho tài liệu lưu trữ lâu dài.** Task file, bug report, báo
  cáo vẫn phải đầy đủ root cause / `file:line` / bằng chứng. Quy tắc này chỉ
  áp cho câu trả lời trong hội thoại.

---

## 10. Bắt tay vào việc đang dở

### 10.1 Ba lệnh đầu tiên, lần nào cũng vậy

```bash
git status
git log --oneline -10
cat .agents/Handover.md
```

**Việc thường bị để lại chưa commit giữa các phiên** — theo đúng §6, agent
không tự commit. Nên `git status` không phải thủ tục: bảng task trông như chưa
ai đụng **cộng với** cây làm việc bẩn nghĩa là việc **đã làm rồi**, chỉ chưa
được ghi lại. Đọc diff trước khi kết luận một task còn nguyên.

### 10.2 Trạng thái sống ở `Handover.md`, không ở đây

File này cố ý **không** liệt kê việc nào đang chạy. Bản trước của nó (ở repo
gốc) có bảng đó và bảng sai chỉ sau vài giờ. Trạng thái sống ở đúng một chỗ:
[`Handover.md`](Handover.md), file được **thay mới** mỗi phiên.

### 10.3 Đọc quyết định trước khi làm

**Bắt buộc: đọc tài liệu quyết định (ADR / `DECISION_*.md`) của việc đang làm
trước khi động vào task con nào.** Nó ghi lại những quyết định đã tranh luận
xong với user — trong đó có những quyết định **đảo ngược** phương án trước đó.
Tự suy luận lại sẽ tốn một phiên và thường ra kết quả khác.

### 10.4 Trước khi kết luận một lỗi là do mình gây ra, A/B nó

Cổng CI có thể báo đỏ những test **không liên quan** tới thay đổi của bạn
(test phụ thuộc thứ tự collection, công cụ thiếu trên `PATH`, môi trường).

```bash
git stash push -u   # chạy gate → ghi kết quả
git stash pop       # chạy lại → so sánh
```

Mất hai phút, và đó là khác biệt giữa một regression thật với một giờ đuổi
theo môi trường.

---

## 11. Checklist trước khi nói "xong"

Không phải bản tóm tắt của các rule — là thứ tự **kiểm** lại. Mỗi dòng trỏ về
nơi định nghĩa nó; nghi ngờ dòng nào thì mở file đó, đừng suy đoán.

- [ ] Gate đầy đủ `<CI_CMD>` exit `0` — **lint + format + type check + test +
      coverage**, không phải chỉ test (`ci-rule.md` §1)
- [ ] Đã **ghi log ra file và quét** nó; mọi hit WARNING/ERROR/CRITICAL đều đã
      được phân loại là defect thật hoặc điều kiện kỳ vọng có lý do
      (`ci-rule.md` §5)
- [ ] Bằng chứng test nằm ở **đúng tầng** — và nếu là mảnh chưa nối vào app
      thật thì đừng khai là E2E (`ci-rule.md` §4)
- [ ] Nếu là bug: regression test đã **đỏ trước, xanh sau**, và ở lại vĩnh viễn
      (`bug-fix-rule.md` §3-4)
- [ ] Nếu đổi interface: đã `grep` implementer ở **cả** `<SRC_DIR>`,
      `scripts/`, `<TEST_DIR>` (`architecture-rule.md` §2)
- [ ] Nếu hoãn một việc hoặc chấp nhận một đánh đổi: đã có **type hoặc test**
      đại diện, không chỉ một đoạn văn (`design-intent-rule.md`)
- [ ] Bookkeeping đã cập nhật **cả ba chỗ**, số đếm tính bằng lệnh (§4)
- [ ] Không commit/push nếu user chưa yêu cầu (§6)
