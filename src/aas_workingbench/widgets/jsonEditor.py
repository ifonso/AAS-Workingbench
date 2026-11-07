#  Copyright (C) 2025  Igor Garmaev, garmaev@gmx.net
#
#  This program is made available under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
#  without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
#  A copy of the GNU General Public License is available at http://www.gnu.org/licenses/
"""An editor for JSON, coloured with the design tokens of the theme in use.

The colours are read when the editor is made and again after every switch of
theme, so an editor that stays open follows the theme (ADR 0025). Each colour
is a token that has the contrast of text on its surface, as checked in
`tests/small/test_design_tokens.py`:

* text and the paper behind it: `fg_primary` on `bg_content`,
* the line numbers and the fold margin: `fg_muted` on `bg_chrome`,
* names of properties: `link`, strings: `status_success`,
  numbers: `status_warning`, `true`, `false` and `null`: `status_error`,
* comments: `fg_muted`.
"""

from PyQt6.Qsci import QsciLexerJSON, QsciScintilla
from PyQt6.QtGui import QColor

from aas_workingbench.domain.design_tokens import ColorTokens
from aas_workingbench.ui.theme import current_tokens, theme_manager

# The number of styles of the JSON lexer that the paper and the text colour are
# set on, so that no style keeps the colours that the lexer starts with.
_STYLE_COUNT = 20


class JSONEditor(QsciScintilla):
    def __init__(self, parent=None):
        super().__init__(parent)
        # 1. Set the Lexer (Syntax Highlighting)
        # QScintilla has a built-in JSON lexer
        self.json_lexer = QsciLexerJSON()
        self.setLexer(self.json_lexer)

        # 2. Line Numbers (Margin 0)
        # We tell it to display numbers in the first margin
        self.setMarginType(0, QsciScintilla.MarginType.NumberMargin)
        self.setMarginWidth(0, "0000")  # Initial width for 4 digits

        # 3. Indentation & Tabs
        self.setTabWidth(2)
        self.setIndentationsUseTabs(False)
        self.setAutoIndent(True)

        # 4. Brace Matching
        self.setBraceMatching(QsciScintilla.BraceMatch.SloppyBraceMatch)

        # 5. Folding (Optional - allows collapsing objects)
        self.setFolding(QsciScintilla.FoldStyle.PlainFoldStyle)

        # 6. Colours of the theme in use, and of the next ones
        self.apply_theme()
        theme_manager().changed.connect(self.apply_theme)

    def apply_theme(self) -> None:
        """Colours the editor with the tokens of the theme in use."""
        tokens = current_tokens()
        paper = QColor(tokens.bg_content)
        text = QColor(tokens.fg_primary)

        # 1. Set Main Editor Colors
        self.setColor(text)
        self.setPaper(paper)
        self.setCaretForegroundColor(text)
        self.setSelectionBackgroundColor(QColor(tokens.bg_selected))
        self.setSelectionForegroundColor(text)
        self.setMatchedBraceBackgroundColor(QColor(tokens.bg_selected))
        self.setMatchedBraceForegroundColor(text)
        self.setUnmatchedBraceBackgroundColor(QColor(tokens.bg_error))
        self.setUnmatchedBraceForegroundColor(QColor(tokens.status_error))

        # 2. Set Margin (Line Number) Colors
        chrome = QColor(tokens.bg_chrome)
        muted = QColor(tokens.fg_muted)
        self.setMarginsBackgroundColor(chrome)
        self.setMarginsForegroundColor(muted)
        self.setFoldMarginColors(chrome, chrome)

        # 3. Configure Lexer Styles (JSON specific)
        self._color_lexer(tokens, paper, text)

    def _color_lexer(
        self, tokens: ColorTokens, paper: QColor, text: QColor
    ) -> None:
        lexer = self.json_lexer
        lexer.setDefaultPaper(paper)
        lexer.setDefaultColor(text)

        # Every style slot (whitespace, default, unclosed strings and so on)
        # gets the paper and the text colour first.
        for style in range(_STYLE_COUNT):
            lexer.setPaper(paper, style)
            lexer.setColor(text, style)

        def set_style(style: int, color: str, bold: bool = False) -> None:
            lexer.setColor(QColor(color), style)
            font = lexer.font(style)
            font.setBold(bold)
            lexer.setFont(font, style)

        set_style(QsciLexerJSON.Number, tokens.status_warning)
        set_style(QsciLexerJSON.String, tokens.status_success)
        # The key of a property ("key": ) is a style of its own.
        set_style(QsciLexerJSON.Property, tokens.link)
        set_style(QsciLexerJSON.Keyword, tokens.status_error, bold=True)
        set_style(QsciLexerJSON.Operator, tokens.fg_secondary)
        set_style(QsciLexerJSON.CommentBlock, tokens.fg_muted)
        set_style(QsciLexerJSON.CommentLine, tokens.fg_muted)
