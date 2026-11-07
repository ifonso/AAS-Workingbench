"""The submodel templates are listed at the start and read when asked for.

Reading all of the 250 bundled files took seconds at the start of every
window. The menu "Add existing submodel" lists the files at once, and reads a
file when the user opens its submenu.
"""

from pathlib import Path
from typing import Any

from basyx.aas.adapter.json import write_aas_json_file
from PyQt6.QtWidgets import QMenu
from PyQt6.QtWidgets import QWidget
import pytest
from pytestqt.qtbot import QtBot
from tests.factories import make_store
from tests.factories import make_submodel
from tests.factories import write_aasx


def _write_json(path: Path, *ids: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    store = make_store(*(make_submodel(f"urn:{name}", name) for name in ids))
    with path.open("w", encoding="utf-8") as stream:
        write_aas_json_file(stream, store)


@pytest.fixture
def folder(tmp_path: Path) -> Path:
    """A folder of templates: one AASX, one JSON, one file that is no AAS."""
    root = tmp_path / "templates"
    sub = root / "Group" / "1" / "0"
    sub.mkdir(parents=True)
    write_aasx(sub / "Alpha.aasx", make_store(make_submodel("urn:a", "Alpha")))
    _write_json(sub / "Beta.json", "Beta", "Gamma")
    (sub / "Broken.json").write_text("{not json", encoding="utf-8")
    return root


@pytest.fixture
def read_count(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    """The files that were read, in order."""
    from aas_editor.infrastructure import submodel_templates

    reads: list[Path] = []
    real = submodel_templates.read_package

    def counting(path: Path, failsafe: bool = False) -> Any:
        reads.append(path)
        return real(path, failsafe=failsafe)

    monkeypatch.setattr(submodel_templates, "read_package", counting)
    # The view read the files itself before, with these functions. If it still
    # holds one, a read through it counts too.
    from aas_editor.treeviews import treeview_pack

    for name in ("read_package", "read_aas_json_file", "read_aas_xml_file"):
        original = getattr(treeview_pack, name, None)
        if original is not None:
            monkeypatch.setattr(
                treeview_pack,
                name,
                lambda path, *a, _o=original, **k: (
                    reads.append(Path(path)),
                    _o(path, *a, **k),
                )[1],
            )
    return reads


def test_listing_the_templates_reads_none_of_them(
    qapp: object, folder: Path, read_count: list[Path]
) -> None:
    from aas_editor.infrastructure.submodel_templates import SubmodelTemplates

    names = SubmodelTemplates(folder).files()

    assert {path.name for path in names} == {
        "Alpha.aasx",
        "Beta.json",
        "Broken.json",
    }
    assert read_count == []


def test_a_template_is_read_once(
    qapp: object, folder: Path, read_count: list[Path]
) -> None:
    from aas_editor.infrastructure.submodel_templates import SubmodelTemplates

    templates = SubmodelTemplates(folder)
    path = Path("Group/1/0/Beta.json")

    first = templates.read(path)
    second = templates.read(path)

    assert first is second
    assert first is not None
    assert first.files is None
    assert len(read_count) == 1


def test_an_aasx_template_brings_its_files(qapp: object, folder: Path) -> None:
    from aas_editor.infrastructure.submodel_templates import SubmodelTemplates

    content = SubmodelTemplates(folder).read(Path("Group/1/0/Alpha.aasx"))

    assert content is not None
    assert content.files is not None
    assert [obj.id_short for obj in content.objects] == ["Alpha"]  # type: ignore[attr-defined]


def test_a_template_that_cannot_be_read_is_skipped_and_not_tried_again(
    qapp: object, folder: Path, read_count: list[Path]
) -> None:
    from aas_editor.infrastructure.submodel_templates import SubmodelTemplates

    templates = SubmodelTemplates(folder)
    path = Path("Group/1/0/Broken.json")

    assert templates.read(path) is None
    assert templates.read(path) is None
    assert len(read_count) == 1


# The menu of the package tree view


@pytest.fixture
def view(
    qapp: object,
    qtbot: QtBot,
    monkeypatch: pytest.MonkeyPatch,
    folder: Path,
    read_count: list[Path],
) -> Any:
    from aas_editor.models import PackTreeViewItem
    from aas_editor.models import PacksTable
    from aas_editor.settings import EXTENDED_COLUMNS_IN_PACK_TABLE
    from aas_editor.settings.app_settings import DEFAULT_COLUMNS_IN_PACKS_TABLE
    from aas_editor.treeviews import treeview_pack

    monkeypatch.setattr(treeview_pack, "SUBMODEL_TEMPLATES_FOLDER", folder)
    window = QWidget()
    qtbot.addWidget(window)
    columns = list(DEFAULT_COLUMNS_IN_PACKS_TABLE)
    columns.extend(EXTENDED_COLUMNS_IN_PACK_TABLE)
    table = PacksTable(columns, PackTreeViewItem(None, None))
    tree = treeview_pack.PackTreeView(window)
    tree.setModelWithProxy(table)
    return tree


def _submenu(menu: QMenu, title: str) -> QMenu:
    for action in menu.actions():
        child = action.menu()
        if child is not None and child.title() == title:
            return child
    raise LookupError(title)


def _texts(menu: QMenu) -> list[str]:
    return [action.text() for action in menu.actions()]


def test_a_new_view_reads_no_template(
    view: Any, read_count: list[Path]
) -> None:
    assert read_count == []


def test_the_menu_lists_the_files_before_any_is_read(
    view: Any, read_count: list[Path]
) -> None:
    menu = view.addExistSubmodelsMenu

    folder_menu = _submenu(menu, "Group")

    assert sorted(
        action.menu().title()
        for action in folder_menu.actions()
        if action.menu() is not None
    ) == ["Alpha.aasx", "Beta.json", "Broken.json"]
    assert read_count == []


def test_opening_a_file_menu_reads_that_file_and_lists_its_submodels(
    view: Any, read_count: list[Path]
) -> None:
    menu = view.addExistSubmodelsMenu
    folder_menu = _submenu(menu, "Group")
    beta = _submenu(folder_menu, "Beta.json")

    beta.aboutToShow.emit()

    assert [path.name for path in read_count] == ["Beta.json"]
    assert sorted(_texts(beta)) == ["Beta", "Gamma"]


def test_a_file_menu_is_filled_once(view: Any, read_count: list[Path]) -> None:
    menu = view.addExistSubmodelsMenu
    folder_menu = _submenu(menu, "Group")
    beta = _submenu(folder_menu, "Beta.json")

    beta.aboutToShow.emit()
    beta.aboutToShow.emit()

    assert len(read_count) == 1
    assert len(beta.actions()) == 2


def test_a_file_that_cannot_be_read_says_so_in_its_menu(view: Any) -> None:
    menu = view.addExistSubmodelsMenu
    folder_menu = _submenu(menu, "Group")
    broken = _submenu(folder_menu, "Broken.json")

    broken.aboutToShow.emit()

    assert len(broken.actions()) == 1
    assert not broken.actions()[0].isEnabled()


def test_choosing_a_submodel_of_a_template_pastes_a_copy(
    view: Any, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    menu = view.addExistSubmodelsMenu
    folder_menu = _submenu(menu, "Group")
    alpha = _submenu(folder_menu, "Alpha.aasx")
    alpha.aboutToShow.emit()
    pasted: list[Any] = []
    monkeypatch.setattr(
        view, "onPaste", lambda: pasted.extend(view.treeClipboard.objects)
    )

    alpha.actions()[0].trigger()

    assert [obj.id_short for obj in pasted] == ["Alpha"]
    original = alpha.actions()[0].data()
    assert pasted[0] is not original
    assert view.treeClipboard.source is not None


def test_two_versions_of_a_file_share_one_menu_and_both_are_listed(
    view: Any, folder: Path
) -> None:
    # The folders of versions are not shown, so these two share the menu "Beta.json".
    _write_json(folder / "Group" / "2" / "0" / "Beta.json", "Delta")
    from aas_editor.treeviews.treeview_pack import PackTreeView

    again = PackTreeView(view.parent())
    group = _submenu(again.addExistSubmodelsMenu, "Group")
    beta = _submenu(group, "Beta.json")

    beta.aboutToShow.emit()

    assert sorted(_texts(beta)) == ["Beta", "Delta", "Gamma"]


def test_a_json_template_with_a_defective_submodel_still_gives_the_others(
    qapp: object, folder: Path
) -> None:
    import json

    from aas_editor.infrastructure.submodel_templates import SubmodelTemplates

    path = folder / "Group" / "1" / "0" / "Beta.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["submodels"].append({"modelType": "Submodel", "idShort": "NoId"})
    path.write_text(json.dumps(data), encoding="utf-8")

    content = SubmodelTemplates(folder).read(Path("Group/1/0/Beta.json"))

    assert content is not None
    names = sorted(obj.id_short for obj in content.objects)  # type: ignore[attr-defined]
    assert names == ["Beta", "Gamma"]
