"""Checks of single texts, shared by the rules and by the hints in dialogs.

A rule looks at the objects of a package. A dialog that asks for an idShort has
no object yet, only the text the user is typing. Both ask the same question, so
the answer lives here, once. Each function returns the reason that a text is
wrong, or None if it is fine.
"""

import re

# AASd-002 as the specification writes it. The SDK checks the characters and
# the first and last one, but accepts an idShort of one letter, which the
# pattern refuses because it needs a second character class at the end.
_ID_SHORT = re.compile(r"[a-zA-Z][a-zA-Z0-9_-]*[a-zA-Z0-9_]+")
# The longest idShort the specification allows (NameType).
_MAX_ID_SHORT_LENGTH = 128
_WHITESPACE = re.compile(r"\s")

ID_SHORT_REQUIREMENT = (
    "must have at least two characters, start with a letter, use only "
    "letters, digits, hyphens and underscores, and not end with a hyphen"
)
COPY_NAME_MARK = "---"


def id_short_problem(id_short: str) -> str | None:
    """Tells why an idShort breaks AASd-002.

    Args:
        id_short: The text to check.

    Returns:
        What the idShort must do, to follow a sentence that names it, or None
        if it matches the pattern.
    """
    if (
        len(id_short) <= _MAX_ID_SHORT_LENGTH
        and _ID_SHORT.fullmatch(id_short) is not None
    ):
        return None
    return ID_SHORT_REQUIREMENT


def copy_name_problem(id_short: str) -> str | None:
    """Tells whether an idShort looks named by a copy and paste.

    Package Explorer names a copy by joining three dashes and a number to the
    name to keep it unique.

    Args:
        id_short: The text to check.

    Returns:
        A sentence, or None if the idShort has no such mark.
    """
    if COPY_NAME_MARK in id_short:
        return (
            "The idShort contains 3 dashes. It was probably named "
            "automatically to keep it unique after a copy and paste"
        )
    return None


def key_value_problem(value: str) -> str | None:
    """Tells whether the value of a reference key has whitespace.

    Args:
        value: The value of the key.

    Returns:
        A sentence, or None if the value has no whitespace.
    """
    if _WHITESPACE.search(value):
        return (
            "There seems to be whitespace in this reference. This could "
            "lead to matching problems"
        )
    return None


def global_asset_id_problem(value: str | None) -> str | None:
    """Tells whether a global asset id is empty.

    Args:
        value: The global asset id, or None if there is none.

    Returns:
        A sentence, or None if there is no global asset id or it has text.
        A missing one is a matter of AASd-131, which the SDK enforces.
    """
    if value is not None and not value.strip():
        return "The global asset id is empty. It should identify the asset"
    return None


ENTITY_GLOBAL_ID_NOTICE = (
    "Please choose the global identifier for the SelfManagedEntity"
)

_NAMED = {
    "Extension": "An extension",
    "SpecificAssetId": "A specific asset id",
}


def entity_global_asset_id_problem(
    is_self_managed: bool, global_asset_id: str | None
) -> str | None:
    """Tells that a self-managed entity should name its global asset id.

    Args:
        is_self_managed: Whether the entity type is `SelfManagedEntity`.
        global_asset_id: The global asset id, or None if there is none.

    Returns:
        A sentence, or None for a co-managed entity and for a self-managed
        one that has a global asset id. A specific asset id would satisfy
        AASd-014 too, but the original asks for the global one, as the
        preferred way to name the asset (F-EDT-04 AC17).
    """
    if is_self_managed and not (global_asset_id or "").strip():
        return ENTITY_GLOBAL_ID_NOTICE
    return None


def blank_name_problem(owner: str, text: str) -> str | None:
    """Tells that the name of an extension or a specific asset id is blank.

    Args:
        owner: The name of the class: `Extension` or `SpecificAssetId`.
        text: The name that the user typed.

    Returns:
        A sentence, or None if the owner has no name or the text has some.
        The SDK refuses a blank name (F-EDT-07 AC12).
    """
    kind = _NAMED.get(owner)
    if kind is not None and not text.strip():
        return f"{kind} needs a name. The name is empty"
    return None


def field_problem(owner: str, param: str, text: str) -> str | None:
    """Tells what the rules say about a text that is typed into a form field.

    A create dialog calls this for each change of a field, so the hint under
    the field is the finding that the rules would make for the finished object.

    Args:
        owner: The name of the class that the dialog makes, such as `Key`.
        param: The name of the parameter that the field fills.
        text: What the user has typed.

    Returns:
        A sentence, or None if the field has no hint for this text. An empty
        idShort has none, because the dialog may fill it in later.
    """
    if param == "id_short" and text:
        problem = id_short_problem(text)
        if problem is not None:
            return f"The idShort '{text}' {problem}"
        return copy_name_problem(text)
    if owner == "Key" and param == "value":
        return key_value_problem(text)
    if param == "name":
        return blank_name_problem(owner, text)
    if param == "global_asset_id" and owner != "Entity":
        # An entity names its asset in its own notice, which knows its type.
        return global_asset_id_problem(text)
    return None
