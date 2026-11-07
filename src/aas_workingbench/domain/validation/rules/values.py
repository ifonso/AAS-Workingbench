"""Rules about values: types, coded values, characters, languages, ranges."""

from collections.abc import Iterable
from collections.abc import Iterator
import re
from typing import Any
from typing import cast

from basyx.aas import model
from basyx.aas.model import datatypes

from aas_workingbench.domain import value_types
from aas_workingbench.domain.language_tags import check_language_tag
from aas_workingbench.domain.language_tags import check_language_tags
from aas_workingbench.domain.validation.context import ValidationContext
from aas_workingbench.domain.validation.findings import Finding
from aas_workingbench.domain.validation.findings import Severity
from aas_workingbench.domain.validation.rule import Rule

QUALIFIER_VALUE_TYPE = "AASd-020"
VALUE_TYPE = "EDT-VALUE-TYPE"
RANGE_ORDER = "EDT-RANGE-ORDER"
QUALIFIER_CODED_VALUE = "AASd-006"
PROPERTY_CODED_VALUE = "AASd-007"
LIST_VALUE_TYPE = "AASd-109"
XML_CHARACTERS = "AASd-130"
LANGUAGE_TAG = "EDT-LANGUAGE-TAG"

# The characters that XML 1.0 forbids, which AASd-130 forbids in a string.
_FORBIDDEN_CHARACTER = re.compile("[^\t\n\r\x20-퟿-�\U00010000-\U0010ffff]")


def qualifier_value_type(context: ValidationContext) -> Iterator[Finding]:
    """Finds a qualifier whose value is not a value of its value type.

    The SDK checks the value when the qualifier is made, but not when the
    value type changes later.
    """
    for qualifiable, qualifier in context.qualifiers:
        problem = _value_problem(qualifier.value, qualifier.value_type)
        if problem:
            yield Finding(
                QUALIFIER_VALUE_TYPE,
                _severity(qualifier.value_type),
                f"The value of the qualifier '{qualifier.type}': {problem}",
                qualifier,
                qualifiable,
                "value",
            )


def value_type(context: ValidationContext) -> Iterator[Finding]:
    """Finds a Property, Range, or Extension with a value of the wrong type.

    Qualifiers have their own constraint, AASd-020. For the others the
    specification has no number, but the same sentence: the value follows the
    value type. The SDK writes such a file but cannot read it again.
    """
    for _, element in context.elements:
        if isinstance(element, model.Property):
            yield from _typed(element, element.value_type, ("value",))
        elif isinstance(element, model.Range):
            yield from _typed(element, element.value_type, ("min", "max"))
    for anchor, extension in context.extensions:
        yield from _typed_extension(anchor, extension)


def range_order(context: ValidationContext) -> Iterator[Finding]:
    """Finds a Range whose minimum is more than its maximum."""
    for _, element in context.elements:
        if not isinstance(element, model.Range):
            continue
        problem = value_types.check_range(
            element.min, element.max, element.value_type
        )
        if problem:
            yield Finding(
                RANGE_ORDER, Severity.WARNING, problem, element, element, "min"
            )


def property_coded_value(context: ValidationContext) -> Iterator[Finding]:
    """Finds a Property whose value is not the coded value of its valueId.

    AASd-007 compares with the value that valueId refers to. The package can
    tell only when valueId is the id of a pair in a value list of one of its
    concept descriptions. For any other valueId nothing is reported.
    """
    for _, element in context.elements:
        if not isinstance(element, model.Property):
            continue
        problem = _coded_problem(
            context, element.value, element.value_type, element.value_id
        )
        if problem:
            yield Finding(
                PROPERTY_CODED_VALUE,
                Severity.ERROR,
                problem,
                element,
                element,
                "value",
            )


def qualifier_coded_value(context: ValidationContext) -> Iterator[Finding]:
    """Finds a qualifier whose value is not the coded value of its valueId."""
    for qualifiable, qualifier in context.qualifiers:
        problem = _coded_problem(
            context, qualifier.value, qualifier.value_type, qualifier.value_id
        )
        if problem:
            yield Finding(
                QUALIFIER_CODED_VALUE,
                Severity.ERROR,
                problem,
                qualifier,
                qualifiable,
                "value",
            )


def list_value_type(context: ValidationContext) -> Iterator[Finding]:
    """Finds an item of a list that has another value type than the list fixes.

    The SDK checks an item when it is added, but not when the value type of an
    item changes later.
    """
    for _, element in context.elements:
        if not isinstance(element, model.SubmodelElementList):
            continue
        fixed = element.value_type_list_element
        if fixed is None:
            continue
        items = cast(
            "Iterable[model.SubmodelElement]",
            element.value,  # pyright: ignore[reportUnknownMemberType]
        )
        for item in items:
            if (
                isinstance(item, (model.Property, model.Range))
                and item.value_type is not fixed
            ):
                yield Finding(
                    LIST_VALUE_TYPE,
                    Severity.ERROR,
                    f"The list needs the value type "
                    f"{value_types.type_name(fixed)} for all items, but this "
                    f"item has {value_types.type_name(item.value_type)}",
                    item,
                    item,
                    "value_type",
                )


def xml_characters(context: ValidationContext) -> Iterator[Finding]:
    """Finds a string value with a character that XML cannot hold.

    The SDK checks names, texts and ids, but not the value of a Property or
    another typed value. The XML writer of the SDK refuses such a value when it
    saves, and JSON accepts it.
    """
    for owner, anchor, attributes in _string_values(context):
        for attribute in attributes:
            value = getattr(owner, attribute)
            if not isinstance(value, str):
                continue
            match = _FORBIDDEN_CHARACTER.search(value)
            if match:
                yield Finding(
                    XML_CHARACTERS,
                    Severity.ERROR,
                    f"The {attribute} has the character "
                    f"U+{ord(match.group()):04X} at position {match.start()}, "
                    "which is not allowed in a string",
                    owner,
                    anchor,
                    attribute,
                )


def language_tags(context: ValidationContext) -> Iterator[Finding]:
    """Finds language tags that are malformed, or repeated in other case.

    BCP 47 ignores the case of a tag, so `en` and `EN` name one language. The
    SDK keeps them as two entries. It refuses a malformed tag when the text is
    made, so that case only arises from files that the SDK reads leniently.
    """
    for language_set in context.language_sets:
        malformed = {
            message
            for tag in language_set.tags
            if (message := check_language_tag(tag)) is not None
        }
        for message in check_language_tags(language_set.tags):
            yield Finding(
                LANGUAGE_TAG,
                Severity.ERROR if message in malformed else Severity.WARNING,
                f"In {language_set.attribute}: {message}",
                language_set.anchor,
                language_set.anchor,
                language_set.attribute,
            )


def _value_problem(value: Any, value_type_: Any) -> str | None:
    if value is None:
        return None
    try:
        return value_types.check(value_types.format_value(value), value_type_)
    except (TypeError, ValueError, NotImplementedError) as error:
        return f"{value!r} cannot be written as {value_type_}: {error}"


def _severity(value_type_: Any) -> Severity:
    """Tells how serious a value that does not fit its type is.

    XSD 1.0 lets an `anyURI` hold any string, and asks only to escape it, so a
    path with spaces is a smell and no error. The SDK reads it and writes it
    back. The editor still refuses to type such a value (ADR 0008).
    """
    if value_type_ is datatypes.AnyURI:
        return Severity.WARNING
    return Severity.ERROR


def _typed(
    element: model.SubmodelElement,
    value_type_: Any,
    attributes: tuple[str, ...],
) -> Iterator[Finding]:
    for attribute in attributes:
        problem = _value_problem(getattr(element, attribute), value_type_)
        if problem:
            yield Finding(
                VALUE_TYPE,
                _severity(value_type_),
                f"The {attribute}: {problem}",
                element,
                element,
                attribute,
            )


def _typed_extension(
    anchor: model.Referable, extension: model.Extension
) -> Iterator[Finding]:
    if extension.value is None:
        return
    if extension.value_type is None:
        yield Finding(
            VALUE_TYPE,
            Severity.ERROR,
            f"The extension '{extension.name}' has a value but no value type",
            extension,
            anchor,
            "value_type",
        )
        return
    problem = _value_problem(extension.value, extension.value_type)
    if problem:
        yield Finding(
            VALUE_TYPE,
            _severity(extension.value_type),
            f"The value of the extension '{extension.name}': {problem}",
            extension,
            anchor,
            "value",
        )


def _coded_problem(
    context: ValidationContext,
    value: Any,
    value_type_: Any,
    value_id: model.Reference | None,
) -> str | None:
    if value is None or value_id is None:
        return None
    texts = context.coded_values.get(value_id)
    if not texts:
        return None
    if any(_is_same_value(value, value_type_, text) for text in texts):
        return None
    wanted = " or ".join(f"'{text}'" for text in texts)
    return (
        f"The value '{value_types.format_value(value)}' is not the coded "
        f"value that valueId refers to, which is {wanted}"
    )


def _is_same_value(value: Any, value_type_: Any, text: str) -> bool:
    if value_types.format_value(value) == text:
        return True
    try:
        return bool(value_types.parse(text, value_type_) == value)
    except value_types.InvalidValueError:
        return False


def _string_values(
    context: ValidationContext,
) -> Iterator[tuple[Any, model.Referable, tuple[str, ...]]]:
    """Yields the objects with a typed value: owner, anchor, attributes."""
    for _, element in context.elements:
        if isinstance(element, model.Property):
            yield element, element, ("value",)
        elif isinstance(element, model.Range):
            yield element, element, ("min", "max")
    for qualifiable, qualifier in context.qualifiers:
        yield qualifier, qualifiable, ("value",)
    for anchor, extension in context.extensions:
        yield extension, anchor, ("value",)


RULES = (
    Rule(
        QUALIFIER_VALUE_TYPE,
        "A qualifier value fits its value type",
        "Part 1, constraint AASd-020. The SDK checks the value when the "
        "qualifier is made, not when the value type is changed.",
        qualifier_value_type,
    ),
    Rule(
        VALUE_TYPE,
        "A value fits its value type",
        "Part 1, Property, Range and Extension: the value has the value type "
        "(the same sentence as AASd-020). The SDK changes value_type without "
        "touching the value, and then cannot read the saved file (ADR 0008).",
        value_type,
    ),
    Rule(
        RANGE_ORDER,
        "A range has min at or below max",
        "Part 1, Range: the minimum and the maximum of a range. Editor rule: "
        "the specification has no constraint number for the order.",
        range_order,
    ),
    Rule(
        PROPERTY_CODED_VALUE,
        "A property value is the coded value of its valueId",
        "Part 1, constraint AASd-007. Checked only when the package holds the "
        "value list that valueId points into. The SDK does not check it.",
        property_coded_value,
    ),
    Rule(
        QUALIFIER_CODED_VALUE,
        "A qualifier value is the coded value of its valueId",
        "Part 1, constraint AASd-006. Checked only when the package holds the "
        "value list that valueId points into. The SDK does not check it.",
        qualifier_coded_value,
    ),
    Rule(
        LIST_VALUE_TYPE,
        "The items of a list have its value type",
        "Part 1, constraint AASd-109. The SDK checks it when an item is added, "
        "not when the value type of an item changes.",
        list_value_type,
    ),
    Rule(
        XML_CHARACTERS,
        "Strings have only XML characters",
        "Part 1, constraint AASd-130. The SDK checks names and texts, not the "
        "value of a Property, Range, Qualifier or Extension.",
        xml_characters,
    ),
    Rule(
        LANGUAGE_TAG,
        "Language tags are well-formed and distinct",
        "BCP 47 (RFC 5646) as Part 1 requires for langStrings. Case does not "
        "matter in a tag, which the SDK does not know.",
        language_tags,
    ),
)
