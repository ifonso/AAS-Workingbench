"""Rules about files: paths with no stored file, and stored files with no path.

These use `domain.file_references`, which the save flow uses too, so the rules
and the save checks cannot disagree about which package can be written.
"""

from collections.abc import Iterator

from basyx.aas import model

from aas_editor.domain.file_references import FileReference
from aas_editor.domain.file_references import missing_files
from aas_editor.domain.file_references import unreferenced_files
from aas_editor.domain.validation.context import FileOwner
from aas_editor.domain.validation.context import ValidationContext
from aas_editor.domain.validation.findings import Finding
from aas_editor.domain.validation.findings import Severity
from aas_editor.domain.validation.rule import Rule

MISSING_FILE = "EDT-MISSING-FILE"
FILE_IN_ANNOTATION = "EDT-FILE-IN-ANNOTATION"
UNREFERENCED_FILE = "EDT-UNREFERENCED-FILE"


def missing_file(context: ValidationContext) -> Iterator[Finding]:
    """Finds a File or thumbnail path that has no stored file.

    The SDK cannot write such a package as AASX, and the original cannot read
    it again, so D5 offers no Save anyway. A path outside the package, such as
    a URL, is not a package path. A File under an annotation is reported by
    its own rule.
    """
    stored = context.stored_files
    if stored is None:
        return
    for owner in context.file_owners:
        in_package = [ref for ref in owner.references if not ref.in_annotation]
        for reference in missing_files(in_package, stored):
            anchor = _anchor(owner, reference)
            yield Finding(
                MISSING_FILE,
                Severity.ERROR,
                f"The path '{reference.path}' ({reference.location}) is not "
                "a file in the package. The package cannot be saved as AASX "
                "until the path is removed or the file is added",
                anchor,
                anchor,
                "value",
                blocks_save=True,
            )


def file_in_annotation(context: ValidationContext) -> Iterator[Finding]:
    """Finds a File under an annotation, which the SDK cannot write.

    The SDK writer skips annotations when it collects files, so an AASX save
    would lose the file.
    """
    for owner in context.file_owners:
        for reference in owner.references:
            if not reference.in_annotation:
                continue
            anchor = _anchor(owner, reference)
            yield Finding(
                FILE_IN_ANNOTATION,
                Severity.ERROR,
                f"The File '{reference.location}' ({reference.path}) is an "
                "annotation. It cannot be saved to an AASX file. Save as JSON "
                "or XML, or move the File out of the annotation",
                anchor,
                anchor,
                "value",
                blocks_save=True,
            )


def unreferenced_file(context: ValidationContext) -> Iterator[Finding]:
    """Finds a stored file that no File element or thumbnail refers to.

    A save to AASX keeps these files (ADR 0030), and a save to JSON or XML
    warns that it drops all files (D7). The finding makes a leftover visible,
    such as a file whose element the user removed.
    """
    stored = context.stored_files
    if stored is None:
        return
    references = [
        ref for owner in context.file_owners for ref in owner.references
    ]
    for name in unreferenced_files(references, stored):
        yield Finding(
            UNREFERENCED_FILE,
            Severity.WARNING,
            f"The file '{name}' is in the package, but no File element or "
            "thumbnail refers to it. A save to AASX keeps it until it is "
            "removed from the package files",
            name,
        )


def _anchor(owner: FileOwner, reference: FileReference) -> model.Referable:
    return owner.elements.get(reference.location, owner.root)


RULES = (
    Rule(
        MISSING_FILE,
        "A File points at a stored file",
        "The SDK writer raises KeyError for a File with no stored file, and "
        "the reader cannot reopen the result (ADR 0006, decision D5).",
        missing_file,
    ),
    Rule(
        FILE_IN_ANNOTATION,
        "No File under an annotation",
        "The SDK skips annotations when it writes the files of an AASX "
        "(ADR 0006).",
        file_in_annotation,
    ),
    Rule(
        UNREFERENCED_FILE,
        "Stored files are used",
        "A file that nothing refers to is kept by a save to AASX (ADR 0030), "
        "and dropped by a save to JSON or XML (D7).",
        unreferenced_file,
    ),
)
