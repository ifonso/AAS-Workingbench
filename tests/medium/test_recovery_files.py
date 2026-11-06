"""Crash recovery keeps what happened to the supplementary files.

A file that nothing refers to yet is not written by the SDK into an AASX, so
it needs its own place in the recovery. Removed and renamed files must also
come back as they were, not as the original file has them.
"""

from pathlib import Path

from tests.factories import make_file_element
from tests.factories import make_shell
from tests.factories import make_store
from tests.factories import make_submodel
from tests.factories import write_aasx

from aas_editor.application import supplementary_files as files
from aas_editor.application.changes import observer_for

DOCUMENT = "/aasx/files/document.pdf"
DRAFT = "/aasx/files/draft.txt"


def _open_package(tmp_path: Path):
    from aas_editor.package import Package

    submodel = make_submodel(
        elements=[make_file_element("Document", DOCUMENT, "application/pdf")]
    )
    source = write_aasx(
        tmp_path / "source.aasx",
        make_store(make_shell(submodels=[submodel]), submodel),
        files={DOCUMENT: (b"%PDF original", "application/pdf")},
    )
    return Package(source), source


def _restore(package, source: Path, tmp_path: Path):
    from aas_editor.package import Package

    recovery = package.write_recovery(tmp_path / "recovery")
    return Package.restore_from_recovery(recovery, source)


def _bytes(package, name: str) -> bytes:
    return files.read_file(package.fileStore, name)


def test_a_new_file_that_nothing_refers_to_survives_a_crash(
    qapp: object, tmp_path: Path
) -> None:
    package, source = _open_package(tmp_path)
    files.add_file(
        package.commandStack,
        observer_for(package),
        package.fileStore,
        DRAFT,
        "unsaved draft".encode(),
        "text/plain",
    )

    restored = _restore(package, source, tmp_path)

    assert sorted(restored.fileStore) == [DOCUMENT, DRAFT]
    assert _bytes(restored, DRAFT) == b"unsaved draft"
    assert restored.fileStore.get_content_type(DRAFT) == "text/plain"
    assert _bytes(restored, DOCUMENT) == b"%PDF original"


def test_the_restored_file_is_stored_again_by_a_save(
    qapp: object, tmp_path: Path
) -> None:
    package, source = _open_package(tmp_path)
    submodel = next(iter(package.submodels))
    files.add_and_link(
        package.commandStack,
        observer_for(package),
        package.fileStore,
        submodel.submodel_element.get_object_by_attribute(
            "id_short", "Document"
        ),
        DRAFT,
        b"linked later",
        "text/plain",
    )
    files.create_text_file(
        package.commandStack,
        observer_for(package),
        package.fileStore,
        "/aasx/files/unused.txt",
        "not referenced",
    )

    restored = _restore(package, source, tmp_path)

    assert "/aasx/files/unused.txt" in restored.fileStore
    assert _bytes(restored, "/aasx/files/unused.txt") == b"not referenced"
    assert _bytes(restored, DRAFT) == b"linked later"


def test_a_file_renamed_in_the_session_is_restored_under_the_new_name(
    qapp: object, tmp_path: Path
) -> None:
    package, source = _open_package(tmp_path)
    files.rename_file(
        package.commandStack,
        observer_for(package),
        package.objStore,
        package.fileStore,
        DOCUMENT,
        "/aasx/central/document.pdf",
    )

    restored = _restore(package, source, tmp_path)

    assert sorted(restored.fileStore) == ["/aasx/central/document.pdf"]
    assert files.find_dangling(restored.objStore, restored.fileStore) == []


def test_a_file_removed_in_the_session_stays_removed_after_a_crash(
    qapp: object, tmp_path: Path
) -> None:
    package, source = _open_package(tmp_path)
    files.remove_file(
        package.commandStack,
        observer_for(package),
        package.objStore,
        package.fileStore,
        DOCUMENT,
        files.ReferenceChoice.CLEAR,
    )

    restored = _restore(package, source, tmp_path)

    assert sorted(restored.fileStore) == []


def test_an_unchanged_package_keeps_the_cheap_json_recovery(
    qapp: object, tmp_path: Path
) -> None:
    package, _ = _open_package(tmp_path)

    recovery = package.write_recovery(tmp_path / "recovery")

    assert recovery.suffix == ".json"
    assert not list((tmp_path / "recovery").glob("*.files.json"))


def test_the_recovery_files_are_deleted_together(
    qapp: object, tmp_path: Path
) -> None:
    package, _ = _open_package(tmp_path)
    files.create_text_file(
        package.commandStack,
        observer_for(package),
        package.fileStore,
        DRAFT,
        "x",
    )
    recovery_dir = tmp_path / "recovery"
    package.write_recovery(recovery_dir)
    assert list(recovery_dir.glob("*.files.json"))

    package.delete_recovery(recovery_dir)

    assert list(recovery_dir.iterdir()) == []


def test_cleanup_keeps_the_extra_files_of_a_restored_recovery(
    qapp: object, tmp_path: Path
) -> None:
    from aas_editor.utils.recovery import cleanup_recovery_dir

    package, _ = _open_package(tmp_path)
    files.create_text_file(
        package.commandStack,
        observer_for(package),
        package.fileStore,
        DRAFT,
        "x",
    )
    recovery_dir = tmp_path / "recovery"
    recovery = package.write_recovery(recovery_dir)

    cleanup_recovery_dir(recovery_dir, [recovery])

    assert list(recovery_dir.glob("*.files.json"))
    assert recovery.exists()
