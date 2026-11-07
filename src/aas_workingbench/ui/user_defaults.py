"""What the user's settings give to new objects: languages and ids.

The rules are in `domain/default_languages.py` and `domain/id_templates.py`,
which read texts. This module is the one place that reads the texts from the
settings of the application, so the dialogs that make new objects ask here and
never touch `AppSettings` themselves.

Example:
    A form that starts a new multi-language text with a row for each default
    language::

        for language in default_languages():
            add_row(language, "")
"""

from collections.abc import Callable

from basyx.aas import model
from basyx.aas.model.concept import ConceptDescription

from aas_workingbench.domain import default_languages as languages
from aas_workingbench.domain import id_templates
from aas_workingbench.domain.id_templates import IdKind
from aas_workingbench.settings.app_settings import AppSettings
from aas_workingbench.settings.app_settings import Setting

ID_TEMPLATE_SETTINGS: dict[IdKind, Setting] = {
    IdKind.AAS: AppSettings.ID_TEMPLATE_AAS,
    IdKind.ASSET: AppSettings.ID_TEMPLATE_ASSET,
    IdKind.SUBMODEL_INSTANCE: AppSettings.ID_TEMPLATE_SUBMODEL_INSTANCE,
    IdKind.SUBMODEL_TEMPLATE: AppSettings.ID_TEMPLATE_SUBMODEL_TEMPLATE,
    IdKind.CONCEPT_DESCRIPTION: AppSettings.ID_TEMPLATE_CONCEPT_DESCRIPTION,
}
"""The setting that holds the template of each kind of id."""


def default_languages() -> tuple[str, ...]:
    """Returns the languages that a new multi-language text starts with."""
    return languages.default_languages(_text(AppSettings.DEFAULT_LANGUAGES))


def first_default_language() -> str:
    """Returns the language of a single new entry of a language list."""
    return default_languages()[0]


def id_template(kind: IdKind) -> str:
    """Returns the template that the user set for a kind of id, or empty."""
    return _text(ID_TEMPLATE_SETTINGS[kind]) or ""


def new_id(kind: IdKind) -> str:
    """Makes an id of a kind from its template, or a `urn:uuid:` without one."""
    return id_templates.generate_id(id_template(kind))


def id_kind_of(obj: object) -> IdKind:
    """Tells which template an id of an object follows.

    Args:
        obj: A shell, a submodel, or a concept description.

    Returns:
        The kind of id. A submodel follows the template of its modelling
        kind, and anything else the one of shells.
    """
    if isinstance(obj, model.Submodel):
        return (
            IdKind.SUBMODEL_TEMPLATE
            if obj.kind is model.ModellingKind.TEMPLATE
            else IdKind.SUBMODEL_INSTANCE
        )
    if isinstance(obj, ConceptDescription):
        return IdKind.CONCEPT_DESCRIPTION
    return IdKind.AAS


def id_generator(kind: IdKind) -> Callable[[], str]:
    """Returns a function that makes a new id of a kind on each call."""
    return lambda: new_id(kind)


def _text(setting: Setting) -> str | None:
    value = setting.value()
    return value if isinstance(value, str) else None
