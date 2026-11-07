"""References from AAS objects to files inside the package."""

from collections.abc import Collection
from collections.abc import Iterable
from dataclasses import dataclass
from dataclasses import field

from basyx.aas import model
from basyx.aas.util import traversal

from aas_workingbench.domain.walking import is_annotation
from aas_workingbench.domain.walking import walk_elements


@dataclass(frozen=True)
class FileReference:
    """A path to a file inside the package, as an AAS object states it.

    Attributes:
        path: The path as written in the object.
        owner_id: The id of the shell or submodel that holds the reference.
        location: Where in the owner the path is, for a message to the user.
        in_annotation: True if the File element is an annotation. The SDK
            writer skips those files.
        holder: The object that has the path: a File element, or the
            `Resource` of a default thumbnail. A command changes the path
            through it. It does not count when references are compared.
        attribute: The attribute of the holder that has the path: `value` of
            a File, `path` of a Resource.
        asset_information: For a default thumbnail, the AssetInformation that
            has it, so that a command can take the thumbnail away. None for
            a File element.
    """

    path: str
    owner_id: str
    location: str
    in_annotation: bool = False
    holder: object = field(default=None, compare=False, repr=False)
    attribute: str = "value"
    asset_information: object = field(default=None, compare=False, repr=False)

    @property
    def is_thumbnail(self) -> bool:
        """Whether the path is the default thumbnail of a shell."""
        return isinstance(self.holder, model.Resource)


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
                    FileReference(
                        thumbnail.path,
                        obj.id,
                        "Default thumbnail",
                        holder=thumbnail,
                        attribute="path",
                        asset_information=obj.asset_information,
                    )
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
                            holder=element,
                        )
                    )
    return references


def _submodel_id_of(element: model.SubmodelElement) -> str:
    """Returns the id of the submodel above an element, or an empty text."""
    parent: object = element.parent
    while isinstance(parent, model.Referable):
        if isinstance(parent, model.Submodel):
            return parent.id
        parent = parent.parent
    return ""


def references_in(
    root: model.Identifiable | model.SubmodelElement,
) -> list[FileReference]:
    """Lists the references to package files inside one object.

    It is `file_references` for one shell, submodel, or element, such as the
    object that is about to be pasted. The elements below an element are
    included, with the annotations of a relationship element.

    Args:
        root: A shell, a submodel, or a submodel element.

    Returns:
        The references, with the id of the shell or submodel as owner. An
        element that is not in a submodel yet has an empty owner.
    """
    if not isinstance(root, model.SubmodelElement):
        return file_references([root])
    owner_id = _submodel_id_of(root)
    elements: list[model.SubmodelElement] = [root]
    for element in elements:
        if isinstance(element, model.AnnotatedRelationshipElement):
            elements.extend(element.annotation)
        elements.extend(traversal.walk_submodel_element(element))
    references: list[FileReference] = []
    seen: set[int] = set()
    for element in elements:
        if id(element) in seen:
            continue
        seen.add(id(element))
        if isinstance(element, model.File) and is_package_path(element.value):
            references.append(
                FileReference(
                    element.value or "",
                    owner_id,
                    element.get_id_short_path(),
                    is_annotation(element),
                    holder=element,
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
