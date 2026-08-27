# EPIC-012E — Tách `ChartFeedCoordinator` khỏi `execution`

**Trạng thái:** ⬜ Chưa làm
**Repo:** Elite
**Phụ thuộc:** `B`, `C`

## Số đo

`execution_coordinator.py`: **357 dòng, 19 tham số ctor** — file to nhất trong
`coordinators/`, và là file gần ngưỡng cứng >400 dòng (§5.4) nhất.

Nó đang làm **hai việc khác vòng đời**:

1. **Chạy backtest thật** — dispatch command, theo dõi tiến độ, phát
   `progress`/`failed`/`cancelled`/`empty`/`succeeded`.
2. **Nạp dữ liệu cho chart** — `emit_chart_data_ready`,
   `emit_strategy_indicator_lines`, `emit_strategy_trend_zones`,
   `get_chart_script_keys`, `get_chart_klines_fetch_limit`.

Việc (2) chạy được **khi không có backtest nào đang chạy**; việc (1) không.
Đó là hai vòng đời, không phải hai bước của một vòng đời.

## Kết quả mong đợi

`execution_coordinator` **357 → ~250 dòng**, **19 → ~13 tham số**.

## Không được làm

`_dispatch_run` có một dict `shared` gom 12 khoá dùng chung cho hai lệnh
dispatch. **Không tách dict đó ra file riêng** — nó mô tả đúng một lời gọi, và
`code-quality-rule.md` "Single-Scope Cohesion" thắng ở đây. Tách theo **vòng
đời**, không tách theo "dòng nào trông giống nhau".

## Nghiệm thu

- `pwsh -NoProfile -File scripts/ci-local.ps1 -Full` → `RESULT: PASS`.
- **Bơm lỗi:** cho `emit_chart_data_ready` thành no-op → test render dữ liệu
  chart phải đỏ, còn test chạy backtest **không được** đỏ. Cả hai điều kiện đều
  phải đúng — nếu test backtest cũng đỏ thì ranh giới vừa vẽ là sai.
