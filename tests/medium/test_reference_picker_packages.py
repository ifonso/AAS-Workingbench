"""The reference picker lists the other open packages too (F-EDT-11 AC1).

A semantic id may name a concept description of another open package. The
picker lists the targets of the package being edited and of the others, says
which package each one is in, and makes the same reference as for one of this
package, an external reference to the id.
"""

from pathlib import Path
from typing import Any

from basyx.aas import model
import pytest
from tests.factories import make_concept_description
from tests.factories import make_property
from tests.factories import make_submodel
from tests.medium.conftest import ELEMENT_ID
from tests.medium.forms import answering

from aas_editor.domain.reference_picker import ReferenceRule
from aas_editor.domain.reference_picker import PickerSource

ANYTHING = ReferenceRule(True, True, (model.Referable,))
CONCEPTS = (model.ConceptDescription,)


def _objects(*concept_ids: str) -> tuple[model.Identifiable, ...]:
    return tuple(make_concept_description(c, c.upper()) for c in concept_ids)


class TestDialog:
    def _dialog(self, qtbot, others=(), **kwargs: Any):
        from aas_editor.ui.reference_picker import ReferencePickerDialog

        dialog = ReferencePickerDialog(
            _objects("mine"),
            ReferenceRule(False, True, ()),
            others=others,
            package_name="this.aasx",
            **kwargs,
        )
        qtbot.addWidget(dialog)
        return dialog

    def _others(self) -> list[PickerSource]:
        return [PickerSource("other.aasx", _objects("theirs"))]

    def test_without_other_packages_nothing_changes(self, qtbot) -> None:
        dialog = self._dialog(qtbot)

        assert dialog.visible_labels() == ["MINE"]
        assert dialog.others_box.isHidden()
        assert dialog.tree.columnCount() == 3

    def test_both_packages_are_listed_with_the_package_of_each(
        self, qtbot
    ) -> None:
        dialog = self._dialog(qtbot, self._others())

        assert dialog.visible_labels() == ["MINE", "THEIRS"]
        assert dialog.tree.headerItem().text(3) == "Package"
        packages = [dialog.tree.topLevelItem(row).text(3) for row in range(2)]
        assert packages == ["this.aasx", "other.aasx"]

    def test_the_box_takes_the_other_packages_out_of_the_list(
        self, qtbot
    ) -> None:
        dialog = self._dialog(qtbot, self._others())

        dialog.others_box.setChecked(False)

        assert dialog.visible_labels() == ["MINE"]

    def test_a_target_of_another_package_gives_an_external_reference_to_its_id(
        self, qtbot
    ) -> None:
        others = self._others()
        dialog = self._dialog(qtbot, others)

        assert dialog.select(others[0].objects[0])
        reference = dialog.reference()

        assert isinstance(reference, model.ExternalReference)
        assert [k.value for k in reference.key] == ["theirs"]
        assert dialog.ok_button.isEnabled()

    def test_the_preview_names_the_package_of_a_target_outside(
        self, qtbot
    ) -> None:
        others = self._others()
        dialog = self._dialog(qtbot, others)

        dialog.select(others[0].objects[0])

        assert "other.aasx" in dialog.problem()

    def test_the_preview_of_a_target_of_this_package_names_no_package(
        self, qtbot
    ) -> None:
        dialog = self._dialog(qtbot, self._others())

        dialog.select(dialog._objects[0])  # noqa: SLF001

        assert "not in this one" not in dialog.problem()

    def test_the_search_covers_the_other_packages(self, qtbot) -> None:
        dialog = self._dialog(qtbot, self._others())

        dialog.set_search("their")

        assert dialog.visible_labels() == ["THEIRS"]


@pytest.fixture
def two_packages(lab_class, monkeypatch: pytest.MonkeyPatch):
    """A lab with an element, and a second open package with a description."""
    from aas_editor.ui.reference_picker import ReferencePickerDialog

    class Two:
        def __init__(self) -> None:
            self.lab = lab_class(
                make_property(ELEMENT_ID, "x"),
            )
            self.lab.package.file = Path("main.aasx")
            self.theirs = make_concept_description("urn:cd:theirs", "Theirs")
            second = self.lab.shown.open_package(
                make_submodel("urn:sm:two", "Two"), self.theirs
            )
            second.file = Path("second.aasx")
            self.seen: list[list[str]] = []

        def pick_theirs(self, widget: Any) -> bool:
            def script(picker: Any) -> None:
                self.seen.append(picker.visible_labels())
                picker.select(self.theirs)

            with answering(monkeypatch, ReferencePickerDialog, script):
                return widget.choose_from_package()

    return Two


def test_the_picker_of_a_form_offers_the_description_of_the_other_package(
    two_packages,
) -> None:
    flow = two_packages()
    attrs = flow.lab.attrs()

    def fill(dialog: Any) -> None:
        assert flow.pick_theirs(dialog.inputWidget)

    flow.lab.edit_in_dialog(attrs, "semantic_id", fill)

    assert "Theirs" in flow.seen[0]
    reference = flow.lab.element().semantic_id
    assert [k.value for k in reference.key] == ["urn:cd:theirs"]
    assert isinstance(reference, model.ExternalReference)
    flow.lab.stack.undo()
    assert flow.lab.element().semantic_id is None
