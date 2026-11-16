"""The icons of the kinds of AAS elements, for the trees.

Each kind has one SVG file of this project's own drawing in `icons/kinds/`,
on a 16 pixel grid with a stroke of 1.33 and a live area of 14. The shape says
the family of the kind and the letters say the kind:

| Shape                         | Family                              |
|-------------------------------|-------------------------------------|
| Filled square                 | Identifiable: shell, submodel, concept description |
| Filled slab                   | Part of an identifiable: asset information, submodel reference |
| Square with a band on top     | Container: collection, list, entity |
| Pill                          | Behavior: operation, capability, event |
| Square                        | Data: property, range, file, and so on |
| Square with a pointed side    | Relation: relationship, annotated relationship |
| Circle                        | Annotation: qualifier, extension, id, reference, data specification |

The files draw in `currentColor`, so `svg_icon` colors them by token (ADR 0027).
Each family of the table above has a color of its own, so that the kinds are
told apart at a glance (proposal 1.4, ADR 0035): structure, container, data,
behavior and relation. The annotations keep the blue of the application.
The Type column and the tooltip always state the kind in words.
"""

from functools import cache
from pathlib import Path
from typing import cast

from basyx.aas import model
from basyx.aas.model.concept import ConceptDescription
from PyQt6.QtGui import QIcon

from aas_workingbench.ui.theme.icons import IconRole
from aas_workingbench.ui.theme.icons import svg_icon

KINDS_FOLDER = Path(__file__).parents[2] / "icons" / "kinds"
"""Where the SVG files of the kinds are."""

KIND_ROLE = IconRole.ACCENT
"""The role of a kind icon that has no family of color: the annotations, such
as a qualifier or a reference, in the blue of the application."""

_FAMILIES: dict[IconRole, tuple[str, ...]] = {
    IconRole.KIND_STRUCTURE: (
        "asset_administration_shell",
        "submodel",
        "concept_description",
        "asset_information",
        "submodel_reference",
    ),
    IconRole.KIND_CONTAINER: (
        "submodel_element_collection",
        "submodel_element_list",
        "entity",
    ),
    IconRole.KIND_DATA: (
        "property",
        "range",
        "multi_language_property",
        "file",
        "blob",
    ),
    IconRole.KIND_BEHAVIOR: ("capability", "operation", "basic_event_element"),
    IconRole.KIND_RELATION: (
        "relationship_element",
        "annotated_relationship_element",
        "reference_element",
    ),
}

KIND_ROLES: dict[str, IconRole] = {
    name: role for role, names in _FAMILIES.items() for name in names
}
"""The color of the icon of each kind, by the family of the kind (proposal
1.4, ADR 0035). A kind that is not here takes `KIND_ROLE`."""

SUBMODEL_REFERENCE = "submodel_reference"

KIND_FILES: dict[type, str] = {
    model.AssetAdministrationShell: "asset_administration_shell",
    model.Submodel: "submodel",
    ConceptDescription: "concept_description",
    model.AssetInformation: "asset_information",
    model.SubmodelElementCollection: "submodel_element_collection",
    model.SubmodelElementList: "submodel_element_list",
    model.Entity: "entity",
    model.Operation: "operation",
    model.Capability: "capability",
    model.BasicEventElement: "basic_event_element",
    model.Property: "property",
    model.MultiLanguageProperty: "multi_language_property",
    model.Range: "range",
    model.Blob: "blob",
    model.File: "file",
    model.ReferenceElement: "reference_element",
    model.RelationshipElement: "relationship_element",
    model.AnnotatedRelationshipElement: "annotated_relationship_element",
    model.Qualifier: "qualifier",
    model.Extension: "extension",
    model.SpecificAssetId: "specific_asset_id",
    model.Reference: "reference",
    model.EmbeddedDataSpecification: "embedded_data_specification",
}
"""The file stem of each class. A subclass takes the file of its nearest base.

`submodel_reference` is not here, because it is a `ModelReference` that points
at a submodel, and is told apart by `kind_name`.
"""

KIND_NAMES: tuple[str, ...] = (
    *dict.fromkeys(KIND_FILES.values()),
    SUBMODEL_REFERENCE,
)
"""Every file stem of `KINDS_FOLDER`."""


def _points_at_submodel(obj: object) -> bool:
    if not isinstance(obj, model.ModelReference):
        return False
    return (
        cast("model.ModelReference[model.Referable]", obj).type
        is model.Submodel
    )


def kind_name(obj: object) -> str | None:
    """Names the kind of an object, as the stem of its icon file.

    Args:
        obj: Any object of a tree.

    Returns:
        The stem, such as `property`, or `None` if the object has no kind icon,
        for example a string or a key. An object takes the stem of its nearest
        base class that has one, so a `ModelReference` is a `reference`, except
        when it points at a submodel, where it is a `submodel_reference`.
    """
    if _points_at_submodel(obj):
        return SUBMODEL_REFERENCE
    for cls in type(obj).__mro__:
        if cls in KIND_FILES:
            return KIND_FILES[cls]
    return None


@cache
def _icon(name: str) -> QIcon:
    return svg_icon(KINDS_FOLDER / f"{name}.svg", kind_role(name))


def kind_role(name: str) -> IconRole:
    """Gives the color of the icon of a kind, by the stem of its file."""
    return KIND_ROLES.get(name, KIND_ROLE)


def kind_icon(obj: object) -> QIcon | None:
    """Gives the icon of the kind of an object.

    Args:
        obj: Any object of a tree.

    Returns:
        The icon, which follows the theme, or `None` if the object has no kind
        icon.
    """
    name = kind_name(obj)
    return None if name is None else _icon(name)
