"""The SDK cannot hold a blank qualifier, extension, or data specification record.

Package Explorer's `Create w/ default!` makes an empty qualifier or record, and
`Add Preset` then replaces it (F-EDT-05 AC16, F-EDT-06 AC14, F-EDT-07 AC1). The
SDK refuses such an object when it is made, when its type is cleared, and when
a file holds one, so no blank member can be in a package for a preset to
replace (ADR 0021). When an SDK upgrade allows one, a test here fails and
names what to build.
"""

import io
import json

from basyx.aas import model
from basyx.aas.adapter.json import read_aas_json_file
import pytest

STRING = model.datatypes.String


def test_a_qualifier_without_a_type_cannot_be_made() -> None:
    with pytest.raises(ValueError, match="minimum length of 1"):
        model.Qualifier("", STRING)


def test_the_type_of_a_qualifier_cannot_be_cleared() -> None:
    qualifier = model.Qualifier("Cardinality", STRING)

    with pytest.raises(ValueError, match="minimum length of 1"):
        qualifier.type = ""


def test_an_extension_without_a_name_cannot_be_made() -> None:
    with pytest.raises(ValueError, match="minimum length of 1"):
        model.Extension("")


def test_a_reference_without_keys_cannot_be_made() -> None:
    with pytest.raises(ValueError, match="at least one key"):
        model.ExternalReference(())


def test_a_data_specification_record_needs_a_reference_with_a_key() -> None:
    content = model.DataSpecificationIEC61360(
        model.PreferredNameTypeIEC61360({"en": "Name"})
    )

    with pytest.raises(ValueError, match="at least one key"):
        model.EmbeddedDataSpecification(model.ExternalReference(()), content)


def _read(document: dict[str, object], failsafe: bool) -> None:
    read_aas_json_file(io.StringIO(json.dumps(document)), failsafe=failsafe)


@pytest.mark.parametrize("failsafe", [False, True])
def test_a_file_with_a_blank_qualifier_cannot_be_read(failsafe: bool) -> None:
    document = {
        "submodels": [
            {
                "modelType": "Submodel",
                "id": "urn:s",
                "idShort": "S",
                "qualifiers": [{"type": "", "valueType": "xs:string"}],
            }
        ]
    }

    with pytest.raises(ValueError, match="minimum length of 1"):
        _read(document, failsafe)


@pytest.mark.parametrize("failsafe", [False, True])
def test_a_file_with_a_blank_record_cannot_be_read(failsafe: bool) -> None:
    document = {
        "conceptDescriptions": [
            {
                "modelType": "ConceptDescription",
                "id": "urn:c",
                "embeddedDataSpecifications": [
                    {
                        "dataSpecification": {
                            "type": "ExternalReference",
                            "keys": [],
                        },
                        "dataSpecificationContent": {
                            "modelType": "DataSpecificationIec61360",
                            "preferredName": [{"language": "en", "text": "x"}],
                        },
                    }
                ],
            }
        ]
    }

    with pytest.raises(ValueError, match="at least one key"):
        _read(document, failsafe)
