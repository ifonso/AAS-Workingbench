"""No attribute that a tab can show goes without a name in the vocabulary.

The first test walks the classes of the SDK, so that a class or an attribute
that a later SDK adds fails here and is named, and does not show up in a tab
as Python. The second test walks the rows that tabs really show for the
bundled packages.
"""

from collections.abc import Iterable
from collections.abc import Iterator
from collections.abc import Mapping
from collections.abc import Sequence
from collections.abc import Set as AbstractSet
from enum import Enum
import inspect

import pytest
from tests.conftest import TEST_DATA_DIR

PACKAGES = (
    "TestPackage.aasx",
    "IDTA 02002-1-0_Template_ContactInformation.aasx",
    "IDTA 02023 _Template_CarbonFootprint.aasx",
    "IDTA 02058-1-0_Template_AIDataset.aasx",
)

# What the tabs show for these is not a set of attributes: containers show
# their entries, and an enumeration or an exception shows nothing.
_NOT_SHOWN_AS_ATTRIBUTES = (
    Enum,
    BaseException,
    Mapping,
    AbstractSet,
    Sequence,
)


def _sdk_classes() -> Iterator[type]:
    import basyx.aas.model.aas as aas
    import basyx.aas.model.base as base
    import basyx.aas.model.concept as concept
    import basyx.aas.model.submodel as submodel

    seen: set[type] = set()
    for module in (aas, base, concept, submodel):
        for _, cls in inspect.getmembers(module, inspect.isclass):
            if (
                cls.__module__ == module.__name__
                and cls not in seen
                and not issubclass(cls, _NOT_SHOWN_AS_ATTRIBUTES)
            ):
                seen.add(cls)
                yield cls


def _attributes_a_tab_shows(cls: type) -> set[str]:
    """The attributes of the class that `getAttrs4detailInfo` lists.

    That function reads an object, which most classes cannot make without
    arguments. The attributes of an object are the public ones of its class,
    and the parameters of its constructor, which are set on the object.
    """
    # The settings must be imported first, or the utils import in a circle.
    import aas_workingbench.settings  # noqa: F401
    from aas_workingbench.utils.util import getAttrsOfCls
    from aas_workingbench.utils.util_classes import ClassesInfo

    of_class = {
        name
        for name in dir(cls)
        if not name.startswith("_") and not callable(getattr(cls, name))
    }
    shown = of_class | set(getAttrsOfCls(cls))
    return shown - set(ClassesInfo.hiddenAttrs(cls))


def test_every_attribute_of_every_class_of_the_sdk_has_an_entry(
    qapp: object,
) -> None:
    from aas_workingbench.domain.attribute_vocabulary import attribute_info

    unnamed = sorted(
        f"{cls.__name__}.{attribute}"
        for cls in _sdk_classes()
        for attribute in _attributes_a_tab_shows(cls)
        if attribute_info(cls, attribute) is None
    )

    assert unnamed == []


def test_the_walk_finds_the_classes_that_tabs_show(qapp: object) -> None:
    names = {cls.__name__ for cls in _sdk_classes()}

    assert {
        "Property",
        "Submodel",
        "AssetAdministrationShell",
        "ConceptDescription",
        "Qualifier",
        "Reference",
        "DataSpecificationIEC61360",
    } <= names


def test_the_walk_finds_the_attributes_that_tabs_show(qapp: object) -> None:
    from basyx.aas import model

    shown = _attributes_a_tab_shows(model.Property)

    assert {
        "id_short",
        "display_name",
        "semantic_id",
        "qualifier",
        "value",
        "value_type",
        "value_id",
    } <= shown
    assert "parent" not in shown


@pytest.mark.parametrize("package_name", PACKAGES)
def test_every_row_of_a_bundled_package_has_a_name_in_the_vocabulary(
    qapp: object, package_name: str
) -> None:
    from PyQt6.QtCore import QModelIndex

    from aas_workingbench.domain.attribute_vocabulary import attribute_info
    from aas_workingbench.domain.attribute_vocabulary import LIST_INDEX
    from aas_workingbench.models import DetailedInfoTable
    from aas_workingbench.models import PackTreeViewItem
    from aas_workingbench.models import PacksTable
    from aas_workingbench.package import Package
    from aas_workingbench.settings import EXTENDED_COLUMNS_IN_PACK_TABLE
    from aas_workingbench.settings.app_settings import (
        DEFAULT_COLUMNS_IN_PACKS_TABLE,
    )
    from aas_workingbench.settings.app_settings import NAME_ROLE
    from aas_workingbench.settings.app_settings import PARENT_OBJ_ROLE

    columns = [*DEFAULT_COLUMNS_IN_PACKS_TABLE, *EXTENDED_COLUMNS_IN_PACK_TABLE]
    table = PacksTable(columns, PackTreeViewItem(None, None))
    table.addItem(Package(TEST_DATA_DIR / package_name))
    unnamed: set[str] = set()

    def walk_tab(tab: DetailedInfoTable, parent: QModelIndex) -> None:
        for row in range(tab.rowCount(parent)):
            index = tab.index(row, 0, parent)
            owner = index.data(PARENT_OBJ_ROLE)
            name = index.data(NAME_ROLE)
            # The rows below a list are its entries, which are named by what
            # they are, and not by an attribute. The row with the position of
            # an item is the editor's, and has its own entry.
            is_attribute = (
                owner is not None
                and not isinstance(owner, Iterable)
                and name != LIST_INDEX.sdk_name
            )
            if is_attribute and attribute_info(type(owner), name) is None:
                unnamed.add(f"{type(owner).__name__}.{name}")
            walk_tab(tab, index)

    def walk_packages(parent: QModelIndex) -> None:
        for row in range(table.rowCount(parent)):
            index = table.index(row, 0, parent)
            walk_tab(DetailedInfoTable(index), QModelIndex())
            walk_packages(index)

    walk_packages(QModelIndex())

    assert sorted(unnamed) == []
