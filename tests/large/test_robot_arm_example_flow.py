"""The robot arm example, clicked through in the real main window.

The example package is opened as a user opens it. Every element in the package
tree gets its tab, and what each tab shows is read: no Python name where a name
for a person should be, no empty cell where the model has a value. The hints of
the editor are judged too: the example has none on what it adds itself, and the
ones that remain are on elements that the IDTA templates define without a name
or a description.

Set `ARM_EXAMPLE_PICTURES` to a folder to have the test save pictures of the
window (`QWidget.grab`, offscreen) there.
"""

from collections import Counter
from collections.abc import Iterator
import os
from pathlib import Path
import re
import shutil
from types import SimpleNamespace
from typing import Any

from basyx.aas import model
from PyQt6.QtCore import QModelIndex
from PyQt6.QtCore import Qt
import pytest

pytest.importorskip(
    "PyQt6.QtWebEngineWidgets", reason="PyQt6.QtWebEngineWidgets not available"
)

PACKAGE = (
    Path(__file__).resolve().parents[2]
    / "example"
    / "robot_arm_pick_and_place.aasx"
)

# What a cell must never show: the text of a Python object.
PYTHON_NAMES = re.compile(
    r"<(class|enum|function|bound)|0x[0-9a-f]{6}|basyx\.|KeyTypes\.|"
    r"MultiLanguage\w*\(|NamespaceSet|Traceback|relativedelta\("
)

# The submodels that follow a template. The templates give their elements no
# display name and no description, so the hints about those are advice that
# this example leaves to the template.
TEMPLATE_SUBMODELS = {
    "Nameplate",
    "ContactInformations",
    "TechnicalData",
    "HandoverDocumentation",
    "HierarchicalStructures",
    "CarbonFootprint",
    "SoftwareNameplate",
    "TimeSeries",
}

# Concept descriptions are alike, so some of them are read.
CONCEPTS_READ = 12
# A tab takes about a second, and the package has more than 800 elements. This
# many of each class, in each submodel, read as well as all of them would.
ELEMENTS_READ_OF_A_KIND = 4

PICTURES = (
    ("nameplate", ("submodels", "Nameplate")),
    ("technical_data", ("submodels", "TechnicalData")),
    ("bill_of_material", ("submodels", "HierarchicalStructures", "PP6Arm")),
    ("operation_pick", ("submodels", "Capabilities", "Pick")),
    ("event", ("submodels", "CycleBehavior", "CycleCompleted")),
    ("job_poses", ("submodels", "PickAndPlaceJob", "Poses")),
    ("operational_state", ("submodels", "OperationalData", "CurrentState")),
    ("blob", ("submodels", "Documentation", "JointCalibration")),
    ("concept", ("concept_descriptions", "OperatingMode")),
)


@pytest.fixture
def editor(qapp: object, qtbot: Any, tmp_path: Path) -> Iterator[Any]:
    """The main window with a copy of the example, so that nothing is saved."""
    from aas_editor.editorApp import EditorApp

    source = tmp_path / PACKAGE.name
    shutil.copy(PACKAGE, source)
    window = EditorApp(fileToOpen=source.as_posix())
    qtbot.addWidget(window)
    window.resize(1500, 900)
    window.show()
    qtbot.waitExposed(window)
    window.mainTreeView.expandAll()

    shown = SimpleNamespace()
    shown.window = window
    shown.view = window.mainTreeView
    shown.tabs = window.mainTabWidget
    (shown.package,) = window.packTreeModel.openedPacks()
    yield shown
    shown.package.commandStack.mark_saved()
    window._recoveryTimer.stop()
    window.close()


def _walk(
    proxy: Any, parent: QModelIndex | None = None
) -> Iterator[QModelIndex]:
    parent = parent if parent is not None else QModelIndex()
    for row in range(proxy.rowCount(parent)):
        index = proxy.index(row, 0, parent)
        yield index
        yield from _walk(proxy, index)


def _path(view: Any, *names: str) -> QModelIndex:
    from aas_editor.settings.app_settings import NAME_ROLE

    proxy = view.model()
    index = proxy.index(0, 0)
    for name in names:
        view.expand(index)
        for row in range(proxy.rowCount(index)):
            child = proxy.index(row, 0, index)
            if child.data(NAME_ROLE) == name:
                index = child
                break
        else:
            raise LookupError(f"{name} below {index.data()}")
    return index


def _rows(attrs: Any) -> list[tuple[str, str, str]]:
    """Reads the name, the value and the type of every row of a tab."""
    proxy = attrs.model()
    found: list[tuple[str, str, str]] = []

    def visit(parent: QModelIndex, depth: int) -> None:
        for row in range(proxy.rowCount(parent)):
            index = proxy.index(row, 0, parent)
            cells = [
                str(proxy.index(row, column, parent).data() or "")
                for column in range(min(proxy.columnCount(parent), 3))
            ]
            cells += [""] * (3 - len(cells))
            found.append((cells[0], cells[1], cells[2]))
            if proxy.hasChildren(index) and depth < 6:
                if proxy.canFetchMore(index):
                    proxy.fetchMore(index)
                visit(index, depth + 1)

    visit(QModelIndex(), 0)
    return found


def _read_tab(editor: Any, index: QModelIndex) -> list[tuple[str, str, str]]:
    editor.tabs.openItemInNewTab(index)
    tab = editor.tabs.currentWidget()
    rows = _rows(tab.attrsTreeView)
    editor.tabs.removeTab(editor.tabs.indexOf(tab))
    tab.deleteLater()
    return rows


ELEMENT_KINDS = {
    "AnnotatedRelationshipElement",
    "BasicEventElement",
    "Blob",
    "Capability",
    "Entity",
    "File",
    "MultiLanguageProperty",
    "Operation",
    "Property",
    "Range",
    "ReferenceElement",
    "RelationshipElement",
    "SubmodelElementCollection",
    "SubmodelElementList",
}


def _submodel_of(obj: object) -> str:
    while isinstance(obj, model.Referable) and obj.parent is not None:
        if isinstance(obj, model.Submodel):
            break
        obj = obj.parent
    return getattr(obj, "id_short", None) or ""


def _is_concept_group(index: QModelIndex) -> bool:
    from aas_editor.settings.app_settings import NAME_ROLE

    parent = index.parent()
    return parent.isValid() and parent.data(NAME_ROLE) == "concept_descriptions"


def test_every_element_has_a_tab_that_reads_well(editor: Any) -> None:
    from aas_editor.settings.app_settings import OBJECT_ROLE

    problems: list[str] = []
    concepts = 0
    kinds_read: Counter[tuple[str, str]] = Counter()
    for index in _walk(editor.view.model()):
        if _is_concept_group(index):
            concepts += 1
            if concepts > CONCEPTS_READ:
                continue
        obj = index.data(OBJECT_ROLE)
        kind = (_submodel_of(obj), type(obj).__name__)
        if kinds_read[kind] >= ELEMENTS_READ_OF_A_KIND:
            continue
        kinds_read[kind] += 1
        rows = _read_tab(editor, index)
        label = f"{index.data()}"
        if not rows and isinstance(obj, model.Referable):
            problems.append(f"{label}: the tab is empty")
        for name, value, _ in rows:
            if PYTHON_NAMES.search(name) or PYTHON_NAMES.search(value):
                problems.append(f"{label}: Python name in {name!r} = {value!r}")
        shown = {name: value for name, value, _ in rows}
        if (
            isinstance(obj, model.Referable)
            and not isinstance(obj, model.Identifiable)
            and shown.get("idShort") != obj.id_short
            and not (obj.id_short or "").startswith("generated_")
        ):
            problems.append(f"{label}: idShort reads {shown.get('idShort')}")
        # An empty cell where the model has a value.
        has_value = (
            isinstance(obj, (model.Property, model.ReferenceElement))
            and obj.value is not None
        )
        if has_value and shown.get("value") in (None, "", "(not set)"):
            problems.append(f"{label}: the value reads empty")

    assert {name for _, name in kinds_read} >= ELEMENT_KINDS
    assert not problems, "\n".join(problems[:30])


def test_the_tab_of_the_package_shows_its_files_and_properties(
    editor: Any,
) -> None:
    rows = _read_tab(editor, editor.view.model().index(0, 0))
    names = {name for name, _, _ in rows}
    values = {name: value for name, value, _ in rows}

    assert "ATTRIBUTES" not in names
    assert "NSMAP" not in names
    assert values["title"].startswith("Workingbench Example Arm PP-6")
    assert values["numOfSubmodels"] == "14"
    assert "/aasx/files/pp6_datasheet.pdf" in values.values()


def test_a_duration_reads_as_a_duration(editor: Any) -> None:
    rows = _read_tab(
        editor,
        _path(editor.view, "submodels", "CycleBehavior", "CycleCompleted"),
    )
    values = {name: value for name, value, _ in rows}

    assert values["minInterval"] == "PT1S"


def test_the_hints_are_only_on_what_the_templates_leave_unnamed(
    editor: Any,
) -> None:
    from aas_editor.ui.validation_service import service_for

    hints = service_for(editor.package).hint_report
    rules = {finding.rule_id for finding in hints.findings}
    imported = [
        o.id
        for o in editor.package.concept_descriptions
        if not o.id.startswith("https://example.com/")
    ]
    elsewhere: list[str] = []
    for finding in hints.findings:
        node: Any = finding.anchor
        while node.parent is not None:
            node = node.parent
        owned = (
            isinstance(node, model.Submodel)
            and node.id_short in TEMPLATE_SUBMODELS
        ) or (
            isinstance(node, model.ConceptDescription) and node.id in imported
        )
        if not owned:
            elsewhere.append(f"{finding.rule_id} {finding.location}")

    assert rules == {
        "EDT-HINT-DESCRIPTION-MISSING",
        "EDT-HINT-DESCRIPTION-ONE-LANGUAGE",
        "EDT-HINT-DISPLAY-NAME-MISSING",
        "EDT-HINT-DISPLAY-NAME-ONE-LANGUAGE",
    }
    assert elsewhere == []


def test_the_window_can_be_drawn_with_the_example_open(
    editor: Any, qtbot: Any
) -> None:
    folder = os.environ.get("ARM_EXAMPLE_PICTURES")
    drawn = 0
    for name, path in PICTURES:
        editor.tabs.openItemInNewTab(_path(editor.view, *path))
        qtbot.wait(30)
        picture = editor.window.grab()
        assert not picture.isNull()
        assert picture.width() >= 1000
        if folder:
            Path(folder).mkdir(parents=True, exist_ok=True)
            assert picture.save((Path(folder) / f"{name}.png").as_posix())
        drawn += 1

    assert drawn == len(PICTURES)
    assert editor.view.model().data(
        editor.view.model().index(0, 0), Qt.ItemDataRole.DisplayRole
    )
