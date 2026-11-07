"""Reading preset files: good entries are kept, bad ones are refused."""

import json
from typing import Any

from basyx.aas import model
import pytest
from tests.factories import make_external_reference

from aas_workingbench.domain.member_json import MemberKind
from aas_workingbench.domain.presets import MAX_ENTRIES
from aas_workingbench.domain.presets import MAX_FILE_CHARS
from aas_workingbench.domain.presets import Preset
from aas_workingbench.domain.presets import PresetValueError
from aas_workingbench.domain.presets import merge_presets
from aas_workingbench.domain.presets import parse_presets

QUALIFIER = {
    "name": "Cardinality = One",
    "qualifier": {
        "kind": "TemplateQualifier",
        "type": "SMT/Cardinality",
        "valueType": "xs:string",
        "value": "One",
        "semanticId": {
            "type": "ExternalReference",
            "keys": [{"type": "GlobalReference", "value": "urn:cardinality"}],
        },
    },
}
EXTENSION = {
    "name": "Animation",
    "extension": {
        "name": "Animate.Args",
        "valueType": "xs:string",
        "value": "x",
    },
}
ASSET_ID = {
    "name": "Catena-X BPN",
    "specificAssetId": {"name": "BPN", "value": ""},
}
IEC = "https://admin-shell.io/DataSpecificationTemplates/DataSpecificationIec61360/3/0"
DATA_SPEC = {
    "name": "IEC 61360",
    "embeddedDataSpecification": {
        "dataSpecification": {
            "type": "ExternalReference",
            "keys": [{"type": "GlobalReference", "value": IEC}],
        },
        "dataSpecificationContent": {
            "modelType": "DataSpecificationIec61360",
            "preferredName": [{"language": "en", "text": "Name"}],
        },
    },
}


def _text(*entries: Any) -> str:
    return json.dumps(list(entries))


def test_a_qualifier_preset_makes_a_qualifier() -> None:
    result = parse_presets(_text(QUALIFIER), MemberKind.QUALIFIER, "shipped")

    (preset,) = result.presets
    qualifier = preset.make()
    assert result.problems == ()
    assert preset.name == "Cardinality = One"
    assert preset.source == "shipped"
    assert isinstance(qualifier, model.Qualifier)
    assert qualifier.type == "SMT/Cardinality"
    assert qualifier.kind is model.QualifierKind.TEMPLATE_QUALIFIER
    assert qualifier.semantic_id == make_external_reference("urn:cardinality")


@pytest.mark.parametrize(
    ("kind", "entry", "member_type"),
    [
        (MemberKind.EXTENSION, EXTENSION, model.Extension),
        (
            MemberKind.SPECIFIC_ASSET_ID,
            {"name": "GTIN", "specificAssetId": {"name": "GTIN", "value": "1"}},
            model.SpecificAssetId,
        ),
        (
            MemberKind.EMBEDDED_DATA_SPECIFICATION,
            DATA_SPEC,
            model.EmbeddedDataSpecification,
        ),
    ],
)
def test_each_kind_makes_its_member(
    kind: MemberKind, entry: dict[str, Any], member_type: type
) -> None:
    result = parse_presets(_text(entry), kind, "user")

    (preset,) = result.presets
    assert result.problems == ()
    assert isinstance(preset.make(), member_type)


def test_every_make_is_a_new_object() -> None:
    (preset,) = parse_presets(
        _text(QUALIFIER), MemberKind.QUALIFIER, "user"
    ).presets

    first, second = preset.make(), preset.make()

    assert first is not second
    assert first.parent is None


def test_whole_line_comments_are_allowed() -> None:
    text = (
        "[\n  // the name is shown in the list\n"
        + json.dumps(QUALIFIER)
        + "\n]"
    )

    result = parse_presets(text, MemberKind.QUALIFIER, "user")

    assert [p.name for p in result.presets] == ["Cardinality = One"]


def test_a_double_slash_inside_a_text_is_not_a_comment() -> None:
    entry = json.loads(json.dumps(QUALIFIER))
    entry["qualifier"]["value"] = "https://example.com/x"

    (preset,) = parse_presets(
        "[\n" + json.dumps(entry, indent=2) + "\n]", MemberKind.QUALIFIER, "u"
    ).presets

    assert preset.make().value == "https://example.com/x"  # type: ignore[union-attr]


def test_the_format_of_package_explorer_is_read() -> None:
    legacy_qualifier = {
        "name": "Legacy",
        "upgradeFrom": ["Cardinality"],
        "qualifier": {
            "kind": "TemplateQualifier",
            "semanticId": None,
            "type": "SMT/Cardinality",
            "value": "One",
            "valueId": None,
        },
    }
    legacy_pair = {
        "name": "GTIN",
        "pair": {
            "semanticId": None,
            "name": "GTIN",
            "value": "1",
            "externalSubjectId": None,
        },
    }
    legacy_spec = {"name": "IEC 61360", "value": IEC}

    qualifiers = parse_presets(
        _text(legacy_qualifier), MemberKind.QUALIFIER, "u"
    )
    pairs = parse_presets(_text(legacy_pair), MemberKind.SPECIFIC_ASSET_ID, "u")
    specs = parse_presets(
        _text(legacy_spec), MemberKind.EMBEDDED_DATA_SPECIFICATION, "u"
    )

    qualifier = qualifiers.presets[0].make()
    assert isinstance(qualifier, model.Qualifier)
    assert qualifier.value_type is model.datatypes.String
    assert pairs.presets[0].make().name == "GTIN"  # type: ignore[union-attr]
    spec = specs.presets[0].make()
    assert isinstance(spec, model.EmbeddedDataSpecification)
    assert spec.data_specification == make_external_reference(IEC)


def test_a_legacy_data_specification_without_a_content_class_is_refused() -> (
    None
):
    entry = {"name": "ISO 13584", "value": "<not yet available>"}

    result = parse_presets(
        _text(entry), MemberKind.EMBEDDED_DATA_SPECIFICATION, "u"
    )

    assert result.presets == ()
    assert "IEC 61360" in result.problems[0].message


def test_a_bad_entry_is_refused_and_the_others_are_kept() -> None:
    bad = {
        "name": "Broken",
        "qualifier": {"type": "T", "valueType": "xs:int", "value": "x"},
    }

    result = parse_presets(
        _text(QUALIFIER, bad, "text", {"qualifier": {}}),
        MemberKind.QUALIFIER,
        "user",
    )

    assert [p.name for p in result.presets] == ["Cardinality = One"]
    assert [p.where for p in result.problems] == [
        "Entry 2 ('Broken')",
        "Entry 3",
        "Entry 4",
    ]
    assert "xs:int" in result.problems[0].message
    assert "not an object" in result.problems[1].message
    assert "name" in result.problems[2].message


def test_an_entry_without_its_member_is_refused() -> None:
    result = parse_presets(_text({"name": "Empty"}), MemberKind.EXTENSION, "u")

    assert result.presets == ()
    assert "extension" in result.problems[0].message


def test_a_name_that_is_used_twice_keeps_the_first() -> None:
    other = json.loads(json.dumps(QUALIFIER))
    other["qualifier"]["value"] = "Other"

    result = parse_presets(_text(QUALIFIER, other), MemberKind.QUALIFIER, "u")

    assert len(result.presets) == 1
    assert result.presets[0].make().value == "One"  # type: ignore[union-attr]
    assert "used by an earlier entry" in result.problems[0].message


@pytest.mark.parametrize(
    ("text", "fragment"),
    [
        ("", "empty"),
        ("   ", "empty"),
        ("not json", "not valid JSON"),
        ("{", "not valid JSON"),
        ('{"a": 1}', "must be an array"),
        ("42", "must be an array"),
        ("null", "must be an array"),
        ("[" * 10000, "nested too deeply"),
    ],
)
def test_a_file_that_is_no_array_is_refused_whole(
    text: str, fragment: str
) -> None:
    result = parse_presets(text, MemberKind.QUALIFIER, "user")

    assert result.presets == ()
    assert len(result.problems) == 1
    assert result.problems[0].where == "File"
    assert fragment in result.problems[0].message


def test_a_file_beyond_the_size_limit_is_refused_unread() -> None:
    result = parse_presets(
        "[" + " " * MAX_FILE_CHARS + "]", MemberKind.QUALIFIER, "user"
    )

    assert result.presets == ()
    assert "too large" in result.problems[0].message


def test_entries_beyond_the_limit_are_refused() -> None:
    entries = [
        {"name": f"n{n}", "extension": {"name": f"e{n}"}}
        for n in range(MAX_ENTRIES + 1)
    ]

    result = parse_presets(_text(*entries), MemberKind.EXTENSION, "u")

    assert result.presets == ()
    assert "more than" in result.problems[0].message


@pytest.mark.parametrize("name", ["", "   ", None, 3, "x" * 300])
def test_a_name_must_be_text_of_reasonable_length(name: Any) -> None:
    entry = {"name": name, "extension": {"name": "E"}}

    result = parse_presets(_text(entry), MemberKind.EXTENSION, "u")

    assert result.presets == ()
    assert "name" in result.problems[0].message


def test_the_user_preset_replaces_the_shipped_one_of_the_same_name() -> None:
    shipped = parse_presets(_text(QUALIFIER), MemberKind.QUALIFIER, "shipped")
    changed = json.loads(json.dumps(QUALIFIER))
    changed["qualifier"]["value"] = "Mine"
    mine = parse_presets(
        _text(changed, {**QUALIFIER, "name": "Another"}),
        MemberKind.QUALIFIER,
        "user",
    )

    merged = merge_presets(shipped.presets, mine.presets)

    assert [p.name for p in merged] == ["Another", "Cardinality = One"]
    assert merged[1].source == "user"
    assert merged[1].make().value == "Mine"  # type: ignore[union-attr]


def test_presets_are_listed_by_name_without_regard_to_case() -> None:
    entries = [
        {"name": name, "extension": {"name": "E"}}
        for name in ("b | two", "A | one", "a | zero")
    ]

    merged = merge_presets(
        parse_presets(_text(*entries), MemberKind.EXTENSION, "u").presets, ()
    )

    assert [p.name for p in merged] == ["A | one", "a | zero", "b | two"]


def test_a_preset_is_an_immutable_value() -> None:
    (preset,) = parse_presets(
        _text(QUALIFIER), MemberKind.QUALIFIER, "u"
    ).presets

    assert isinstance(preset, Preset)
    with pytest.raises(AttributeError):
        preset.name = "other"  # type: ignore[misc]


def test_a_specific_asset_id_without_a_value_asks_for_one() -> None:
    # The SDK refuses an empty value, so the user must give one.
    (preset,) = parse_presets(
        _text(ASSET_ID), MemberKind.SPECIFIC_ASSET_ID, "u"
    ).presets

    made = preset.make("BPNL0001")

    assert preset.value_required
    assert isinstance(made, model.SpecificAssetId)
    assert (made.name, made.value) == ("BPN", "BPNL0001")
    with pytest.raises(PresetValueError):
        preset.make()
    with pytest.raises(PresetValueError):
        preset.make("   ")


def test_a_specific_asset_id_with_a_value_needs_none() -> None:
    entry = {"name": "GTIN", "specificAssetId": {"name": "GTIN", "value": "1"}}
    (preset,) = parse_presets(
        _text(entry), MemberKind.SPECIFIC_ASSET_ID, "u"
    ).presets

    assert not preset.value_required
    assert preset.make().value == "1"  # type: ignore[union-attr]
    assert preset.make("other").value == "1"  # type: ignore[union-attr]
