"""Validating a package for the dock and for the save gate."""

from dataclasses import dataclass
from dataclasses import field
import io
from pathlib import Path

from basyx.aas import model
from basyx.aas.adapter.aasx import DictSupplementaryFileContainer
import pyecma376_2
from tests.factories import make_annotated_relationship
from tests.factories import make_file_element
from tests.factories import make_property
from tests.factories import make_shell
from tests.factories import make_store
from tests.factories import make_submodel
from tests.factories import make_valid_environment
from tests.validation_factories import store_with

from aas_editor.application.save import SaveOptions
from aas_editor.application.save import check_save
from aas_editor.application.validation import save_check_for
from aas_editor.application.validation import validate_package
from aas_editor.domain.parts import Thumbnail

DOCUMENT = "/aasx/files/document.pdf"


@dataclass
class FakeSource:
    """A package with real BaSyx objects and in-memory files."""

    objects: model.SetIdentifiableStore = field(
        default_factory=model.SetIdentifiableStore
    )
    files: DictSupplementaryFileContainer = field(
        default_factory=DictSupplementaryFileContainer
    )
    thumbnail: Thumbnail | None = None
    core_properties: pyecma376_2.OPCCoreProperties | None = None
    partial: bool = False
    source_file: Path | None = None


def _source(objects: model.SetIdentifiableStore) -> FakeSource:
    return FakeSource(objects=objects)


def test_validate_package_uses_the_stored_files_of_the_source() -> None:
    source = _source(store_with(make_file_element("Manual", DOCUMENT)))
    source.files.add_file(DOCUMENT, io.BytesIO(b"pdf"), "application/pdf")

    report = validate_package(source)

    assert report.is_clean


def test_validate_package_reports_a_file_that_is_not_stored() -> None:
    source = _source(store_with(make_file_element("Manual", DOCUMENT)))

    report = validate_package(source)

    assert report.counts_by_rule() == {"EDT-MISSING-FILE": 1}


def test_validate_package_is_clean_when_the_environment_is_valid() -> None:
    assert validate_package(_source(make_valid_environment())).is_clean


def test_save_check_for_has_no_issues_when_the_report_is_clean() -> None:
    check = save_check_for(validate_package(_source(make_valid_environment())))

    assert check.blockers == ()
    assert check.warnings == ()


def test_save_check_for_blocks_when_a_file_is_missing() -> None:
    source = _source(store_with(make_file_element("Manual", DOCUMENT)))

    check = save_check_for(validate_package(source))

    assert len(check.blockers) == 1
    assert check.blockers[0].message.startswith("EDT-MISSING-FILE")
    assert check.warnings == ()


def test_save_check_for_asks_when_the_findings_are_errors_that_do_not_block() -> (
    None
):
    source = _source(store_with(make_property("X", "1")))

    check = save_check_for(validate_package(source))

    assert check.blockers == ()
    assert len(check.warnings) == 1
    assert check.warnings[0].message == (
        "AASd-002: idShort matches the pattern (1 found)"
    )
    assert check.warnings[0].details == (
        "Property 'X' of Submodel 'Submodel': The idShort 'X' must have at "
        "least two characters, start with a letter, use only letters, "
        "digits, hyphens and underscores, and not end with a hyphen",
    )


def test_save_check_for_leaves_out_warnings_of_the_rules() -> None:
    dangling = model.ReferenceElement(
        "Link",
        value=model.ModelReference(
            (model.Key(model.KeyTypes.SUBMODEL, "urn:gone"),), model.Submodel
        ),
    )

    check = save_check_for(validate_package(_source(store_with(dangling))))

    assert check.blockers == ()
    assert check.warnings == ()


def test_save_check_for_lists_at_most_ten_locations_of_a_rule() -> None:
    elements = [
        make_property(chr(ord("A") + number), "1") for number in range(12)
    ]

    check = save_check_for(validate_package(_source(store_with(*elements))))

    assert check.warnings[0].message.endswith("(12 found)")
    assert len(check.warnings[0].details) == 11
    assert check.warnings[0].details[-1] == "... and 2 more"


# ---------------------------------------------------------------------------
# The blockers agree with the save flow
# ---------------------------------------------------------------------------


def test_blocking_findings_agree_with_the_save_check_when_a_file_is_missing() -> (
    None
):
    source = _source(
        make_store(
            make_shell(),
            make_submodel(elements=[make_file_element("Manual", DOCUMENT)]),
        )
    )

    blocked_by_validation = validate_package(source).blocking
    blocked_by_save = check_save(
        source, Path("out.aasx"), SaveOptions()
    ).blockers

    assert len(blocked_by_validation) == 1
    assert len(blocked_by_save) == 1


def test_blocking_findings_agree_with_the_save_check_when_a_file_is_an_annotation() -> (
    None
):
    annotation = make_file_element("Evidence", DOCUMENT)
    source = _source(
        store_with(make_annotated_relationship("Link", [annotation]))
    )
    source.files.add_file(DOCUMENT, io.BytesIO(b"pdf"), "application/pdf")

    blocked_by_validation = validate_package(source).blocking
    blocked_by_save = check_save(
        source, Path("out.aasx"), SaveOptions()
    ).blockers

    assert len(blocked_by_validation) == 1
    assert len(blocked_by_save) == 1


def test_blocking_findings_agree_with_the_save_check_when_the_package_is_fine() -> (
    None
):
    source = _source(make_valid_environment())

    blocked_by_validation = validate_package(source).blocking
    blocked_by_save = check_save(
        source, Path("out.aasx"), SaveOptions()
    ).blockers

    assert blocked_by_validation == ()
    assert blocked_by_save == ()
