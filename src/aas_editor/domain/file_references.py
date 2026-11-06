"""References from AAS objects to files inside the package."""

from collections.abc import Collection
from collections.abc import Iterable
from dataclasses import dataclass

from basyx.aas import model

from aas_editor.domain.walking import is_annotation
from aas_editor.domain.walking import walk_elements


@dataclass(frozen=True)
class FileReference:
    """A path to a file inside the package, as an AAS object states it.

    Attributes:
        path: The path as written in the object.
        owner_id: The id of the shell or submodel that holds the reference.
        location: Where in the owner the path is, for a message to the user.
        in_annotation: True if the File element is an annotation. The SDK
            writer skips those files.
    """

    path: str
    owner_id: str
    location: str
    in_annotation: bool = False


def is_package_path(path: str | None) -> bool:
    """Tells whether a File value refers to a file inside the package.

    The SDK treats a value as package-internal unless it is empty, a
    network-path reference such as `//host/file`, or has a scheme such as
    `https:` in its first segment. This mirrors that rule, so that a URL is
    never reported as missing.

    Args:
        path: The value of a File element or of a thumbnail path.

    Returns:
        True if the SDK looks up this path in the package.
    """
    if not path:
        return False
    return not (path.startswith("//") or ":" in path.split("/")[0])


def file_references(
    objects: Iterable[model.Identifiable],
) -> list[FileReference]:
    """Lists every reference to a file inside the package.

    The default thumbnail of a shell and every File element count, including
    the ones under annotations. Values that point outside the package are left
    out.

    Args:
        objects: The shells and submodels of a package. Other objects are
            ignored.

    Returns:
        The references, in the iteration order of the objects.
    """
    references: list[FileReference] = []
    for obj in objects:
        if isinstance(obj, model.AssetAdministrationShell):
            thumbnail = obj.asset_information.default_thumbnail
            if thumbnail is not None and is_package_path(thumbnail.path):
                references.append(
                    FileReference(thumbnail.path, obj.id, "Default thumbnail")
                )
        elif isinstance(obj, model.Submodel):
            for element in walk_elements(obj):
                if isinstance(element, model.File) and is_package_path(
                    element.value
                ):
                    references.append(
                        FileReference(
                            element.value or "",
                            obj.id,
                            element.get_id_short_path(),
                            is_annotation(element),
                        )
                    )
    return references


def missing_files(
    references: Iterable[FileReference], stored_files: Collection[str]
) -> list[FileReference]:
    """Selects the references whose path has no stored file.

    A path is matched exactly, as the SDK writer matches it.

    Args:
        references: The references of the package.
        stored_files: The names of the files stored in the package.

    Returns:
        The references that the SDK cannot write.
    """
    return [ref for ref in references if ref.path not in stored_files]


def unreferenced_files(
    references: Iterable[FileReference], stored_files: Iterable[str]
) -> list[str]:
    """Selects the stored files that no object refers to.

    The SDK writes only the files that a File element or a thumbnail refers to.

    Args:
        references: The references of the package.
        stored_files: The names of the files stored in the package.

    Returns:
        The names that a save would drop, sorted.
    """
    referenced = {ref.path for ref in references}
    return sorted(name for name in stored_files if name not in referenced)
