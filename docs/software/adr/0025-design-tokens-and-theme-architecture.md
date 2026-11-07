# ADR 0025: One table of design tokens makes the style sheet, the palette, and the colors of text

**Status:** Accepted

## Context

The look of the editor came from three sources that disagreed (see the [UI and UX plan](../../planning/ui-ux-plan.md), V7). The vendored Breeze style sheets colored the widgets, `settings/colors.py` held the colors of links and changed rows as fixed `QColor`s, and `ui/colors.py` held two colors for problems and advisories, with a comment that the palette does not follow the theme. Contrast failed in several places: the action icons were 1.66 to 1 on the light theme, a link was 2.5 to 1 on the grey one, and a green for new rows was 2.07 to 1. Each fix had to be made three times.

The owner decided (2026-11-06) that the default is a light theme in the off-white and grey of Microsoft's light surfaces, that the blue accent stays because it recalls the AAS, that dark stays as a choice, that "follow the system" is not the default, and that the old themes go in the last phase of the plan.

## Decision

- **One table of tokens.** `domain/design_tokens.py` holds the colors of the light and the dark theme (`ColorTokens`), the spacing ramp, the radii, the density (the height of a row: 28, 24, 20, with 24 as the default), and the type ramp. It has no Qt, so the pairs of colors can be measured in a small test. The neutrals follow Fluent 2 (MIT). The accent (`#0f62b8`, dark `#6cb0f5`), the selection, and the status colors are the project's own.
- **A list of every pair that carries text or an icon.** `CONTRAST_PAIRS` names each foreground token on each surface that it is drawn on, with the least contrast: 4.5 for text and 3 for icons and edges of inputs. A small test measures all of them in both themes. A new token that carries text needs a pair here, and a test checks that each existing one has one. Disabled text and decorative strokes are exempt, and a stroke is never the only edge of a control.
- **Fusion everywhere.** The new themes set the Qt style `Fusion`, so that all systems share the same metrics. The native styles measured differently for the same font (a row of 16 pixels in Fusion and 18 in `windows11` and `windowsvista`). `QProxyStyle` is not used: under a style sheet the widget's style is the style of the sheet, and the proxy did not receive every primitive.
- **A generated style sheet, a palette, and a manager.** `ui/theme/app.qss.template` has names that start with a dollar sign, and `stylesheet.py` fills them from the tokens. `palette.py` makes a `QPalette` from the same tokens, so widgets that no rule reaches and the parts that Fusion draws agree with the sheet. `assets.py` draws the few images that a sheet needs (a tick, a dot, arrows) in the colors of the theme and writes them to the cache folder of the user. `manager.py` puts a theme on the application, forces the color scheme of Qt so that native parts follow it, follows the system when asked, and emits `changed`.
- **The sheet leaves out fonts and row height on purpose.** A font in a style sheet takes precedence over the zoom that the trees set in code, and Qt ignores the height of an item in a sheet, so the delegate sets it. Inter, the type ramp in use, and the delegate belong to the next phases.
- **The themes are Follow system, Light, Dark, and Native** (phase M; phase D had them as `fluent-light`, `fluent-dark`, and `fluent-system` beside the old ones). They are in View, Choose Theme, in that order, and `application/theme_choice.py` has their ids (`system`, `light`, `dark`, `native`), labels, and the default, which is Light. Following the system costs one signal. Native gives back the style and the palette that the application started with, and no style sheet. A saved name is mapped on start: `grey` and `dark` are Dark, `light` and `default` are Light (the plan had read `default` as Native, and the owner chose Light), the ids of phase D are mapped to their themes, and a name that is not known is Light. The old themes, the Breeze style sheets, are removed.
- **`ui/colors.py` reads the tokens.** The constants became functions (`problem_color()`, `advisory_color()`, `problem_style()`, `advisory_style()`, `problem_border_style()`), because a string fixed at import cannot follow a switch. A dialog reads them when it styles a widget. A widget that stays open across a switch connects `ThemeManager.changed`.
- **The API for the next phases is `current_tokens()`, `theme_manager()`, and the constants of `design_tokens`.** Read a color when drawing or styling, never at import.

## Consequences

- On a first run, and for everyone who never chose a theme, the window is light. Users who chose `grey` see Dark, in other colors, and users who chose `light` or `default` see Light.
- The tree views, tables, and tab bars take their colors from the sheet and the palette. Several things still look as before until their phases: the action icons keep their light blue (phase E), the rows keep their stripes, bold underlined names, and `LINK_BLUE`, `CHANGED_BLUE`, and `NEW_GREEN` of `settings/colors.py` (phase F), and the tab bar keeps its fixed size and its red close button (phase H). The JSON editor has fixed dark colors and is not themed.
- The whole-application sheet costs a little at a switch. A switch rewrites the application's style sheet, which the plan measured at 0.35 to 0.45 seconds with a larger sheet.
- A theme switch does not restyle a dialog that stays open unless it connects `changed`. Only the recovery warning of the main window does so far.
- Check boxes, radio buttons, and the arrows of combo boxes and spin boxes point at SVG files in the cache folder. If the folder cannot be written, those parts lose their marks until it can.
- `QStyleHints.setColorScheme` needs Qt 6.8 or later. `pyproject.toml` does not set a floor on `PyQt6`, and the plan asks for one. Setting it needs a new lock file, so it was left for the owner.
- The scheme detection, and native dialogs that follow a forced scheme, were tried only on Windows. Linux and macOS are not verified.

## Alternatives considered

- **PyQt-Fluent-Widgets.** Rejected in the plan: GPLv3 with a commercial note that is unclear for a build that someone sells, and its own widget classes would replace the legacy forms.
- **Keep the Breeze sheets and recolor them.** Rejected, and removed in phase M: 800 lines per theme and generated images, and three colors for every change.
- **Follow the system accent.** Rejected: the system accent returned `#29f7ff` on the machine of the plan, which fails on white.
- **Follow the system by default.** Rejected by the owner. It stays as a choice.
- **Put the sheet in a Python string.** Rejected: the template is easier to read and edit as a file. It needs a line in `aas_manager.spec`, which is added.
