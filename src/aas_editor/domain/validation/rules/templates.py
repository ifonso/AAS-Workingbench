"""Rules about template qualifiers: they belong in a template submodel."""

from collections.abc import Iterator

from basyx.aas import model

from aas_editor.domain.validation.context import ValidationContext
from aas_editor.domain.validation.findings import Finding
from aas_editor.domain.validation.findings import Severity
from aas_editor.domain.validation.rule import Rule

TEMPLATE_QUALIFIER_ON_SUBMODEL = "AASd-119"
TEMPLATE_QUALIFIER_IN_ELEMENT = "AASd-129"


def template_qualifier_on_submodel(
    context: ValidationContext,
) -> Iterator[Finding]:
    """Finds a submodel that has a template qualifier but is no template.

    The only class with a `kind` in V3.1 is the Submodel, so AASd-119 applies
    to the qualifiers of a Submodel. The SDK does not check it.
    """
    for submodel in context.submodels:
        if submodel.kind is model.ModellingKind.TEMPLATE:
            continue
        for qualifier in submodel.qualifier:
            if qualifier.kind is model.QualifierKind.TEMPLATE_QUALIFIER:
                yield Finding(
                    TEMPLATE_QUALIFIER_ON_SUBMODEL,
                    Severity.ERROR,
                    f"The qualifier '{qualifier.type}' is a template "
                    f"qualifier, but the submodel has the kind "
                    f"{submodel.kind.name.title()}, not Template",
                    qualifier,
                    submodel,
                    "kind",
                )


def template_qualifier_in_element(
    context: ValidationContext,
) -> Iterator[Finding]:
    """Finds an element with a template qualifier in a submodel that is no template.

    This is the V3.1 text of AASd-129. V3.2 adds an exception for the elements
    of an operation variable, which the editor does not apply, because the
    target is V3.1 (ADR 0005). The SDK does not check it.
    """
    for submodel, element in context.elements:
        if submodel.kind is model.ModellingKind.TEMPLATE:
            continue
        for qualifier in element.qualifier:
            if qualifier.kind is model.QualifierKind.TEMPLATE_QUALIFIER:
                yield Finding(
                    TEMPLATE_QUALIFIER_IN_ELEMENT,
                    Severity.ERROR,
                    f"The qualifier '{qualifier.type}' is a template "
                    "qualifier, but the submodel has the kind "
                    f"{submodel.kind.name.title()}, not Template",
                    qualifier,
                    element,
                    "kind",
                )


RULES = (
    Rule(
        TEMPLATE_QUALIFIER_ON_SUBMODEL,
        "A template qualifier on a submodel needs a template",
        "Part 1, constraint AASd-119. The SDK does not check it.",
        template_qualifier_on_submodel,
    ),
    Rule(
        TEMPLATE_QUALIFIER_IN_ELEMENT,
        "A template qualifier on an element needs a template submodel",
        "Part 1, constraint AASd-129, V3.1 wording without the V3.2 exception "
        "for operation variables. The SDK does not check it.",
        template_qualifier_in_element,
    ),
)
