"""Undo, bulk steps, read mode, and the dirty flag through the real views."""

from pathlib import Path

from basyx.aas import model
from PyQt6.QtCore import QModelIndex
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog
import pytest
from tests.factories import make_collection
from tests.factories import make_list
from tests.factories import make_property
from tests.factories import make_shell
from tests.factories import make_submodel
from tests.package_factories import write_package_with_missing_file
from tests.serialization import snapshot

EDIT = Qt.ItemDataRole.EditRole


def _anonymous(value: str) -> model.Property:
    """A property for a list, which has no idShort of its own."""
    return model.Property(
        id_short=None, value_type=model.datatypes.String, value=value
    )


def _collection():
    return make_collection(
        "Collection",
        [make_property("x"), make_property("y"), make_property("z")],
    )


def _ids(collection: model.SubmodelElementCollection) -> list[str]:
    return [element.id_short for element in collection.value]


class TestBulkSteps:
    def test_deleting_several_rows_is_one_step_that_restores_all(
        self, views
    ) -> None:
        collection = _collection()
        shown = views()
        package = shown.open_package(make_submodel(elements=[collection]))
        original = snapshot(package.objStore)
        shown.select(
            shown.index("submodels", "Submodel", "Collection", "x"),
            shown.index("submodels", "Submodel", "Collection", "z"),
        )

        shown.view.onDelClear()
        left = _ids(collection)
        shown.view.onUndo()

        assert left == ["y"]
        assert _ids(collection) == ["x", "y", "z"]
        assert snapshot(package.objStore) == original
        assert not package.commandStack.can_undo
        assert package.commandStack.redo_description == "Delete 2 items"

    def test_cutting_several_rows_is_one_step_that_restores_all(
        self, views
    ) -> None:
        collection = _collection()
        shown = views()
        package = shown.open_package(make_submodel(elements=[collection]))
        original = snapshot(package.objStore)
        shown.select(
            shown.index("submodels", "Submodel", "Collection", "x"),
            shown.index("submodels", "Submodel", "Collection", "y"),
        )

        shown.view.onCut()
        left = _ids(collection)
        shown.view.onUndo()

        assert left == ["z"]
        assert snapshot(package.objStore) == original
        assert not package.commandStack.can_undo
        assert len(shown.view.treeClipboard.objects[-1]) == 2

    def test_cutting_one_row_is_one_step(self, views) -> None:
        collection = _collection()
        shown = views()
        package = shown.open_package(make_submodel(elements=[collection]))
        shown.select(shown.index("submodels", "Submodel", "Collection", "y"))

        shown.view.onCut()
        shown.view.onUndo()

        assert _ids(collection) == ["x", "y", "z"]
        assert not package.commandStack.can_undo

    def test_pasting_several_rows_is_one_step(self, views) -> None:
        source = _collection()
        target = make_collection("Target", [make_property("t")])
        shown = views()
        package = shown.open_package(make_submodel(elements=[source, target]))
        shown.select(
            shown.index("submodels", "Submodel", "Collection", "x"),
            shown.index("submodels", "Submodel", "Collection", "y"),
        )
        shown.view.onCopy()
        shown.select(shown.index("submodels", "Submodel", "Target"))

        shown.view.onPaste()
        after_paste = _ids(target)
        shown.view.onUndo()

        assert after_paste == ["t", "x", "y"]
        assert _ids(target) == ["t"]
        assert not package.commandStack.can_undo


class TestCutFromEveryKindOfParent:
    """The original leaves the source of a cut in lists, entities, and more."""

    def test_cut_from_a_list_removes_the_source_and_undo_puts_it_back(
        self, views
    ) -> None:
        elements = make_list(
            "List",
            [
                _anonymous("a"),
                _anonymous("b"),
                _anonymous("c"),
            ],
        )
        shown = views()
        package = shown.open_package(make_submodel(elements=[elements]))
        original = snapshot(package.objStore)
        list_index = shown.index("submodels", "Submodel", "List")
        shown.select(shown.view.model().index(1, 0, list_index))

        shown.view.onCut()
        left = [element.value for element in elements.value]
        shown.view.onUndo()

        assert left == ["a", "c"]
        assert [element.value for element in elements.value] == ["a", "b", "c"]
        assert snapshot(package.objStore) == original

    def test_cut_from_an_entity_removes_the_source_and_undo_puts_it_back(
        self, views
    ) -> None:
        entity = model.Entity(
            id_short="Entity",
            entity_type=model.EntityType.CO_MANAGED_ENTITY,
            statement=[make_property("s1"), make_property("s2")],
        )
        shown = views()
        package = shown.open_package(make_submodel(elements=[entity]))
        original = snapshot(package.objStore)
        shown.select(shown.index("submodels", "Submodel", "Entity", "s1"))

        shown.view.onCut()
        left = [element.id_short for element in entity.statement]
        shown.view.onUndo()

        assert left == ["s2"]
        assert [e.id_short for e in entity.statement] == ["s1", "s2"]
        assert snapshot(package.objStore) == original


class _FakeDialog:
    """Stands in for the edit dialogs: accepts and returns a prepared object."""

    answer: object = None

    def __init__(self, **_: object) -> None:
        pass

    def exec(self) -> int:
        return QDialog.DialogCode.Accepted

    def result(self) -> int:
        return QDialog.DialogCode.Accepted

    def getObj2add(self) -> object:
        return self.answer

    def deleteLater(self) -> None:
        pass


class TestDialogFlows:
    """The edit and add flows that open a dialog end in one undoable step."""

    def test_replacing_an_element_through_a_dialog_is_one_undoable_step(
        self, views
    ) -> None:
        collection = _collection()
        shown = views()
        package = shown.open_package(make_submodel(elements=[collection]))
        original = snapshot(package.objStore)
        dialog = type("Dialog", (_FakeDialog,), {"answer": make_property("n")})

        shown.view.replItemWithDialog(
            index=shown.index("submodels", "Submodel", "Collection", "y"),
            objVal="{}",
            editDialogType=dialog,
        )
        after_edit = _ids(collection)
        shown.view.onUndo()

        assert after_edit == ["x", "n", "z"]
        assert snapshot(package.objStore) == original
        assert not package.commandStack.can_undo

    def test_adding_an_element_through_a_dialog_is_one_undoable_step(
        self, views
    ) -> None:
        collection = _collection()
        shown = views()
        package = shown.open_package(make_submodel(elements=[collection]))
        original = snapshot(package.objStore)
        dialog = type("Dialog", (_FakeDialog,), {"answer": make_property("n")})

        shown.view.addItemWithDialog(
            parent=shown.index("submodels", "Submodel", "Collection"),
            objTypeHint=model.Property,
            editDialogType=dialog,
        )
        after_add = _ids(collection)
        shown.view.onUndo()

        assert after_add == ["x", "y", "z", "n"]
        assert snapshot(package.objStore) == original
        assert not package.commandStack.can_undo

    def test_clearing_an_attribute_to_its_default_is_undone(
        self, views
    ) -> None:
        prop = make_property("p")
        prop.category = "Parameter"
        shown = views()
        package = shown.open_package(make_submodel(elements=[prop]))
        original = snapshot(package.objStore)
        source = shown.view.sourceModel()
        column = [
            source.headerData(section, Qt.Orientation.Horizontal, 0)
            for section in range(source.columnCount())
        ].index("category")
        cell = shown.index("submodels", "Submodel", "p").siblingAtColumn(column)

        shown.view.setCurrentIndex(cell)

        shown.view.onOneItemDelClear(cell)
        cleared = prop.category
        shown.view.onUndo()

        assert cleared is None
        assert snapshot(package.objStore) == original


class TestUndoActsOnTheActivePackage:
    def test_undo_takes_back_the_step_of_the_package_that_is_current(
        self, views
    ) -> None:
        first_collection = _collection()
        second_collection = make_collection(
            "Collection", [make_property("p"), make_property("q")]
        )
        shown = views()
        first = shown.open_package(
            make_submodel("urn:uuid:s1", "Submodel", [first_collection])
        )
        second = shown.open_package(
            make_submodel("urn:uuid:s2", "Submodel", [second_collection])
        )
        shown.select(
            shown.index("submodels", "Submodel", "Collection", "x", package=0)
        )
        shown.view.onDelClear()
        shown.select(
            shown.index("submodels", "Submodel", "Collection", "p", package=1)
        )
        shown.view.onDelClear()

        shown.select(
            shown.index("submodels", "Submodel", "Collection", "y", package=0)
        )
        shown.view.onUndo()

        assert _ids(first_collection) == ["x", "y", "z"]
        assert _ids(second_collection) == ["q"]
        assert not first.commandStack.can_undo
        assert second.commandStack.can_undo

    def test_undo_action_is_enabled_by_the_history_of_the_active_package(
        self, views
    ) -> None:
        shown = views()
        shown.open_package(
            make_submodel("urn:uuid:s1", "Submodel", [_collection()])
        )
        shown.open_package(
            make_submodel("urn:uuid:s2", "Submodel", [_collection()])
        )
        shown.select(
            shown.index("submodels", "Submodel", "Collection", "x", package=0)
        )
        shown.view.onDelClear()

        enabled_in_edited = shown.view.undoAct.isEnabled()
        shown.select(
            shown.index("submodels", "Submodel", "Collection", "x", package=1)
        )

        assert enabled_in_edited
        assert not shown.view.undoAct.isEnabled()

    def test_undo_takes_back_the_step_of_the_only_package_without_a_selection(
        self, views
    ) -> None:
        collection = _collection()
        shown = views()
        shown.open_package(make_submodel(elements=[collection]))
        shown.select(shown.index("submodels", "Submodel", "Collection", "y"))
        shown.view.onDelClear()
        shown.view.setCurrentIndex(QModelIndex())

        shown.view.onUndo()

        assert _ids(collection) == ["x", "y", "z"]

    def test_attrs_view_undoes_the_package_it_shows(self, views) -> None:
        collection = _collection()
        shown = views()
        shown.open_package(make_submodel(elements=[collection]))
        attrs = shown.attrs_view("submodels", "Submodel", "Collection", "y")
        model_ = attrs.model()
        id_short = _row_named(attrs, "id_short")
        assert model_.index(id_short.row(), 0).data() == "idShort"

        attrs._setItemData(id_short.siblingAtColumn(1), "q", EDIT)
        renamed = _ids(collection)
        attrs.onUndo()

        assert renamed == ["x", "q", "z"]
        assert _ids(collection) == ["x", "y", "z"]


class TestSavedState:
    @pytest.fixture(autouse=True)
    def _confirm_save(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # The one-letter idShorts of the test package are errors of AASd-002,
        # which the save gate asks about (D5).
        monkeypatch.setattr(
            "aas_editor.treeviews.treeview_pack.confirm_save",
            lambda check, parent=None, extra=None: True,
        )

    def test_package_is_clean_after_a_save_and_changed_after_undoing_it(
        self, views, tmp_path: Path
    ) -> None:
        collection = _collection()
        shown = views()
        package = shown.open_package(make_submodel(elements=[collection]))
        shown.select(shown.index("submodels", "Submodel", "Collection", "y"))
        shown.view.onDelClear()

        saved = shown.view.savePack(package, (tmp_path / "p.json").as_posix())
        clean_after_save = not package.changed
        window_modified_after_save = shown.window.isWindowModified()
        shown.view.onUndo()

        assert saved
        assert clean_after_save
        assert not window_modified_after_save
        assert package.changed
        assert shown.window.isWindowModified()

    def test_package_is_clean_again_when_the_undone_step_is_redone(
        self, views, tmp_path: Path
    ) -> None:
        shown = views()
        package = shown.open_package(make_submodel(elements=[_collection()]))
        shown.select(shown.index("submodels", "Submodel", "Collection", "y"))
        shown.view.onDelClear()
        shown.view.savePack(package, (tmp_path / "p.json").as_posix())
        shown.view.onUndo()

        shown.view.onRedo()

        assert not package.changed
        assert not shown.window.isWindowModified()

    def test_window_is_modified_after_an_edit_and_clean_after_undo(
        self, views
    ) -> None:
        shown = views()
        shown.open_package(make_submodel(elements=[_collection()]))
        shown.select(shown.index("submodels", "Submodel", "Collection", "y"))

        shown.view.onDelClear()
        modified = shown.window.isWindowModified()
        shown.view.onUndo()

        assert modified
        assert not shown.window.isWindowModified()

    def test_failed_save_leaves_the_package_changed(
        self, views, tmp_path: Path
    ) -> None:
        shown = views()
        package = shown.open_package(make_submodel(elements=[_collection()]))
        shown.select(shown.index("submodels", "Submodel", "Collection", "y"))
        shown.view.onDelClear()

        saved = shown.view.savePack(
            package, (tmp_path / "missing folder" / "p.json").as_posix()
        )

        assert not saved
        assert package.changed

    def test_refused_save_leaves_the_package_changed(
        self, views, tmp_path: Path
    ) -> None:
        from aas_editor.package import Package

        source = write_package_with_missing_file(tmp_path / "dangling.aasx")
        package = Package(source)
        shown = views()
        shown.table.addItem(package)
        package.commandStack.mark_unsaved()

        saved = shown.view.savePack(package)

        assert not saved
        assert package.changed

    def test_package_restored_after_a_crash_is_changed_until_saved(
        self, views, tmp_path: Path
    ) -> None:
        shown = views()
        package = shown.open_package(make_submodel())

        package.changed = True
        changed = package.changed
        shown.view.savePack(package, (tmp_path / "p.json").as_posix())

        assert changed
        assert not package.changed


class TestReadModeInTheViews:
    def test_editing_actions_are_disabled_and_come_back(self, views) -> None:
        from aas_editor.application.editing import edit_mode

        shown = views()
        shown.open_package(make_submodel(elements=[_collection()]))
        shown.select(shown.index("submodels", "Submodel", "Collection", "y"))
        shown.view.onDelClear()
        shown.select(shown.index("submodels", "Submodel", "Collection"))
        view = shown.view
        enabled_in_edit_mode = (
            view.delClearAct.isEnabled(),
            view.cutAct.isEnabled(),
            view.undoAct.isEnabled(),
            view.addAct.isEnabled(),
        )

        edit_mode().set_editing(False)
        enabled_while_reading = [
            act.isEnabled()
            for act in (
                view.delClearAct,
                view.cutAct,
                view.pasteAct,
                view.undoAct,
                view.redoAct,
                view.addAct,
                view.editCreateInDialogAct,
                view.addAsJsonAct,
                view.editJsonAct,
                view.linkSubmodelsAct,
            )
        ]
        copy_enabled = view.copyAct.isEnabled()
        edit_mode().set_editing(True)

        assert enabled_in_edit_mode == (True, True, True, True)
        assert enabled_while_reading == [False] * 10
        assert copy_enabled
        assert view.delClearAct.isEnabled()
        assert view.undoAct.isEnabled()

    def test_inline_editing_is_blocked_while_reading(self, views) -> None:
        from aas_editor.application.editing import edit_mode

        shown = views()
        shown.open_package(make_submodel(elements=[_collection()]))
        cell = shown.index("submodels", "Submodel", "Collection", "y")
        shown.view.setCurrentIndex(cell)
        edit_mode().set_editing(False)

        started = shown.view.edit(
            cell, shown.view.EditTrigger.AllEditTriggers, None
        )

        assert started is False
        assert not shown.view.model().flags(cell) & Qt.ItemFlag.ItemIsEditable

    def test_delete_shortcut_changes_nothing_while_reading(self, views) -> None:
        from aas_editor.application.editing import edit_mode

        collection = _collection()
        shown = views()
        shown.open_package(make_submodel(elements=[collection]))
        shown.select(shown.index("submodels", "Submodel", "Collection", "y"))
        edit_mode().set_editing(False)

        shown.view.onDelClear()

        assert _ids(collection) == ["x", "y", "z"]
        assert len(shown.shown_errors) == 1
        assert "Read mode" in shown.shown_errors[0]

    def test_undo_shows_a_clear_error_while_reading(self, views) -> None:
        from aas_editor.application.editing import edit_mode

        collection = _collection()
        shown = views()
        shown.open_package(make_submodel(elements=[collection]))
        shown.select(shown.index("submodels", "Submodel", "Collection", "y"))
        shown.view.onDelClear()
        edit_mode().set_editing(False)

        shown.view.onUndo()

        assert _ids(collection) == ["x", "z"]
        assert "Read mode" in shown.shown_errors[0]

    def test_link_action_is_refused_with_an_error_while_reading(
        self, views
    ) -> None:
        from aas_editor.application.editing import edit_mode

        shown = views()
        package = shown.open_package(
            make_shell(), make_submodel(elements=[_collection()])
        )
        shown.select(shown.index("shells"))
        edit_mode().set_editing(False)

        added = shown.view.linkAllSubmodelsToFirstAas()

        assert added == 0
        assert not package.changed
        assert "Read mode" in shown.shown_errors[0]


class TestOtherTabsKeepTheirState:
    def test_a_tab_does_not_move_its_current_row_when_another_tab_adds_a_row(
        self, views
    ) -> None:
        shown = views()
        shown.open_package(make_submodel(elements=[_collection()]))
        acting = shown.attrs_view("submodels", "Submodel")
        following = shown.attrs_view("submodels", "Submodel")
        current_row = _row_named(following, "id_short")
        following.setCurrentIndex(current_row)
        extensions = _row_named(acting, "extension")

        acting._setItemData(
            extensions, model.Extension(name="Note"), _add_role()
        )

        assert (
            following.currentIndex()
            .siblingAtColumn(0)
            .data(Qt.ItemDataRole.DisplayRole)
            == "idShort"
        )

    def test_the_acting_tab_selects_the_new_row(self, views) -> None:
        shown = views()
        shown.open_package(make_submodel(elements=[_collection()]))
        acting = shown.attrs_view("submodels", "Submodel")
        extensions = _row_named(acting, "extension")

        acting._setItemData(
            extensions, model.Extension(name="Note"), _add_role()
        )

        # The row of an extension is named by the name of the extension.
        assert (
            acting.currentIndex()
            .siblingAtColumn(0)
            .data(Qt.ItemDataRole.DisplayRole)
            == "Note"
        )

    def test_a_tab_keeps_expanded_rows_when_another_tab_adds_a_row(
        self, views
    ) -> None:
        shown = views()
        submodel = make_submodel(elements=[_collection()])
        submodel.extension.add(model.Extension(name="First"))
        shown.open_package(submodel)
        acting = shown.attrs_view("submodels", "Submodel")
        following = shown.attrs_view("submodels", "Submodel")
        following.expand(_row_named(following, "extension"))

        acting._setItemData(
            _row_named(acting, "extension"),
            model.Extension(name="Second"),
            _add_role(),
        )

        assert following.isExpanded(_row_named(following, "extension"))

    def test_a_tab_keeps_its_current_row_when_another_tab_edits_the_object(
        self, views
    ) -> None:
        shown = views()
        shown.open_package(make_submodel(elements=[_collection()]))
        acting = shown.attrs_view("submodels", "Submodel", "Collection", "y")
        following = shown.attrs_view("submodels", "Submodel", "Collection", "y")
        following.setCurrentIndex(_row_named(following, "value"))

        acting._setItemData(
            _row_named(acting, "value").siblingAtColumn(1), "Changed", EDIT
        )

        assert (
            following.currentIndex()
            .siblingAtColumn(0)
            .data(Qt.ItemDataRole.DisplayRole)
            == "value"
        )


def _add_role() -> int:
    from aas_editor.settings.app_settings import ADD_ITEM_ROLE

    return ADD_ITEM_ROLE


def _row_named(view, name: str) -> QModelIndex:
    from aas_editor.settings.app_settings import NAME_ROLE

    # The rows are found by the attribute of the SDK. The first column shows
    # the name that the metamodel gives, such as idShort for id_short.
    model_ = view.model()
    for row in range(model_.rowCount()):
        index = model_.index(row, 0)
        if index.data(NAME_ROLE) == name:
            return index
    raise LookupError(name)
