import json
import logging
from pathlib import Path

import pytest

from aas_workingbench import package as package_mod
from aas_workingbench.package import Package
from aas_workingbench.utils.recovery import (
    find_recovery_files,
    delete_recovery_file,
    cleanup_recovery_dir,
    take_over_recovery_files,
)


def _write_entry(
    recovery_dir: Path, name: str, original_path, data: str = "{}"
):
    """Write a recovery data file and its sidecar meta, as write_recovery would."""
    recovery_dir.mkdir(parents=True, exist_ok=True)
    rec = recovery_dir / f"{name}.json"
    rec.write_text(data)
    meta = recovery_dir / f"{name}.meta.json"
    meta.write_text(
        json.dumps(
            {
                "original_path": Path(original_path).as_posix(),
                "recovery_filename": rec.name,
            }
        )
    )
    return rec, meta


# ---------------------------------------------------------------------------
# Package.write_recovery / delete_recovery
# ---------------------------------------------------------------------------


class TestWriteRecovery:
    def test_writes_json_data_and_meta(
        self, qapp: object, json_file: Path, tmp_path: Path
    ) -> None:
        pkg = Package(json_file)
        rec = pkg.write_recovery(tmp_path)
        meta = tmp_path / f"{rec.stem}.meta.json"
        assert rec.suffix == ".json"
        assert rec.exists()
        assert (
            json.loads(meta.read_text())["original_path"]
            == json_file.absolute().as_posix()
        )

    def test_aasx_recovery_is_json_only(
        self, qapp: object, aasx_file: Path, tmp_path: Path
    ) -> None:
        pkg = Package(aasx_file)
        rec = pkg.write_recovery(tmp_path)
        assert rec.suffix == ".json"
        assert not list(tmp_path.glob("*.aasx"))

    def test_recovery_roundtrips(
        self, qapp: object, aasx_file: Path, tmp_path: Path
    ) -> None:
        src = Package(aasx_file)
        rec = src.write_recovery(tmp_path)
        reloaded = Package(rec)
        assert reloaded.numOfShells == src.numOfShells
        assert reloaded.numOfSubmodels == src.numOfSubmodels

    def test_original_path_unchanged_after_write(
        self, qapp: object, json_file: Path, tmp_path: Path
    ) -> None:
        pkg = Package(json_file)
        pkg.write_recovery(tmp_path)
        assert pkg.file == json_file.absolute()

    def test_failed_write_leaves_no_tmp_or_meta(
        self, qapp: object, json_file: Path, tmp_path: Path, monkeypatch
    ) -> None:
        pkg = Package(json_file)

        def boom(fileIO, store, **kwargs):
            fileIO.write("partial")  # a real, half-written temp file
            raise RuntimeError("write failed")

        monkeypatch.setattr(package_mod, "write_aas_json_file", boom)
        with pytest.raises(RuntimeError):
            pkg.write_recovery(tmp_path)
        assert not list(tmp_path.glob("*.tmp*"))
        assert not list(tmp_path.glob("*.meta.json"))

    def test_delete_recovery_removes_all(
        self, qapp: object, json_file: Path, tmp_path: Path
    ) -> None:
        pkg = Package(json_file)
        rec = pkg.write_recovery(tmp_path)
        pkg.delete_recovery(tmp_path)
        assert not rec.exists()
        assert not (tmp_path / f"{rec.stem}.meta.json").exists()

    def test_delete_recovery_for_previous_file(
        self, qapp: object, json_file: Path, tmp_path: Path
    ) -> None:
        pkg = Package(json_file)
        rec = pkg.write_recovery(tmp_path)
        pkg.file = tmp_path / "saved_as.json"  # Save-As moved the current path
        pkg.delete_recovery(tmp_path, for_file=json_file)
        assert not rec.exists()


# ---------------------------------------------------------------------------
# Package.restore_from_recovery
# ---------------------------------------------------------------------------


class TestRestoreFromRecovery:
    def test_restores_objects_and_targets_original(
        self, qapp: object, json_file: Path, tmp_path: Path
    ) -> None:
        src = Package(json_file)
        rec = src.write_recovery(tmp_path)
        restored = Package.restore_from_recovery(rec, json_file)
        assert restored.file == json_file.absolute()
        assert restored.numOfShells == src.numOfShells
        assert restored.numOfSubmodels == src.numOfSubmodels

    def test_reloads_supplementary_files_from_aasx(
        self, qapp: object, tmp_path: Path
    ) -> None:
        original = (
            Path(__file__).parents[1]
            / "data"
            / "IDTA 02023 _Template_CarbonFootprint.aasx"
        )
        src = Package(original)
        assert (
            len(list(src.fileStore)) > 0
        )  # guard: fixture must carry supplementary files
        rec = src.write_recovery(tmp_path)
        restored = Package.restore_from_recovery(rec, original)
        assert len(list(restored.fileStore)) == len(list(src.fileStore))

    def test_missing_original_warns_and_keeps_objects(
        self, qapp: object, json_file: Path, tmp_path: Path, caplog
    ) -> None:
        src = Package(json_file)
        rec = src.write_recovery(tmp_path)
        missing = tmp_path / "gone.aasx"
        with caplog.at_level(logging.WARNING):
            restored = Package.restore_from_recovery(rec, missing)
        assert restored.numOfShells == src.numOfShells
        assert len(list(restored.fileStore)) == 0
        assert "supplementary files not recovered" in caplog.text


# ---------------------------------------------------------------------------
# find_recovery_files
# ---------------------------------------------------------------------------


class TestFindRecoveryFiles:
    def test_missing_dir_returns_empty(self, tmp_path: Path) -> None:
        assert find_recovery_files(tmp_path / "nope") == {}

    def test_returns_entry(self, tmp_path: Path) -> None:
        original = tmp_path / "model.json"
        _write_entry(tmp_path / "rec", "abc", original)
        result = find_recovery_files(tmp_path / "rec")
        assert result == {original.resolve(): tmp_path / "rec" / "abc.json"}

    def test_skips_entry_with_missing_data(self, tmp_path: Path) -> None:
        rec_dir = tmp_path / "rec"
        rec, _ = _write_entry(rec_dir, "abc", tmp_path / "model.json")
        rec.unlink()  # data gone, meta stays
        assert find_recovery_files(rec_dir) == {}

    def test_skips_corrupt_meta_and_logs(self, tmp_path: Path, caplog) -> None:
        rec_dir = tmp_path / "rec"
        rec_dir.mkdir()
        (rec_dir / "abc.json").write_text("{}")
        (rec_dir / "abc.meta.json").write_text("{ not json")
        with caplog.at_level(logging.WARNING):
            assert find_recovery_files(rec_dir) == {}
        assert "recovery meta" in caplog.text

    def test_key_is_resolved(self, tmp_path: Path) -> None:
        sub = tmp_path / "sub"
        sub.mkdir()
        original = sub / "model.json"
        unresolved = sub / ".." / "sub" / "model.json"
        _write_entry(tmp_path / "rec", "abc", unresolved)
        assert original.resolve() in find_recovery_files(tmp_path / "rec")


# ---------------------------------------------------------------------------
# delete_recovery_file / cleanup_recovery_dir
# ---------------------------------------------------------------------------


class TestCleanup:
    def test_delete_recovery_file_removes_pair(self, tmp_path: Path) -> None:
        rec, meta = _write_entry(tmp_path, "abc", tmp_path / "model.json")
        delete_recovery_file(rec)
        assert not rec.exists()
        assert not meta.exists()

    def test_cleanup_keeps_only_requested(self, tmp_path: Path) -> None:
        keep_rec, keep_meta = _write_entry(
            tmp_path, "keep", tmp_path / "a.json"
        )
        drop_rec, drop_meta = _write_entry(
            tmp_path, "drop", tmp_path / "b.json"
        )
        (tmp_path / "leftover.tmp.json").write_text("stale")

        cleanup_recovery_dir(tmp_path, keep=[keep_rec])

        assert keep_rec.exists() and keep_meta.exists()
        assert not drop_rec.exists() and not drop_meta.exists()
        assert not (tmp_path / "leftover.tmp.json").exists()

    def test_cleanup_missing_dir_is_noop(self, tmp_path: Path) -> None:
        cleanup_recovery_dir(tmp_path / "nope")  # must not raise


# ---------------------------------------------------------------------------
# Where the recovery files are, and the take-over from the old folder
# ---------------------------------------------------------------------------


class TestRecoveryFolder:
    def test_it_is_in_the_data_folder_of_the_user_and_not_in_the_source_tree(
        self, qapp: object
    ) -> None:
        from PyQt6.QtCore import QStandardPaths

        from aas_workingbench.settings import app_settings

        # The package keeps the function that the fixture replaces in
        # `app_settings`, because it was bound when the package was imported.
        from aas_workingbench.settings import recovery_dir

        folder = recovery_dir()

        data = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.AppDataLocation
        )
        assert folder == Path(data) / "recovery"
        assert not folder.is_relative_to(app_settings.SETTINGS_FILE.parent)

    def test_a_test_does_not_use_the_folder_of_the_user(
        self, qapp: object
    ) -> None:
        from aas_workingbench.settings import app_settings
        from aas_workingbench.settings import recovery_dir

        assert app_settings.recovery_dir() != recovery_dir()
        assert app_settings.OLD_RECOVERY_DIR.name == "old-recovery"


def _entry_files(folder: Path) -> list[str]:
    return sorted(path.name for path in folder.iterdir())


class TestTakeOver:
    def test_an_entry_of_the_old_folder_moves_to_the_new_one(
        self, tmp_path: Path
    ) -> None:
        old, new = tmp_path / "old", tmp_path / "new"
        _write_entry(old, "abc", tmp_path / "model.json", '{"a": 1}')
        (old / "abc.files.json").write_text("{}")

        taken = take_over_recovery_files(old, new)

        assert taken == 1
        assert _entry_files(new) == [
            "abc.files.json",
            "abc.json",
            "abc.meta.json",
        ]
        assert (new / "abc.json").read_text() == '{"a": 1}'
        assert _entry_files(old) == []
        assert find_recovery_files(new) == {
            (tmp_path / "model.json").resolve(): new / "abc.json"
        }

    def test_an_entry_of_the_new_folder_is_kept_and_the_old_one_goes(
        self, tmp_path: Path
    ) -> None:
        old, new = tmp_path / "old", tmp_path / "new"
        _write_entry(old, "abc", tmp_path / "model.json", "old")
        _write_entry(new, "abc", tmp_path / "model.json", "new")

        taken = take_over_recovery_files(old, new)

        assert taken == 0
        assert (new / "abc.json").read_text() == "new"
        assert _entry_files(old) == []

    def test_a_file_without_a_meta_file_is_not_an_entry(
        self, tmp_path: Path
    ) -> None:
        old, new = tmp_path / "old", tmp_path / "new"
        old.mkdir()
        (old / "abc.json").write_text("half an entry")

        assert take_over_recovery_files(old, new) == 0
        assert (old / "abc.json").exists()
        assert not new.exists()

    def test_a_missing_old_folder_does_nothing(self, tmp_path: Path) -> None:
        assert take_over_recovery_files(tmp_path / "gone", tmp_path / "n") == 0
        assert not (tmp_path / "n").exists()

    def test_the_same_folder_is_left_alone(self, tmp_path: Path) -> None:
        _write_entry(tmp_path, "abc", tmp_path / "model.json")

        assert take_over_recovery_files(tmp_path, tmp_path) == 0
        assert (tmp_path / "abc.json").exists()

    def test_an_entry_that_cannot_be_copied_stays_in_the_old_folder(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog
    ) -> None:
        old, new = tmp_path / "old", tmp_path / "new"
        _write_entry(old, "abc", tmp_path / "model.json")

        def refuse(source: object, target: object) -> None:
            raise PermissionError("read-only")

        monkeypatch.setattr(
            "aas_workingbench.utils.recovery.shutil.copy2", refuse
        )
        with caplog.at_level(logging.WARNING):
            taken = take_over_recovery_files(old, new)

        assert taken == 0
        assert _entry_files(old) == ["abc.json", "abc.meta.json"]
        assert not (new / "abc.meta.json").exists()
        assert "could not be taken over" in caplog.text

    def test_a_taken_over_aasx_entry_restores_with_its_files(
        self, qapp: object, tmp_path: Path
    ) -> None:
        from aas_workingbench.application import supplementary_files as files
        from aas_workingbench.application.changes import observer_for

        original = (
            Path(__file__).parents[1]
            / "data"
            / "IDTA 02023 _Template_CarbonFootprint.aasx"
        )
        package = Package(original)
        files.create_text_file(
            package.commandStack,
            observer_for(package),
            package.fileStore,
            "/aasx/files/draft.txt",
            "unsaved draft",
        )
        old, new = tmp_path / "old", tmp_path / "new"
        package.write_recovery(old)

        assert take_over_recovery_files(old, new) == 1
        (recovery,) = find_recovery_files(new).values()
        restored = Package.restore_from_recovery(recovery, original)

        assert "/aasx/files/draft.txt" in restored.fileStore
        assert len(list(restored.fileStore)) == len(list(package.fileStore))


# ---------------------------------------------------------------------------
# Recovery follows the dirty state of the undo history
# ---------------------------------------------------------------------------


class TestUpdateRecovery:
    @pytest.fixture
    def edited(self, qapp: object, json_file: Path, tmp_path: Path):
        from aas_workingbench.application.changes import observer_for
        from aas_workingbench.application.edits import SetAttribute

        package = Package(json_file)
        submodel = next(iter(package.submodels))
        package.commandStack.push(
            SetAttribute(observer_for(package), submodel, "category", "Edited")
        )
        return package, tmp_path / "recovery"

    def test_a_package_with_unsaved_changes_gets_a_recovery_file(
        self, edited
    ) -> None:
        package, recovery_dir = edited

        package.update_recovery(recovery_dir)

        assert package.recovery_path(recovery_dir).exists()

    def test_recovery_file_is_removed_when_undo_reaches_the_saved_state(
        self, edited
    ) -> None:
        package, recovery_dir = edited
        package.update_recovery(recovery_dir)

        package.commandStack.undo()
        package.update_recovery(recovery_dir)

        assert not package.recovery_path(recovery_dir).exists()
        assert not list(recovery_dir.glob("*.meta.json"))

    def test_recovery_file_is_written_again_when_the_step_is_redone(
        self, edited
    ) -> None:
        package, recovery_dir = edited
        package.update_recovery(recovery_dir)
        package.commandStack.undo()
        package.update_recovery(recovery_dir)

        package.commandStack.redo()
        package.update_recovery(recovery_dir)

        assert package.recovery_path(recovery_dir).exists()

    def test_a_clean_package_writes_no_recovery_file(
        self, qapp: object, json_file: Path, tmp_path: Path
    ) -> None:
        package = Package(json_file)

        package.update_recovery(tmp_path)

        assert not list(tmp_path.glob("*"))
