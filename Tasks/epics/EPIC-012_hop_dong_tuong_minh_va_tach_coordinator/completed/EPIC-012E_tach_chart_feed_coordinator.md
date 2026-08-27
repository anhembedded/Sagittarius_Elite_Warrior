# EPIC-012E — Tách `ChartFeedCoordinator` khỏi `execution`

**Trạng thái:** ✅ Xong 2026-08-27
**Repo:** Elite
**Phụ thuộc:** `B`, `C`

## Kết quả

| | Dòng | Tham số ctor | Method công khai |
| :--- | ---: | ---: | ---: |
| `execution_coordinator.py` **trước** | 354 | 17 | 5 |
| `execution_coordinator.py` **sau** | **251** | **14** | 4 |
| `chart_feed_coordinator.py` **mới** | **154** | **7** | 1 |

Đúng dự đoán của task (357 → ~250 dòng). Tham số 17 → 14, không phải 13 như
ước tính, vì phát sinh thêm `on_result_ready` — xem dưới.

## Ranh giới: vòng đời, không phải "dòng nào trông giống nhau"

- **Chạy backtest**: chỉ tồn tại **trong lúc** một run đang bay.
- **Nạp chart**: chạy **khi không có run nào** — nó là thứ xảy ra *sau khi* một
  run kết thúc, và **lỗi ở đây không được phép huỷ `BacktestResult` đã báo**.

Bất đối xứng đó (một bên hỏng thì bên kia vẫn đúng) chính là bằng chứng hai
vòng đời khác nhau, và là lý do bước nạp chart vốn đã tách khỏi dispatch từ
`BOT-056` — chỉ là chưa tách thành file.

Dict `shared` 12 khoá trong `_dispatch_run` **giữ nguyên**, đúng như task dặn:
nó mô tả đúng một lời gọi, và Single-Scope Cohesion thắng ở đó.

## `on_result_ready` — cái mà đo dependency đã bỏ sót

Lúc lập kế hoạch, tôi quét dependency bằng `ast` nhưng chỉ bắt `self._*`
(thuộc tính private). Vì thế **bỏ lọt một lời gọi method công khai**:
`run()` gọi thẳng `self.fetch_and_emit_chart_data(...)` ở dòng cuối. Tách xong
là `AttributeError`, và **test bắt được ngay** — không phải mắt.

Sửa **không** phải bằng cách tiêm `ChartFeedCoordinator` vào
`ExecutionCoordinator`. Làm vậy là buộc bên chạy run phải biết bên vẽ chart tồn
tại. Thay vào đó thêm một callable **thông báo**:

```python
self._on_result_ready(resolved_action_id, config, result)
```

`ExecutionCoordinator` chỉ nói *"có kết quả rồi, đây"*. Chuyện gì xảy ra tiếp —
hôm nay là `ChartFeedCoordinator` đi lấy nến để vẽ — **không phải việc của nó**.
Đây cũng chính là cơ chế giữ được bất đối xứng ở trên.

`factory.py` nối nó qua `presenter._chart_feed`, **không** bind thẳng vào local
`_chart_feed`: file này đã bị bỏng 4 lần vì capture sớm một thứ mà test thay
sau đó.

**Bài học ghi lại:** quét dependency để tìm chỗ tách **phải tính cả lời gọi
method công khai giữa hai nửa**, không chỉ thuộc tính.

## Test cũng tách, doubles về conftest

`test_chart_feed_coordinator.py` nhận test về *chuỗi nến nào thuộc về một
result*; `test_execution_coordinator.py` giữ 8 test về *run kết thúc thế nào*.

`FakeCancellationToken`/`run_config`/`committed_bar`/`backtest_result`/
`RecordingDispatcher` chuyển vào `conftest.py` dùng chung — tiếp tục cùng lý do
với `012C`/`012D`.

## Verify — bơm lỗi đúng như nghiệm thu yêu cầu

Cho `emit_chart_data_ready` thành no-op:

- `test_a_realtime_run_charts_its_own_committed_bars` **đỏ** ✅
- 8 test của `ExecutionCoordinator` **vẫn xanh** ✅ — nghĩa là ranh giới vẽ đúng.

Khôi phục → 53/53 xanh.

## Nghiệm thu

- `pwsh -NoProfile -File scripts/ci-local.ps1 -Full` → `RESULT: PASS`, log quét
  sạch `FAILED|ERROR|Traceback|ResourceWarning`.
