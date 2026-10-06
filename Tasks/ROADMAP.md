# 🗺️ Project Roadmap

> [!NOTE]
> The hand-written part of the board: the folder layout, how the board is produced, the
> complexity scale and the direction the owner settled. **Nothing here lists tasks or counts
> them**: that is generated, so two pull requests never edit the same lines (`BOT-163`).

---

## 📂 Task folders

```text
Sagittarius_Elite_Warrior/Tasks/
├── 🟢 completed/   # finished and verified tasks
├── 🟡 in_progress/ # tasks being worked on now
├── 🔴 backlog/     # tasks waiting their turn
├── ❌ cancelled/   # tasks dropped on purpose, with the reason kept
├── 🐞 bug_report/  # bugs: incomplete/ and completed/; its README is the bug process
├── 🏛️ epics/       # epics; epics/README.md is the epic board
├── 📜 history/     # the hand-written boards, frozen on 2026-10-06
└── 📄 reports/     # analysis and audit reports
```

---

## 📊 The board

The board is generated from the files. Each task and bug file carries its own one-line entry,
its `**Board:**` field, and `python3 scripts/render_board.py` writes the count tables and the
lists from them (`--write` saves `Tasks/BOARD.md`, which is not tracked). A change of state is
a change to the file alone: move it between folders, set its `**Status:**`, and write its
`**Board:**` line (ONBOARDING §6). `tests/unit/test_task_board_is_consistent.py` fails when a
file has no `**Board:**` line, or when a list or a count table comes back into this file.

Entries written by hand before 2026-10-06 are frozen in
[`history/ROADMAP_until_2026-10-06.md`](history/ROADMAP_until_2026-10-06.md) and
[`history/BUG_BOARD_until_2026-10-06.md`](history/BUG_BOARD_until_2026-10-06.md).

---

### 🤖 Phân loại Độ phức tạp & Loại Agent AI phù hợp (Agent Complexity Matrix)

| Ký hiệu / Badge | Độ phức tạp | Loại AI Agent phù hợp | Tiêu chí đánh giá & Loại Task |
| :---: | :---: | :---: | :--- |
| 🟢 **`S (Fast Agent)`** | **Thấp** | **Fast / Routine Models** *(Gemini Flash, Haiku, GPT-4o-mini)* | Sửa Docs/Roadmap, thêm config key, styling QML đơn giản, refactor 1 file độc lập, unit test nhỏ. |
| 🟡 **`M (Standard Agent)`** | **Trung bình** | **Standard Coding Models** *(Gemini Pro, GPT-4o, Sonnet non-thinking)* | Thêm Use Case mới (Command + Handler), QML component/modal mới, mở rộng Parameter Schema, kết nối ViewModel. |
| 🔴 **`L (Thinking Agent)`** | **Cao** | **Deep Reasoning / Thinking Models** *(Sonnet Thinking, Gemini Thinking, o3-mini)* | FSM State Machine, Thread-affinity (UI vs Worker), Thuật toán tài chính, Out-of-sample, Cooperative Cancellation, Action Ownership. |
| 🛡️ / ⚡ **`Specialized`** | **Chuyên biệt** | **Specialized Agents** *(Sentinel 🛡️ / Bolt ⚡)* | **Sentinel 🛡️**: Security audit, injection defense. **Bolt ⚡**: Tối ưu thuật toán O(N²), profiling rendering/memory, benchmark throughput. |

---

> ## 🧭 Định hướng đã chốt: **Backtest đáng tin trước, giao dịch thật gác lại**
>
> Từ 📄 [Rà soát định hướng App](reports/app_direction_audit.md) §3. Bot **chưa đặt được
> lệnh nào** — [`market_tick_event_handler.py`](../src/modules/strategy/application/event_handlers/market_tick_event_handler.py)
> chỉ `logger.info()` rồi return; [`BOT-008`](backlog/BOT-008_live_trading_strategy_execution.md)
> là **P1**, ghi *"sẵn sàng bắt đầu"*, vẫn chưa hề động tới.
>
> User đã chốt: **ưu tiên [Epic `BOT-078`](backlog/BOT-078_backtest_trustworthiness_epic.md)
> (`BOT-079` → `BOT-080`) trước `BOT-008`.** Lý do: chiến lược chưa kiểm định
> out-of-sample, và [`PythonBinanceClient`](../src/infrastructure/binance/client.py)
> hiện nối thẳng **mainnet thật** (`Client(api_key, api_secret)`, không có testnet nào
> cấu hình sẵn) — bật `BOT-008` lên trước khi biết chiến lược có edge thật là rủi ro tiền
> thật không cần thiết. `BOT-008` **không bị xoá khỏi backlog**, chỉ xếp sau.
>
> ✅ **Cập nhật (14/08)**: `BOT-079`/`BOT-080`/`BOT-081` — toàn bộ Epic `BOT-078` — đã
> xong. Chưa tự ý coi `BOT-008` là đã mở khoá — đó là quyết định của user, không tự suy ra
> từ việc code xong.
>
> ✅ **Cập nhật (2026-09-01)**: lập [Epic `EPIC-021`](epics/EPIC-021_ket_noi_binance_futures_testnet/README.md)
> — kết nối **USD-M Futures Testnet** và dựng đường đi lệnh thật. Điều này **không** mở khoá
> `BOT-008`: `TradingVenue` cố ý **không có member `MAINNET`**, nên giao dịch tiền thật vẫn là
> một epic riêng chưa được duyệt (xem [ADR](epics/EPIC-021_ket_noi_binance_futures_testnet/DECISION_2026-09-01_moi_truong_san_va_duong_di_lenh.md) §3).
> Khảo sát để lập epic này mở thêm 2 bug: [`BUG-080`](bug_report/completed/BUG-080_settings_api_credentials_never_reach_the_exchange_client.md)
> (key nhập ở Settings không bao giờ tới client) và [`BUG-081`](bug_report/completed/BUG-081_binance_endpoint_config_keys_are_dead.md)
> (2 key endpoint là config chết).
>
> ✅ **Cập nhật (2026-09-20)**: lập [`PRO-005`](proposal/PRO-005.md) và [Epic `EPIC-026`](epics/EPIC-026_road_to_real_money/README.md) — lộ trình 5 cổng tới tiền thật. `BOT-008` vẫn **chưa** mở khoá: cổng 3 mới thêm `TradingVenue.FUTURES_MAINNET`, và chỉ sau khi user duyệt ADR của epic.
