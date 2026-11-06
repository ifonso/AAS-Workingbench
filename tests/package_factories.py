"""Builders for AASX packages whose files are not what a normal writer makes.

They complement `tests/factories.py` for the safe-save tests: a package with a
File element that points to a missing part, and a File under an annotation.
Everything is written through BaSyx, never by hand.
"""

from collections.abc import Mapping
import io
from pathlib import Path

from basyx.aas import model
from basyx.aas.adapter.aasx import AASXWriter
from basyx.aas.adapter.aasx import DictSupplementaryFileContainer
import pyecma376_2
from tests.factories import make_external_reference
from tests.factories import make_file_element
from tests.factories import make_property
from tests.factories import make_shell
from tests.factories import make_store
from tests.factories import make_submodel

DOCUMENT_PART = "/aasx/files/document.pdf"
DOCUMENT_BYTES = b"%PDF-1.4 document"
MISSING_PART = "/aasx/files/datasheet_en.pdf"
ANNOTATION_PART = "/aasx/files/annotation.txt"
ANNOTATION_BYTES = b"annotation text"


def write_aasx_tolerating_missing_files(
    path: Path,
    objects: model.SetIdentifiableStore,
    files: Mapping[str, tuple[bytes, str]] | None = None,
    thumbnail: tuple[str, bytes, str] | None = None,
    core_properties: pyecma376_2.OPCCoreProperties | None = None,
) -> Path:
    """Writes an AASX package, even when a File element has no stored file.

    The BaSyx writer in failsafe mode skips a missing file and warns. Packages
    made by other tools look like this, and so do the real templates that fail
    to open without a tolerant reader.
    """
    file_store = DictSupplementaryFileContainer()
    for name, (content, content_type) in (files or {}).items():
        file_store.add_file(name, io.BytesIO(content), content_type)
    with AASXWriter(path.as_posix(), failsafe=True) as writer:
        writer.write_all_aas_objects(
            "/aasx/data.xml", objects, file_store, write_json=False
        )
        if thumbnail is not None:
            name, content, content_type = thumbnail
            writer.write_thumbnail(name, bytearray(content), content_type)
        if core_properties is not None:
            writer.write_core_properties(core_properties)
    return path


def make_annotated_relationship(
    id_short: str = "Annotated",
    annotations: tuple[model.DataElement, ...] = (),
) -> model.AnnotatedRelationshipElement:
    """Builds an annotated relationship element between two global ids."""
    return model.AnnotatedRelationshipElement(
        id_short=id_short,
        first=make_external_reference("urn:example:first"),
        second=make_external_reference("urn:example:second"),
        annotation=annotations,
    )


def write_package_with_missing_file(path: Path) -> Path:
    """Writes an AASX with one stored file and one File with no stored file."""
    submodel = make_submodel(
        elements=[
            make_file_element("Document", DOCUMENT_PART, "application/pdf"),
            make_file_element("Datasheet", MISSING_PART, "application/pdf"),
        ]
    )
    return write_aasx_tolerating_missing_files(
        path,
        make_store(make_shell(submodels=[submodel]), submodel),
        files={DOCUMENT_PART: (DOCUMENT_BYTES, "application/pdf")},
    )


def write_package_with_file_in_annotation(path: Path) -> Path:
    """Writes an AASX whose only reference to a stored file is in an annotation.

    The SDK scans annotations neither when it writes nor when it reads. To get
    the part into the package, a second submodel with a normal File element
    is written as a split part, which the reader never reads.
    """
    annotated = make_annotated_relationship(
        annotations=(make_file_element("Note", ANNOTATION_PART, "text/plain"),)
    )
    submodel = make_submodel(elements=[annotated])
    shell = make_shell(submodels=[submodel])
    carrier_submodel = make_submodel(
        id_="urn:uuid:00000000-0000-4000-8000-000000000099",
        id_short="Carrier",
        elements=[make_file_element("Note", ANNOTATION_PART, "text/plain")],
    )
    file_store = DictSupplementaryFileContainer()
    file_store.add_file(
        ANNOTATION_PART, io.BytesIO(ANNOTATION_BYTES), "text/plain"
    )
    with AASXWriter(path.as_posix(), failsafe=False) as writer:
        writer.write_all_aas_objects(
            "/aasx/carrier.xml",
            make_store(carrier_submodel),
            file_store,
            split_part=True,
        )
        writer.write_all_aas_objects(
            "/aasx/data.xml", make_store(shell, submodel), file_store
        )
    return path


SHARED_ID = "urn:uuid:00000000-0000-4000-8000-0000000000aa"
FIRST_PART = "/aasx/main.xml"
SECOND_PART = "/aasx/second.xml"


def write_package_with_same_id_in_two_parts(
    path: Path, identical: bool = False
) -> Path:
    """Writes an AASX in which two parts hold a submodel with the same id.

    The part that the reader reads first has the submodel `First`. The second
    part has `Second` with the same id, or an equal copy of `First`. The SDK
    keeps the first, and it skips the second without a log record, in strict
    mode as well.

    Args:
        path: Where to write the package.
        identical: Whether the second submodel is a copy of the first.
    """
    first = make_submodel(
        id_=SHARED_ID, id_short="First", elements=[make_property("Kept")]
    )
    second = (
        make_submodel(
            id_=SHARED_ID, id_short="First", elements=[make_property("Kept")]
        )
        if identical
        else make_submodel(
            id_=SHARED_ID, id_short="Second", elements=[make_property("Lost")]
        )
    )
    with AASXWriter(path.as_posix(), failsafe=False) as writer:
        writer.write_all_aas_objects(
            FIRST_PART,
            make_store(make_shell(submodels=[first]), first),
            DictSupplementaryFileContainer(),
        )
        writer.write_all_aas_objects(
            SECOND_PART, make_store(second), DictSupplementaryFileContainer()
        )
    return path
