"""Qualifiers, extensions and the like as SDK JSON, and back."""

import json

from basyx.aas import model
import pytest
from tests.factories import make_external_reference

from aas_workingbench.domain.clipboard_json import ClipboardError
from aas_workingbench.domain.clipboard_json import dump_members
from aas_workingbench.domain.clipboard_json import load_members
from aas_workingbench.domain.member_json import MemberJsonError
from aas_workingbench.domain.member_json import MemberKind
from aas_workingbench.domain.member_json import clone_member
from aas_workingbench.domain.member_json import member_from_data

QUALIFIER = {
    "type": "SMT/Cardinality",
    "valueType": "xs:string",
    "value": "One",
    "kind": "TemplateQualifier",
    "semanticId": {
        "type": "ExternalReference",
        "keys": [{"type": "GlobalReference", "value": "https://example.com/c"}],
    },
}
EXTENSION = {"name": "Animate.Args", "valueType": "xs:string", "value": "{}"}
ASSET_ID = {"name": "BPN", "value": "BPNL0001"}


def _one(text: str, kind: MemberKind):
    (member,) = load_members(text, kind)
    return member


def test_a_qualifier_object_becomes_a_qualifier() -> None:
    qualifier = _one(json.dumps(QUALIFIER), MemberKind.QUALIFIER)

    assert isinstance(qualifier, model.Qualifier)
    assert (qualifier.type, qualifier.value, qualifier.kind) == (
        "SMT/Cardinality",
        "One",
        model.QualifierKind.TEMPLATE_QUALIFIER,
    )
    assert qualifier.value_type is model.datatypes.String
    assert qualifier.semantic_id == make_external_reference(
        "https://example.com/c"
    )


def test_an_array_gives_every_member_in_order() -> None:
    members = load_members(
        json.dumps([EXTENSION, {"name": "Second"}]), MemberKind.EXTENSION
    )

    assert [m.name for m in members] == ["Animate.Args", "Second"]


def test_a_specific_asset_id_keeps_its_external_subject() -> None:
    data = {
        **ASSET_ID,
        "externalSubjectId": {
            "type": "ExternalReference",
            "keys": [{"type": "GlobalReference", "value": "urn:subject"}],
        },
    }

    member = _one(json.dumps(data), MemberKind.SPECIFIC_ASSET_ID)

    assert isinstance(member, model.SpecificAssetId)
    assert member.external_subject_id == make_external_reference("urn:subject")
    assert (member.name, member.value) == ("BPN", "BPNL0001")


def test_an_embedded_data_specification_becomes_one() -> None:
    data = {
        "dataSpecification": {
            "type": "ExternalReference",
            "keys": [{"type": "GlobalReference", "value": "urn:spec"}],
        },
        "dataSpecificationContent": {
            "modelType": "DataSpecificationIec61360",
            "preferredName": [{"language": "en", "text": "Name"}],
        },
    }

    member = _one(json.dumps(data), MemberKind.EMBEDDED_DATA_SPECIFICATION)

    assert isinstance(member, model.EmbeddedDataSpecification)
    assert isinstance(
        member.data_specification_content, model.DataSpecificationIEC61360
    )


def test_a_model_type_that_names_the_kind_is_accepted() -> None:
    data = {**QUALIFIER, "modelType": "Qualifier"}

    assert isinstance(
        _one(json.dumps(data), MemberKind.QUALIFIER), model.Qualifier
    )


def test_null_means_absent() -> None:
    data = {**QUALIFIER, "valueId": None, "semanticId": None}

    qualifier = _one(json.dumps(data), MemberKind.QUALIFIER)

    assert qualifier.value_id is None
    assert qualifier.semantic_id is None


def test_every_call_gives_new_objects_without_a_parent() -> None:
    text = json.dumps(QUALIFIER)

    first = _one(text, MemberKind.QUALIFIER)
    second = _one(text, MemberKind.QUALIFIER)

    assert first is not second
    assert first.parent is None


def test_a_dump_reads_back_equal() -> None:
    original = _one(json.dumps(QUALIFIER), MemberKind.QUALIFIER)

    again = _one(dump_members([original]), MemberKind.QUALIFIER)

    assert (again.type, again.value, again.kind, again.semantic_id) == (
        original.type,
        original.value,
        original.kind,
        original.semantic_id,
    )


@pytest.mark.parametrize("kind", list(MemberKind))
def test_a_clone_equals_the_member_and_is_a_new_object(
    kind: MemberKind,
) -> None:
    samples = {
        MemberKind.QUALIFIER: QUALIFIER,
        MemberKind.EXTENSION: EXTENSION,
        MemberKind.SPECIFIC_ASSET_ID: ASSET_ID,
        MemberKind.EMBEDDED_DATA_SPECIFICATION: {
            "dataSpecification": {
                "type": "ExternalReference",
                "keys": [{"type": "GlobalReference", "value": "urn:spec"}],
            },
            "dataSpecificationContent": {
                "modelType": "DataSpecificationIec61360",
                "preferredName": [{"language": "en", "text": "Name"}],
            },
        },
    }
    member = member_from_data(samples[kind], kind)

    copy = clone_member(member, kind)

    assert copy is not member
    assert json.loads(dump_members([copy])) == json.loads(
        dump_members([member])
    )


@pytest.mark.parametrize(
    ("text", "fragment"),
    [
        ("", "does not hold AAS JSON"),
        ("hello", "does not hold AAS JSON"),
        ("{", "not valid JSON"),
        ("[]", "holds no"),
        ("[1]", "not a JSON object"),
        ('["x"]', "not a JSON object"),
        ('{"type": "T"}', "valueType"),
        ('{"type": "T", "valueType": "nope"}', "valueType"),
        ('{"type": "T", "valueType": "xs:int", "value": "abc"}', "abc"),
        ('{"type": "", "valueType": "xs:string"}', "minimum length"),
        (
            '{"type": "T", "valueType": "xs:string", "semanticId": "x"}',
            "semanticId",
        ),
        (
            '{"modelType": "Property", "idShort": "P", "valueType": "xs:string"}',
            "is a Property, not a Qualifier",
        ),
        (
            '[{"type": "T", "valueType": "xs:string"}, {"nonsense": 1}]',
            "Entry 2",
        ),
    ],
)
def test_content_that_is_no_qualifier_is_refused_with_a_reason(
    text: str, fragment: str
) -> None:
    with pytest.raises(ClipboardError) as caught:
        load_members(text, MemberKind.QUALIFIER)

    assert fragment in str(caught.value)


def test_an_extension_with_a_value_but_no_type_is_refused() -> None:
    with pytest.raises(ClipboardError) as caught:
        load_members('{"name": "E", "value": "1"}', MemberKind.EXTENSION)

    assert "valueType" in str(caught.value)


def test_a_specific_asset_id_without_a_value_is_refused() -> None:
    with pytest.raises(ClipboardError) as caught:
        load_members('{"name": "BPN"}', MemberKind.SPECIFIC_ASSET_ID)

    assert "value" in str(caught.value)


def test_text_that_is_too_large_is_refused() -> None:
    with pytest.raises(ClipboardError) as caught:
        load_members("[" + " " * 20_000_001, MemberKind.QUALIFIER)

    assert "too large" in str(caught.value)


def test_deeply_nested_json_is_refused_and_never_crashes() -> None:
    text = "[" * 5000 + "]" * 5000

    with pytest.raises(ClipboardError):
        load_members(text, MemberKind.QUALIFIER)


def test_member_from_data_refuses_a_non_object_with_the_json_error() -> None:
    with pytest.raises(MemberJsonError):
        member_from_data(["x"], MemberKind.EXTENSION)
