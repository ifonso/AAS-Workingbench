"""The save gate: lost content and the errors of the rules in one check (D5)."""

from collections.abc import Iterator
from dataclasses import dataclass
from dataclasses import field
import io
from pathlib import Path

from basyx.aas import model
from basyx.aas.adapter.aasx import DictSupplementaryFileContainer
from tests.factories import make_annotated_relationship
from tests.factories import make_file_element
from tests.factories import make_property
from tests.factories import make_valid_environment
from tests.validation_factories import store_with

from aas_workingbench.application.save import SaveCheck
from aas_workingbench.application.save import SaveOptions
from aas_workingbench.application.save import SaveStatus
from aas_workingbench.application.save import check_save
from aas_workingbench.application.save import save
from aas_workingbench.application.validation import SaveGate
from aas_workingbench.domain.load_report import LoadReport
from aas_workingbench.domain.parts import CoreProperties
from aas_workingbench.domain.parts import Thumbnail
from aas_workingbench.domain.validation import Finding
from aas_workingbench.domain.validation import Rule
from aas_workingbench.domain.validation.context import ValidationContext
from aas_workingbench.domain.validation.rules.identity import (
    RULES as IDENTITY_RULES,
)

DOCUMENT = "/aasx/files/document.pdf"
OPTIONS = SaveOptions()
TARGET = Path("out.aasx")
JSON_TARGET = Path("out.json")


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
    core_properties: CoreProperties | None = None
    partial: bool = False
    source_file: Path | None = None
    load_report: LoadReport = field(default_factory=LoadReport)


class RecordingWriter:
    def __init__(self) -> None:
        self.targets: list[Path] = []

    def __call__(
        self, target: Path, source: object, options: SaveOptions
    ) -> None:
        self.targets.append(target)


def _with_one_letter_id_short() -> FakeSource:
    return FakeSource(objects=store_with(make_property("X", "1")))


# ---------------------------------------------------------------------------
# Blockers
# ---------------------------------------------------------------------------


def test_gate_lists_a_missing_file_once_when_it_blocks() -> None:
    source = FakeSource(
        objects=store_with(make_file_element("Manual", DOCUMENT))
    )

    check = SaveGate().check(source, TARGET, OPTIONS)

    assert check == check_save(source, TARGET, OPTIONS)
    assert len(check.blockers) == 1


def test_gate_lists_a_file_under_an_annotation_once_when_it_blocks() -> None:
    annotation = make_file_element("Evidence", DOCUMENT)
    source = FakeSource(
        objects=store_with(make_annotated_relationship("Link", [annotation]))
    )
    source.files.add_file(DOCUMENT, io.BytesIO(b"pdf"), "application/pdf")

    check = SaveGate().check(source, TARGET, OPTIONS)

    assert len(check.blockers) == 1
    assert check.blockers == check_save(source, TARGET, OPTIONS).blockers


def test_gate_does_not_block_a_missing_file_when_the_target_is_json() -> None:
    source = FakeSource(
        objects=store_with(make_file_element("Manual", DOCUMENT))
    )

    check = SaveGate().check(source, Path("out.json"), OPTIONS)

    assert check.blockers == ()


# ---------------------------------------------------------------------------
# Errors that the user may confirm
# ---------------------------------------------------------------------------


def test_gate_has_nothing_to_say_when_the_package_is_valid() -> None:
    source = FakeSource(objects=make_valid_environment())

    assert SaveGate().check(source, TARGET, OPTIONS) == SaveCheck()


def test_gate_asks_when_a_rule_finds_an_error_that_does_not_block() -> None:
    check = SaveGate().check(_with_one_letter_id_short(), TARGET, OPTIONS)

    assert check.blockers == ()
    assert [issue.message for issue in check.warnings] == [
        "AASd-002: idShort matches the pattern (1 found)"
    ]


def test_gate_does_not_ask_when_a_rule_finds_only_a_warning() -> None:
    dangling = model.ReferenceElement(
        "Link",
        value=model.ModelReference(
            (model.Key(model.KeyTypes.SUBMODEL, "urn:gone"),), model.Submodel
        ),
    )
    source = FakeSource(objects=store_with(dangling))

    assert SaveGate().check(source, TARGET, OPTIONS) == SaveCheck()


def test_gate_lists_lost_content_before_the_errors_of_the_rules() -> None:
    source = _with_one_letter_id_short()
    source.files.add_file(DOCUMENT, io.BytesIO(b"pdf"), "application/pdf")

    check = SaveGate().check(source, JSON_TARGET, OPTIONS)

    assert check.warnings[0].message.startswith(
        "JSON files cannot hold supplementary files"
    )
    assert check.warnings[1].message.startswith("AASd-002")


# ---------------------------------------------------------------------------
# Asking once
# ---------------------------------------------------------------------------


def test_gate_does_not_ask_again_for_errors_the_user_confirmed() -> None:
    gate = SaveGate()
    source = _with_one_letter_id_short()
    asked: list[SaveCheck] = []

    def ask(check: SaveCheck) -> bool:
        asked.append(check)
        return True

    first = save(
        source,
        TARGET,
        OPTIONS,
        RecordingWriter(),
        lambda c: gate.confirm(c, ask),
        gate.check,
    )
    second = save(
        source,
        TARGET,
        OPTIONS,
        RecordingWriter(),
        lambda c: gate.confirm(c, ask),
        gate.check,
    )

    assert first.status is SaveStatus.SAVED
    assert second.status is SaveStatus.SAVED
    assert len(asked) == 1


def test_gate_asks_again_when_the_user_cancelled() -> None:
    gate = SaveGate()
    source = _with_one_letter_id_short()
    asked: list[SaveCheck] = []

    def ask(check: SaveCheck) -> bool:
        asked.append(check)
        return False

    for _ in range(2):
        outcome = save(
            source,
            TARGET,
            OPTIONS,
            RecordingWriter(),
            lambda c: gate.confirm(c, ask),
            gate.check,
        )
        assert outcome.status is SaveStatus.CANCELLED

    assert len(asked) == 2


def test_gate_asks_about_an_error_that_is_new_after_the_first_confirmation() -> (
    None
):
    gate = SaveGate()
    source = _with_one_letter_id_short()
    submodel = next(o for o in source.objects if isinstance(o, model.Submodel))
    asked: list[SaveCheck] = []

    def ask(check: SaveCheck) -> bool:
        asked.append(check)
        return True

    save(
        source,
        TARGET,
        OPTIONS,
        RecordingWriter(),
        lambda c: gate.confirm(c, ask),
        gate.check,
    )
    submodel.submodel_element.add(make_property("Y", "2"))
    save(
        source,
        TARGET,
        OPTIONS,
        RecordingWriter(),
        lambda c: gate.confirm(c, ask),
        gate.check,
    )

    assert len(asked) == 2
    assert asked[1].warnings[0].details[0].startswith("Property 'Y'")
    assert len(asked[1].warnings[0].details) == 1


def test_gate_asks_again_about_lost_content_on_every_save() -> None:
    gate = SaveGate()
    source = FakeSource(objects=make_valid_environment())
    source.files.add_file(DOCUMENT, io.BytesIO(b"pdf"), "application/pdf")
    asked: list[SaveCheck] = []

    def ask(check: SaveCheck) -> bool:
        asked.append(check)
        return True

    for _ in range(2):
        save(
            source,
            JSON_TARGET,
            OPTIONS,
            RecordingWriter(),
            lambda c: gate.confirm(c, ask),
            gate.check,
        )

    assert len(asked) == 2


# ---------------------------------------------------------------------------
# A rule that raises
# ---------------------------------------------------------------------------


def _failing(context: ValidationContext) -> Iterator[Finding]:
    yield from ()
    raise RuntimeError("defect")


FAILING = Rule("TEST-FAILS", "Always fails", "A test", _failing)


def test_gate_does_not_stop_a_save_when_a_rule_raises() -> None:
    gate = SaveGate(rules=(FAILING, *IDENTITY_RULES))
    source = FakeSource(objects=make_valid_environment())
    writer = RecordingWriter()

    outcome = save(
        source,
        TARGET,
        OPTIONS,
        writer,
        lambda c: gate.confirm(c, lambda _: True),
        gate.check,
    )

    assert outcome.status is SaveStatus.SAVED
    assert writer.targets == [TARGET]
    assert outcome.check == SaveCheck()


def test_gate_still_finds_the_errors_of_other_rules_when_a_rule_raises() -> (
    None
):
    gate = SaveGate(rules=(FAILING, *IDENTITY_RULES))

    check = gate.check(_with_one_letter_id_short(), TARGET, OPTIONS)

    assert [issue.message.split(" ")[0] for issue in check.warnings] == [
        "AASd-002:"
    ]
