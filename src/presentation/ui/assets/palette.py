class Palette:
    """
    @brief Single source of truth for the app's black/gold palette
    ("Sagittarius Elite Warrior" theme, BOT-029 Phase 1).

    @details
    `IconTheme` (icon_loader.py) re-exports the icon-relevant subset of
    these for backward compatibility with existing QtWidgets code. QML
    screens (BOT-030) consume the same values via the engine's shared
    theme bridge (sagittarius_engine.extensions.pyside_mvc.tokens,
    configured once with this app's own palette dict via
    `configure_app_qml()` in app_bootstrapper.py) — so QtWidgets and QML
    never hardcode the same hex value in two places independently.

    Widgets get their look from `qdarktheme` (`app_bootstrapper.py:_apply_theme`), whose
    only accent override reads `Palette.ACCENT` — not a second hardcoded copy. There used
    to be a `qss/style.qss` claimed here as the one place still copying hex by hand; it
    was actually dead since the BOT-030 QML migration (nothing in `src/` loaded it —
    confirmed via `git log`/grep before removal, EPIC-005B) and has been deleted rather
    than kept "just in case", to stop a future reader trusting a comment over the code.
    """

    BG = "#0a0a0c"
    BG_SIDEBAR = "#0d0e11"
    BG_CARD = "#111318"
    BG_CARD_HEADER = "#15171d"
    BORDER = "#23262e"
    TEXT_PRIMARY = "#e8e9ec"

    ACCENT = "#F3BA2F"  # Binance yellow
    SUCCESS = "#0ECB81"  # green
    #: Amber — "something needs attention but nothing has failed". Not a new
    #: colour invented here: this is the exact literal the backtest screen's
    #: stale-results and coverage-gap banners already hardcoded
    #: (`backtest_top_panel.py`, `#d97706` border over a `#2a1c07` ground).
    #: Deliberately NOT folded into ACCENT — the preview banner right beside
    #: them uses ACCENT for "here is some information", so merging the two
    #: would make a warning indistinguishable from a notice. Required by the
    #: engine since EPIC-007B (`tokens.vocabulary.REQUIRED_COLOUR_TOKENS`).
    WARNING = "#d97706"  # amber
    DANGER = "#F6465D"  # red
    MUTED = "#848E9C"  # gray

    # State tokens (sagittarius_engine.extensions.pyside_mvc.tokens.state_tokens) —
    # this app's real values, overriding the engine's generic placeholders.
    # These are the exact literals every button/card in this app already
    # hand-rolled independently before the StatefulButton/FieldBackground/
    # BaseCard migration — kept here so migrating a screen onto those shared
    # components changes NOTHING visually, only removes the duplication.
    STATE_IDLE_BG = "#17181d"
    STATE_HOVER_BG = "#1f2127"
    #: 12%-alpha accent gold — matches Sidebar's pre-migration
    #: `Qt.rgba(0.95, 0.73, 0.18, 0.12)` (alpha 0x1F) applied to ACCENT.
    STATE_ACTIVE_TINT = "#1FF3BA2F"
    STATE_NAV_BORDER = "#2a2d36"

    #: Corner radii, measured from what this app actually draws — counted
    #: across every `border-radius:` in `src/presentation/ui` on 2026-08-25:
    #: 6px ×29, 4px ×20, 8px ×8, then a negligible tail (3/2/1/9/11px).
    #:
    #: Named by the tier each engine role reads, NOT by "small/medium/large"
    #: in the abstract: `FIELD`/`BADGE`/the button roles read `radiusSm`, and
    #: this app's fields and buttons are 6px; `SURFACE` reads `radiusMd`, and
    #: its cards are 8px. Getting these backwards is what turned Settings'
    #: cards 8px→6px and its fields 6px→4px earlier in `EPIC-007F`.
    RADIUS_SM = 6
    RADIUS_MD = 8
    #: Unused by any role today. Kept so an app value exists for the tier
    #: rather than silently falling through to the engine's 10px.
    RADIUS_LG = 10

    #: Font sizes, same method: 11px ×64, 10px ×27, 12px ×20, 13px ×8,
    #: 18px ×2, 15px ×2, 9px ×4. Note the engine's default `fontSizeLg` of
    #: 16px appears **zero** times in this app.
    #:
    #: `CAPTION`/`SECTION_LABEL` read `fontSizeSm` (11px here — the app's
    #: single most common size); `BODY_LABEL` reads `fontSizeMd` (12px, its
    #: form-field labels); `HEADING` reads `fontSizeLg` (14px, its panel and
    #: dialog titles).
    FONT_SIZE_SM = 11
    FONT_SIZE_MD = 12
    FONT_SIZE_LG = 14

    @classmethod
    def _size_tokens(cls) -> dict[str, float]:
        """The non-colour half of the vocabulary the engine reads.

        Split out from `as_ui_dict()` so the colour map stays readable and
        so a test can assert on sizes alone.
        """
        return {
            "radiusSm": cls.RADIUS_SM,
            "radiusMd": cls.RADIUS_MD,
            "radiusLg": cls.RADIUS_LG,
            "fontSizeSm": cls.FONT_SIZE_SM,
            "fontSizeMd": cls.FONT_SIZE_MD,
            "fontSizeLg": cls.FONT_SIZE_LG,
        }

    @classmethod
    def as_ui_dict(cls) -> dict[str, str | float]:
        """Maps token name -> value, for the engine's shared theme bridge.

        **Sizes are here, not just colours** (`EPIC-007F`). The engine ships
        *defaults* for spacing/radius/typography and lets an app's own values
        win on any key collision (`tokens.defaults.with_token_defaults`), but
        this app supplied none — so its widgets silently rendered on a scale
        the engine invented (`radiusLg` 10px, `fontSizeMd` 13px, `fontSizeLg`
        16px) and this app has never used anywhere.

        That is where every visual change in `EPIC-007F` came from: adopting
        an engine widget quietly reskinned the screen it landed on. The
        values below are measured from what this app actually draws, so the
        engine renders *this* design instead of its own generic one.

        Engine owns the vocabulary (which token a role reads); the app owns
        what each token means. Colours already worked this way — the required
        colour tokens have no engine default at all, by design.
        """
        return {
            **cls._size_tokens(),
            "bg": cls.BG,
            "bgSidebar": cls.BG_SIDEBAR,
            "bgCard": cls.BG_CARD,
            "bgCardHeader": cls.BG_CARD_HEADER,
            "border": cls.BORDER,
            "textPrimary": cls.TEXT_PRIMARY,
            "accent": cls.ACCENT,
            "success": cls.SUCCESS,
            "warning": cls.WARNING,
            "danger": cls.DANGER,
            "muted": cls.MUTED,
            "stateIdleBg": cls.STATE_IDLE_BG,
            "stateHoverBg": cls.STATE_HOVER_BG,
            "stateActiveTint": cls.STATE_ACTIVE_TINT,
            "stateNavBorder": cls.STATE_NAV_BORDER,
        }

    @classmethod
    def as_icon_dict(cls) -> dict[str, str]:
        """Maps icon-color token -> color, for `configure_app_qml()`'s
        `icon_palette` (used in `image://icons/<name>/<token>` URLs).
        Historically a separate, smaller vocabulary than `as_ui_dict()` —
        kept distinct rather than unified, matching the icon URLs already
        in QML (e.g. "image://icons/play/success") that only ever
        reference this subset."""
        return {
            "accent": cls.ACCENT,
            "success": cls.SUCCESS,
            "danger": cls.DANGER,
            "muted": cls.MUTED,
            "text": cls.TEXT_PRIMARY,
            "bg": cls.BG,
        }
