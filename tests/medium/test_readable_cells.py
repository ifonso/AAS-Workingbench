"""A cell reads names and counts, and what is edited stays the value itself."""

from typing import Any

from basyx.aas import model
from basyx.aas.model import datatypes
from PyQt6.QtCore import QModelIndex
from PyQt6.QtCore import Qt
import pytest
from tests.factories import make_blob
from tests.factories import make_property
from tests.factories import make_submodel

FILE = "/aasx/files/data.bin"
CONTENT = b"\x00\x01\x02hello"


@pytest.fixture
def shown(views: Any) -> Any:
    speed = make_property("Speed")
    speed.qualifier.add(model.Qualifier("Cardinality", datatypes.String, "One"))
    speed.qualifier.add(model.Qualifier("Unit", datatypes.String, "rpm"))
    speed.extension.add(model.Extension("Origin", datatypes.String, "sheet"))
    package_views = views()
    package_views.open_package(
        make_submodel(elements=[speed, make_blob("Cert", CONTENT)]),
        files={FILE: (CONTENT, "application/x-binary")},
    )
    return package_views


def _value_cell(attrs: Any, *names: str) -> QModelIndex:
    from aas_editor.settings.app_settings import NAME_ROLE

    proxy = attrs.model()
    index = QModelIndex()
    for wanted in names:
        for row in range(proxy.rowCount(index)):
            candidate = proxy.index(row, 0, index)
            if candidate.data(NAME_ROLE) == wanted:
                index = candidate
                break
        else:
            raise LookupError(wanted)
    return index.siblingAtColumn(1)


def test_a_set_of_qualifiers_reads_a_count_and_edits_as_the_set(
    shown: Any,
) -> None:
    attrs = shown.attrs_view("submodels", "Submodel", "Speed")

    cell = _value_cell(attrs, "qualifier")

    assert cell.data(Qt.ItemDataRole.DisplayRole) == "2 qualifiers"
    edited = cell.data(Qt.ItemDataRole.EditRole)
    assert isinstance(edited, model.NamespaceSet)
    assert [q.type for q in edited] == ["Cardinality", "Unit"]


def test_an_extension_reads_its_name_and_value(shown: Any) -> None:
    attrs = shown.attrs_view("submodels", "Submodel", "Speed")

    assert _value_cell(attrs, "extension").data() == "1 extension"
    assert _value_cell(attrs, "extension", "Extension 0").data() == (
        "Origin: sheet"
    )


def test_a_blob_reads_its_size_and_content_type_and_edits_the_bytes(
    shown: Any,
) -> None:
    attrs = shown.attrs_view("submodels", "Submodel", "Cert")

    cell = _value_cell(attrs, "value")

    assert cell.data(Qt.ItemDataRole.DisplayRole) == (
        "8 bytes, application/octet-stream"
    )
    assert cell.data(Qt.ItemDataRole.EditRole) == CONTENT


def test_a_stored_file_reads_its_size_and_media_type_and_edits_the_bytes(
    shown: Any,
) -> None:
    attrs = shown.attrs_view("fileStore", FILE)

    cell = _value_cell(attrs, "value")

    assert cell.data(Qt.ItemDataRole.DisplayRole) == (
        "8 bytes, application/x-binary"
    )
    assert cell.data(Qt.ItemDataRole.EditRole) == CONTENT


def test_no_cell_of_a_tab_reads_like_python(shown: Any) -> None:
    attrs = shown.attrs_view("submodels", "Submodel", "Speed")
    attrs.expandAll()
    proxy = attrs.model()
    texts: list[str] = []

    def collect(parent: QModelIndex) -> None:
        for row in range(proxy.rowCount(parent)):
            index = proxy.index(row, 1, parent)
            texts.append(str(index.data(Qt.ItemDataRole.DisplayRole)))
            collect(proxy.index(row, 0, parent))

    collect(QModelIndex())

    assert not [t for t in texts if "Qualifier(" in t or "Extension(" in t]
    assert not [t for t in texts if t.startswith(("{", "(Key", "[Key"))]
