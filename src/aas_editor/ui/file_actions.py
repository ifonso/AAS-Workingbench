"""Context menu actions for the files of a package.

The panel of the package files has the same functions as buttons. These
actions put them where the files are in the package tree: on the rows of the
stored files and their folder, on File elements (the picker of D15), and on
the asset information for its default thumbnail. Registering them is done by
`register_file_actions`, which `__main__.py` calls before the first view.
"""

from basyx.aas import model
from basyx.aas.adapter.aasx import AbstractSupplementaryFileContainer

from aas_editor.application import supplementary_files as files
from aas_editor.settings.app_settings import OBJECT_ROLE
from aas_editor.ui.actions import ActionContext
from aas_editor.ui.actions import ActionSpec
from aas_editor.ui.actions import ViewKind
from aas_editor.ui.actions import default_registry
from aas_editor.ui.actions import register_action
from aas_editor.ui.file_controller import FileController
from aas_editor.ui.file_controller import FilePackage

PREFIX = "files."
_ORDER = 300


def _object(context: ActionContext) -> object:
    return context.index.data(OBJECT_ROLE)


def _stored_name(context: ActionContext) -> str | None:
    """The name of the stored file of the current row, or None."""
    from aas_editor.package import StoredFile

    obj = _object(context)
    return obj.name if isinstance(obj, StoredFile) else None


def _file_element(context: ActionContext) -> model.File | None:
    obj = _object(context)
    return obj if isinstance(obj, model.File) else None


def _asset_information(context: ActionContext) -> model.AssetInformation | None:
    obj = _object(context)
    if isinstance(obj, model.AssetInformation):
        return obj
    if isinstance(obj, model.AssetAdministrationShell):
        return obj.asset_information
    return None


def _is_file_area(context: ActionContext) -> bool:
    """Whether the current row is a stored file or the folder of them."""
    return _stored_name(context) is not None or isinstance(
        _object(context), AbstractSupplementaryFileContainer
    )


def _controller(context: ActionContext) -> FileController | None:
    package = context.package
    if package is None:
        return None
    # The package is a legacy object. It has the three attributes needed.
    return FileController(_as_file_package(package), context.view)


def _as_file_package(package: object) -> FilePackage:
    return package  # pyright: ignore[reportReturnType]


# -- the rows of the stored files -------------------------------------------


def _add(context: ActionContext) -> None:
    controller = _controller(context)
    if controller is not None:
        controller.add_from_disk()


def _new_text(context: ActionContext) -> None:
    controller = _controller(context)
    if controller is not None:
        controller.new_text_file()


def _is_text_file(context: ActionContext) -> bool:
    from aas_editor.domain import part_names

    name = _stored_name(context)
    package = context.package
    if name is None or package is None:
        return False
    store = _as_file_package(package).fileStore
    return name in store and part_names.is_text_type(
        store.get_content_type(name)
    )


def _edit_text(context: ActionContext) -> None:
    controller = _controller(context)
    name = _stored_name(context)
    if controller is not None and name is not None:
        controller.edit_text(name)


def _rename(context: ActionContext) -> None:
    controller = _controller(context)
    name = _stored_name(context)
    if controller is not None and name is not None:
        controller.rename(name)


def _move(context: ActionContext) -> None:
    controller = _controller(context)
    name = _stored_name(context)
    if controller is not None and name is not None:
        controller.move(name)


def _save_as(context: ActionContext) -> None:
    controller = _controller(context)
    name = _stored_name(context)
    if controller is not None and name is not None:
        controller.save_to_disk(name)


def _has_stored_name(context: ActionContext) -> bool:
    return _stored_name(context) is not None


# -- File elements and thumbnails -------------------------------------------


def _is_file_element(context: ActionContext) -> bool:
    return _file_element(context) is not None


def _choose(context: ActionContext) -> None:
    controller = _controller(context)
    element = _file_element(context)
    if controller is not None and element is not None:
        controller.choose_for(element)


def _add_and_link(context: ActionContext) -> None:
    controller = _controller(context)
    element = _file_element(context)
    if controller is not None and element is not None:
        controller.add_for(element)


def _create_and_link(context: ActionContext) -> None:
    controller = _controller(context)
    element = _file_element(context)
    if controller is not None and element is not None:
        controller.new_text_file(element)


def _links_to_text_file(context: ActionContext) -> bool:
    from aas_editor.domain import part_names

    element = _file_element(context)
    package = context.package
    if element is None or package is None or not element.value:
        return False
    store = _as_file_package(package).fileStore
    return element.value in store and part_names.is_text_type(
        store.get_content_type(element.value)
    )


def _edit_linked(context: ActionContext) -> None:
    controller = _controller(context)
    element = _file_element(context)
    if controller is not None and element is not None:
        controller.edit_text_of(element)


def _has_asset_information(context: ActionContext) -> bool:
    return _asset_information(context) is not None


def _choose_thumbnail(context: ActionContext) -> None:
    controller = _controller(context)
    asset = _asset_information(context)
    if controller is not None and asset is not None:
        controller.choose_thumbnail(asset)


def _add_thumbnail(context: ActionContext) -> None:
    controller = _controller(context)
    asset = _asset_information(context)
    if controller is not None and asset is not None:
        controller.add_thumbnail(asset)


def _is_package_row(context: ActionContext) -> bool:
    from aas_editor.package import Package

    return isinstance(_object(context), Package)


def _change_package_thumbnail(context: ActionContext) -> None:
    controller = _controller(context)
    if controller is not None:
        controller.change_package_thumbnail()


def _has_thumbnail(context: ActionContext) -> bool:
    asset = _asset_information(context)
    return asset is not None and asset.default_thumbnail is not None


def _remove_thumbnail(context: ActionContext) -> None:
    controller = _controller(context)
    asset = _asset_information(context)
    if controller is not None and asset is not None:
        controller.remove_thumbnail(asset)


# -- the package --------------------------------------------------------------


def _has_package(context: ActionContext) -> bool:
    return context.package is not None


def _find_dangling(context: ActionContext) -> None:
    controller = _controller(context)
    if controller is not None:
        controller.repair_dangling()


def _show_files(context: ActionContext) -> None:
    signal = getattr(context.view, "packageFilesRequested", None)
    if signal is not None and context.package is not None:
        signal.emit(context.package)


def _specs() -> list[ActionSpec]:
    packages = ViewKind.PACKAGES
    anywhere = ViewKind.ANY
    return [
        ActionSpec(
            f"{PREFIX}add",
            "Add file to package...",
            _add,
            _is_file_area,
            views=packages,
            status_tip="Add a file from disk to the supplementary files",
            order=_ORDER,
        ),
        ActionSpec(
            f"{PREFIX}new_text",
            "Create text file in package...",
            _new_text,
            _is_file_area,
            views=packages,
            status_tip="Create an empty text file in the package",
            order=_ORDER + 1,
        ),
        ActionSpec(
            f"{PREFIX}edit_text",
            "Edit text file...",
            _edit_text,
            _is_text_file,
            views=packages,
            order=_ORDER + 2,
        ),
        ActionSpec(
            f"{PREFIX}rename",
            "Rename file...",
            _rename,
            _has_stored_name,
            views=packages,
            status_tip="Rename the file and update what refers to it",
            order=_ORDER + 3,
        ),
        ActionSpec(
            f"{PREFIX}move",
            "Move file to folder...",
            _move,
            _has_stored_name,
            views=packages,
            status_tip="Move the file to a central folder of the package",
            order=_ORDER + 4,
        ),
        ActionSpec(
            f"{PREFIX}save_as",
            "Save file as...",
            _save_as,
            _has_stored_name,
            mutates=False,
            views=packages,
            status_tip="Write the stored file to a file on disk",
            order=_ORDER + 5,
        ),
        ActionSpec(
            f"{PREFIX}choose",
            "Choose package file...",
            _choose,
            _is_file_element,
            views=anywhere,
            status_tip="Make this File refer to a supplementary file",
            order=_ORDER + 6,
        ),
        ActionSpec(
            f"{PREFIX}add_and_link",
            "Add file to package and link...",
            _add_and_link,
            _is_file_element,
            views=anywhere,
            status_tip="Add a file from disk and make this File refer to it",
            order=_ORDER + 7,
        ),
        ActionSpec(
            f"{PREFIX}create_and_link",
            "Create text file and link...",
            _create_and_link,
            _is_file_element,
            views=anywhere,
            order=_ORDER + 8,
        ),
        ActionSpec(
            f"{PREFIX}edit_linked",
            "Edit linked text file...",
            _edit_linked,
            _links_to_text_file,
            views=anywhere,
            order=_ORDER + 9,
        ),
        ActionSpec(
            f"{PREFIX}choose_thumbnail",
            "Choose default thumbnail from package files...",
            _choose_thumbnail,
            _has_asset_information,
            views=anywhere,
            order=_ORDER + 10,
        ),
        ActionSpec(
            f"{PREFIX}add_thumbnail",
            "Add file as default thumbnail...",
            _add_thumbnail,
            _has_asset_information,
            views=anywhere,
            order=_ORDER + 11,
        ),
        ActionSpec(
            f"{PREFIX}package_thumbnail",
            "Change package thumbnail...",
            _change_package_thumbnail,
            _is_package_row,
            views=packages,
            status_tip=(
                "Choose the image that a file browser shows for the AASX file"
            ),
            order=_ORDER + 15,
        ),
        ActionSpec(
            f"{PREFIX}remove_thumbnail",
            "Remove default thumbnail...",
            _remove_thumbnail,
            _has_thumbnail,
            views=anywhere,
            status_tip="Take the default thumbnail away. The file stays",
            order=_ORDER + 14,
        ),
        ActionSpec(
            f"{PREFIX}show",
            "Show package files",
            _show_files,
            _has_package,
            mutates=False,
            views=packages,
            order=_ORDER + 12,
        ),
        ActionSpec(
            f"{PREFIX}dangling",
            "Find dangling file references...",
            _find_dangling,
            _has_package,
            mutates=False,
            views=packages,
            status_tip="Find File elements that point to a file that is not stored",
            order=_ORDER + 13,
        ),
    ]


def action_ids() -> list[str]:
    """Returns the ids of the actions of this module."""
    return [spec.action_id for spec in _specs()]


def register_file_actions() -> None:
    """Adds the actions to the registry, once.

    Call it before the first view is created, from the composition root.
    """
    registered = {
        spec.action_id for spec in default_registry().specs_for(ViewKind.ANY)
    }
    for spec in _specs():
        if spec.action_id not in registered:
            register_action(spec)


def dangling_count(package: FilePackage) -> int:
    """Counts the references to files that the package does not hold."""
    return len(files.find_dangling(package.objStore, package.fileStore))
