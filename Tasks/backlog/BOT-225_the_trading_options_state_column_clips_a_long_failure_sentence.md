# BOT-225 — The Trading options State column shows a long failure sentence whole

**Status:** 🔵 Backlog
**Priority:** P3
**Board:** At the Options dialog's minimum size the State cell of a refused key ("Binance refused the key. It may belong to…") is clipped after a few lines by the grid, so the advice cannot be read.
**Source:** Found while building [BOT-224](../completed/BOT-224_options_trading_shows_the_machines_public_ip_for_the_key_whitelist.md); the `public_ip_*` frames in its `BOT-224_assets/` show it.
**Risk:** 🟢 — layout of one page.
**Complexity:** S — find why the wrapped `StateBadge` in the grid gets less height than its text needs.
**Depends on:** None

---

## 1. Context and problem
`TradingSettingsView._grid` holds a wrapped `StateBadge` per venue in a narrow column; the dialog does not propagate height-for-width, so a 200-character `-2015` sentence is cut after about eight lines although the page has free space below. It happened before `BOT-224`.

## 2. Acceptance criteria
- [ ] At the dialog's minimum size, a refused key's State text is readable whole, light and dark.

## 3. Design
To be chosen: a full-width wrapped line under the grid for the selected row, or giving the State column more width.

## 3a. Reuse
To be filled when taken (`StateBadge`, `plain_label`).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/ui/settings/trading_settings_view.py` | layout of the State column |

## 5. Testing
A conformance-style check at the minimum size that the State label's height holds its wrapped text.

## 6. Docs touched
none, because it is a layout fix.
