"""Qualifiers, extensions, specific asset ids and data specifications as JSON.

These four are not Referables, so they have no `modelType` of their own in the
JSON of the metamodel, and the SDK's decoder does not read them alone. They
are read here by placing the JSON in the attribute of a small holder, which
the SDK's own decoder reads as it reads a whole package: a Capability for
qualifiers, extensions and data specifications, and an AssetInformation for
specific asset ids. No JSON of the metamodel is parsed by hand. The holder is
thrown away, and only the members it read are returned.

The same functions read the clipboard and the presets (see
`aas_editor.domain.clipboard_json` and `aas_editor.domain.presets`). The JSON
may come from any program, so every problem is a `MemberJsonError` with a
message for the user, and nothing is evaluated.

Two conveniences go beyond the SDK, and both are documented in the
presets guide:

- A `null` in an object means the attribute is absent. Package Explorer
  writes its files this way.
- A `modelType` that names the kind (`Qualifier`, `Extension`,
  `SpecificAssetId`) is accepted. One that names something else is refused.

Example:
    Reading a qualifier::

        (qualifier,) = members_from_data(
            [{"type": "SMT/Cardinality", "valueType": "xs:string"}],
            MemberKind.QUALIFIER,
        )
"""

from collections.abc import Iterable
from collections.abc import Sequence
import enum
import json
from typing import Any
from typing import cast

from basyx.aas import model
from basyx.aas.adapter.json import AASToJsonEncoder
from basyx.aas.adapter.json import StrictAASFromJsonDecoder

from aas_editor.domain import value_types

Member = (
    model.Qualifier
    | model.Extension
    | model.SpecificAssetId
    | model.EmbeddedDataSpecification
)
"""What a `MemberKind` stands for."""


class MemberJsonError(ValueError):
    """JSON that is no qualifier, extension, specific asset id or the like.

    The message is meant for the user.
    """


class MemberKind(enum.Enum):
    """The kinds of members that can be added to many objects at once."""

    QUALIFIER = ("qualifier", "qualifiers", "qualifier", "Qualifier")
    EXTENSION = ("extension", "extensions", "extension", "Extension")
    SPECIFIC_ASSET_ID = (
        "specific asset id",
        "specificAssetIds",
        "specific_asset_id",
        "SpecificAssetId",
    )
    EMBEDDED_DATA_SPECIFICATION = (
        "data specification",
        "embeddedDataSpecifications",
        "embedded_data_specifications",
        "",
    )

    @property
    def label(self) -> str:
        """The name for the user, such as `specific asset id`."""
        return self.value[0]

    @property
    def json_key(self) -> str:
        """The key of the JSON holder that lists the members."""
        return self.value[1]

    @property
    def attribute(self) -> str:
        """The attribute of the owner that holds the members."""
        return self.value[2]

    @property
    def model_type(self) -> str:
        """The `modelType` the JSON may carry, or empty if it has none."""
        return self.value[3]


def explain(error: BaseException) -> str:
    """Turns an exception of the SDK's decoder into a sentence.

    Args:
        error: What the decoder raised.

    Returns:
        A message without the dump of the JSON that the SDK appends.
    """
    if isinstance(error, KeyError) and error.args:
        text = f"it is missing the attribute '{error.args[0]}'"
    else:
        text = str(error)
    marker = "Error while trying to convert JSON object into"
    if text.startswith(marker):
        _, _, text = text.partition(": ")
    text = text.partition(" >>> ")[0]
    return text.strip()


def members_from_data(
    items: Sequence[object], kind: MemberKind
) -> list[Member]:
    """Reads members from parsed JSON.

    Args:
        items: One JSON object for each member.
        kind: What the objects are.

    Returns:
        New members, without a parent.

    Raises:
        MemberJsonError: If an item is no member of the kind. With several
            items, the message names the first that is wrong.
    """
    members: list[Member] = []
    for number, item in enumerate(items, start=1):
        try:
            members.append(member_from_data(item, kind))
        except MemberJsonError as error:
            if len(items) > 1:
                raise MemberJsonError(f"Entry {number}: {error}") from None
            raise
    return members


def member_from_data(item: object, kind: MemberKind) -> Member:
    """Reads one member from a parsed JSON object.

    Args:
        item: The JSON object.
        kind: What it is.

    Returns:
        A new member, without a parent.

    Raises:
        MemberJsonError: If the object is no member of the kind.
    """
    if not isinstance(item, dict):
        raise MemberJsonError(
            f"The {kind.label} is not a JSON object, but {_describe(item)}"
        )
    data = cast("dict[str, Any]", _without_null(item))
    _check_model_type(data, kind)
    _check_types(data, kind)
    holder = _holder(kind, data)
    try:
        read = json.loads(json.dumps(holder), cls=StrictAASFromJsonDecoder)
    except RecursionError:
        raise MemberJsonError(
            f"The {kind.label} is nested too deeply"
        ) from None
    except (
        KeyError,
        TypeError,
        ValueError,
        AttributeError,
        model.AASConstraintViolation,
    ) as error:
        raise MemberJsonError(
            f"The {kind.label} is not valid: {explain(error)}"
        ) from None
    found = _members_of(read, kind)
    if len(found) != 1:
        raise MemberJsonError(f"The {kind.label} could not be read")
    return found[0]


def to_data(member: Member) -> dict[str, Any]:
    """Returns the JSON object of a member, as the SDK writes it."""
    if isinstance(member, model.EmbeddedDataSpecification):
        # The encoder writes a data specification only inside its owner.
        holder = model.Capability("Holder")
        holder.embedded_data_specifications.append(member)
        written = json.loads(json.dumps(holder, cls=AASToJsonEncoder))
        return cast("dict[str, Any]", written["embeddedDataSpecifications"][0])
    return cast(
        "dict[str, Any]", json.loads(json.dumps(member, cls=AASToJsonEncoder))
    )


def dump_text(members: Iterable[Member]) -> str:
    """Serializes members to a JSON array with the SDK's encoder."""
    return json.dumps([to_data(member) for member in members], indent=2)


def clone_member(member: Member, kind: MemberKind) -> Member:
    """Makes a copy of a member that has no parent.

    A member can belong to one owner only, so each owner needs its own copy.

    Args:
        member: The member to copy. It is not changed.
        kind: What it is.

    Returns:
        A new member with the same content, made by the SDK's JSON adapter.

    Raises:
        MemberJsonError: If the SDK cannot read back what it wrote.
    """
    return member_from_data(to_data(member), kind)


def _describe(item: object) -> str:
    if item is None:
        return "null"
    return f"a {type(item).__name__}"


def _without_null(node: object) -> object:
    """Drops the object attributes whose value is null, at every depth."""
    if isinstance(node, dict):
        entries = cast("dict[str, object]", node)
        return {
            key: _without_null(value)
            for key, value in entries.items()
            if value is not None
        }
    if isinstance(node, list):
        return [_without_null(value) for value in cast("list[object]", node)]
    return node


def _check_model_type(data: dict[str, Any], kind: MemberKind) -> None:
    if "modelType" not in data:
        return
    named = data.pop("modelType")
    if kind.model_type and named == kind.model_type:
        return
    raise MemberJsonError(
        f"This is a {named}, not a {kind.model_type or kind.label}"
        if isinstance(named, str)
        else f"The {kind.label} has a modelType that is no text"
    )


def _check_types(data: dict[str, Any], kind: MemberKind) -> None:
    """Gives the value type problems a message of the editor, not the SDK's."""
    if kind not in (MemberKind.QUALIFIER, MemberKind.EXTENSION):
        return
    value_type = data.get("valueType")
    if value_type is None:
        if kind is MemberKind.EXTENSION and "value" in data:
            raise MemberJsonError(
                f"The {kind.label} has a value but no valueType"
            )
        return
    if not isinstance(value_type, str):
        raise MemberJsonError(f"The valueType of the {kind.label} is no text")
    xsd_type = model.datatypes.XSD_TYPE_CLASSES.get(value_type)
    if xsd_type is None:
        raise MemberJsonError(
            f"The valueType '{value_type}' is not an XSD value type such as "
            "xs:string or xs:int"
        )
    value = data.get("value")
    if isinstance(value, str):
        problem = value_types.check(value, xsd_type)
        if problem:
            raise MemberJsonError(f"The value: {problem}")


def _holder(kind: MemberKind, data: dict[str, Any]) -> dict[str, Any]:
    if kind is MemberKind.SPECIFIC_ASSET_ID:
        return {
            "modelType": "AssetInformation",
            "assetKind": "Instance",
            "specificAssetIds": [data],
        }
    return {
        "modelType": "Capability",
        "idShort": "Holder",
        kind.json_key: [data],
    }


def _members_of(holder: object, kind: MemberKind) -> list[Member]:
    if kind is MemberKind.SPECIFIC_ASSET_ID:
        if not isinstance(holder, model.AssetInformation):
            raise MemberJsonError(f"The {kind.label} could not be read")
        return list(holder.specific_asset_id)
    if not isinstance(holder, model.Capability):
        raise MemberJsonError(f"The {kind.label} could not be read")
    members = getattr(holder, kind.attribute)
    found = list(cast("Iterable[Member]", members))
    if isinstance(members, model.NamespaceSet):
        # A qualifier or extension belongs to one owner. Leave the holder.
        for member in found:
            cast("model.NamespaceSet[Any]", members).remove(member)
    return found
