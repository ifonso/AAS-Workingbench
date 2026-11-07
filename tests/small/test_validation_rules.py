"""Each rule of the validation, with a case that passes and one that fails.

The SDK refuses most invalid objects when they are made. These tests reach an
invalid state the way a user can: by a later edit, or through an argument that
the SDK does not check. A rule whose invalid state the SDK makes unreachable
has no rule, and is listed in `domain.validation.coverage`.
"""

import io

from basyx.aas import model
from basyx.aas.adapter.aasx import DictSupplementaryFileContainer
from tests.factories import make_annotated_relationship
from tests.factories import make_collection
from tests.factories import make_entity
from tests.factories import make_external_reference
from tests.factories import make_file_element
from tests.factories import make_list
from tests.factories import make_multi_language_property
from tests.factories import make_operation
from tests.factories import make_property
from tests.factories import make_shell
from tests.factories import make_store
from tests.factories import make_submodel
from tests.validation_factories import concept_with_value_list
from tests.validation_factories import model_reference_to_submodel
from tests.validation_factories import store_with
from tests.validation_factories import template_qualifier

from aas_editor.domain.validation import Severity
from aas_editor.domain.validation import validate

DOCUMENT = "/aasx/files/document.pdf"


# ---------------------------------------------------------------------------
# EDT-DUPLICATE-ID
# ---------------------------------------------------------------------------


def test_duplicate_id_is_reported_when_an_edit_gives_two_objects_one_id() -> (
    None
):
    first = make_submodel(id_="urn:a", id_short="One")
    second = make_submodel(id_="urn:b", id_short="Two")
    store = make_store(first, second)
    second.id = "urn:a"

    report = validate(store)

    findings = report.of_rule("EDT-DUPLICATE-ID")
    assert len(findings) == 2
    assert findings[0].severity is Severity.ERROR
    anchors = [finding.anchor for finding in findings]
    assert first in anchors
    assert second in anchors


def test_duplicate_id_is_not_reported_when_ids_differ() -> None:
    store = make_store(
        make_submodel(id_="urn:a", id_short="One"),
        make_submodel(id_="urn:b", id_short="Two"),
    )

    report = validate(store)

    assert report.of_rule("EDT-DUPLICATE-ID") == ()


# ---------------------------------------------------------------------------
# AASd-002
# ---------------------------------------------------------------------------


def test_id_short_pattern_is_reported_when_the_id_short_has_one_letter() -> (
    None
):
    store = store_with(make_property("X", "1"))

    report = validate(store)

    findings = report.of_rule("AASd-002")
    assert len(findings) == 1
    assert findings[0].attribute == "id_short"
    assert findings[0].location == "Property 'X' of Submodel 'Submodel'"


def test_id_short_pattern_is_not_reported_when_the_id_short_has_two_letters() -> (
    None
):
    store = store_with(make_property("Xy", "1"))

    report = validate(store)

    assert report.of_rule("AASd-002") == ()


def test_id_short_pattern_is_not_reported_when_the_sdk_names_a_list_item() -> (
    None
):
    # The SDK gives an item of a list a generated idShort (D17). It is valid.
    item = model.Property(None, model.datatypes.String, "a")
    store = store_with(make_list("Items", [item]))

    report = validate(store)

    assert report.of_rule("AASd-002") == ()


# ---------------------------------------------------------------------------
# AASd-005
# ---------------------------------------------------------------------------


def test_revision_needs_version_is_reported_when_the_version_is_cleared() -> (
    None
):
    submodel = make_submodel()
    submodel.administration = model.AdministrativeInformation(
        version="1", revision="2"
    )
    submodel.administration.version = None

    report = validate(make_store(submodel))

    findings = report.of_rule("AASd-005")
    assert len(findings) == 1
    assert findings[0].anchor is submodel
    assert findings[0].attribute == "revision"


def test_revision_needs_version_is_not_reported_when_both_are_set() -> None:
    submodel = make_submodel()
    submodel.administration = model.AdministrativeInformation(
        version="1", revision="2"
    )

    report = validate(make_store(submodel))

    assert report.of_rule("AASd-005") == ()


# ---------------------------------------------------------------------------
# EDT-DANGLING-REFERENCE
# ---------------------------------------------------------------------------


def test_dangling_reference_is_reported_when_a_model_reference_has_no_target() -> (
    None
):
    reference = model.ReferenceElement(
        "Link", value=model_reference_to_submodel("urn:missing")
    )
    store = store_with(reference)

    report = validate(store)

    findings = report.of_rule("EDT-DANGLING-REFERENCE")
    assert len(findings) == 1
    assert findings[0].severity is Severity.WARNING
    assert findings[0].anchor is reference
    assert "urn:missing" in findings[0].message


def test_dangling_reference_is_not_reported_when_the_target_is_in_the_package() -> (
    None
):
    submodel = make_submodel(
        id_="urn:target", elements=[make_property("Other")]
    )
    reference = model.ReferenceElement(
        "Link", value=model_reference_to_submodel("urn:target")
    )
    submodel.submodel_element.add(reference)

    report = validate(make_store(make_shell(submodels=[submodel]), submodel))

    assert report.of_rule("EDT-DANGLING-REFERENCE") == ()


def test_dangling_reference_is_not_reported_when_the_reference_is_external() -> (
    None
):
    reference = model.ReferenceElement(
        "Link", value=make_external_reference("urn:elsewhere")
    )

    report = validate(store_with(reference))

    assert report.of_rule("EDT-DANGLING-REFERENCE") == ()


# ---------------------------------------------------------------------------
# AASd-118
# ---------------------------------------------------------------------------


def test_supplemental_needs_semantic_is_reported_when_made_without_semantic_id() -> (
    None
):
    prop = model.Property(
        "Speed",
        model.datatypes.String,
        supplemental_semantic_id=[make_external_reference("urn:extra")],
    )

    report = validate(store_with(prop))

    findings = report.of_rule("AASd-118")
    assert len(findings) == 1
    assert findings[0].anchor is prop
    assert findings[0].subject is prop


def test_supplemental_needs_semantic_is_reported_for_a_qualifier() -> None:
    qualifier = model.Qualifier(
        "Kind",
        model.datatypes.String,
        supplemental_semantic_id=[make_external_reference("urn:extra")],
    )
    prop = make_property("Speed")
    prop.qualifier.add(qualifier)

    report = validate(store_with(prop))

    findings = report.of_rule("AASd-118")
    assert len(findings) == 1
    assert findings[0].subject is qualifier
    assert findings[0].anchor is prop


def test_supplemental_needs_semantic_is_not_reported_when_both_are_set() -> (
    None
):
    prop = model.Property(
        "Speed",
        model.datatypes.String,
        semantic_id=make_external_reference("urn:main"),
        supplemental_semantic_id=[make_external_reference("urn:extra")],
    )

    report = validate(store_with(prop))

    assert report.of_rule("AASd-118") == ()


# ---------------------------------------------------------------------------
# EDT-MISSING-FILE, EDT-FILE-IN-ANNOTATION, EDT-UNREFERENCED-FILE
# ---------------------------------------------------------------------------


def test_missing_file_is_reported_and_blocks_when_the_path_has_no_stored_file() -> (
    None
):
    element = make_file_element("Manual", DOCUMENT)

    report = validate(store_with(element), stored_files=[])

    findings = report.of_rule("EDT-MISSING-FILE")
    assert len(findings) == 1
    assert findings[0].severity is Severity.ERROR
    assert findings[0].blocks_save is True
    assert findings[0].anchor is element
    assert report.blocking == findings


def test_missing_file_is_reported_for_the_default_thumbnail_of_a_shell() -> (
    None
):
    shell = make_shell()
    shell.asset_information.default_thumbnail = model.Resource(
        "/aasx/files/thumb.png"
    )

    report = validate(make_store(shell), stored_files=[])

    findings = report.of_rule("EDT-MISSING-FILE")
    assert len(findings) == 1
    assert findings[0].anchor is shell


def test_missing_file_is_not_reported_when_the_file_is_stored() -> None:
    report = validate(
        store_with(make_file_element("Manual", DOCUMENT)),
        stored_files=[DOCUMENT],
    )

    assert report.of_rule("EDT-MISSING-FILE") == ()


def test_missing_file_is_not_reported_when_the_value_is_a_url() -> None:
    element = make_file_element("Manual", "https://example.com/manual.pdf")

    report = validate(store_with(element), stored_files=[])

    assert report.of_rule("EDT-MISSING-FILE") == ()


def test_missing_file_is_not_reported_when_the_stored_files_are_unknown() -> (
    None
):
    report = validate(store_with(make_file_element("Manual", DOCUMENT)))

    assert report.of_rule("EDT-MISSING-FILE") == ()


def test_file_in_annotation_is_reported_and_blocks_when_a_file_is_an_annotation() -> (
    None
):
    annotation = make_file_element("Evidence", DOCUMENT)
    relationship = make_annotated_relationship("Link", [annotation])

    report = validate(store_with(relationship), stored_files=[DOCUMENT])

    findings = report.of_rule("EDT-FILE-IN-ANNOTATION")
    assert len(findings) == 1
    assert findings[0].blocks_save is True
    assert findings[0].anchor is annotation
    assert report.of_rule("EDT-MISSING-FILE") == ()


def test_file_in_annotation_is_not_reported_when_the_file_is_in_a_collection() -> (
    None
):
    collection = make_collection("Documents", [make_file_element("Manual")])

    report = validate(store_with(collection), stored_files=[DOCUMENT])

    assert report.of_rule("EDT-FILE-IN-ANNOTATION") == ()


def test_unreferenced_file_is_reported_when_nothing_refers_to_a_stored_file() -> (
    None
):
    report = validate(
        store_with(make_property("Name")), stored_files=[DOCUMENT]
    )

    findings = report.of_rule("EDT-UNREFERENCED-FILE")
    assert len(findings) == 1
    assert findings[0].severity is Severity.INFO
    assert findings[0].subject == DOCUMENT
    assert findings[0].anchor is None
    assert findings[0].location == "Package"
    assert findings[0].blocks_save is False


def test_unreferenced_file_is_not_reported_when_a_file_element_refers_to_it() -> (
    None
):
    report = validate(
        store_with(make_file_element("Manual", DOCUMENT)),
        stored_files=[DOCUMENT],
    )

    assert report.of_rule("EDT-UNREFERENCED-FILE") == ()


# ---------------------------------------------------------------------------
# AASd-020, EDT-VALUE-TYPE, EDT-RANGE-ORDER
# ---------------------------------------------------------------------------


def test_qualifier_value_type_is_reported_when_the_value_type_changes() -> None:
    qualifier = model.Qualifier("Limit", model.datatypes.Int, 3)
    qualifier.value_type = model.datatypes.Date
    prop = make_property("Speed")
    prop.qualifier.add(qualifier)

    report = validate(store_with(prop))

    findings = report.of_rule("AASd-020")
    assert len(findings) == 1
    assert findings[0].subject is qualifier
    assert findings[0].anchor is prop
    assert findings[0].severity is Severity.ERROR


def test_qualifier_value_type_is_not_reported_when_the_value_fits() -> None:
    prop = make_property("Speed")
    prop.qualifier.add(model.Qualifier("Limit", model.datatypes.Int, 3))

    report = validate(store_with(prop))

    assert report.of_rule("AASd-020") == ()


def test_value_type_is_reported_when_the_value_type_of_a_property_changes() -> (
    None
):
    prop = make_property("Count", 3, model.datatypes.Int)
    prop.value_type = model.datatypes.Date

    report = validate(store_with(prop))

    findings = report.of_rule("EDT-VALUE-TYPE")
    assert len(findings) == 1
    assert findings[0].anchor is prop
    assert findings[0].attribute == "value"


def test_value_type_is_reported_for_each_limit_of_a_range() -> None:
    limits = model.Range("Span", model.datatypes.Int, 1, 5)
    limits.value_type = model.datatypes.Date

    report = validate(store_with(limits))

    assert len(report.of_rule("EDT-VALUE-TYPE")) == 2


def test_value_type_is_reported_when_the_value_type_of_an_extension_changes() -> (
    None
):
    extension = model.Extension("Note", model.datatypes.Int, 3)
    extension.value_type = model.datatypes.Date
    prop = make_property("Speed")
    prop.extension.add(extension)

    report = validate(store_with(prop))

    findings = report.of_rule("EDT-VALUE-TYPE")
    assert len(findings) == 1
    assert findings[0].subject is extension


def test_value_type_is_not_reported_when_every_value_fits_its_type() -> None:
    limits = model.Range("Span", model.datatypes.Int, 1, 5)
    count = make_property("Count", 3, model.datatypes.Int)
    extension = model.Extension("Note", model.datatypes.Int, 3)
    count.extension.add(extension)

    report = validate(store_with(limits, count))

    assert report.of_rule("EDT-VALUE-TYPE") == ()


def test_value_type_is_only_a_warning_when_an_any_uri_has_spaces() -> None:
    # XSD 1.0 allows any string in an anyURI. The SDK reads and writes it.
    path = make_property(
        "InstallationPath", "C:\\Program Files\\Demo", model.datatypes.AnyURI
    )

    report = validate(store_with(path))

    findings = report.of_rule("EDT-VALUE-TYPE")
    assert len(findings) == 1
    assert findings[0].severity is Severity.WARNING


def test_range_order_is_reported_when_the_minimum_is_above_the_maximum() -> (
    None
):
    limits = model.Range("Span", model.datatypes.Int, 5, 1)

    report = validate(store_with(limits))

    findings = report.of_rule("EDT-RANGE-ORDER")
    assert len(findings) == 1
    assert findings[0].severity is Severity.WARNING
    assert findings[0].anchor is limits


def test_range_order_is_not_reported_when_the_minimum_is_below_the_maximum() -> (
    None
):
    limits = model.Range("Span", model.datatypes.Int, 1, 5)

    report = validate(store_with(limits))

    assert report.of_rule("EDT-RANGE-ORDER") == ()


# ---------------------------------------------------------------------------
# AASd-006, AASd-007
# ---------------------------------------------------------------------------


def test_property_coded_value_is_reported_when_the_value_differs_from_the_list() -> (
    None
):
    concept = concept_with_value_list(
        "urn:cd:color", [("red", "urn:value:red"), ("blue", "urn:value:blue")]
    )
    prop = model.Property(
        "Color",
        model.datatypes.String,
        "green",
        value_id=make_external_reference("urn:value:red"),
    )
    store = store_with(prop)
    store.add(concept)

    report = validate(store)

    findings = report.of_rule("AASd-007")
    assert len(findings) == 1
    assert findings[0].anchor is prop
    assert "'red'" in findings[0].message


def test_property_coded_value_is_not_reported_when_the_value_matches_the_list() -> (
    None
):
    concept = concept_with_value_list(
        "urn:cd:color", [("red", "urn:value:red")]
    )
    prop = model.Property(
        "Color",
        model.datatypes.String,
        "red",
        value_id=make_external_reference("urn:value:red"),
    )
    store = store_with(prop)
    store.add(concept)

    report = validate(store)

    assert report.of_rule("AASd-007") == ()


def test_property_coded_value_is_not_reported_when_the_number_is_written_differently() -> (
    None
):
    concept = concept_with_value_list("urn:cd:size", [("5", "urn:value:five")])
    prop = model.Property(
        "Size",
        model.datatypes.Double,
        5.0,
        value_id=make_external_reference("urn:value:five"),
    )
    store = store_with(prop)
    store.add(concept)

    report = validate(store)

    assert report.of_rule("AASd-007") == ()


def test_property_coded_value_is_not_reported_when_the_value_id_is_not_in_the_package() -> (
    None
):
    prop = model.Property(
        "Color",
        model.datatypes.String,
        "green",
        value_id=make_external_reference("urn:value:elsewhere"),
    )

    report = validate(store_with(prop))

    assert report.of_rule("AASd-007") == ()


def test_qualifier_coded_value_is_reported_when_the_value_differs_from_the_list() -> (
    None
):
    concept = concept_with_value_list(
        "urn:cd:level", [("high", "urn:value:high")]
    )
    qualifier = model.Qualifier(
        "Level",
        model.datatypes.String,
        "low",
        value_id=make_external_reference("urn:value:high"),
    )
    prop = make_property("Speed")
    prop.qualifier.add(qualifier)
    store = store_with(prop)
    store.add(concept)

    report = validate(store)

    findings = report.of_rule("AASd-006")
    assert len(findings) == 1
    assert findings[0].subject is qualifier
    assert findings[0].anchor is prop


def test_qualifier_coded_value_is_not_reported_when_the_value_matches_the_list() -> (
    None
):
    concept = concept_with_value_list(
        "urn:cd:level", [("high", "urn:value:high")]
    )
    prop = make_property("Speed")
    prop.qualifier.add(
        model.Qualifier(
            "Level",
            model.datatypes.String,
            "high",
            value_id=make_external_reference("urn:value:high"),
        )
    )
    store = store_with(prop)
    store.add(concept)

    report = validate(store)

    assert report.of_rule("AASd-006") == ()


# ---------------------------------------------------------------------------
# AASd-109
# ---------------------------------------------------------------------------


def test_list_value_type_is_reported_when_an_item_changes_its_value_type() -> (
    None
):
    item = model.Property(None, model.datatypes.String, "1")
    items = make_list("Items", [item])
    item.value_type = model.datatypes.Int

    report = validate(store_with(items))

    findings = report.of_rule("AASd-109")
    assert len(findings) == 1
    assert findings[0].subject is item
    assert findings[0].attribute == "value_type"


def test_list_value_type_is_not_reported_when_the_items_have_the_value_type() -> (
    None
):
    items = make_list(
        "Items", [model.Property(None, model.datatypes.String, "a")]
    )

    report = validate(store_with(items))

    assert report.of_rule("AASd-109") == ()


# ---------------------------------------------------------------------------
# AASd-130
# ---------------------------------------------------------------------------


def test_xml_characters_is_reported_when_a_value_has_a_control_character() -> (
    None
):
    prop = make_property("Note", "a")
    prop.value = "bad\x00text"

    report = validate(store_with(prop))

    findings = report.of_rule("AASd-130")
    assert len(findings) == 1
    assert findings[0].anchor is prop
    assert "U+0000" in findings[0].message
    assert "position 3" in findings[0].message


def test_xml_characters_is_not_reported_when_a_value_has_tabs_and_line_breaks() -> (
    None
):
    prop = make_property("Note", "line one\n\tline two")

    report = validate(store_with(prop))

    assert report.of_rule("AASd-130") == ()


# ---------------------------------------------------------------------------
# EDT-LANGUAGE-TAG
# ---------------------------------------------------------------------------


def test_language_tags_is_reported_when_two_tags_differ_only_in_case() -> None:
    prop = make_multi_language_property("Name", {"en": "Pump", "EN": "Pumpe"})

    report = validate(store_with(prop))

    findings = report.of_rule("EDT-LANGUAGE-TAG")
    assert len(findings) == 1
    assert findings[0].severity is Severity.WARNING
    assert findings[0].anchor is prop
    assert findings[0].attribute == "value"


def test_language_tags_is_reported_for_a_description() -> None:
    prop = make_property("Name")
    prop.description = model.MultiLanguageTextType({"de": "a", "DE": "b"})

    report = validate(store_with(prop))

    assert len(report.of_rule("EDT-LANGUAGE-TAG")) == 1


def test_language_tags_is_not_reported_when_the_tags_are_distinct() -> None:
    prop = make_multi_language_property(
        "Name", {"en": "Pump", "de-DE": "Pumpe"}
    )
    prop.description = model.MultiLanguageTextType({"en": "a", "fr": "b"})

    report = validate(store_with(prop))

    assert report.of_rule("EDT-LANGUAGE-TAG") == ()


# ---------------------------------------------------------------------------
# AASd-116, AASd-133
# ---------------------------------------------------------------------------


def test_reserved_asset_name_is_reported_when_a_specific_asset_id_is_named_global() -> (
    None
):
    shell = make_shell()
    shell.asset_information.specific_asset_id.append(
        model.SpecificAssetId("GlobalAssetId", "urn:asset")
    )

    report = validate(make_store(shell))

    findings = report.of_rule("AASd-116")
    assert len(findings) == 1
    assert findings[0].anchor is shell
    assert findings[0].attribute == "name"


def test_reserved_asset_name_is_reported_for_an_entity() -> None:
    entity = make_entity("Part")
    entity.specific_asset_id.append(
        model.SpecificAssetId("globalassetid", "urn:asset")
    )

    report = validate(store_with(entity))

    assert len(report.of_rule("AASd-116")) == 1


def test_reserved_asset_name_is_not_reported_when_the_name_is_another() -> None:
    shell = make_shell()
    shell.asset_information.specific_asset_id.append(
        model.SpecificAssetId("serialNumber", "42")
    )

    report = validate(make_store(shell))

    assert report.of_rule("AASd-116") == ()


def test_external_subject_is_reported_when_it_is_a_model_reference() -> None:
    shell = make_shell()
    shell.asset_information.specific_asset_id.append(
        model.SpecificAssetId(
            "serialNumber",
            "42",
            external_subject_id=model_reference_to_submodel("urn:sm"),  # pyright: ignore[reportArgumentType]
        )
    )

    report = validate(make_store(shell))

    findings = report.of_rule("AASd-133")
    assert len(findings) == 1
    assert findings[0].anchor is shell


def test_external_subject_is_not_reported_when_it_is_an_external_reference() -> (
    None
):
    shell = make_shell()
    shell.asset_information.specific_asset_id.append(
        model.SpecificAssetId(
            "serialNumber",
            "42",
            external_subject_id=model.ExternalReference(
                (model.Key(model.KeyTypes.GLOBAL_REFERENCE, "urn:subject"),)
            ),
        )
    )

    report = validate(make_store(shell))

    assert report.of_rule("AASd-133") == ()


# ---------------------------------------------------------------------------
# AASd-119, AASd-129
# ---------------------------------------------------------------------------


def test_template_qualifier_on_submodel_is_reported_when_the_submodel_is_an_instance() -> (
    None
):
    submodel = make_submodel()
    submodel.qualifier.add(template_qualifier())

    report = validate(make_store(submodel))

    findings = report.of_rule("AASd-119")
    assert len(findings) == 1
    assert findings[0].anchor is submodel
    assert "Instance" in findings[0].message


def test_template_qualifier_on_submodel_is_not_reported_when_it_is_a_template() -> (
    None
):
    submodel = make_submodel()
    submodel.kind = model.ModellingKind.TEMPLATE
    submodel.qualifier.add(template_qualifier())

    report = validate(make_store(submodel))

    assert report.of_rule("AASd-119") == ()


def test_template_qualifier_in_element_is_reported_when_the_submodel_is_an_instance() -> (
    None
):
    prop = make_property("Speed")
    qualifier = template_qualifier()
    prop.qualifier.add(qualifier)

    report = validate(store_with(prop, kind=model.ModellingKind.INSTANCE))

    findings = report.of_rule("AASd-129")
    assert len(findings) == 1
    assert findings[0].anchor is prop
    assert findings[0].subject is qualifier


def test_template_qualifier_in_element_is_not_reported_when_the_submodel_is_a_template() -> (
    None
):
    prop = make_property("Speed")
    prop.qualifier.add(template_qualifier())

    report = validate(store_with(prop, kind=model.ModellingKind.TEMPLATE))

    assert report.of_rule("AASd-129") == ()


def test_template_qualifier_in_element_is_reported_for_an_operation_variable() -> (
    None
):
    # V3.2 exempts operation variables. The editor follows the V3.1 text.
    variable = make_property("Input")
    variable.qualifier.add(template_qualifier())
    operation = make_operation("Run", input_variables=[variable])

    report = validate(store_with(operation, kind=model.ModellingKind.INSTANCE))

    assert len(report.of_rule("AASd-129")) == 1


# ---------------------------------------------------------------------------
# Rules that need no store: the stored files argument and the empty package
# ---------------------------------------------------------------------------


def test_validate_finds_nothing_when_the_package_is_empty() -> None:
    report = validate(make_store(), stored_files=[])

    assert report.is_clean


def test_validate_reads_the_stored_files_from_a_file_container() -> None:
    files = DictSupplementaryFileContainer()
    files.add_file(DOCUMENT, io.BytesIO(b"content"), "application/pdf")

    report = validate(
        store_with(make_file_element("Manual", DOCUMENT)), stored_files=files
    )

    assert report.is_clean
