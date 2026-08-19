# Nhiệm vụ: Bug — Execution Trigger Rule: cờ `locked` đảo ngược, trạng thái không rời khỏi QML

> **Trạng thái:** ✅ **HOÀN THÀNH**
> Thuộc Epic [`BOT-073`](../backlog/BOT-073_realtime_tick_backtest_epic.md).
>
> Phát hiện khi user hỏi *"cơ chế thực thi tập lệnh khi lệnh được khớp — hiện tại có
> đảm bảo không?"* và đi kiểm tra xem checkbox đó nối vào đâu. Câu trả lời: **không
> nối vào đâu cả, nhưng vẫn bấm được.**

## 1. Triệu chứng

Trong menu "Thực thi tập lệnh" (Backtest Top Panel / `OrderExecutionModal.qml`):

- **"On bar close"** — cái **duy nhất** thật sự chạy — bị **làm mờ (opacity 0.4),
  không bấm được**.
- **3 lựa chọn chưa cài đặt** ("Khi lệnh được khớp", "Trên mỗi tick của thanh lịch
  sử", "Trên mỗi tick của thanh thời gian thực") — **sáng rõ, bấm được bình thường**.

User tick "Khi lệnh được khớp" → UI nhận, nhìn như đã bật → **và không có gì thay
đổi**. Đúng loại "lỗi bị nuốt im lặng" (lớp B trong
[Phân tích Lớp Lỗi Engine](../reports/engine_defect_class_analysis.md)) mà
[`BOT-066`](BOT-066_fail_loud_ui_action_errors.md) vừa làm để chống.

## 2. Root cause (đã verify)

### 2.1. Cờ `locked` bị đảo

[`OrderExecutionModal.qml`](../../src/presentation/ui/components/OrderExecutionModal.qml)
có comment ghi rõ **ý định đúng**:

> *"Only 'On bar close' is real today (`RunStaticBacktestCommandHandler` evaluates the
> strategy once per closed candle — BOT-021). The other 3 need BOT-042 (tick-level
> engine support) before they mean anything, so they're **shown-but-disabled** rather
> than hidden, per BOT-022 §3."*

Nhưng `ListModel` thật thì ngược lại: `"On bar close"` mang `locked: true`, còn 3 cái
kia mang `locked: false`. Delegate dùng `enabled: !model.locked` (và `opacity:
delegateItem.enabled ? 1.0 : 0.45`) → kết quả đúng bằng triệu chứng ở §1.

Nguồn gốc: `locked` đang **gộp 2 khái niệm khác nhau** vào 1 cờ:

1. *"Bị ép bật, không tắt được"* → đúng với "On bar close".
2. *"Chưa khả dụng"* → đúng với 3 cái còn lại.

Cả hai đều phải dẫn tới `enabled: false`, nên cần đặt `locked: true`
cho **cả 4**.

### 2.2. Trạng thái không bao giờ rời khỏi QML

`grep` toàn repo: **không có `executionTrigger`/`calc_on_order` nào ở Python**;
`OrderExecutionModal` chỉ được dùng từ Backtest screen. `CheckBox`
chỉ ghi ngược vào `model.checked` của chính `ListModel` cục bộ trong QML — không tới
`BackTestViewModel`, không tới `RunStaticBacktestCommand`.

Nên kể cả khi cờ `locked` đúng, việc tick vào một lựa chọn đã cài đặt **vẫn sẽ không
có tác dụng** cho tới khi có người nối dây.

## 3. Phạm vi đã thực hiện

- [x] Sửa `locked` cho **cả 4** lựa chọn thành `true` (giữ `checked: true` cho "On
      bar close", `false` cho 3 cái còn lại) → UI trung thực: hiện đủ 4 để user biết
      lộ trình, nhưng không cái nào bấm được, đúng ý định đã ghi trong comment.
- [x] Sửa comment trong file cho khớp thực tế và bổ sung `textFormat: Text.PlainText`
      theo chuẩn `qml-rule.md`.
- [x] Test guard (`tests/unit/presentation/ui/screens/test_order_execution_modal.py`):
      assert **cả 4** `chkExecutionTrigger_*` và `triggerCheckBox_*` đều `enabled == false`,
      và đúng 1 cái (`chkExecutionTrigger_0`) `checked == true`.

**KHÔNG làm trong task này**: nối `executionTrigger` xuống ViewModel/Command. Chưa có
consumer thật nào ở engine để nối tới — dựng plumbing trước consumer là đúng thứ
`BOT-032`/`BOT-044` đã phải trả giá một lần (chừa sẵn `params` rồi bỏ không dùng suốt
nhiều task). Việc nối dây thuộc [`BOT-076`](../in_progress/BOT-076_realtime_backtest_engine.md), lúc
đã có chế độ thật để chọn.

## 4. Rủi ro / Lưu ý

- Test guard ở §3 sẽ **cố tình vỡ** khi `BOT-076`/`BOT-077` mở khoá lựa chọn đầu
  tiên. **Đó là mục đích** — nó buộc người mở khoá phải sửa test, và lúc sửa sẽ phải
  đối mặt với câu hỏi "đã nối dây xuống Python chưa?". Ghi rõ ý này trong docstring
  của test, đừng để người sau tưởng là test cũ hỏng rồi xoá đi.
- 4 lựa chọn cùng disabled trông hơi lạ về mặt UX. Chấp nhận có chủ đích: thà hiện
  đủ lộ trình mà thành thật, còn hơn cho bấm rồi không làm gì (đúng nguyên tắc
  `BOT-022` §3 đã chốt từ đầu).
- File này **chưa từng sửa** kể từ `BOT-022` (`be274c5`) — không liên quan đợt
  redesign UI đang làm dở, không sợ đụng nhau.

## 5. Phụ thuộc

- Không phụ thuộc task nào. Sửa **chỉ trong `Sagittarius_Elite_Warrior/src/`**.
- [`BOT-076`](../in_progress/BOT-076_realtime_backtest_engine.md) — sẽ mở khoá & nối dây thật.
