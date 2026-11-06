"""Files come along when objects are copied to another package."""

import gc
import io

from basyx.aas import model
from basyx.aas.adapter.aasx import DictSupplementaryFileContainer
from tests.factories import make_asset_information
from tests.factories import make_file_element
from tests.factories import make_shell
from tests.factories import make_submodel

from aas_editor.application import supplementary_files as files
from aas_editor.application.changes import ModelChangeObserver
from aas_editor.application.commands import CommandStack
from aas_editor.application.edits import AddMember
from aas_editor.application.file_transfer import CopySource
from aas_editor.application.file_transfer import plan_transfer
from aas_editor.application.file_transfer import transfer_reports
from aas_editor.application.file_transfer import with_copied_files
from aas_editor.domain.file_references import references_in

DOC = "/aasx/files/doc.pdf"


def _stores(
    source: dict[str, tuple[bytes, str]], target: dict[str, tuple[bytes, str]]
) -> tuple[DictSupplementaryFileContainer, DictSupplementaryFileContainer]:
    result = []
    for contents in (source, target):
        store = DictSupplementaryFileContainer()
        for name, (data, content_type) in contents.items():
            store.add_file(name, io.BytesIO(data), content_type)
        result.append(store)
    return result[0], result[1]


class _Paste:
    """Pastes a submodel with one File into a target package."""

    def __init__(
        self,
        source: dict[str, tuple[bytes, str]],
        target: dict[str, tuple[bytes, str]],
        path: str = DOC,
    ) -> None:
        self.source, self.target = _stores(source, target)
        self.element = make_file_element("Doc", path, "application/pdf")
        self.submodel = make_submodel(elements=[self.element])
        self.objects = model.SetIdentifiableStore[model.Identifiable]()
        self.observer = ModelChangeObserver()
        self.stack = CommandStack()

    def paste(
        self, source: DictSupplementaryFileContainer | None = None
    ) -> None:
        command = with_copied_files(
            AddMember(self.observer, self.objects, self.submodel),
            self.submodel,
            self.source if source is None else source,
            self.target,
            self.observer,
        )
        self.stack.push(command)

    def stored(self, name: str) -> bytes:
        return files.read_file(self.target, name)


def test_the_file_is_copied_with_the_submodel_and_undone_with_it() -> None:
    paste = _Paste({DOC: (b"%PDF", "application/pdf")}, {})

    paste.paste()

    assert paste.stored(DOC) == b"%PDF"
    assert paste.target.get_content_type(DOC) == "application/pdf"
    assert paste.element.value == DOC
    assert paste.submodel in paste.objects
    paste.stack.undo()
    assert list(paste.target) == []
    assert paste.submodel not in paste.objects
    paste.stack.redo()
    assert paste.stored(DOC) == b"%PDF"
    assert paste.element.value == DOC


def test_an_identical_file_in_the_target_is_reused_and_survives_undo() -> None:
    paste = _Paste(
        {DOC: (b"%PDF", "application/pdf")},
        {DOC: (b"%PDF", "application/pdf")},
    )

    paste.paste()
    paste.stack.undo()

    assert list(paste.target) == [DOC]
    assert paste.stored(DOC) == b"%PDF"


def test_a_different_file_of_the_same_name_is_never_overwritten() -> None:
    paste = _Paste(
        {DOC: (b"copied", "application/pdf")},
        {DOC: (b"original", "application/pdf")},
    )

    paste.paste()

    assert paste.stored(DOC) == b"original"
    assert paste.element.value == "/aasx/files/doc_0001.pdf"
    assert paste.stored("/aasx/files/doc_0001.pdf") == b"copied"
    paste.stack.undo()
    assert paste.element.value == DOC
    assert list(paste.target) == [DOC]
    assert paste.stored(DOC) == b"original"


def test_a_name_that_differs_only_in_case_counts_as_taken() -> None:
    paste = _Paste(
        {DOC: (b"copied", "application/pdf")},
        {"/AASX/files/DOC.pdf": (b"original", "application/pdf")},
    )

    paste.paste()

    assert paste.element.value == "/aasx/files/doc_0001.pdf"
    assert paste.stored("/AASX/files/DOC.pdf") == b"original"


def test_the_same_content_with_another_media_type_is_a_different_file() -> None:
    paste = _Paste(
        {DOC: (b"same", "application/pdf")}, {DOC: (b"same", "text/plain")}
    )

    paste.paste()

    assert paste.element.value != DOC
    assert paste.target.get_content_type(DOC) == "text/plain"


def test_a_file_missing_in_the_source_leaves_the_path_and_adds_nothing() -> (
    None
):
    paste = _Paste({}, {})

    paste.paste()

    assert paste.element.value == DOC
    assert list(paste.target) == []
    assert paste.submodel in paste.objects


def test_nothing_is_done_when_the_source_is_unknown_or_the_same_package() -> (
    None
):
    paste = _Paste({DOC: (b"x", "application/pdf")}, {})
    command = AddMember(paste.observer, paste.objects, paste.submodel)

    unchanged = with_copied_files(
        command, paste.submodel, None, paste.target, paste.observer
    )
    same = with_copied_files(
        command, paste.submodel, paste.target, paste.target, paste.observer
    )

    assert unchanged is command
    assert same is command


def test_a_url_and_an_object_without_files_need_no_transfer() -> None:
    paste = _Paste({DOC: (b"x", "application/pdf")}, {}, "https://e.com/a.pdf")
    command = AddMember(paste.observer, paste.objects, paste.submodel)

    result = with_copied_files(
        command, paste.submodel, paste.source, paste.target, paste.observer
    )

    assert result is command


def test_two_references_to_one_file_copy_it_once() -> None:
    source, target = _stores({DOC: (b"x", "application/pdf")}, {})
    first = make_file_element("A", DOC)
    second = make_file_element("B", DOC)

    plan = plan_transfer(
        references_in(make_submodel(elements=[first, second])), source, target
    )

    assert [copy.target for copy in plan.copies] == [DOC]


def test_hostile_stored_names_are_not_copied() -> None:
    source = DictSupplementaryFileContainer()
    source.add_file("/../evil.txt", io.BytesIO(b"x"), "text/plain")
    target = DictSupplementaryFileContainer()
    element = make_file_element("A", "/../evil.txt")

    plan = plan_transfer(references_in(element), source, target)

    assert plan.copies == ()
    assert plan.invalid == ("/../evil.txt",)


def test_the_plan_is_announced_for_the_status_bar() -> None:
    reports: list[str] = []
    subscription = transfer_reports.subscribe(
        lambda plan: reports.append(plan.summary())
    )
    paste = _Paste(
        {DOC: (b"a", "application/pdf")}, {DOC: (b"b", "application/pdf")}
    )

    paste.paste()
    subscription.cancel()

    assert len(reports) == 1
    assert "1 file(s) copied" in reports[0]
    assert "doc_0001.pdf" in reports[0]


def test_a_copy_source_is_forgotten_when_its_package_is_gone() -> None:
    source = CopySource()
    store = DictSupplementaryFileContainer()

    source.remember(store)
    known = source.store
    del store, known
    gc.collect()
    assert source.store is None


def test_a_copy_source_can_be_cleared() -> None:
    source = CopySource()
    store = DictSupplementaryFileContainer()
    source.remember(store)

    source.forget()

    assert source.store is None


def test_the_thumbnail_of_a_copied_shell_follows() -> None:
    source, target = _stores(
        {"/aasx/t.png": (b"png", "image/png")},
        {"/aasx/t.png": (b"other", "image/png")},
    )
    shell = make_shell(
        asset_information=make_asset_information(
            default_thumbnail=model.Resource("/aasx/t.png")
        )
    )
    observer = ModelChangeObserver()
    objects = model.SetIdentifiableStore[model.Identifiable]()
    stack = CommandStack()

    stack.push(
        with_copied_files(
            AddMember(observer, objects, shell), shell, source, target, observer
        )
    )

    assert shell.asset_information.default_thumbnail is not None
    assert shell.asset_information.default_thumbnail.path == "/aasx/t_0001.png"
    assert files.read_file(target, "/aasx/t_0001.png") == b"png"
