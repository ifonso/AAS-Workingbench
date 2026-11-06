"""The objects of one package, listed once for all rules.

Every rule needs some view of the package: all elements, all qualifiers, all
language strings. Walking the package once for each rule would still be linear,
but it would repeat the work 20 times. The context walks lazily, and a rule
that does not need a view does not pay for it.
"""

from collections.abc import Iterable
from collections.abc import Iterator
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cached_property
from typing import cast

from basyx.aas import model

from aas_editor.domain.file_references import FileReference
from aas_editor.domain.file_references import file_references
from aas_editor.domain.references import ReferenceIndex
from aas_editor.domain.walking import walk_elements


@dataclass(frozen=True, eq=False)
class FileOwner:
    """A shell or submodel that refers to files in the package.

    Attributes:
        root: The shell or submodel.
        references: The paths it refers to, in document order.
        elements: The File elements of the root by the path in
            `FileReference.location`, so that a finding can go to the element.
    """

    root: model.Identifiable
    references: tuple[FileReference, ...]
    elements: dict[str, model.File]


@dataclass(frozen=True, eq=False)
class Held:
    """An object that is part of a referable, such as one of its qualifiers.

    Attributes:
        anchor: The referable that holds it.
        part: The held object.
    """

    anchor: model.Referable
    part: object


@dataclass(frozen=True, eq=False)
class LanguageSet:
    """A multi-language text of an object.

    Attributes:
        anchor: The referable that has the text.
        attribute: The attribute that holds it, such as `description`.
        tags: The language tags, in the order of the text.
    """

    anchor: model.Referable
    attribute: str
    tags: tuple[str, ...]


class ValidationContext:
    """The objects to validate, with views that rules share.

    Attributes:
        objects: The shells, submodels and concept descriptions.
        stored_files: The names of the files stored in the package, or None if
            the caller cannot tell. Rules about files do nothing then.
    """

    def __init__(
        self,
        objects: Iterable[model.Identifiable],
        stored_files: Iterable[str] | None = None,
    ) -> None:
        """Takes the objects. Nothing is walked until a rule asks.

        Args:
            objects: The identifiables of the package, such as its object
                store.
            stored_files: The names of the stored supplementary files, or None
                to skip the rules about files.
        """
        self.objects = tuple(objects)
        self.stored_files = (
            None if stored_files is None else frozenset(stored_files)
        )

    @cached_property
    def index(self) -> ReferenceIndex:
        """The ids and references of the package."""
        return ReferenceIndex(self.objects)

    @cached_property
    def submodels(self) -> tuple[model.Submodel, ...]:
        """The submodels of the package."""
        return tuple(o for o in self.objects if isinstance(o, model.Submodel))

    @cached_property
    def elements(
        self,
    ) -> tuple[tuple[model.Submodel, model.SubmodelElement], ...]:
        """Every element of every submodel, annotations included."""
        return tuple(
            (submodel, element)
            for submodel in self.submodels
            for element in walk_elements(submodel)
        )

    @cached_property
    def referables(self) -> tuple[model.Referable, ...]:
        """The identifiables, then every element."""
        return (*self.objects, *(element for _, element in self.elements))

    @cached_property
    def file_owners(self) -> tuple[FileOwner, ...]:
        """The shells and submodels that refer to files in the package."""
        files: dict[int, dict[str, model.File]] = {}
        for submodel, element in self.elements:
            if isinstance(element, model.File):
                path = element.get_id_short_path()
                files.setdefault(id(submodel), {})[path] = element
        owners: list[FileOwner] = []
        for obj in self.objects:
            references = file_references([obj])
            if references:
                owners.append(
                    FileOwner(obj, tuple(references), files.get(id(obj), {}))
                )
        return tuple(owners)

    @cached_property
    def qualifiers(self) -> tuple[tuple[model.Referable, model.Qualifier], ...]:
        """Every qualifier, with the submodel or element that it qualifies."""
        found: list[tuple[model.Referable, model.Qualifier]] = []
        for referable in self.referables:
            if isinstance(referable, model.Qualifiable):
                found.extend((referable, q) for q in referable.qualifier)
        return tuple(found)

    @cached_property
    def extensions(self) -> tuple[tuple[model.Referable, model.Extension], ...]:
        """Every extension, with the object that has it."""
        return tuple(
            (referable, extension)
            for referable in self.referables
            for extension in referable.extension
        )

    @cached_property
    def specific_asset_ids(self) -> tuple[Held, ...]:
        """Every specific asset id of a shell and of an entity."""
        found: list[Held] = []
        for referable in self.referables:
            if isinstance(referable, model.AssetAdministrationShell):
                found.extend(
                    Held(referable, s)
                    for s in referable.asset_information.specific_asset_id
                )
            elif isinstance(referable, model.Entity):
                found.extend(
                    Held(referable, s) for s in referable.specific_asset_id
                )
        return tuple(found)

    @cached_property
    def semantic_holders(self) -> tuple[Held, ...]:
        """Every object that has a semantic id, with the referable it is in."""
        found: list[Held] = []
        for referable in self.referables:
            if isinstance(referable, model.HasSemantics):
                found.append(Held(referable, referable))
        found.extend(Held(anchor, q) for anchor, q in self.qualifiers)
        found.extend(Held(anchor, e) for anchor, e in self.extensions)
        found.extend(self.specific_asset_ids)
        return tuple(found)

    @cached_property
    def language_sets(self) -> tuple[LanguageSet, ...]:
        """Every multi-language text: names, descriptions, values, IEC 61360."""
        found: list[LanguageSet] = []
        for referable in self.referables:
            for attribute in ("display_name", "description"):
                found.append(_language_set(referable, attribute, referable))
            if isinstance(referable, model.MultiLanguageProperty):
                found.append(_language_set(referable, "value", referable))
            for spec in _iec_61360(referable):
                found.extend(
                    _language_set(referable, name, spec)
                    for name in ("preferred_name", "short_name", "definition")
                )
        return tuple(s for s in found if s.tags)

    @cached_property
    def coded_values(self) -> dict[model.Reference, tuple[str, ...]]:
        """The texts that value lists give to the references of their values.

        A `ValueReferencePair` of an IEC 61360 value list says that the
        reference `value_id` stands for the text `value`. This is what a
        `valueId` points at, when the package holds the list.
        """
        coded: dict[model.Reference, list[str]] = {}
        for referable in self.referables:
            for spec in _iec_61360(referable):
                value_list = spec.value_list
                if value_list is None:
                    continue
                for pair in value_list:
                    if pair.value_id is not None:
                        coded.setdefault(pair.value_id, []).append(pair.value)
        return {reference: tuple(values) for reference, values in coded.items()}


def _iec_61360(
    referable: model.Referable,
) -> Iterator[model.DataSpecificationIEC61360]:
    if not isinstance(referable, model.HasDataSpecification):
        return
    for embedded in referable.embedded_data_specifications:
        content = embedded.data_specification_content
        if isinstance(content, model.DataSpecificationIEC61360):
            yield content


def _language_set(
    anchor: model.Referable, attribute: str, owner: object
) -> LanguageSet:
    value = cast("Mapping[str, str] | None", getattr(owner, attribute, None))
    tags = () if value is None else tuple(value.keys())
    return LanguageSet(anchor, attribute, tags)
