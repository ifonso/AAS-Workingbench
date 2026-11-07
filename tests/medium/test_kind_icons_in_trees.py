"""The kind icons show in the trees, follow the theme, and can be told apart."""

from collections.abc import Iterator
from itertools import combinations

from basyx.aas import model
from PyQt6.QtCore import QRect
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtGui import QIcon
from PyQt6.QtGui import QImage
from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import QApplication
import pytest
from tests.factories import make_annotated_relationship
from tests.factories import make_blob
from tests.factories import make_collection
from tests.factories import make_concept_description
from tests.factories import make_entity
from tests.factories import make_external_reference
from tests.factories import make_file_element
from tests.factories import make_list
from tests.factories import make_multi_language_property
from tests.factories import make_operation
from tests.factories import make_property
from tests.factories import make_reference_to
from tests.factories import make_shell
from tests.factories import make_submodel

from aas_workingbench.domain.design_tokens import DARK
from aas_workingbench.domain.design_tokens import LIGHT
from aas_workingbench.models.item_standard import StandardItem
from aas_workingbench.ui.theme import THEME_DARK
from aas_workingbench.ui.theme import THEME_LIGHT
from aas_workingbench.ui.theme import theme_manager
from aas_workingbench.ui.theme.kind_icons import KIND_NAMES
from aas_workingbench.ui.theme.kind_icons import KIND_ROLE
from aas_workingbench.ui.theme.kind_icons import kind_icon
from aas_workingbench.ui.theme.kind_icons import kind_name
from aas_workingbench.ui.theme.kind_icons import KINDS_FOLDER
from aas_workingbench.ui.theme.icons import icon_color
from aas_workingbench.ui.theme.icons import svg_icon

SIZE = 16


@pytest.fixture(autouse=True)
def native_look(qapp: QApplication) -> Iterator[None]:
    yield
    theme_manager().reset_to_native()


def _one_of_every_kind() -> list[object]:
    submodel = make_submodel(elements=[make_property("P")])
    reference = make_reference_to(submodel)
    return [
        make_shell(),
        submodel,
        make_concept_description(),
        make_shell().asset_information,
        reference,
        make_collection(),
        make_list(),
        make_entity(),
        make_operation(),
        model.Capability("Capability"),
        model.BasicEventElement(
            "Event",
            observed=reference,
            direction=model.Direction.OUTPUT,
            state=model.StateOfEvent.ON,
        ),
        make_property(),
        make_multi_language_property(),
        model.Range("Range", model.datatypes.Int, 1, 2),
        make_blob(),
        make_file_element(),
        model.ReferenceElement("Reference", value=reference),
        model.RelationshipElement(
            "Relationship",
            make_external_reference("urn:a"),
            make_external_reference("urn:b"),
        ),
        make_annotated_relationship(),
        model.Qualifier("q", model.datatypes.String),
        model.Extension("e"),
        model.SpecificAssetId("serial", "42"),
        make_external_reference("urn:x"),
        model.EmbeddedDataSpecification(
            make_external_reference("urn:spec"),
            model.DataSpecificationIEC61360(
                model.PreferredNameTypeIEC61360({"en": "Name"})
            ),
        ),
    ]


def _draw(icon: QIcon, mode: QIcon.Mode = QIcon.Mode.Normal) -> QImage:
    image = QImage(SIZE, SIZE, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    icon.paint(
        painter, QRect(0, 0, SIZE, SIZE), Qt.AlignmentFlag.AlignCenter, mode
    )
    painter.end()
    return image


def _kind_files() -> list[QIcon]:
    return [
        svg_icon(KINDS_FOLDER / f"{name}.svg", KIND_ROLE) for name in KIND_NAMES
    ]


@pytest.mark.parametrize(
    "obj", _one_of_every_kind(), ids=lambda o: type(o).__name__
)
def test_a_row_of_every_kind_has_an_icon(
    qapp: QApplication, obj: object
) -> None:
    item = StandardItem(obj)

    assert not item.icon.isNull()
    assert item.data(Qt.ItemDataRole.DecorationRole) is not None


def test_the_rows_of_the_trees_reach_all_24_icons() -> None:
    reached = {kind_name(obj) for obj in _one_of_every_kind()}

    assert reached == set(KIND_NAMES)


def test_a_value_that_is_no_kind_has_no_icon(qapp: QApplication) -> None:
    assert kind_icon("text") is None
    assert StandardItem("text").icon.isNull()


def test_the_package_tree_shows_the_kind_icons(views: object) -> None:
    shown = views()  # type: ignore[operator]
    shown.open_package(  # type: ignore[attr-defined]
        make_shell(),
        make_submodel(
            elements=[make_property("Speed"), make_collection("Group")]
        ),
        make_concept_description(),
    )

    def icon_at(*names: str) -> QIcon:
        return shown.index(*names).data(Qt.ItemDataRole.DecorationRole)  # type: ignore[attr-defined,no-any-return]

    icons = [
        icon_at("submodels", "Submodel"),
        icon_at("submodels", "Submodel", "Speed"),
        icon_at("submodels", "Submodel", "Group"),
    ]
    images = [_draw(icon) for icon in icons]
    assert all(not icon.isNull() for icon in icons)
    assert images[0] != images[1]
    assert images[1] != images[2]
    assert images[0] != images[2]


@pytest.mark.parametrize(
    "theme, tokens", [(THEME_LIGHT, LIGHT), (THEME_DARK, DARK)]
)
def test_every_kind_icon_draws_in_the_color_of_the_theme(
    qapp: QApplication, theme: str, tokens: object
) -> None:
    theme_manager().apply(theme)
    wanted = QColor(icon_color(tokens, KIND_ROLE, QIcon.Mode.Normal))  # type: ignore[arg-type]

    for icon in _kind_files():
        image = _draw(icon)
        inked = [
            image.pixelColor(x, y)
            for x in range(SIZE)
            for y in range(SIZE)
            if image.pixelColor(x, y).alpha() >= 200
        ]
        assert inked
        # Qt keeps pixels premultiplied, so a color can be off by rounding.
        assert all(
            abs(c.red() - wanted.red()) <= 8
            and abs(c.green() - wanted.green()) <= 8
            and abs(c.blue() - wanted.blue()) <= 8
            for c in inked
        )


def test_a_kind_icon_changes_with_the_theme(qapp: QApplication) -> None:
    icon = kind_icon(make_property())
    assert icon is not None

    theme_manager().apply(THEME_LIGHT)
    light = _draw(icon)
    theme_manager().apply(THEME_DARK)
    dark = _draw(icon)

    assert light != dark


@pytest.mark.parametrize("theme", [THEME_LIGHT, THEME_DARK])
def test_every_kind_has_ink_at_16_pixels_and_no_two_look_alike(
    qapp: QApplication, theme: str
) -> None:
    theme_manager().apply(theme)
    images = {
        name: _draw(icon)
        for name, icon in zip(KIND_NAMES, _kind_files(), strict=True)
    }

    for name, image in images.items():
        ink = sum(
            image.pixelColor(x, y).alpha()
            for x in range(SIZE)
            for y in range(SIZE)
        )
        assert ink > 255 * 20, name
    for (first, a), (second, b) in combinations(images.items(), 2):
        different = sum(
            a.pixel(x, y) != b.pixel(x, y)
            for x in range(SIZE)
            for y in range(SIZE)
        )
        assert different >= 12, (first, second)
