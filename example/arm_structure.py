"""The bill of material of the arm, as entities with statements.

It follows the IDTA template Hierarchical Structures enabling Bills of
Material 1.1.1, archetype Full: one entry node, and below it the parts in a
tree. Each part is a self-managed entity with an asset id of its own. The
statements say what the part is, with the article number and the mass, and
how it relates to the other parts: `HasPart` points down and `IsPartOf` up.
"""

from dataclasses import dataclass

from basyx.aas import model
from basyx.aas.model import datatypes

from arm_helpers import ASSET_ID
from arm_helpers import find
from arm_helpers import names
from arm_helpers import prop
from arm_helpers import qualifier
from arm_helpers import reference_to
from arm_helpers import texts
from arm_templates import Template
from arm_templates import like

ROOT = "PP6Arm"


@dataclass(frozen=True)
class Part:
    """One node of the bill of material.

    Attributes:
        key: The idShort of the entity.
        parent: The idShort of the entity above, or None for the entry node.
        names: The name in English, German and Portuguese.
        article: The article number.
        mass: The mass of the part itself in kilograms, or None for the entry
            node, an assembly that has none of its own, and a bulk part.
        optional: True for an option that the arm can be delivered without.
        count: The number of identical parts, for a bulk part.
    """

    key: str
    parent: str | None
    names: tuple[str, str, str]
    article: str
    mass: float | None = None
    optional: bool = False
    count: int | None = None


def _joint(
    number: int,
    parent: str,
    name: tuple[str, str, str],
    housing: float,
    motor: float,
    encoder: float,
) -> list[Part]:
    return [
        Part(f"Joint{number}", parent, (f"Joint {number}, {name[0]}", f"Gelenk {number}, {name[1]}", f"Junta {number}, {name[2]}"), f"PP6-12{number}-0001", housing),
        Part(f"Motor{number}", f"Joint{number}", (f"Motor of joint {number}", f"Motor von Gelenk {number}", f"Motor da junta {number}"), f"PP6-13{number}-0001", motor),
        Part(f"Encoder{number}", f"Joint{number}", (f"Encoder of joint {number}", f"Geber von Gelenk {number}", f"Encoder da junta {number}"), f"PP6-14{number}-0001", encoder),
    ]  # fmt: skip


PARTS: tuple[Part, ...] = (
    Part(
        ROOT,
        None,
        (
            "Workingbench Example Arm PP-6",
            "Workingbench Beispiel-Arm PP-6",
            "Braço de exemplo Workingbench PP-6",
        ),
        "PP6-100-0001",
    ),
    Part("Base", ROOT, ("Base", "Basis", "Base"), "PP6-110-0001", 4.8),
    Part("BaseBolts", "Base", ("Mounting bolts", "Befestigungsschrauben", "Parafusos de fixação"), "ISO4762-M8X25", count=4),
    *_joint(1, ROOT, ("base rotation", "Basisdrehung", "rotação da base"), 2.6, 0.9, 0.1),
    *_joint(2, ROOT, ("shoulder", "Schulter", "ombro"), 5.0, 1.4, 0.1),
    *_joint(3, ROOT, ("elbow", "Ellbogen", "cotovelo"), 4.2, 1.1, 0.1),
    Part("Wrist", ROOT, ("Wrist", "Handgelenk", "Punho"), "PP6-150-0001", 1.2),
    *_joint(4, "Wrist", ("wrist 1", "Handgelenk 1", "punho 1"), 1.0, 0.3, 0.05),
    *_joint(5, "Wrist", ("wrist 2", "Handgelenk 2", "punho 2"), 1.0, 0.3, 0.05),
    *_joint(6, "Wrist", ("wrist 3", "Handgelenk 3", "punho 3"), 0.7, 0.2, 0.05),
    Part("CableHarness", ROOT, ("Cable harness", "Kabelbaum", "Chicote de cabos"), "PP6-160-0001", 2.85),
    Part("Gripper", ROOT, ("Gripper", "Greifer", "Garra"), "PP6-200-0001", 0.55),
    Part("FingerLeft", "Gripper", ("Left finger", "Linker Finger", "Dedo esquerdo"), "PP6-210-0001", 0.06),
    Part("FingerRight", "Gripper", ("Right finger", "Rechter Finger", "Dedo direito"), "PP6-210-0002", 0.06),
    Part("VacuumOption", "Gripper", ("Vacuum option", "Vakuumoption", "Opção de vácuo"), "PP6-220-0001", 0.18, optional=True),
    Part("Controller", ROOT, ("Controller CU-2", "Steuerung CU-2", "Controlador CU-2"), "PP6-300-0001", 12.0),
)  # fmt: skip

# The parts that the mass of the arm counts: all but the gripper and the
# controller, which are separate products on the nameplate.
ARM_PARTS = frozenset(
    part.key
    for part in PARTS
    if part.key not in {"Gripper", "FingerLeft", "FingerRight"}
    and part.key not in {"VacuumOption", "Controller", ROOT}
)


def _children(key: str) -> list[Part]:
    return [part for part in PARTS if part.parent == key]


def hierarchical_structure() -> model.Submodel:
    """Builds the bill of material of the arm.

    Returns:
        The submodel, from the template Hierarchical Structures enabling
        Bills of Material 1.1.1.
    """
    t = Template("structure")
    entry = t.at("EntryNode")
    node = t.at("EntryNode", "Node")
    entities: dict[str, model.Entity] = {}
    has_part: dict[str, list[model.RelationshipElement]] = {}
    is_part_of: dict[str, model.RelationshipElement] = {}

    def statements(part: Part) -> list[model.SubmodelElement]:
        out: list[model.SubmodelElement] = [
            prop("PartArticleNumber", str, part.article)
        ]
        if part.mass is not None:
            out.append(prop("PartMass", float, part.mass))
        if part.count is not None:
            out.append(
                like(
                    node.get_referable("BulkCount"),  # pyright: ignore[reportAttributeAccessIssue]
                    datatypes.UnsignedLong(part.count),
                    display_name=names("Bulk count", "Stückzahl", "Quantidade"),
                    description=texts(
                        "How many identical parts of this kind the arm has.",
                        "Wie viele gleiche Teile dieser Art der Arm hat.",
                        "Quantas peças iguais deste tipo o braço tem.",
                    ),
                )
            )
        return out

    def make(part: Part) -> model.Entity:
        template = entry if part.parent is None else node
        children: list[model.SubmodelElement] = statements(part)
        for child in _children(part.key):
            children.append(make(child))
        down = []
        for child in _children(part.key):
            relation = like(
                template.get_referable("HasPart"),  # pyright: ignore[reportAttributeAccessIssue]
                (None, None),
                id_short=f"HasPart_{child.key}",
                display_name=names(
                    f"Has part: {child.names[0]}",
                    f"Hat Bauteil: {child.names[1]}",
                    f"Tem a peça: {child.names[2]}",
                ),
                description=texts(
                    f"{part.names[0]} contains {child.names[0]}.",
                    f"{part.names[1]} enthält {child.names[1]}.",
                    f"{part.names[2]} contém {child.names[2]}.",
                ),
            )
            down.append((child, relation))
        children.extend(relation for _, relation in down)
        if part.parent is not None:
            above = next(p for p in PARTS if p.key == part.parent)
            up = like(
                template.get_referable("IsPartOf"),  # pyright: ignore[reportAttributeAccessIssue]
                (None, None),
                id_short="IsPartOf",
                display_name=names(
                    f"Is part of: {above.names[0]}",
                    f"Ist Teil von: {above.names[1]}",
                    f"É parte de: {above.names[2]}",
                ),
                description=texts(
                    f"{part.names[0]} belongs to {above.names[0]}.",
                    f"{part.names[1]} gehört zu {above.names[1]}.",
                    f"{part.names[2]} pertence a {above.names[2]}.",
                ),
            )
            is_part_of[part.key] = up
            children.append(up)
        entity = like(
            template,
            children=children,
            id_short=part.key,
            global_asset_id=(
                ASSET_ID
                if part.parent is None
                else f"{ASSET_ID}/part/{part.key}"
            ),
            display_name=names(*part.names),
            description=texts(
                f"{part.names[0]}, article {part.article}.",
                f"{part.names[1]}, Artikelnummer {part.article}.",
                f"{part.names[2]}, artigo {part.article}.",
            ),
            qualifier=(
                [qualifier("OptionalPart", bool, True)] if part.optional else []
            ),
        )
        entities[part.key] = entity
        has_part[part.key] = [relation for _, relation in down]
        return entity

    root = [part for part in PARTS if part.parent is None][0]
    submodel = t.instance(
        "HierarchicalStructures",
        [
            make(root),
            like(
                t.at("ArcheType"),
                "Full",
                display_name=names("Archetype", "Archetyp", "Arquétipo"),
                description=texts(
                    "Full: the submodel lists every level of the structure.",
                    "Full: das Submodel listet jede Ebene der Struktur.",
                    "Full: o submodelo lista todos os níveis da estrutura.",
                ),
            ),
        ],
    )
    # The references need the entities to be in the submodel.
    for key, relations in has_part.items():
        children = _children(key)
        for child, relation in zip(children, relations, strict=True):
            relation.first = reference_to(entities[key])
            relation.second = reference_to(entities[child.key])
    for key, relation in is_part_of.items():
        parent = next(p.parent for p in PARTS if p.key == key)
        assert parent is not None
        relation.first = reference_to(entities[key])
        relation.second = reference_to(entities[parent])
    return submodel


def entry_node(submodel: model.Submodel) -> model.Entity:
    """Finds the entry node of the bill of material.

    Args:
        submodel: The bill of material.

    Returns:
        The root entity.
    """
    node = find(submodel, ROOT)
    assert isinstance(node, model.Entity)
    return node
