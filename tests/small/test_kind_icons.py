"""Every kind of AAS element has an icon file of the project, and a name for it."""

import inspect
from xml.etree import ElementTree

from basyx.aas import model
import pytest
from tests.factories import make_external_reference
from tests.factories import make_property
from tests.factories import make_reference_to
from tests.factories import make_submodel

from aas_workingbench.ui.theme.kind_icons import KIND_FILES
from aas_workingbench.ui.theme.kind_icons import KIND_NAMES
from aas_workingbench.ui.theme.kind_icons import KINDS_FOLDER
from aas_workingbench.ui.theme.kind_icons import SUBMODEL_REFERENCE
from aas_workingbench.ui.theme.kind_icons import kind_name

SVG = "{http://www.w3.org/2000/svg}"
# What can show in a tree besides the subclasses that are found by walking the
# SDK: the parts of the metamodel that the plan names as kinds.
PARTS = (
    model.AssetInformation,
    model.Qualifier,
    model.Extension,
    model.SpecificAssetId,
    model.Reference,
    model.EmbeddedDataSpecification,
)


def _concrete_subclasses(base: type) -> list[type]:
    found: list[type] = []
    for sub in base.__subclasses__():
        found.extend(_concrete_subclasses(sub))
        if not inspect.isabstract(sub):
            found.append(sub)
    return found


def _kinds_in_trees() -> list[type]:
    kinds: list[type] = []
    for base in (model.SubmodelElement, model.Identifiable, model.Reference):
        kinds.extend(_concrete_subclasses(base))
    kinds.extend(PARTS)
    return list(dict.fromkeys(kinds))


def test_there_are_24_kinds_and_a_file_for_each() -> None:
    files = {path.stem for path in KINDS_FOLDER.glob("*.svg")}

    assert len(KIND_NAMES) == 24
    assert files == set(KIND_NAMES)


@pytest.mark.parametrize("cls", _kinds_in_trees(), ids=lambda c: c.__name__)
def test_every_kind_that_can_appear_in_a_tree_has_an_icon_name(
    cls: type,
) -> None:
    covered = next((c for c in cls.__mro__ if c in KIND_FILES), None)

    assert covered is not None
    assert (KINDS_FOLDER / f"{KIND_FILES[covered]}.svg").is_file()


def test_a_relationship_with_annotations_is_not_a_plain_relationship() -> None:
    plain = model.RelationshipElement(
        "Rel",
        make_external_reference("urn:a"),
        make_external_reference("urn:b"),
    )
    annotated = model.AnnotatedRelationshipElement(
        "Rel",
        make_external_reference("urn:a"),
        make_external_reference("urn:b"),
    )

    assert kind_name(plain) == "relationship_element"
    assert kind_name(annotated) == "annotated_relationship_element"


def test_a_reference_to_a_submodel_is_told_from_any_other_reference() -> None:
    submodel = make_submodel(elements=[make_property("P")])

    assert kind_name(make_reference_to(submodel)) == SUBMODEL_REFERENCE
    assert kind_name(make_reference_to(submodel.get_referable("P"))) == (
        "reference"
    )
    assert kind_name(make_external_reference("urn:x")) == "reference"


@pytest.mark.parametrize("obj", ["text", 3, None, model.Key, (), []])
def test_what_is_not_a_kind_has_no_icon_name(obj: object) -> None:
    assert kind_name(obj) is None


@pytest.mark.parametrize("name", KIND_NAMES)
def test_a_kind_file_is_plain_one_color_vector_art_on_the_grid(
    name: str,
) -> None:
    text = (KINDS_FOLDER / f"{name}.svg").read_text(encoding="utf-8")
    root = ElementTree.fromstring(text)
    tags = {element.tag.removeprefix(SVG) for element in root.iter()}

    assert root.attrib["viewBox"] == "0 0 16 16"
    assert root.attrib["stroke-width"] == "1.33"
    # One color, set at run time, so nothing may name another.
    assert "currentColor" in text
    assert "#" not in text
    assert "rgb" not in text
    # No text (so no font is needed), no scripts, no styles, no images.
    assert tags <= {"svg", "path", "rect", "circle"}
