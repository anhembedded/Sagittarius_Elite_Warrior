---
name: UI Presentation Rule
description: Presentation layer — declarative views, reactive bindings, responsive sizing, a single source of truth for shared layout, injection defense, icons, and the preview convention.
trigger: on_file_change
patterns:
  - <SRC_DIR>/presentation/**
---

# UI & PRESENTATION RULES

The Coordinator pattern and everything about background work is **not** here —
see [`async-action-rule.md`](async-action-rule.md): that is a rule about action
ownership, not about presentation.

---

## 1. Separate logic from UI, absolutely

- **Views are purely declarative.** A view file (template/markup/QML/JSX) only
  defines layout, theme bindings, micro-animations, and interaction signals.
- **No complex logic inside the view.** Calculations, data transformations,
  domain validation and state machines belong in the ViewModel / Presenter /
  Domain. View-local helpers (focus handling, invoking a slot, resetting an
  already-rendered input) are permitted only when they **don't** duplicate a
  business rule and **don't** become a second source of state.
- **One-way command dispatch:** the UI triggers actions by calling ViewModel
  methods; the Presenter handles the logic and updates ViewModel properties.

## 2. Reactive bindings, not manual assignment

Bind UI element properties directly to ViewModel properties and to the theme.
**Never break a binding with an imperative assignment inside a signal
handler** — that is how a value silently detaches from its source of truth.

## 3. Break components down

- Treat **300 lines** as a mandatory review threshold for a view file, not as a
  mechanical failure count.
- **Anything shareable must be built as shared**, not as a "nearly identical"
  copy. Shared components live in the shared directory; a component used by a
  single screen lives with that screen (see "not in the same directory",
  [`architecture-rule.md`](architecture-rule.md) §5).
- **Adding a feature to an existing widget always starts with the question:**
  does the current design still hold, or is this the moment to redesign?

## 4. Naming & testability

- **Every interactive element MUST have a stable identifier** (`objectName`,
  `data-testid`…). It is usually the **only** thing integration/E2E tests can
  target. **Never** use a generated index as the only test identity.
- Keep property and signal naming consistent across the repository; name signals
  as **verb phrases** describing what happened (`runRequested`, `chosen`).

## 5. Responsive — no rigid dimensions

- **Never hard-code fixed `width`/`height`** on modals, dialogs, popups or
  cards. Use preferred sizes clamped to the available bounds.
- Use the framework's layout managers instead of manual coordinates.
- Inner scrollable containers must declare **clipping** and responsive content
  widths.

## 6. Tables/grids: column widths are a single source of truth

For every table with a header, column widths MUST be declared **centrally** and
bound to **both** the header and the row delegate — that is the only way to
guarantee alignment stays exact through window resizes and splitter drags.

## 7. Injection defense

Always force **plain-text** rendering for any element displaying dynamic or
externally sourced data (logs, error messages, user-entered names, API data).
Anywhere rich text/HTML is rendered from uncontrolled data is a UI injection
hole.

## 8. Icons & theming

- Icons are **standardised vectors** in an asset directory, not raw emoji.
- Render icons through **one** centralised theme-tinting mechanism, so changing
  the theme doesn't mean editing every usage.

## 9. Micro-animations

Smooth transitions with short animations (150-250ms) on colour/opacity/size.
Never block the UI thread to run one.

## 10. The preview convention — mandatory for every UI package

Every UI package (each screen, each shared component) MUST have a standalone
preview entry point (`preview.py` exposing `build_preview()`, a story, or the
equivalent) for fast rendering **without booting the whole application**.

Along with:
- a one-command way to run a preview, with a `--list` of available targets;
- a **guard test** verifying every UI package has one — without it, this
  convention rots within weeks.

## 11. UI tests

- **ViewModel tests need no GUI** — most of a widget's coverage belongs here,
  not in a rendered test.
- **Render tests are deliberately thin:** they prove only that the view **loads**
  and that its bindings point at properties the ViewModel actually has — exactly
  the class of error linters and type checkers cannot see. Don't duplicate
  ViewModel-level assertions there.
- **Never hold a reference to a delegate/child across a refresh.** Many
  frameworks destroy and recreate every delegate when the model changes — look
  it up again after each refresh.
- **Simulate real input** (the framework's test-input API) rather than invoking
  a signal by hand with a guessed signature.
- **A failed load must raise, not render an empty box.** Every view host must
  turn a failed load into an explicit exception — render-and-hope turns a syntax
  error into a blank screen nobody investigates.
