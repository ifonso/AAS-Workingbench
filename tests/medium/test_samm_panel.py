"""A concept description with a SAMM element, in its tab (F-EDT-05 AC18).

The tab lists the Identifiable attributes before the Referable ones, and the
hint about a missing data specification stays away.
"""

from basyx.aas import model
from tests.factories import make_concept_description
from tests.factories import make_samm_concept
from tests.factories import make_store

from aas_workingbench.settings.app_settings import NAME_ROLE
from aas_workingbench.domain.validation import HINT_RULES
from aas_workingbench.domain.validation import validate


def _attribute_names(views, id_short: str, concept: model.ConceptDescription):
    shown = views()
    shown.open_package(concept)
    attrs = shown.attrs_view("concept_descriptions", id_short)
    proxy = attrs.model()
    return [
        proxy.index(row, 0).data(NAME_ROLE) for row in range(proxy.rowCount())
    ]


def test_a_samm_description_lists_id_before_id_short(views) -> None:
    names = _attribute_names(
        views, "Aspect", make_samm_concept("urn:samm:a", "Aspect")
    )

    assert names.index("id") < names.index("id_short")
    assert names.index("administration") < names.index("id_short")


def test_another_description_lists_id_short_before_id(views) -> None:
    names = _attribute_names(
        views, "Plain", make_concept_description("urn:cd:p", "Plain")
    )

    assert names.index("id_short") < names.index("id")


def test_a_description_without_data_specification_gets_a_hint() -> None:

    report = validate(
        make_store(make_concept_description("urn:cd:p", "Plain")),
        rules=HINT_RULES,
    )

    (finding,) = report.of_rule("EDT-HINT-NO-DATA-SPEC")
    assert "no data specification" in finding.message


def test_a_samm_description_gets_no_such_hint() -> None:

    report = validate(
        make_store(make_samm_concept("urn:samm:a", "Aspect")),
        rules=HINT_RULES,
    )

    assert report.of_rule("EDT-HINT-NO-DATA-SPEC") == ()


def test_a_description_with_a_record_gets_no_hint() -> None:

    concept = make_concept_description("urn:cd:p", "Plain")
    concept.embedded_data_specifications.append(
        model.EmbeddedDataSpecification(
            model.ExternalReference(
                (model.Key(model.KeyTypes.GLOBAL_REFERENCE, "urn:template"),)
            ),
            model.DataSpecificationIEC61360(
                model.PreferredNameTypeIEC61360({"en": "Name"})
            ),
        )
    )

    report = validate(make_store(concept), rules=HINT_RULES)

    assert report.of_rule("EDT-HINT-NO-DATA-SPEC") == ()
