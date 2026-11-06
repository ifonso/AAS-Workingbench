#  Copyright (C) 2021  Igor Garmaev, garmaev@gmx.net
#
#  This program is made available under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
#  without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
#  A copy of the GNU General Public License is available at http://www.gnu.org/licenses/
#
#  This program is made available under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
#  without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
#  A copy of the GNU General Public License is available at http://www.gnu.org/licenses/

from basyx.aas.model import (
    Entity,
    EntityType,
    Key,
    KeyTypes,
    File,
    Blob,
    SubmodelElement,
    Property,
    AssetAdministrationShell,
    Submodel,
    SubmodelElementList,
)
from basyx.aas.model.datatypes import String

from collections.abc import Callable

from basyx.aas.model.concept import ConceptDescription

from aas_editor.additional.classes import DictItem
from aas_editor.domain.language_tags import COMMON_LANGUAGE_TAGS
from aas_editor.domain.id_templates import IdKind

CATEGORIES = ["CONSTANT", "PARAMETER", "VARIABLE"]

LANGUAGES = list(COMMON_LANGUAGE_TAGS)

MIME_TYPES = [
    "application/graphql",
    "application/javascript",
    "application/json",
    "application/ld+json",
    "application/msw",
    "application/pdf",
    "application/sql",
    "application/vnd.api+json",
    "application/vnd.ms-excel",
    "application/vnd.ms-powerpoint",
    "application/vnd.oasis.opendocument.text",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/x-www-form-urlencoded",
    "application/xml",
    "application/zip",
    "application/zstd",
    "audio/mpeg",
    "audio/ogg",
    "image/gif",
    "image/jpeg",
    "image/png",
    "multipart/form-data",
    "text/css",
    "text/csv",
    "text/html",
    "text/php",
    "text/plain",
    "text/xml",
]

DEFAULT_INHERITOR = {
    SubmodelElement: Property,
}
# Default parameter values of types
DEFAULTS = {
    Key: {
        "type_": KeyTypes.GLOBAL_REFERENCE,
        "value": "https://www.example.com/",
    },
    Property: {
        "value_type": String,
    },
    SubmodelElementList: {
        "type_value_list_element": Property,
        "value_type_list_element": String,
    },
    # The original makes a new entity self-managed (F-EDT-04 AC17).
    Entity: {"entity_type": EntityType.SELF_MANAGED_ENTITY},
}


def _new_id(kind: IdKind) -> str:
    # Read when a dialog opens, and imported here because the settings package
    # is imported by the module that reads the settings.
    from aas_editor.ui.user_defaults import new_id

    return new_id(kind)


# Parameters whose default is made when a dialog opens, so that every new
# object gets its own value. A fixed id would be refused as a duplicate for the
# second object (D14).
GENERATED_DEFAULTS: dict[type, dict[str, Callable[[], str]]] = {
    AssetAdministrationShell: {"id_": lambda: _new_id(IdKind.AAS)},
    Submodel: {"id_": lambda: _new_id(IdKind.SUBMODEL_INSTANCE)},
    ConceptDescription: {"id_": lambda: _new_id(IdKind.CONCEPT_DESCRIPTION)},
}

DEFAULT_COMPLETIONS = {
    Key: {"value": []},
    File: {"content_type": MIME_TYPES},
    Blob: {"content_type": MIME_TYPES},
    DictItem: {"key": LANGUAGES},
    Property: {"category": CATEGORIES},
}
