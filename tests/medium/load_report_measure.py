"""An independent count of what a package file holds, to check a load report.

A load report says what the SDK left out. This module counts `idShort` entries,
which every element, concept description and most shells and submodels have,
in the XML of the package file itself and in the objects that were loaded. The
difference is what was lost, measured without the log. An object or element
that the report says is gone takes its whole subtree with it, so the module
also counts the entries below the place the report names.

The count reads the XML with `lxml` for this check only. The editor never does.
"""

from collections import defaultdict
from dataclasses import dataclass
import re
from pathlib import Path
import zipfile

from basyx.aas import model
from lxml import etree

from aas_editor.domain.load_report import LoadIssue
from aas_editor.domain.load_report import LoadReport
from aas_editor.domain.load_report import Outcome
from aas_editor.domain.load_report import Scope
from aas_editor.domain.walking import descendants

_AAS_NAMESPACES = (
    "https://admin-shell.io/aas/3/1",
    "https://admin-shell.io/aas/3/0",
)
_LAST_CONSTRUCT = re.compile(
    r"Failed to construct (\S+) on line (\d+) using \w+!\s*$"
)
_DUPLICATE_ID = re.compile(r"^\w+\[(.*)\] has a duplicate identifier")
_OBJECT_TAGS = ("submodel", "assetAdministrationShell", "conceptDescription")
GENERATED_NAME = "generated_submodel_list_hack_"


@dataclass
class Measure:
    """What the file holds, what was loaded, and what the report accounts for.

    Attributes:
        in_file: The `idShort` entries in the AAS parts of the file.
        loaded: The `idShort` entries of the objects that were read.
        explained: The entries that the objects and elements named by the
            report held in the file.
        unplaced: Issues about an object or element that could not be found in
            the file, so their share is not in `explained`.
    """

    in_file: int
    loaded: int
    explained: int
    unplaced: list[LoadIssue]

    @property
    def shortfall(self) -> int:
        """The entries that are in the file and not in the objects."""
        return self.in_file - self.loaded


def loaded_id_shorts(objects: model.AbstractObjectStore) -> int:  # pyright: ignore[reportMissingTypeArgument, reportUnknownParameterType]
    """Counts the `idShort` entries of the objects that were read."""
    total = 0
    for obj in objects:  # pyright: ignore[reportUnknownVariableType]
        if getattr(obj, "id_short", None):
            total += 1
        if isinstance(obj, model.Submodel):
            total += sum(1 for e in descendants(obj) if _has_written_name(e))
    return total


def _has_written_name(element: model.SubmodelElement) -> bool:
    """Tells whether the file could have had an `idShort` for the element.

    The SDK gives an item of a list that has none a name of its own, which
    starts with `generated_submodel_list_hack_`. It is not in the file.
    """
    return bool(element.id_short) and not (element.id_short or "").startswith(
        GENERATED_NAME
    )


def measure(
    path: Path,
    objects: model.AbstractObjectStore,
    report: LoadReport,  # pyright: ignore[reportMissingTypeArgument, reportUnknownParameterType]
) -> Measure:
    """Counts the entries of a package file, of its objects, and of the report.

    Args:
        path: The AASX file that was read.
        objects: The objects that were loaded from it.
        report: What the reader reported.

    Returns:
        The three counts.
    """
    trees = _aas_parts(path)
    in_file = sum(_count(tree.getroot()) for tree in trees.values())
    unplaced: list[LoadIssue] = []
    dropped_ids: dict[tuple[str, str], int] = defaultdict(int)
    gone: list[etree._Element] = []  # pyright: ignore[reportPrivateUsage]
    for issue in report.left_out:
        if issue.scope not in (Scope.OBJECT, Scope.ELEMENT):
            continue
        element = _locate(issue, trees, dropped_ids)
        if element is None:
            unplaced.append(issue)
        else:
            gone.append(element)
    # An element that failed inside a submodel that failed as well is gone
    # once, and not twice.
    outermost = [
        node
        for node in gone
        if not any(
            other is not node and node in other.iterdescendants()
            for other in gone
        )
    ]
    explained = sum(_count(node) for node in outermost)
    return Measure(in_file, loaded_id_shorts(objects), explained, unplaced)


def _aas_parts(path: Path) -> dict[str, etree._ElementTree]:  # pyright: ignore[reportPrivateUsage]
    """Parses the XML parts of a package that hold AAS objects."""
    trees: dict[str, etree._ElementTree] = {}  # pyright: ignore[reportPrivateUsage]
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            if not name.lower().endswith(".xml"):
                continue
            try:
                tree = etree.parse(archive.open(name))
            except etree.XMLSyntaxError:
                continue
            root = tree.getroot()
            if etree.QName(root).namespace in _AAS_NAMESPACES:
                trees["/" + name.lstrip("/")] = tree
    return trees


def _count(element: etree._Element) -> int:  # pyright: ignore[reportPrivateUsage]
    """Counts the `idShort` elements with a text below an element.

    A few templates have an empty `<aas:idShort/>`, which names nothing.
    """
    return sum(
        1
        for node in element.iter()
        if isinstance(node.tag, str)
        and etree.QName(node).localname == "idShort"
        and (node.text or "").strip()
    )


def _locate(
    issue: LoadIssue,
    trees: dict[str, etree._ElementTree],  # pyright: ignore[reportPrivateUsage]
    dropped_ids: dict[tuple[str, str], int],
) -> etree._Element | None:  # pyright: ignore[reportPrivateUsage]
    tree = trees.get(issue.part)
    if tree is None:
        return None
    construct = _LAST_CONSTRUCT.search(issue.text)
    if construct is not None:
        tag, line = construct.group(1), int(construct.group(2))
        local = re.split(r"[}:]", tag)[-1]
        for node in tree.getroot().iter():
            if (
                isinstance(node.tag, str)
                and node.sourceline == line
                and etree.QName(node).localname == local
            ):
                return node
        return None
    duplicate = _DUPLICATE_ID.match(issue.text)
    identifier = duplicate.group(1) if duplicate else _id_of(issue)
    if identifier is None:
        return None
    holders = [
        node
        for node in tree.getroot().iter()
        if isinstance(node.tag, str)
        and etree.QName(node).localname in _OBJECT_TAGS
        and _text_of_child(node, "id") == identifier
    ]
    key = (issue.part, identifier)
    dropped_ids[key] += 1
    # In one document the first object with an id was kept, and each later one
    # has a record of its own. A part that an earlier part shadows has none
    # that was kept.
    index = dropped_ids[key] if duplicate else dropped_ids[key] - 1
    if issue.outcome is Outcome.LEFT_OUT and index < len(holders):
        return holders[index]
    return None


def _id_of(issue: LoadIssue) -> str | None:
    return (
        issue.location.removeprefix("id ")
        if issue.location.startswith("id ")
        else None
    )


def _text_of_child(node: etree._Element, local: str) -> str | None:  # pyright: ignore[reportPrivateUsage]
    for child in node:
        if isinstance(child.tag, str) and etree.QName(child).localname == local:
            return child.text
    return None
