"""Every kind of file that a person can hand to the editor, through Open.

Files that the editor reads open quietly. A file that only opens in failsafe
mode asks first and then lists what was left out. A file that cannot be read at
all, such as a file of the metamodel 1 or 2, an empty file or a file with the
wrong extension, is refused with a sentence that says why, and the person is not
asked to go on. The window is the real one, the file comes from the Open
action, from the list of recent files, or from a drop.
"""

import os
from pathlib import Path
import shutil
import zipfile

from PyQt6.QtCore import QMimeData
from PyQt6.QtCore import QPoint
from PyQt6.QtCore import QPointF
from PyQt6.QtCore import Qt
from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDragEnterEvent
from PyQt6.QtGui import QDropEvent
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWidgets import QMessageBox
import pytest
from tests.conftest import TEST_DATA_DIR
from tests.usage_open_window import close_window
from tests.usage_open_window import every_action  # noqa: F401
from tests.usage_open_window import open_window
from tests.usage_open_window import screen  # noqa: F401

pytest.importorskip(
    "PyQt6.QtWebEngineWidgets", reason="PyQt6.QtWebEngineWidgets not available"
)

TEMPLATES = (
    Path(__file__).parents[2] / "src" / "aas_editor" / "submodel_templates"
)
CORPUS_ROOT = os.environ.get("AAS_CORPUS_ROOT")
SAMPLES = (
    Path(CORPUS_ROOT) / "package-explorer" / "src" if CORPUS_ROOT else None
)

V2_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<aas:aasenv xmlns:aas="http://www.admin-shell.io/aas/2/0">'
    "<aas:assetAdministrationShells/></aas:aasenv>"
)
V1_JSON = (
    '{"assetAdministrationShells": [{"identification": {"id": "urn:x", '
    '"idType": "URI"}, "idShort": "old"}], "assets": [], "submodels": []}'
)
V3_XML_WITHOUT_CONTENT = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<environment xmlns="https://admin-shell.io/aas/3/1"/>'
)

# The words of the Python libraries that a person must not have to read.
INTERNAL_WORDS = (
    "KeyError",
    "ValueError",
    "TypeError",
    "JSONDecodeError",
    "XMLSyntaxError",
    "ECMA376",
    "Traceback",
    "namespaces are not declared",
    "Wrong file type",
    "Continue anyway",
)


@pytest.fixture
def editor(qapp: object, qtbot, tmp_path: Path, screen, every_action):  # noqa: F811
    """The main window with no package, and an empty folder for the files."""
    shown = open_window(qtbot)
    shown.screen = screen
    shown.tmp_path = tmp_path
    yield shown
    close_window(shown)


def _open(editor, path: Path) -> None:
    """Opens a file as the Open action does.

    The dialog comes back when the file did not open, and the person gives up.
    """
    editor.screen.open_paths.extend([path.as_posix(), ""])
    editor.view.openPackAct.trigger()


def _make_v2_aasx(path: Path) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats'
            '.org/package/2006/content-types"><Default Extension="xml" '
            'ContentType="application/xml"/></Types>',
        )
        archive.writestr("aasx/old.aas.xml", V2_XML)
    return path


def _refused(editor) -> object:
    """The one message that refused the file."""
    (shown,) = [s for s in editor.screen.shown if s.kind == "message box"]
    return shown


REFUSED = {
    "notes.txt": ("not a file that the editor opens (.txt)", b"hello"),
    "doc.pdf": ("not a file that the editor opens (.pdf)", b"%PDF-1.4"),
    "package": (
        "not a file that the editor opens (without an extension)",
        b"{}",
    ),
    "empty.aasx": ("empty.aasx is empty", b""),
    "empty.json": ("empty.json is empty", b""),
    "empty.xml": ("empty.xml is empty", b""),
    "text.aasx": ("text.aasx is not an AASX package", b"just some words"),
    "damaged.aasx": (
        "damaged.aasx is not an AASX package",
        b"PK\x03\x04" + b"garbage" * 20,
    ),
    "broken.json": (
        "broken.json is not valid JSON",
        b'{"assetAdministrationShells": [',
    ),
    "broken.xml": ("broken.xml is not well-formed XML", b"<environment><oops>"),
    "old.xml": (
        "old.xml was made for version 2.0 of the AAS metamodel",
        V2_XML.encode(),
    ),
    "old.json": (
        "old.json was made for version 1 or 2 of the AAS metamodel",
        V1_JSON.encode(),
    ),
}


@pytest.mark.parametrize("name", list(REFUSED))
def test_a_file_that_cannot_be_read_is_refused_in_plain_words(
    name: str, editor
) -> None:
    sentence, content = REFUSED[name]
    path = editor.tmp_path / name
    path.write_bytes(content)

    _open(editor, path)

    refusal = _refused(editor)
    assert refusal.title == "Cannot open file"
    assert sentence in refusal.texts[0]
    for word in INTERNAL_WORDS:
        assert word not in refusal.texts[0]
        assert word not in refusal.texts[1]
    assert len(editor.screen.shown) == 1
    assert not editor.model.openedPacks()


def test_a_package_of_the_metamodel_2_in_an_aasx_says_the_version(
    editor,
) -> None:
    path = _make_v2_aasx(editor.tmp_path / "old.aasx")

    _open(editor, path)

    refusal = _refused(editor)
    assert (
        "old.aasx was made for version 2.0 of the AAS metamodel"
        in refusal.texts[0]
    )
    assert "version 3.0 and 3.1" in refusal.texts[1]
    assert "AASX Package Explorer" in refusal.texts[1]
    assert not editor.model.openedPacks()


def test_a_zip_without_the_parts_of_a_package_is_refused_in_plain_words(
    editor,
) -> None:
    path = editor.tmp_path / "plain.aasx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("hello.txt", "hello")

    _open(editor, path)

    assert (
        "plain.aasx is a ZIP archive, but not an AASX package"
        in (_refused(editor).texts[0])
    )


def test_a_file_that_is_gone_is_refused_and_leaves_the_recent_files(
    editor,
) -> None:
    path = editor.tmp_path / "gone.aasx"
    shutil.copy(TEST_DATA_DIR / "Requester_screwing.aasx", path)
    _open(editor, path)
    editor.view.setCurrentIndex(editor.view.model().index(0, 0))
    editor.view.closeAct.trigger()
    recent = [a for a in editor.view.recentFileActs if a.isVisible()]
    assert [a.data() for a in recent] == [path.absolute().as_posix()]
    path.unlink()
    editor.screen.forget()

    recent[0].trigger()

    assert "gone.aasx does not exist" in _refused(editor).texts[0]
    assert not [a for a in editor.view.recentFileActs if a.isVisible()]


def test_a_file_that_is_open_twice_is_said_to_be_open_and_not_read_again(
    editor,
) -> None:
    path = editor.tmp_path / "Requester_screwing.aasx"
    shutil.copy(TEST_DATA_DIR / "Requester_screwing.aasx", path)
    _open(editor, path)
    editor.screen.forget()

    editor.screen.box_answer = QMessageBox.StandardButton.Cancel
    editor.view.openPack(path.as_posix())

    assert [s.kind for s in editor.screen.shown] == ["critical"]
    assert "already opened" in editor.screen.last().text
    assert len(editor.model.openedPacks()) == 1


# What a template does on opening. Each of the three kinds is in the list of
# 260 files: it opens strictly, it opens with files that it points to missing
# from the package, or it opens only in failsafe mode.
TEMPLATE_KINDS = [
    ("IDTA 02023 _Template_CarbonFootprint.aasx", []),
    ("IDTA 02002-1-0_Template_ContactInformation.json", []),
    ("IDTA 02027-1-0_Template_AIMC.aasx", ["IssuesDialog"]),
]


# Its strict read fails on a duplicate id of a concept description.
FAILSAFE_TEMPLATE = "IDTA 02059-1-0-1_Template_AIDeployment.aasx"
# It fails in failsafe mode too, because the SDK builds an empty path.
UNREADABLE_TEMPLATE = "IDTA 02006-3-0_Template_Digital Nameplate.json"


def _template(name: str) -> Path:
    return next(TEMPLATES.rglob(name))


@pytest.mark.parametrize(("name", "dialogs"), TEMPLATE_KINDS)
def test_a_template_that_the_sdk_reads_opens_with_the_dialogs_it_needs(
    name: str, dialogs: list[str], editor
) -> None:
    path = editor.tmp_path / name
    shutil.copy(_template(name), path)

    _open(editor, path)

    assert [s.kind for s in editor.screen.shown] == dialogs
    (package,) = editor.model.openedPacks()
    assert package.partial is False


def test_a_missing_file_is_listed_with_its_path_when_the_template_opens(
    editor,
) -> None:
    name = "IDTA 02027-1-0_Template_AIMC.aasx"
    path = editor.tmp_path / name
    shutil.copy(_template(name), path)

    _open(editor, path)

    shown = editor.screen.last()
    assert shown.title == "Files missing in package"
    assert "/aasx/files/Siemens_Sentron_PAC4200.jpg" in shown.text
    assert "cannot be saved as AASX until" in shown.text


def test_a_template_that_opens_only_in_failsafe_mode_asks_then_lists_the_loss(
    editor,
) -> None:
    path = editor.tmp_path / FAILSAFE_TEMPLATE
    shutil.copy(_template(FAILSAFE_TEMPLATE), path)

    _open(editor, path)

    kinds = [s.kind for s in editor.screen.shown]
    assert kinds[0] == "message box"
    assert "Continue anyway?" in editor.screen.shown[0].texts[1]
    report = [
        s
        for s in editor.screen.shown
        if s.title == "Content left out of the package"
    ]
    assert len(report) == 1
    assert "could not be read completely" in report[0].texts[0]
    (package,) = editor.model.openedPacks()
    assert package.partial is True


def test_a_template_that_fails_in_failsafe_mode_too_is_refused_in_words(
    editor,
) -> None:
    path = editor.tmp_path / UNREADABLE_TEMPLATE
    shutil.copy(_template(UNREADABLE_TEMPLATE), path)

    _open(editor, path)

    refusal = editor.screen.last()
    assert refusal.title == "Cannot open file"
    assert "cannot be opened, not even without the parts" in refusal.texts[0]
    assert not editor.model.openedPacks()


def test_cancelling_the_question_of_a_failsafe_template_opens_nothing(
    editor,
) -> None:
    path = editor.tmp_path / FAILSAFE_TEMPLATE
    shutil.copy(_template(FAILSAFE_TEMPLATE), path)
    editor.screen.box_answer = QMessageBox.StandardButton.Cancel
    # The Open dialog comes back when the file did not open.
    editor.screen.open_paths.extend([path.as_posix(), ""])

    editor.view.openPackAct.trigger()

    assert [s.kind for s in editor.screen.shown] == ["message box"]
    assert not editor.model.openedPacks()


def test_a_failsafe_package_cannot_overwrite_its_file_and_can_be_saved_as_a_copy(
    editor,
) -> None:
    path = editor.tmp_path / FAILSAFE_TEMPLATE
    shutil.copy(_template(FAILSAFE_TEMPLATE), path)
    before = path.read_bytes()
    _open(editor, path)
    (package,) = editor.model.openedPacks()
    editor.view.setCurrentIndex(editor.view.model().index(0, 0))
    editor.screen.forget()

    editor.view.saveAct.trigger()

    assert editor.screen.last().title == "Package cannot be saved"
    assert "nothing was changed" in editor.screen.last().text
    assert path.read_bytes() == before
    copy = editor.tmp_path / "copy.aasx"
    editor.screen.save_paths.append(copy.as_posix())
    editor.view.saveAsAct.trigger()
    assert copy.exists()
    assert package.file == copy


def _drag(
    widget, paths: list[Path], rejected: list[bool] | None = None
) -> None:
    """Drops files on a widget with the events that a drag sends."""
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(p)) for p in paths])
    point = QPoint(5, 5)
    enter = QDragEnterEvent(
        point,
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(widget, enter)
    if rejected is not None:
        rejected.append(not enter.isAccepted())
    drop = QDropEvent(
        QPointF(point),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(widget, drop)


def test_dropping_files_on_the_start_opens_each_and_refuses_the_wrong_one(
    editor,
) -> None:
    good = editor.tmp_path / "Requester_screwing.aasx"
    shutil.copy(TEST_DATA_DIR / "Requester_screwing.aasx", good)
    wrong = editor.tmp_path / "notes.txt"
    wrong.write_text("hello")
    refused: list[bool] = []

    _drag(editor.window.emptyState, [wrong, good], refused)

    assert refused == [False]
    assert [p.name for p in editor.model.openedPacks()] == [
        "Requester_screwing.aasx"
    ]
    assert (
        "not a file that the editor opens (.txt)" in _refused(editor).texts[0]
    )


def test_dropping_a_file_on_the_tree_opens_it_next_to_the_open_package(
    editor,
) -> None:
    first = editor.tmp_path / "Requester_screwing.aasx"
    shutil.copy(TEST_DATA_DIR / "Requester_screwing.aasx", first)
    second = editor.tmp_path / "carbon.aasx"
    shutil.copy(
        TEST_DATA_DIR / "IDTA 02023 _Template_CarbonFootprint.aasx", second
    )
    _open(editor, first)

    _drag(editor.view.viewport(), [second])

    assert sorted(p.name for p in editor.model.openedPacks()) == [
        "Requester_screwing.aasx",
        "carbon.aasx",
    ]


def test_a_drag_of_text_is_not_accepted_by_the_tree(editor) -> None:
    first = editor.tmp_path / "Requester_screwing.aasx"
    shutil.copy(TEST_DATA_DIR / "Requester_screwing.aasx", first)
    _open(editor, first)
    mime = QMimeData()
    mime.setText("just words")
    enter = QDragEnterEvent(
        QPoint(5, 5),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    enter.ignore()

    QApplication.sendEvent(editor.view.viewport(), enter)

    assert not enter.isAccepted()


_SAMPLE_FILES = {
    "v1-json": "AasxToolkit/schemaV10/AAS_Example_v1.4.json",
    "v2-xml": "AasxToolkit/schemaV20/Example_AAS_ServoDCMotor - Simplified V2.0.xml",
    "v2-aasx": "AasxPackageExplorer/content-for-demo/Example_AAS_ServoDCMotor_21.aasx",
    "v2-aasx-festo": "BlazorUI/01_Festo_SPAU_VR3.aasx",
    "v2-aasx-timeseries": "BlazorUI/TimesSeries - 6 - admin-shell-io-2.aasx",
    "v2-json": "AasxToolkit.Tests/TestResources/AasxToolkit.Tests/sample.json",
    "v2-xml-sample": "AasxToolkit.Tests/TestResources/AasxToolkit.Tests/sample.xml",
}


@pytest.mark.parametrize("key", list(_SAMPLE_FILES))
def test_the_old_samples_of_the_package_explorer_say_that_they_are_old(
    key: str, editor
) -> None:
    if SAMPLES is None or not (SAMPLES / _SAMPLE_FILES[key]).is_file():
        pytest.skip(
            "Set AAS_CORPUS_ROOT to the folder with package-explorer/src"
        )
    source = SAMPLES / _SAMPLE_FILES[key]
    path = editor.tmp_path / source.name
    shutil.copy(source, path)

    _open(editor, path)

    refusal = _refused(editor)
    assert "was made for version" in refusal.texts[0]
    assert "AAS metamodel" in refusal.texts[0]
    assert not editor.model.openedPacks()


def test_the_battery_pass_sample_opens_in_failsafe_mode_and_lists_the_cause(
    editor,
) -> None:
    if SAMPLES is None:
        pytest.skip(
            "Set AAS_CORPUS_ROOT to the folder with package-explorer/src"
        )
    source = (
        SAMPLES
        / "AasxCore.Samm2_2_0/documentation/examples"
        / "ExampleAASX_CD_Movement_BatteryPass_Guided.aasx"
    )
    if not source.is_file():
        pytest.skip("The battery pass sample is not in the folder")
    path = editor.tmp_path / source.name
    shutil.copy(source, path)

    _open(editor, path)

    report = editor.screen.last()
    assert report.title == "Content left out of the package"
    assert "Constraint AASd-131" in report.text
    (package,) = editor.model.openedPacks()
    assert package.partial is True
