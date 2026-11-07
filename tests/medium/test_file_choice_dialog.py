"""The selector of the stored files for a File element (F-EDT-11 AC5).

V3.1 has no key type for a stored file, so no reference can point at one, and
the reference picker has no file filter. The File element has a selector of its
own that lists only the stored files, and gives the name of the one chosen,
which becomes the value of the element (tested in `test_package_files_ui`).
"""

from pytestqt.qtbot import QtBot

from aas_workingbench.application.supplementary_files import StoredFileInfo
from aas_workingbench.ui.file_dialogs import FileChoiceDialog


def _infos() -> list[StoredFileInfo]:
    return [
        StoredFileInfo("/aasx/files/manual.pdf", "application/pdf", 10, ()),
        StoredFileInfo("/aasx/files/photo.png", "image/png", 20, ()),
        StoredFileInfo("/aasx/files/notes.txt", "text/plain", 30, ()),
    ]


def _listed(dialog: FileChoiceDialog) -> list[str]:
    items = (
        dialog.files_list.item(n) for n in range(dialog.files_list.count())
    )
    return [
        item.text()
        for item in items
        if item is not None and not item.isHidden()
    ]


def test_it_lists_the_stored_files_and_nothing_else(
    qapp: object, qtbot: QtBot
) -> None:
    dialog = FileChoiceDialog(_infos())
    qtbot.addWidget(dialog)

    assert _listed(dialog) == [
        "/aasx/files/manual.pdf   (application/pdf)",
        "/aasx/files/photo.png   (image/png)",
        "/aasx/files/notes.txt   (text/plain)",
    ]


def test_the_chosen_name_is_the_part_name_that_becomes_the_value(
    qapp: object, qtbot: QtBot
) -> None:
    dialog = FileChoiceDialog(_infos(), current="/aasx/files/photo.png")
    qtbot.addWidget(dialog)

    assert dialog.chosen == "/aasx/files/photo.png"


def test_the_filter_narrows_the_list_to_the_names_that_contain_the_text(
    qapp: object, qtbot: QtBot
) -> None:
    dialog = FileChoiceDialog(_infos())
    qtbot.addWidget(dialog)

    dialog.filter_edit.setText(".png")

    assert _listed(dialog) == ["/aasx/files/photo.png   (image/png)"]


def test_a_package_without_files_says_so(qapp: object, qtbot: QtBot) -> None:
    dialog = FileChoiceDialog([])
    qtbot.addWidget(dialog)

    assert not dialog.empty_label.isHidden()
    assert dialog.chosen is None


def test_no_key_type_of_v31_names_a_stored_file() -> None:
    """The probe behind the decision: a reference cannot point at a file."""
    from basyx.aas import model

    names = {key_type.name for key_type in model.KeyTypes}

    # FILE is the key type of the File *element*, the one that holds the path.
    assert model.KEY_TYPES_CLASSES[model.File] is model.KeyTypes.FILE
    assert {"SUPPLEMENTARY_FILE", "SUPPLEMENTAL_FILE", "PART"}.isdisjoint(names)
