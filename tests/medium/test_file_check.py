"""The aas-test-engines check behind the AAS Test tool."""

from pathlib import Path

import pytest

from aas_editor.tools.aas_test.file_check import CHECKED_VERSION
from aas_editor.tools.aas_test.file_check import checkFile

DATA_DIR = Path(__file__).parents[1] / "data"


def test_check_labels_the_checked_version_as_v3_0() -> None:
    assert CHECKED_VERSION == "V3.0"


def test_check_reads_the_zip_when_file_is_an_aasx() -> None:
    result = checkFile(
        str(DATA_DIR / "IDTA 02002-1-0_Template_ContactInformation.aasx")
    )

    html = result.to_html()

    # An AASX opened as text would fail to decode, or be reported as no ZIP.
    assert "Cannot read" not in html
    assert "ContactInformation" in html


def test_check_reads_the_file_when_file_is_json() -> None:
    result = checkFile(
        str(DATA_DIR / "IDTA 02002-1-0_Template_ContactInformation.json")
    )

    assert "Invalid JSON" not in result.to_html()


def test_check_refuses_file_when_extension_is_unknown(tmp_path: Path) -> None:
    unknown = tmp_path / "package.txt"
    unknown.write_text("text")

    with pytest.raises(TypeError):
        checkFile(str(unknown))
