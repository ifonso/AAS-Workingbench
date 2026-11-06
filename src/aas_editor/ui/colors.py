"""The colors of problems and advisories in dialogs, for light and dark themes.

The themes are style sheets of the application, and the palette does not
follow them, so a color cannot be chosen from the palette. These two have a
contrast of at least 3 to 1 on white and on the dark gray of the dark themes.
The dark red that they replace, #b00020, had 2.2 to 1 on the dark gray and
could hardly be read.
"""

PROBLEM_COLOR = "#e5484d"
"""Text that says why an input is refused."""

ADVISORY_COLOR = "#c98a10"
"""Text that advises, and does not refuse."""

PROBLEM_STYLE = f"color: {PROBLEM_COLOR};"
ADVISORY_STYLE = f"color: {ADVISORY_COLOR};"
PROBLEM_BORDER_STYLE = f"border: 1px solid {PROBLEM_COLOR};"
