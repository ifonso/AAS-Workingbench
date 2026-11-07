"""The owner's capability request file, opened, looked through, edited and saved.

`Requester_screwing.aasx` has the first relationship types of the AASX format,
the ones that start with `www.`. It holds one shell, one submodel with a deep
tree of collections, and 34 concept descriptions. It is opened through the File
menu as a person opens it. Every row is selected so that its tab is built, one
value is changed, the file is saved, and what is on disk is compared with the
original through the SDK.
"""

from collections import Counter
import json
from pathlib import Path
import shutil
import zipfile

from basyx.aas import model
from basyx.aas.adapter.json import AASToJsonEncoder
from PyQt6.QtCore import QModelIndex
from PyQt6.QtCore import Qt
import pytest
from tests.conftest import TEST_DATA_DIR
from tests.usage_open_window import all_rows
from tests.usage_open_window import close_window
from tests.usage_open_window import column_of
from tests.usage_open_window import every_action  # noqa: F401
from tests.usage_open_window import open_window
from tests.usage_open_window import row_named
from tests.usage_open_window import screen  # noqa: F401

pytest.importorskip(
    "PyQt6.QtWebEngineWidgets", reason="PyQt6.QtWebEngineWidgets not available"
)

PACKAGE = "Requester_screwing.aasx"
SUBMODEL = ("submodels", "CapabilityDescription")
THREAD_SYSTEM = (
    *SUBMODEL,
    "CapabilitySet",
    "ScrewingRequestedContainer",
    "ScrewingFastenerRequirementSet",
    "ThreadSystemContainer",
    "ThreadSystem",
)


def _dump(objects: object) -> dict[str, str]:
    """The SDK's JSON of every object, by id, to compare two packages."""
    return {
        obj.id: json.dumps(obj, cls=AASToJsonEncoder, sort_keys=True)  # pyright: ignore[reportAttributeAccessIssue]
        for obj in objects  # pyright: ignore[reportGeneralTypeIssues]
    }


def _elements_below(parent: object) -> int:
    """Counts the submodel elements below a submodel or a container."""
    children = (
        parent.submodel_element  # pyright: ignore[reportAttributeAccessIssue]
        if isinstance(parent, model.Submodel)
        else parent.value  # pyright: ignore[reportAttributeAccessIssue]
    )
    return sum(
        1
        + (
            _elements_below(child)
            if isinstance(
                child,
                (model.SubmodelElementCollection, model.SubmodelElementList),
            )
            else 0
        )
        for child in children
    )


@pytest.fixture
def editor(
    qapp: object,
    qtbot,
    tmp_path: Path,
    screen,  # noqa: F811
    every_action,  # noqa: F811
):
    """The main window with a copy of the file, opened from the File menu."""
    source = tmp_path / PACKAGE
    shutil.copy(TEST_DATA_DIR / PACKAGE, source)
    original = tmp_path / "original.aasx"
    shutil.copy(source, original)
    shown = open_window(qtbot)
    screen.open_paths.append(source.as_posix())

    shown.view.openPackAct.trigger()

    shown.source = source
    shown.original = original
    shown.screen = screen
    shown.tmp_path = tmp_path
    (shown.package,) = shown.model.openedPacks()
    shown.view.expandAll()
    yield shown
    close_window(shown)


def _enter(view: object, column: str, text: str, *names: str) -> bool:
    cell = row_named(view, *names).siblingAtColumn(column_of(view, column))
    return view.model().setData(cell, text, Qt.ItemDataRole.EditRole)  # pyright: ignore[reportAttributeAccessIssue]


def _words_of_tab(tab: object) -> list[str]:
    """Every text that the attribute view of a tab shows, in all columns."""
    view = tab.attrsTreeView  # pyright: ignore[reportAttributeAccessIssue]
    proxy = view.model()
    words: list[str] = []

    def walk(parent: QModelIndex) -> None:
        for row in range(proxy.rowCount(parent)):
            for column in range(proxy.columnCount(parent)):
                cell = proxy.index(row, column, parent)
                words.append(str(cell.data(Qt.ItemDataRole.DisplayRole)))
            walk(proxy.index(row, 0, parent))

    walk(QModelIndex())
    return words


def test_the_file_with_old_relationship_types_opens_without_a_question(
    editor,
) -> None:
    assert editor.screen.shown == []
    assert editor.package.partial is False
    assert editor.package.loadReport.issues == ()
    assert editor.package.file == editor.source.absolute()


def test_every_object_of_the_file_shows_in_the_tree(editor) -> None:
    rows = list(all_rows(editor.view))

    # The package, its four groups, the shell, the submodel, 65 elements below
    # it, and 34 concept descriptions.
    assert len(rows) == 1 + 4 + 1 + 1 + 65 + 34
    assert [row.data(Qt.ItemDataRole.DisplayRole) for row in rows[:6]] == [
        "Requester_screwing.aasx",
        "Asset Administration Shells",
        "BoardUMB",
        "Submodels",
        "CapabilityDescription",
        "CapabilitySet",
    ]
    (submodel,) = editor.package.submodels
    assert _elements_below(submodel) == 65
    assert len(list(editor.package.concept_descriptions)) == 34


def test_every_row_opens_a_tab_that_shows_no_python_name(editor) -> None:
    from aas_editor.domain.attribute_display import is_generated_id_short

    opened: list[str] = []
    leaked: list[str] = []

    for row in all_rows(editor.view):
        editor.view.setCurrentIndex(row)
        tab = editor.tabs.currentWidget()
        assert QModelIndex(tab.packItem).siblingAtColumn(0) == row
        opened.append(row.data(Qt.ItemDataRole.DisplayRole))
        leaked += [
            word
            for word in _words_of_tab(tab)
            if is_generated_id_short(word)
            or "Traceback" in word
            or "object at 0x" in word
            or "<class" in word
        ]

    assert len(opened) == 106
    assert leaked == []


def test_a_changed_value_is_saved_and_the_rest_is_as_the_sdk_read_it(
    editor,
) -> None:
    from aas_editor.infrastructure.package_io import read_package

    before = read_package(editor.original)
    assert _enter(editor.view, "value", "ISO metric", *THREAD_SYSTEM)
    editor.view.setCurrentIndex(row_named(editor.view, *THREAD_SYSTEM))
    assert editor.package.changed

    editor.view.saveAct.trigger()

    assert not editor.package.changed
    after = read_package(editor.source)
    assert after.partial is False
    assert after.load_report.issues == ()
    changed = {
        key
        for key, text in _dump(after.objects).items()
        if _dump(before.objects)[key] != text
    }
    assert changed == {
        "https://example.com/ids/sm/capability-description/f-res-pos-requester/boardumb"
    }
    assert _dump(after.objects).keys() == _dump(before.objects).keys()
    (submodel,) = [o for o in after.objects if isinstance(o, model.Submodel)]
    value = submodel.get_referable(
        [
            "CapabilitySet",
            "ScrewingRequestedContainer",
            "ScrewingFastenerRequirementSet",
            "ThreadSystemContainer",
            "ThreadSystem",
        ]
    )
    assert value.value == "ISO metric"  # pyright: ignore[reportAttributeAccessIssue]


def test_the_saved_file_has_the_current_relationship_types_and_opens_again(
    editor,
) -> None:
    editor.view.setCurrentIndex(row_named(editor.view, *THREAD_SYSTEM))
    assert _enter(editor.view, "value", "ISO metric", *THREAD_SYSTEM)
    editor.view.saveAct.trigger()

    with zipfile.ZipFile(editor.source) as archive:
        names = archive.namelist()
        root_relations = archive.read("_rels/.rels").decode()

    assert "aasx/aasx-origin" in names
    assert "www.admin-shell.io" not in root_relations
    editor.view.setCurrentIndex(row_named(editor.view))
    editor.view.closeAct.trigger()
    assert not editor.model.openedPacks()

    editor.screen.open_paths.append(editor.source.as_posix())
    editor.view.openPackAct.trigger()
    editor.view.expandAll()
    (package,) = editor.model.openedPacks()

    assert editor.screen.shown == []
    assert len(list(all_rows(editor.view))) == 106
    assert len(list(package.concept_descriptions)) == 34


def test_validation_finds_no_error_and_its_hints_are_true(
    editor, qtbot
) -> None:
    from aas_editor.ui.validation_service import service_for

    controller = editor.window.validationController
    editor.view.setCurrentIndex(row_named(editor.view))
    qtbot.wait(300)
    counts = controller.status.counts
    kinds = Counter(
        finding.rule_id
        for finding in service_for(editor.package).hint_report.findings
    )

    controller.dock.toggleViewAction().trigger()
    qtbot.wait(300)

    # The panel lists the rules of the specification, and there is no finding.
    assert controller.dock.counts_label.text() == "No findings"
    assert controller.dock.visible_findings() == []
    assert (counts.errors, counts.warnings) == (0, 0)
    # The status bar has no count for the package. The Hints view has it.
    assert controller.status.hints_button.isHidden()
    controller.dock.show_hints()
    assert controller.dock.hints_view.shown_count == 202
    assert {
        g.rule_id: g.count for g in controller.dock.hints_view.groups
    } == dict(kinds)
    # Counted again from the SDK objects: 67 without a display name, 34 with a
    # display name in one language (the concept descriptions), 2 without a
    # description (the shell and the item of the list), 99 with a description
    # in one language.
    assert kinds == Counter(
        {
            "EDT-HINT-DISPLAY-NAME-MISSING": 67,
            "EDT-HINT-DISPLAY-NAME-ONE-LANGUAGE": 34,
            "EDT-HINT-DESCRIPTION-MISSING": 2,
            "EDT-HINT-DESCRIPTION-ONE-LANGUAGE": 99,
        }
    )


def test_the_hint_of_the_shell_is_on_its_tab(editor) -> None:
    editor.view.setCurrentIndex(row_named(editor.view, "shells", "BoardUMB"))

    lines = editor.tabs.currentWidget().hintsBar.lines

    # The shell has neither a display name nor a description.
    assert lines == [
        "2 hints about displayName, description. Hover to read them"
    ]
