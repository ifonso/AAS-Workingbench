"""Making AssetInformation that the SDK accepts, with messages for the user.

A shell needs AssetInformation, and the SDK refuses one that has neither a
global asset id nor a specific asset id (AASd-131). It also refuses empty ids
and ids longer than 2048 characters. The generated form of the editor cannot
show this in advance, so a new shell failed with a traceback. The functions
here check the input first and say what is wrong in plain words.

Example:
    Making the AssetInformation of a new shell::

        info = build_asset_information(
            model.AssetKind.INSTANCE,
            global_asset_id=new_global_asset_id(),
            specific_asset_ids=[build_specific_asset_id("serial", "4711")],
        )
"""

from collections.abc import Iterable

from basyx.aas import model

from aas_editor.domain.ids import new_identifier

MAX_IDENTIFIER_LENGTH = 2048
"""The longest id, asset type, or key value the metamodel allows."""

ASSET_KINDS: tuple[model.AssetKind, ...] = tuple(model.AssetKind)
"""The kinds of asset that V3.1 knows. `Batch` is new in V3.2."""

DEFAULT_ASSET_KIND = model.AssetKind.INSTANCE
"""What a new shell gets. Package Explorer hints that `Instance` is usual."""


class AssetInformationError(ValueError):
    """The input does not make valid AssetInformation. The text is for the user."""


def new_global_asset_id() -> str:
    """Returns a new global asset id, a `urn:uuid:` URN (D14)."""
    return new_identifier()


def clean_identifier(text: str | None) -> str | None:
    """Trims a text that the user typed as an id.

    Args:
        text: What the user typed, or None.

    Returns:
        The trimmed text, or None when nothing but blanks was typed. An empty
        id is not allowed, so an empty field means the id is not given.
    """
    if text is None:
        return None
    stripped = text.strip()
    return stripped or None


def build_specific_asset_id(
    name: str,
    value: str,
    external_subject_id: model.ExternalReference | None = None,
) -> model.SpecificAssetId:
    """Makes a specific asset id, for example a serial number.

    Args:
        name: The name of the id, such as `serialNumber`.
        value: The value of the id.
        external_subject_id: Who the id is meant for, if anyone.

    Returns:
        The id. A specific asset id cannot be changed after it is made, so an
        edit replaces it with another one.

    Raises:
        AssetInformationError: If the name or the value is empty or too long.
    """
    clean_name = clean_identifier(name)
    clean_value = clean_identifier(value)
    if clean_name is None:
        raise AssetInformationError("A specific asset id needs a name")
    if clean_value is None:
        raise AssetInformationError(
            f"The specific asset id '{clean_name}' needs a value"
        )
    try:
        return model.SpecificAssetId(
            clean_name, clean_value, external_subject_id=external_subject_id
        )
    except (ValueError, model.AASConstraintViolation) as error:
        raise AssetInformationError(
            f"'{clean_name}' is not a valid specific asset id: {error}"
        ) from error


def check_asset_ids(
    global_asset_id: str | None,
    specific_asset_ids: Iterable[model.SpecificAssetId],
) -> str | None:
    """Tells why a combination of asset ids is not valid.

    Args:
        global_asset_id: The global asset id, or None.
        specific_asset_ids: The specific asset ids.

    Returns:
        The problem as a sentence, or None if the ids are valid. The SDK
        needs one of the two kinds of id (AASd-131) and limits their length.
    """
    clean = clean_identifier(global_asset_id)
    if clean is None and not list(specific_asset_ids):
        return (
            "An asset needs a global asset id or at least one specific "
            "asset id (AASd-131)"
        )
    if clean is not None and len(clean) > MAX_IDENTIFIER_LENGTH:
        return (
            f"The global asset id has {len(clean)} characters, "
            f"and {MAX_IDENTIFIER_LENGTH} are allowed"
        )
    return None


def build_asset_information(
    asset_kind: model.AssetKind,
    global_asset_id: str | None,
    specific_asset_ids: Iterable[model.SpecificAssetId] = (),
    asset_type: str | None = None,
) -> model.AssetInformation:
    """Makes AssetInformation, or says what is missing.

    Args:
        asset_kind: Whether the asset is a type, an instance, or has no kind.
        global_asset_id: The global asset id. A blank text means none.
        specific_asset_ids: The specific asset ids.
        asset_type: The type of the asset, if known. A blank text means none.

    Returns:
        The AssetInformation.

    Raises:
        AssetInformationError: If the ids break a rule of the metamodel.
    """
    specific = list(specific_asset_ids)
    global_id = clean_identifier(global_asset_id)
    problem = check_asset_ids(global_id, specific)
    if problem is not None:
        raise AssetInformationError(problem)
    kind_of_asset = clean_identifier(asset_type)
    if kind_of_asset is not None and len(kind_of_asset) > MAX_IDENTIFIER_LENGTH:
        raise AssetInformationError(
            f"The asset type has {len(kind_of_asset)} characters, "
            f"and {MAX_IDENTIFIER_LENGTH} are allowed"
        )
    try:
        return model.AssetInformation(
            asset_kind=asset_kind,
            global_asset_id=global_id,
            specific_asset_id=specific,
            asset_type=kind_of_asset,
        )
    except (ValueError, model.AASConstraintViolation) as error:
        raise AssetInformationError(str(error)) from error
