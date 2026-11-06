#  Copyright (C) 2021  Igor Garmaev, garmaev@gmx.net
#
#  This program is made available under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
#  without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
#  A copy of the GNU General Public License is available at http://www.gnu.org/licenses/
import datetime
import typing
from dataclasses import dataclass
from pathlib import Path

import toml
from PyQt6.QtCore import QSize, QSettings, QDir
from PyQt6.QtGui import QFont, QIcon
from PyQt6 import QtCore

from aas_editor.settings.util_constants import NOT_GIVEN

# Anchor: aas_editor/ package directory (this file lives in aas_editor/settings/)
_PACKAGE_DIR = Path(__file__).resolve().parent.parent


def _register_search_path(path: Path) -> Path:
    QDir.addSearchPath("themes", str(path))
    return path


SUBMODEL_TEMPLATES_FOLDER = _PACKAGE_DIR / "submodel_templates"

# Frozen builds ship pyproject.toml next to the package; source checkouts keep it
# at the repository root, above src/.
_PYPROJECT_FILE = next(
    path
    for path in (
        _PACKAGE_DIR.parent / "pyproject.toml",
        _PACKAGE_DIR.parent.parent / "pyproject.toml",
    )
    if path.is_file()
)
PYPROJECT_TOML = toml.load(_PYPROJECT_FILE)

VERSION = PYPROJECT_TOML["project"]["version"]
APPLICATION_NAME = "AAS Manager"
APPLICATION_INFO = PYPROJECT_TOML["project"]["description"]
COPYRIGHT_YEAR = datetime.datetime.now().year
CONTRIBUTORS = ", ".join(
    [
        f"{author['name']}: {author['email']}"
        for author in PYPROJECT_TOML["project"]["authors"]
    ]
)
DEVELOPER_WEB = "www.iat.rwth-aachen.de"
CONTACT = PYPROJECT_TOML["project"]["authors"][0]["email"]
REPORT_ERROR_LINK = PYPROJECT_TOML["project"]["urls"]["Issues"]
APPLICATION_LINK = PYPROJECT_TOML["project"]["urls"]["Homepage"]
IAT = "IAT"
LICENSE = PYPROJECT_TOML["project"]["license"]["text"]
AAS_METAMODEL_VERSION = "3.1"

WINDOW_TITLE = (
    f"{APPLICATION_NAME} {VERSION} (Metamodel V{AAS_METAMODEL_VERSION})"
)

TOOLBARS_HEIGHT = 30
# The attribute and type columns of a tab are as wide as the names that nearly
# every element shows need, measured with the font of the tab: the longest
# attribute of the common classes, `embeddedDataSpecifications`, and the
# longest type that an attribute declares there, `MultiLanguageNameType`. The
# longer `list of EmbeddedDataSpecification` is cut with an ellipsis and read
# in the tooltip. The padding is the branch, the cell margins and the sort mark.
WIDEST_ATTRIBUTE_NAME = "embeddedDataSpecifications"
WIDEST_TYPE_NAME = "MultiLanguageNameType"
ATTR_COLUMN_PADDING = 64
TYPE_COLUMN_PADDING = 28
# What the column gets when the font cannot be measured.
ATTR_COLUMN_WIDTH = 250
TYPE_COLUMN_WIDTH = 190
# What users edit is the value, so it gets the room that is left: it stretches
# between the name and the type.
VALUE_COLUMN_WIDTH = 200
# Raise it when the default columns of the attribute tabs change. A saved
# header state of another version is not restored, so the new default shows
# once, and what the user changes later is kept (see application/header_state).
TAB_HEADER_LAYOUT_VERSION = 3
# The same for the header of the package tree, and for the sizes of the two
# zones of the window (the tree and the tabs). Raise each one when its default
# changes, so that a session of an older release does not hide the new default.
PACK_TREE_HEADER_LAYOUT_VERSION = 1
ZONES_LAYOUT_VERSION = 1
PACK_TREE_OBJECT_COLUMN_WIDTH = 340

DEFAULT_MAINWINDOW_SIZE = QSize(1194, 624)
MAX_FONT_SIZE = 60
MIN_FONT_SIZE = 6
DEFAULT_FONT = QFont()
DEFAULT_FONT.setWeight(40)
DEFAULT_FONT.setPointSize(12)

MAX_RECENT_FILES = 10
MAX_SIGNS_TO_SHOW = 1000
MAX_SIGNS_TO_SHOW_IN_TREE = 150

# Custom roles
PACKAGE_ROLE = 1010
NAME_ROLE = 1020
COLUMN_NAME_ROLE = 1025
OBJECT_ROLE = 1030
PARENT_OBJ_ROLE = 1040
PACK_ITEM_ROLE = 1050
LINKED_ITEM_ROLE = 1060
IS_LINK_ROLE = 1070
IS_MEDIA_ROLE = 1080
IS_URL_MEDIA_ROLE = 1090
MEDIA_CONTENT_ROLE = 1100
OPENED_PACKS_ROLE = 1110
OPENED_FILES_ROLE = 1120
ADD_ITEM_ROLE = 1130
CLEAR_ROW_ROLE = 1140
UPDATE_ROLE = 1150
COPY_ROLE = 1155
DATA_CHANGE_FAILED_ROLE = 1180
TYPE_ROLE = 1190
TYPE_HINT_ROLE = 1200
TYPE_CHECK_ROLE = 1210
# The object and the attribute name that editing a cell sets: a tuple, or None.
EDIT_TARGET_ROLE = 1220

# Columns
OBJECT_COLUMN_NAME = "object"
OBJECT_VALUE_COLUMN_NAME = "object value"
TYPE_COLUMN_NAME = "type"
TYPEHINT_COLUMN_NAME = "typehint"

DEFAULT_COLUMNS_IN_DETAILED_INFO = (
    OBJECT_COLUMN_NAME,
    OBJECT_VALUE_COLUMN_NAME,
    TYPE_COLUMN_NAME,
    TYPEHINT_COLUMN_NAME,
)
# What the header of an attribute tab says. The last column shows the type that
# the Python SDK declares, which is hidden unless a user asks for it.
COLUMNS_IN_ATTRIBUTE_TABS = ("Attribute", "Value", "Type", "Python type")
DEFAULT_COLUMNS_IN_PACKS_TABLE = (
    OBJECT_COLUMN_NAME,
    OBJECT_VALUE_COLUMN_NAME,
    TYPE_COLUMN_NAME,
    TYPEHINT_COLUMN_NAME,
)
DEFAULT_COLUMNS_IN_PACKS_TABLE_TO_SHOW = (OBJECT_COLUMN_NAME, TYPE_COLUMN_NAME)
ATTRIBUTE_COLUMN = 0
VALUE_COLUMN = 1
TYPE_COLUMN = 2
TYPE_HINT_COLUMN = 3

# Files
SETTINGS_FILE = Path(__file__).resolve().parent / "settings.ini"
RECOVERY_DIR = Path(__file__).resolve().parent / "recovery"
# Interval between periodic recovery writes, so a native crash loses at most this
# window of edits.
RECOVERY_INTERVAL_MS = 300_000
THEMES_FOLDER = _register_search_path(_PACKAGE_DIR / "themes")
ICONS_FOLDER = _register_search_path(_PACKAGE_DIR / "icons")
CUSTOM_COLUMN_LISTS_FILE = _PACKAGE_DIR / "custom_column_lists.json"

# Themes
APP_LOGO = QIcon(str(ICONS_FOLDER / "logo.svg"))
DEFAULT_THEME = "grey"

SETTINGS = QSettings(str(SETTINGS_FILE), QSettings.Format.IniFormat)


@dataclass(order=True)
class Setting:
    name: str
    default: typing.Any = NOT_GIVEN
    type: typing.Type = NOT_GIVEN
    display_name: typing.Optional[str] = None
    description: str = ""
    options: dict[str:object] = NOT_GIVEN

    def setValue(self, value):
        return SETTINGS.setValue(self.name, value)

    def isSaved(self) -> bool:
        """Tell whether a session saved a value, and not only the default."""
        return bool(SETTINGS.contains(self.name))

    def value(self):
        args = [self.name]
        if self.default != NOT_GIVEN:
            args.append(self.default)
        if self.type != NOT_GIVEN:
            args.append(self.type)
        return SETTINGS.value(*args)


class AppSettings:
    THEME = Setting("theme", DEFAULT_THEME, str)
    SIZE = Setting("size", DEFAULT_MAINWINDOW_SIZE)
    ORIENTATION = Setting("orientation", QtCore.Qt.Orientation.Vertical, int)
    LEFT_ZONE_SIZE = Setting("leftZoneSize", QSize(300, 624))
    RIGHT_ZONE_SIZE = Setting("rightZoneSize", QSize(300, 624))
    AAS_FILES_TO_OPEN_ON_START = Setting("openedAasFiles", set())
    FONTSIZE_FILES_VIEW = Setting(
        "fontSizeFilesView", DEFAULT_FONT.pointSize(), int
    )
    FONTSIZE_DETAILED_VIEW = Setting(
        "fontSizeDetailedView", DEFAULT_FONT.pointSize(), int
    )
    PACKTREEVIEW_HEADER_STATE = Setting("packTreeViewHeaderState", None)
    # The layout that the saved state of the header of the tree was made for.
    PACKTREEVIEW_HEADER_LAYOUT = Setting("packTreeViewHeaderLayout", 0, int)
    # The layout that the saved sizes of the two zones were made for.
    ZONES_LAYOUT = Setting("zonesLayout", 0, int)
    PACKTREEVIEW_HEADER_CUSTOM_COLUMN_LISTS_FILE = CUSTOM_COLUMN_LISTS_FILE
    TABTREEVIEW_HEADER_STATE = Setting("tabTreeViewHeaderState", None)
    # The layout that the saved state of the tab header was made for.
    TABTREEVIEW_HEADER_LAYOUT = Setting("tabTreeViewHeaderLayout", 0, int)

    DEFAULT_NEW_FILETYPE = Setting(
        name="defaultNewFileType",
        display_name="Standard initialisation file type",
        description="Choose the file type that is used per default when creating a new file.",
        options={
            "json": "json",
            "xml": "xml",
            "aasx": "aasx",
        },
        default="json",
        type=str,
    )
    WRITE_JSON_IN_AASX = Setting(
        name="writeJsonInAasx",
        display_name="Write JSON in AASX",
        description="If enabled, JSON parts are created in the AASX file instead of XML parts.",
        options={"JSON": True, "XML": False},
        default=False,
        type=bool,
    )
    WRITE_PRETTY_JSON = Setting(
        name="writePrettyJson",
        display_name="Write Pretty JSON",
        description="If enabled, JSON files are saved in pretty format with indentation.",
        options={"Yes": True, "No": False},
        default=True,
        type=bool,
    )
    SORT_KEYS_IN_JSON = Setting(
        name="sortKeysInJson",
        display_name="Sort Keys in JSON",
        description="If enabled, JSON files are saved with their keys ordered alphabetically.",
        options={"Yes": True, "No": False},
        default=True,
        type=bool,
    )

    SETTINGS_TO_CHOOSE_BY_USER = [
        DEFAULT_NEW_FILETYPE,
        WRITE_JSON_IN_AASX,
        WRITE_PRETTY_JSON,
        SORT_KEYS_IN_JSON,
    ]

    # Settings that the user types. Each is a text, and the dialog of the
    # settings checks it with the function of its `aas_editor.domain` module.
    DEFAULT_LANGUAGES = Setting(
        name="defaultLanguages",
        display_name="Default languages",
        description="Language tags separated by commas, such as en,de. A new "
        "MultiLanguageProperty starts with an empty row for each of them, and "
        "a new row of a language list starts with the first one.",
        default="en",
        type=str,
    )
    ID_TEMPLATE_AAS = Setting(
        name="idTemplateAas",
        display_name="Id template for shells",
        default="",
        type=str,
    )
    ID_TEMPLATE_ASSET = Setting(
        name="idTemplateAsset",
        display_name="Id template for global asset ids",
        default="",
        type=str,
    )
    ID_TEMPLATE_SUBMODEL_INSTANCE = Setting(
        name="idTemplateSubmodelInstance",
        display_name="Id template for submodels of kind Instance",
        default="",
        type=str,
    )
    ID_TEMPLATE_SUBMODEL_TEMPLATE = Setting(
        name="idTemplateSubmodelTemplate",
        display_name="Id template for submodels of kind Template",
        default="",
        type=str,
    )
    ID_TEMPLATE_CONCEPT_DESCRIPTION = Setting(
        name="idTemplateConceptDescription",
        display_name="Id template for concept descriptions",
        default="",
        type=str,
    )
    ID_TEMPLATE_DESCRIPTION = (
        "D is replaced by a digit, X by a hexadecimal digit and A by a "
        "letter, at random. A backslash makes the next character literal. "
        "Leave it empty for a urn:uuid: id."
    )
