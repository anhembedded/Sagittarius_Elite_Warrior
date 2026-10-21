# BOT-225 — The Trading options State column shows a long failure sentence whole

**Status:** ✅ Done (2026-10-21)
**Board:** The State of a venue is now a line of its own under its row and the Trading page scrolls once at itself, so the `-2015` sentence is shown whole at the Options dialog's minimum size instead of in a 75 px column cut to 12 px.
**Source:** Found while building [BOT-224](../completed/BOT-224_options_trading_shows_the_machines_public_ip_for_the_key_whitelist.md); the `public_ip_*` frames in its `BOT-224_assets/` show it.
**Risk:** 🟢 — layout of one page.
**Complexity:** S — find why the wrapped `StateBadge` in the grid gets less height than its text needs.
**Depends on:** None

---

## 1. Context and problem
`TradingSettingsView._grid` holds a wrapped `StateBadge` per venue in a narrow column; the dialog does not propagate height-for-width, so a 200-character `-2015` sentence is cut after about eight lines although the page has free space below. It happened before `BOT-224`.

## 2. Acceptance criteria
- [x] At the dialog's minimum size, a refused key's State text is readable whole, light and dark.

## 3. Design
A full-width wrapped State line under each venue's row, and the page's content in one `ContentWidthScrollArea` so a sentence taller than the dialog scrolls whole (§7).

## 3a. Reuse
`StateBadge`, `plain_label`: used. Capability catalog: no row fit a page scroll that keeps its content's width; `PlanColumn`'s `BUG-246` logic is extracted as `ContentWidthScrollArea` and catalogued, with `PlanColumn` as its first user.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/ui/settings/trading_settings_view.py` | the State is a full-width line under each venue; the page content sits in one scroll area |
| `src/support/ui_kit/content_width_scroll_area.py` | new: the minimum-width logic `PlanColumn` had, shared |
| `src/modules/bots/ui/bots_screen/plan_column.py` | extends `ContentWidthScrollArea`; behaviour unchanged |
| `src/modules/trading/ui/settings/trading_settings_presenter.py` | the failed-check status says "See its state under the key." |
| `tests/unit/modules/trading/ui/settings/test_a_refused_keys_sentence_is_shown_whole.py`, `tests/unit/support/ui_kit/test_content_width_scroll_area.py` | the sentence is shown whole; the area keeps its content's width |

## 5. Testing
A conformance-style check at the minimum size that the State label's height holds its wrapped text.

## 6. Docs touched
`.claude/rules/capabilities.md` (generated: the new capability row). `Docs/MODULES/bots/05-building-blocks.md` and `Docs/MODULES/trading`: no design change, `PlanColumn` is still one scroll holding the column.

## 7. Implementation notes (2026-10-21)
- **Measured before:** at the dialog's minimum size (631×330) the State label was 75 px wide and 12 px tall where its text needs 375 (a column squeezed by the Key and the buttons; the grid does not carry height-for-width into a dialog's minimum size).
- **Design chosen** (the task's first option, plus the scroll that makes it hold): the State is a full-width line under each venue's row (`trading_settings_view.py`, `_add_row`; the "State" heading goes, the badge carries its own word), and the page's content sits in one scroll area, `ContentWidthScrollArea` (`support/ui_kit/`), which asks its content's `heightForWidth` so a wrapped sentence has the height its text needs, and keeps the width its content needs so nothing is cut at the side. It is `PlanColumn`'s own minimum-width logic (`BUG-246`) moved to the shared class, so the two do not define it twice (`test_presenter_duplication_only_shrinks.py`). Tried and dropped: a `heightForWidth` minimum on the wrapped label itself (the dialog's layout did not re-query it at the settled width).
- **Price paid:** the page scrolls down where the dialog is shorter than its content, and the dialog can now be dragged shorter than before (its minimum height is no longer the content's, as the Bots plan column's is not).
- **Test:** `tests/unit/modules/trading/ui/settings/test_a_refused_keys_sentence_is_shown_whole.py`, the real `OptionsDialog` around the real page, at the minimum, a narrow and a wide size: the label's height holds `heightForWidth` (red before: 12 against 375 and 29 against 375).
- **Frames**, light and dark (a dark Fusion palette stands in for the Windows scheme on the offscreen platform), before and after, before at the dialog's old minimum size (631×330), after at the same size scrolled to the refused key: `BOT-225_assets/options_{before,after}_{light,dark}.png`.
