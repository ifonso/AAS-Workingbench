"""The JSON editor is coloured by the theme, and follows a switch of theme."""

from collections.abc import Iterator

from PyQt6.Qsci import QsciLexerJSON
from PyQt6.QtCore import QStandardPaths
from PyQt6.QtWidgets import QApplication
import pytest

from aas_editor.domain.design_tokens import DARK
from aas_editor.domain.design_tokens import LIGHT
from aas_editor.ui.theme import FLUENT_DARK
from aas_editor.ui.theme import FLUENT_LIGHT
from aas_editor.ui.theme import theme_manager


@pytest.fixture(autouse=True)
def native_look(qapp: QApplication) -> Iterator[None]:
    """Gives the other tests the look of the platform back."""
    QStandardPaths.setTestModeEnabled(True)
    yield
    theme_manager().reset_to_native()
    QStandardPaths.setTestModeEnabled(False)


def test_the_editor_is_light_on_the_light_theme(qapp: QApplication) -> None:
    from aas_editor.widgets.jsonEditor import JSONEditor

    theme_manager().apply(FLUENT_LIGHT)

    editor = JSONEditor()

    assert (
        editor.json_lexer.paper(QsciLexerJSON.Default).name()
        == LIGHT.bg_content
    )
    assert (
        editor.json_lexer.color(QsciLexerJSON.Default).name()
        == LIGHT.fg_primary
    )


def test_the_editor_is_dark_on_the_dark_theme(qapp: QApplication) -> None:
    from aas_editor.widgets.jsonEditor import JSONEditor

    theme_manager().apply(FLUENT_DARK)

    editor = JSONEditor()

    assert (
        editor.json_lexer.paper(QsciLexerJSON.Default).name() == DARK.bg_content
    )
    assert (
        editor.json_lexer.color(QsciLexerJSON.Default).name() == DARK.fg_primary
    )


def test_the_colors_of_the_syntax_are_those_of_the_theme(
    qapp: QApplication,
) -> None:
    from aas_editor.widgets.jsonEditor import JSONEditor

    theme_manager().apply(FLUENT_LIGHT)

    editor = JSONEditor()

    lexer = editor.json_lexer
    assert lexer.color(QsciLexerJSON.String).name() == LIGHT.status_success
    assert lexer.color(QsciLexerJSON.Number).name() == LIGHT.status_warning
    assert lexer.color(QsciLexerJSON.Property).name() == LIGHT.link
    assert lexer.paper(QsciLexerJSON.String).name() == LIGHT.bg_content


def test_an_editor_that_is_open_follows_a_switch_of_theme(
    qapp: QApplication,
) -> None:
    from aas_editor.widgets.jsonEditor import JSONEditor

    theme_manager().apply(FLUENT_LIGHT)
    editor = JSONEditor()

    theme_manager().apply(FLUENT_DARK)

    assert (
        editor.json_lexer.paper(QsciLexerJSON.Default).name() == DARK.bg_content
    )
    assert (
        editor.json_lexer.color(QsciLexerJSON.String).name()
        == DARK.status_success
    )
