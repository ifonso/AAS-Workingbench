"""IEC 61360 data specifications of concept descriptions.

A concept description holds embedded data specifications. Each pairs a
reference to a template with the content of the template. The SDK has one kind
of content, `DataSpecificationIEC61360`, so this module is about that one:

- the key that names the template, and how to tell it from older spellings,
- a draft of the content as plain text, which a dialog can fill in while the
  user types, and which becomes the SDK object only when it is valid,
- the constraints on the content, split into those the SDK enforces (they
  refuse the object) and those it does not (they are advisories),
- the attributes that the SDK accepts but that are empty, and so invalid in a
  saved file.

The SDK refuses a data specification without a preferred name, and a text of
the wrong length. The draft says so in words before the SDK is asked.

Example:
    Making a record from what a user typed::

        draft = Iec61360Draft(preferred_name=[("en", "Max speed")])
        report = check_draft(draft)
        if report.is_valid:
            record = build_record(draft)
"""

from collections.abc import Iterable
from collections.abc import Sequence
from dataclasses import dataclass
from dataclasses import field
import enum
import re

from basyx.aas import model

from aas_workingbench.domain.language_tags import check_language_tag

# The key of the template, as the SDK documents it for metamodel V3.1
# (constraint AASc-3a-050). Files of older tools use other spellings, which
# `match_template` still recognizes.
IEC_61360_TEMPLATE_KEY = (
    "https://admin-shell.io/DataSpecificationTemplates/"
    "DataSpecificationIEC61360/3/1"
)

# The longest texts the SDK accepts (constrained string types).
MAX_PREFERRED_NAME = 255
MAX_SHORT_NAME = 18
MAX_DEFINITION = 1023
MAX_VALUE = 2048

DEFAULT_LANGUAGE = "en"

_TEMPLATE_SPELLINGS = re.compile(
    r"https?://admin-shell\.io/dataspecificationtemplates/"
    r"dataspecificationiec61360(/3(/[01])?)?/?",
    re.IGNORECASE,
)

# Types that need a unit (AASc-3a-009, as the original's model library has it).
_NEEDS_UNIT = frozenset(
    {
        model.DataTypeIEC61360.INTEGER_MEASURE,
        model.DataTypeIEC61360.REAL_MEASURE,
        model.DataTypeIEC61360.RATIONAL_MEASURE,
        model.DataTypeIEC61360.INTEGER_CURRENCY,
        model.DataTypeIEC61360.REAL_CURRENCY,
    }
)

# The attributes of the content that hold plain text.
_TEXT_ATTRIBUTES = ("unit", "source_of_definition", "symbol", "value_format")


class TemplateMatch(enum.Enum):
    """How a reference relates to the IEC 61360 template key."""

    CURRENT = "current"
    """An external reference with the one key of `IEC_61360_TEMPLATE_KEY`."""
    OTHER_SPELLING = "other_spelling"
    """Names the IEC 61360 template in another spelling or version."""
    UNKNOWN = "unknown"
    """Names something else."""


DATA_TYPE_GROUPS: tuple[tuple[str, tuple[model.DataTypeIEC61360, ...]], ...] = (
    (
        "Property or value",
        (
            model.DataTypeIEC61360.STRING,
            model.DataTypeIEC61360.STRING_TRANSLATABLE,
            model.DataTypeIEC61360.BOOLEAN,
            model.DataTypeIEC61360.DATE,
            model.DataTypeIEC61360.TIME,
            model.DataTypeIEC61360.TIMESTAMP,
            model.DataTypeIEC61360.INTEGER_COUNT,
            model.DataTypeIEC61360.INTEGER_MEASURE,
            model.DataTypeIEC61360.INTEGER_CURRENCY,
            model.DataTypeIEC61360.REAL_COUNT,
            model.DataTypeIEC61360.REAL_MEASURE,
            model.DataTypeIEC61360.REAL_CURRENCY,
            model.DataTypeIEC61360.RATIONAL,
            model.DataTypeIEC61360.RATIONAL_MEASURE,
        ),
    ),
    (
        "Reference",
        (model.DataTypeIEC61360.IRI, model.DataTypeIEC61360.IRDI),
    ),
    (
        "Document",
        (
            model.DataTypeIEC61360.FILE,
            model.DataTypeIEC61360.BLOB,
            model.DataTypeIEC61360.HTML,
        ),
    ),
)

LEVEL_TYPE_LABELS: tuple[tuple[model.IEC61360LevelType, str], ...] = (
    (model.IEC61360LevelType.MIN, "min"),
    (model.IEC61360LevelType.NOM, "nom"),
    (model.IEC61360LevelType.TYP, "typ"),
    (model.IEC61360LevelType.MAX, "max"),
)


def template_reference() -> model.ExternalReference:
    """Builds the reference that names the IEC 61360 template.

    Returns:
        An external reference with one `GlobalReference` key.
    """
    return model.ExternalReference(
        (model.Key(model.KeyTypes.GLOBAL_REFERENCE, IEC_61360_TEMPLATE_KEY),)
    )


def match_template(reference: model.Reference) -> TemplateMatch:
    """Tells whether a reference names the IEC 61360 template.

    Args:
        reference: The `data_specification` of an embedded record.

    Returns:
        `CURRENT` for the key of metamodel V3.1. `OTHER_SPELLING` when the
        reference names the template in another case, with `http`, with
        another version (3, 3/0), or as a model reference or with another key
        type. `UNKNOWN` for anything else, including more than one key.
    """
    if (
        isinstance(reference, model.ExternalReference)
        and len(reference.key) == 1
        and reference.key[0].type is model.KeyTypes.GLOBAL_REFERENCE
        and reference.key[0].value == IEC_61360_TEMPLATE_KEY
    ):
        return TemplateMatch.CURRENT
    if len(reference.key) == 1 and _TEMPLATE_SPELLINGS.fullmatch(
        reference.key[0].value
    ):
        return TemplateMatch.OTHER_SPELLING
    return TemplateMatch.UNKNOWN


def iec_content_of(
    record: model.EmbeddedDataSpecification,
) -> model.DataSpecificationIEC61360 | None:
    """Returns the IEC 61360 content of a record, or None."""
    content = record.data_specification_content
    if isinstance(content, model.DataSpecificationIEC61360):
        return content
    return None


@dataclass
class Iec61360Draft:
    """The content of an IEC 61360 record as the user types it.

    Text fields hold what is typed. An empty text, or one of only spaces,
    means the attribute is absent. A name has one `(language, text)` row for
    each language, and a row without text is a blank row of the form and is
    ignored.

    Attributes:
        preferred_name: Rows of the preferred name. At least one needs text.
        short_name: Rows of the short name, at most 18 characters each.
        definition: Rows of the definition, at most 1023 characters each.
        unit: The unit, such as `m/s`.
        unit_id: The value of a global reference to the unit, such as an IRDI.
        source_of_definition: Where the definition comes from.
        symbol: The symbol of the unit.
        data_type: The data type, or None.
        value_format: The format of the value.
        value: One value, which excludes a value list (AASc-3a-010).
        level_types: The level types that are set.
        value_list: The pairs of the value list, or None for no value list.
            The dialog can remove pairs and does not edit them; the importer
            fills it.
    """

    preferred_name: list[tuple[str, str]] = field(
        default_factory=lambda: [(DEFAULT_LANGUAGE, "")]
    )
    short_name: list[tuple[str, str]] = field(
        default_factory=list[tuple[str, str]]
    )
    definition: list[tuple[str, str]] = field(
        default_factory=list[tuple[str, str]]
    )
    unit: str = ""
    unit_id: str = ""
    source_of_definition: str = ""
    symbol: str = ""
    data_type: model.DataTypeIEC61360 | None = None
    value_format: str = ""
    value: str = ""
    level_types: frozenset[model.IEC61360LevelType] = frozenset()
    value_list: tuple[model.ValueReferencePair, ...] | None = None


@dataclass(frozen=True)
class DraftReport:
    """What is wrong with a draft.

    Attributes:
        errors: Reasons why the SDK would refuse the content. The record
            cannot be made while there are any.
        advisories: Constraints that the SDK does not check. The record can be
            made, and a file with it breaks the constraint.
    """

    errors: tuple[str, ...] = ()
    advisories: tuple[str, ...] = ()

    @property
    def is_valid(self) -> bool:
        """Whether the record can be made."""
        return not self.errors


class DraftError(ValueError):
    """A draft that cannot be made into content. The message lists the reasons."""

    def __init__(self, errors: Sequence[str]) -> None:
        super().__init__("\n".join(errors))
        self.errors = tuple(errors)


def _filled(text: str) -> str | None:
    return text if text.strip() else None


def _rows(
    name: str, rows: Iterable[tuple[str, str]], longest: int
) -> tuple[dict[str, str], list[str]]:
    texts: dict[str, str] = {}
    errors: list[str] = []
    seen: set[str] = set()
    for language, text in rows:
        if not text.strip():
            continue
        if not language.strip():
            errors.append(f"{name}: a text has no language.")
            continue
        problem = check_language_tag(language)
        if problem is not None:
            errors.append(f"{name}: {problem}.")
            continue
        if language.lower() in seen:
            errors.append(f"{name}: the language '{language}' is used twice.")
            continue
        seen.add(language.lower())
        if len(text) > longest:
            errors.append(
                f"{name} in '{language}' has {len(text)} characters, "
                f"and at most {longest} are allowed."
            )
            continue
        texts[language] = text
    return texts, errors


@dataclass(frozen=True)
class _Texts:
    """The language rows of a draft that are fine, by language."""

    preferred: dict[str, str]
    short: dict[str, str]
    definition: dict[str, str]
    errors: tuple[str, ...]


def _texts(draft: Iec61360Draft) -> _Texts:
    errors: list[str] = []
    preferred, problems = _rows(
        "Preferred name", draft.preferred_name, MAX_PREFERRED_NAME
    )
    errors.extend(problems)
    if not preferred and not problems:
        errors.append(
            "Enter a preferred name in at least one language. A data "
            "specification cannot be made without one."
        )
    short, problems = _rows("Short name", draft.short_name, MAX_SHORT_NAME)
    errors.extend(problems)
    definition, problems = _rows("Definition", draft.definition, MAX_DEFINITION)
    errors.extend(problems)
    value = _filled(draft.value)
    if value is not None and len(value) > MAX_VALUE:
        errors.append(
            f"The value has {len(value)} characters, "
            f"and at most {MAX_VALUE} are allowed."
        )
    return _Texts(preferred, short, definition, tuple(errors))


def check_draft(draft: Iec61360Draft) -> DraftReport:
    """Checks a draft against the SDK and against the constraints it lacks.

    Args:
        draft: What the user typed.

    Returns:
        The reasons, in words for the user. No exception is raised.
    """
    texts = _texts(draft)
    return DraftReport(texts.errors, _advisories(draft, texts.definition))


def _advisories(
    draft: Iec61360Draft, definition: dict[str, str]
) -> tuple[str, ...]:
    notes: list[str] = []
    has_value = _filled(draft.value) is not None
    has_list = bool(draft.value_list)
    if (
        draft.data_type in _NEEDS_UNIT
        and _filled(draft.unit) is None
        and _filled(draft.unit_id) is None
    ):
        notes.append(
            f"AASc-3a-009: the data type {draft.data_type.name} needs a unit "
            "or a unit id."
        )
    if has_value and has_list:
        notes.append(
            "AASc-3a-010: a value and a value list exclude each other."
        )
    english = any(
        language.lower().split("-")[0] == "en" for language in definition
    )
    if not english and not has_value and not has_list:
        notes.append("AASc-3a-008: the definition should be given in English.")
    return tuple(notes)


def build_content(draft: Iec61360Draft) -> model.DataSpecificationIEC61360:
    """Makes the SDK object from a draft.

    Args:
        draft: What the user typed.

    Returns:
        The content. Attributes without text are None, never empty.

    Raises:
        DraftError: If `check_draft` finds errors. The message lists them.
    """
    texts = _texts(draft)
    if texts.errors:
        raise DraftError(texts.errors)
    unit_id = _filled(draft.unit_id)
    value_list = draft.value_list
    return model.DataSpecificationIEC61360(
        preferred_name=model.PreferredNameTypeIEC61360(texts.preferred),
        data_type=draft.data_type,
        definition=(
            model.DefinitionTypeIEC61360(texts.definition)
            if texts.definition
            else None
        ),
        short_name=(
            model.ShortNameTypeIEC61360(texts.short) if texts.short else None
        ),
        unit=_filled(draft.unit),
        unit_id=(
            None
            if unit_id is None
            else model.ExternalReference(
                (model.Key(model.KeyTypes.GLOBAL_REFERENCE, unit_id),)
            )
        ),
        source_of_definition=_filled(draft.source_of_definition),
        symbol=_filled(draft.symbol),
        value_format=_filled(draft.value_format),
        value_list=set(value_list) if value_list else None,
        value=_filled(draft.value),
        level_types=draft.level_types,
    )


def build_record(draft: Iec61360Draft) -> model.EmbeddedDataSpecification:
    """Makes a record with the template key and the content of a draft.

    Raises:
        DraftError: If the draft has errors.
    """
    return model.EmbeddedDataSpecification(
        template_reference(), build_content(draft)
    )


def draft_of(content: model.DataSpecificationIEC61360) -> Iec61360Draft:
    """Reads the content of a record into a draft, to edit it.

    A `unit_id` that is not one global reference key is not kept: the draft
    shows only the value of a single key.
    """

    def rows(texts: Iterable[tuple[str, str]] | None) -> list[tuple[str, str]]:
        return list(texts) if texts else []

    unit_id = content.unit_id
    return Iec61360Draft(
        preferred_name=rows(
            content.preferred_name.items() if content.preferred_name else None
        )
        or [(DEFAULT_LANGUAGE, "")],
        short_name=rows(
            content.short_name.items() if content.short_name else None
        ),
        definition=rows(
            content.definition.items() if content.definition else None
        ),
        unit=content.unit or "",
        unit_id=(
            unit_id.key[0].value
            if unit_id is not None and len(unit_id.key) == 1
            else ""
        ),
        source_of_definition=content.source_of_definition or "",
        symbol=content.symbol or "",
        data_type=content.data_type,
        value_format=content.value_format or "",
        value=content.value or "",
        level_types=frozenset(content.level_types),
        value_list=tuple(content.value_list) if content.value_list else None,
    )


def advisories_of(content: model.DataSpecificationIEC61360) -> tuple[str, ...]:
    """Lists the constraints that existing content breaks and the SDK allows."""
    return check_draft(draft_of(content)).advisories


def empty_attributes(
    content: model.DataSpecificationIEC61360,
) -> tuple[str, ...]:
    """Names the attributes that are present but empty.

    The SDK accepts an empty `unit`, `symbol`, `source_of_definition` and
    `value_format`, and an empty value list. A saved file with them breaks the
    schema: JSON writes `"unit": ""` and `"valueReferencePairs": []`.

    Args:
        content: The content to look at.

    Returns:
        The attribute names, in the order of the constructor.
    """
    names = [
        name
        for name in _TEXT_ATTRIBUTES
        if isinstance(getattr(content, name), str)
        and not getattr(content, name).strip()
    ]
    if content.value_list is not None and not content.value_list:
        names.append("value_list")
    return tuple(sorted(names, key=_ORDER.index))


_ORDER = (
    "unit",
    "source_of_definition",
    "symbol",
    "value_format",
    "value_list",
)
