"""The settings that new objects follow: id templates and default languages.

The settings of the application are a tracked file, so each test works on a
file of its own.
"""

from collections.abc import Callable
from collections.abc import Iterator
from pathlib import Path
import re
from typing import Any

from basyx.aas import model
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QDialog
from PyQt6.QtWidgets import QPushButton
import pytest
from tests.reference_factories import make_linked

MAIN = ("submodels", "Main")


@pytest.fixture
def settings(
    qapp: object, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Iterator[Callable[..., None]]:
    """Gives the application an empty settings file, and a way to set a value."""
    from aas_editor.settings import app_settings

    own = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr(app_settings, "SETTINGS", own)

    def put(setting: object, value: str) -> None:
        own.setValue(setting.name, value)  # type: ignore[attr-defined]

    yield put


def test_a_new_shell_dialog_follows_the_templates_of_the_settings(
    settings: Callable[..., None],
) -> None:
    from aas_editor.settings.app_settings import AppSettings
    from aas_editor.ui.create_dialogs import CreateShellDialog

    settings(AppSettings.ID_TEMPLATE_AAS, "urn:x:DDDD")
    settings(AppSettings.ID_TEMPLATE_ASSET, "urn:asset:XXXX")

    dialog = CreateShellDialog([])
    first = dialog.global_id_edit.text()
    dialog.generate_button.click()
    second = dialog.global_id_edit.text()

    assert re.fullmatch(r"urn:x:\d{4}", dialog.id_edit.text())
    assert re.fullmatch(r"urn:asset:[0-9A-F]{4}", first)
    assert re.fullmatch(r"urn:asset:[0-9A-F]{4}", second)


def test_without_templates_a_new_shell_gets_uuid_urns(
    settings: Callable[..., None],
) -> None:
    from aas_editor.ui.create_dialogs import CreateShellDialog

    dialog = CreateShellDialog([])

    assert dialog.id_edit.text().startswith("urn:uuid:")
    assert dialog.global_id_edit.text().startswith("urn:uuid:")


def test_a_template_that_cannot_make_ids_gives_uuid_urns(
    settings: Callable[..., None],
) -> None:
    from aas_editor.settings.app_settings import AppSettings
    from aas_editor.ui.create_dialogs import CreateShellDialog

    settings(AppSettings.ID_TEMPLATE_AAS, "urn:x:fixed")

    assert CreateShellDialog([]).id_edit.text().startswith("urn:uuid:")


def test_a_submodel_takes_the_template_of_its_kind(
    settings: Callable[..., None],
) -> None:
    from aas_editor.settings.app_settings import AppSettings
    from aas_editor.ui.create_dialogs import CreateSubmodelDialog

    settings(AppSettings.ID_TEMPLATE_SUBMODEL_INSTANCE, "urn:inst:DDDD")
    settings(AppSettings.ID_TEMPLATE_SUBMODEL_TEMPLATE, "urn:tmpl:DDDD")
    dialog = CreateSubmodelDialog([], [])
    instance = dialog.id_edit.text()

    dialog.kind_box.setCurrentIndex(
        dialog.kind_box.findData(model.ModellingKind.TEMPLATE)
    )
    template = dialog.id_edit.text()
    dialog.kind_box.setCurrentIndex(
        dialog.kind_box.findData(model.ModellingKind.INSTANCE)
    )

    assert re.fullmatch(r"urn:inst:\d{4}", instance)
    assert re.fullmatch(r"urn:tmpl:\d{4}", template)
    assert re.fullmatch(r"urn:inst:\d{4}", dialog.id_edit.text())


def test_an_id_the_user_typed_stays_when_the_kind_changes(
    settings: Callable[..., None],
) -> None:
    from aas_editor.settings.app_settings import AppSettings
    from aas_editor.ui.create_dialogs import CreateSubmodelDialog

    settings(AppSettings.ID_TEMPLATE_SUBMODEL_TEMPLATE, "urn:tmpl:DDDD")
    dialog = CreateSubmodelDialog([], [])
    dialog.id_edit.setText("urn:mine:1")

    dialog.kind_box.setCurrentIndex(
        dialog.kind_box.findData(model.ModellingKind.TEMPLATE)
    )

    assert dialog.id_edit.text() == "urn:mine:1"


def test_generate_in_the_rename_dialog_follows_the_template_and_renames(
    views, settings: Callable[..., None], monkeypatch: pytest.MonkeyPatch
) -> None:
    from aas_editor.settings.app_settings import AppSettings
    from aas_editor.ui.reference_actions import register_reference_actions

    register_reference_actions()
    settings(AppSettings.ID_TEMPLATE_SUBMODEL_INSTANCE, "urn:x:DDDD")
    linked = make_linked()
    shown = views()
    shown.open_package(*linked.store)
    shown.select(shown.index(*MAIN))
    shown.view.updateActions(shown.view.currentIndex())
    generated: list[str] = []

    def generate_twice(dialog: QDialog) -> None:
        for _ in range(2):
            dialog.generate_button.click()  # type: ignore[attr-defined]
            generated.append(dialog.edit.text())  # type: ignore[attr-defined]
        dialog.accept()

    monkeypatch.setattr(
        QDialog,
        "exec",
        lambda self: (generate_twice(self), self.result())[1],
    )

    shown.view.registeredActions.find("references.rename_id").trigger()

    assert all(re.fullmatch(r"urn:x:\d{4}", text) for text in generated)
    assert linked.main.id == generated[-1]
    assert linked.link.value.key[0].value == generated[-1]


def test_the_generic_dialog_of_a_concept_description_follows_its_template(
    settings: Callable[..., None],
) -> None:
    from aas_editor.settings.app_settings import AppSettings
    from aas_editor.settings.defaults import GENERATED_DEFAULTS

    settings(AppSettings.ID_TEMPLATE_CONCEPT_DESCRIPTION, "urn:cd:DDDDD")

    made = GENERATED_DEFAULTS[model.ConceptDescription]["id_"]()

    assert re.fullmatch(r"urn:cd:\d{5}", made)


class TestSettingsDialog:
    def test_the_default_languages_and_the_templates_are_saved(
        self, settings: Callable[..., None]
    ) -> None:
        from aas_editor.settings.app_settings import AppSettings
        from aas_editor.widgets.settingWidgets import SettingsDialog

        dialog = SettingsDialog()
        boxes = {
            box.title(): box
            for box in dialog.optionGroupBoxes
            if not box.title().startswith(("Standard", "Write", "Sort"))
        }
        boxes["Default languages"].fields["defaultLanguages"].setText("en, de")
        boxes["Id templates"].fields["idTemplateAas"].setText("urn:x:DDDD")

        dialog.accept()

        from aas_editor.ui.user_defaults import default_languages

        assert default_languages() == ("en", "de")
        assert AppSettings.ID_TEMPLATE_AAS.value() == "urn:x:DDDD"

    def test_a_text_that_cannot_be_used_keeps_the_dialog_open_with_its_reason(
        self, settings: Callable[..., None]
    ) -> None:
        from aas_editor.settings.app_settings import AppSettings
        from aas_editor.widgets.settingWidgets import SettingsDialog

        dialog = SettingsDialog()
        dialog.show()
        languages = next(
            box
            for box in dialog.optionGroupBoxes
            if box.title() == "Default languages"
        )
        languages.fields["defaultLanguages"].setText("en_US")

        dialog.accept()

        assert dialog.result() != QDialog.DialogCode.Accepted
        assert "use a hyphen, not an underscore" in (
            languages.problemLabel.text()
        )
        assert languages.problemLabel.isVisible()
        assert AppSettings.DEFAULT_LANGUAGES.value() == "en"


class TestDefaultLanguages:
    @pytest.fixture
    def languages(self, settings: Callable[..., None]) -> Callable[[str], None]:
        from aas_editor.settings.app_settings import AppSettings

        return lambda text: settings(AppSettings.DEFAULT_LANGUAGES, text)

    @staticmethod
    def _rows(group: Any) -> list[tuple[str, str]]:
        return [
            (
                row.paramWidgets["key"].widget.text(),
                row.paramWidgets["value"].widget.toPlainText(),
            )
            for row in group.inputWidgets
        ]

    def test_a_new_multi_language_property_has_an_empty_row_for_each_language(
        self, lab, languages
    ) -> None:
        languages("en,de")
        seen: list[list[tuple[str, str]]] = []

        def fill(form: Any) -> None:
            form.choose_type(model.MultiLanguageProperty)
            form.type_text("id_short", "Element")
            group = form.widget("value")
            seen.append(self._rows(group))
            group.inputWidgets[0].paramWidgets["value"].widget.setPlainText(
                "Hello"
            )
            group.inputWidgets[1].paramWidgets["value"].widget.setPlainText(
                "Hallo"
            )

        lab.add(fill)

        assert seen == [[("en", ""), ("de", "")]]
        assert dict(lab.element().value or {}) == {"en": "Hello", "de": "Hallo"}

    def test_without_a_setting_the_one_row_is_english(
        self, lab, settings: Callable[..., None]
    ) -> None:
        seen: list[list[tuple[str, str]]] = []

        def fill(form: Any) -> None:
            form.choose_type(model.MultiLanguageProperty)
            form.type_text("id_short", "Element")
            seen.append(self._rows(form.widget("value")))

        lab.add(fill)

        assert seen == [[("en", "")]]

    def test_a_row_without_text_is_left_out(self, lab, languages) -> None:
        languages("en,de")

        def fill(form: Any) -> None:
            form.choose_type(model.MultiLanguageProperty)
            form.type_text("id_short", "Element")
            group = form.widget("value")
            group.inputWidgets[1].paramWidgets["value"].widget.setPlainText(
                "Hallo"
            )

        lab.add(fill)

        assert dict(lab.element().value or {}) == {"de": "Hallo"}

    def test_no_text_at_all_means_no_value(self, lab, languages) -> None:
        languages("en,de")

        def fill(form: Any) -> None:
            form.choose_type(model.MultiLanguageProperty)
            form.type_text("id_short", "Element")

        lab.add(fill)

        assert lab.element().value is None

    def test_creating_a_display_name_starts_with_one_row_in_the_first_language(
        self, lab, languages
    ) -> None:
        # "Create w/ default" (F-EDT-06 AC1). The SDK refuses an empty text, so
        # the row waits for the text of the user.
        languages("de,en")
        lab.add(
            lambda form: (
                form.choose_type(model.Property),
                form.type_text("id_short", "Element"),
            )
        )
        seen: list[list[tuple[str, str]]] = []

        def fill(dialog: Any) -> None:
            group = dialog.inputWidget
            seen.append(self._rows(group))
            group.inputWidgets[0].paramWidgets["value"].widget.setPlainText(
                "Name"
            )

        lab.edit_in_dialog(lab.attrs(), "display_name", fill)

        assert seen == [[("de", "")]]
        assert dict(lab.element().display_name or {}) == {"de": "Name"}

    def test_a_new_row_takes_the_first_default_language_not_used_yet(
        self, qapp: object, languages
    ) -> None:
        from aas_editor.widgets.groupBoxes import LangStringSetGroupBox

        languages("en,de")
        box = LangStringSetGroupBox(model.MultiLanguageTextType, optional=True)

        box.findChild(QPushButton).click()
        box.findChild(QPushButton).click()
        box.findChild(QPushButton).click()

        assert [key for key, _ in self._rows(box)] == ["en", "de", ""]

    def test_the_concept_dialog_adds_rows_in_the_default_languages(
        self, qapp: object, languages
    ) -> None:
        from aas_editor.ui.iec61360_dialog import LanguageRows

        languages("de,en")
        rows = LanguageRows(18)

        rows.add_button.click()
        rows.add_button.click()
        rows.add_button.click()

        assert [language for language, _ in rows.rows()] == ["de", "en", ""]
