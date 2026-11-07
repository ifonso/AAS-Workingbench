"""Loading preset files from disk: the shipped ones, the user's, and bad ones."""

import json
from pathlib import Path

import pytest

from aas_workingbench.domain.member_json import MemberKind
from aas_workingbench.domain.presets import FILE_NAMES
from aas_workingbench.infrastructure.preset_files import SHIPPED_PRESETS_DIR
from aas_workingbench.infrastructure.preset_files import ensure_user_dir
from aas_workingbench.infrastructure.preset_files import load_presets


def _qualifier(name: str, value: str = "One") -> dict[str, object]:
    return {
        "name": name,
        "qualifier": {"type": "T", "valueType": "xs:string", "value": value},
    }


def _write(directory: Path, kind: MemberKind, content: object) -> Path:
    directory.mkdir(exist_ok=True)
    path = directory / FILE_NAMES[kind]
    path.write_text(json.dumps(content), encoding="utf-8")
    return path


@pytest.mark.parametrize("kind", list(MemberKind))
def test_every_shipped_file_is_valid_and_makes_members(
    kind: MemberKind,
) -> None:
    loaded = load_presets(kind, SHIPPED_PRESETS_DIR, None)

    assert loaded.problems == ()
    assert len(loaded.presets) >= 1
    for preset in loaded.presets:
        member = preset.make("a value" if preset.value_required else None)
        assert getattr(member, "parent", None) is None


def test_the_shipped_qualifiers_offer_the_template_cardinalities() -> None:
    loaded = load_presets(MemberKind.QUALIFIER, SHIPPED_PRESETS_DIR, None)

    names = {preset.name for preset in loaded.presets}
    assert {
        "Submodel templates | Cardinality = One",
        "Submodel templates | Cardinality = ZeroToMany",
    } <= names


def test_user_presets_replace_and_extend_the_shipped_ones(
    tmp_path: Path,
) -> None:
    shipped = tmp_path / "shipped"
    user = tmp_path / "user"
    _write(shipped, MemberKind.QUALIFIER, [_qualifier("A"), _qualifier("B")])
    _write(
        user, MemberKind.QUALIFIER, [_qualifier("B", "mine"), _qualifier("C")]
    )

    loaded = load_presets(MemberKind.QUALIFIER, shipped, user)

    assert [(p.name, p.source) for p in loaded.presets] == [
        ("A", "shipped"),
        ("B", "user"),
        ("C", "user"),
    ]
    assert loaded.presets[1].make().value == "mine"  # type: ignore[union-attr]


def test_a_missing_user_folder_or_file_is_normal(tmp_path: Path) -> None:
    shipped = tmp_path / "shipped"
    _write(shipped, MemberKind.QUALIFIER, [_qualifier("A")])

    without_folder = load_presets(
        MemberKind.QUALIFIER, shipped, tmp_path / "nowhere"
    )
    without_none = load_presets(MemberKind.QUALIFIER, shipped, None)

    assert [p.name for p in without_folder.presets] == ["A"]
    assert without_folder.problems == ()
    assert without_none.problems == ()


def test_a_missing_shipped_file_is_reported(tmp_path: Path) -> None:
    loaded = load_presets(MemberKind.EXTENSION, tmp_path, None)

    assert loaded.presets == ()
    assert "missing" in str(loaded.problems[0])


def test_a_broken_user_file_is_reported_and_the_shipped_presets_stay(
    tmp_path: Path,
) -> None:
    shipped = tmp_path / "shipped"
    user = tmp_path / "user"
    _write(shipped, MemberKind.QUALIFIER, [_qualifier("A")])
    user.mkdir()
    (user / FILE_NAMES[MemberKind.QUALIFIER]).write_text(
        "{oops", encoding="utf-8"
    )

    loaded = load_presets(MemberKind.QUALIFIER, shipped, user)

    assert [p.name for p in loaded.presets] == ["A"]
    (problem,) = loaded.problems
    assert problem.source == "user"
    assert "not valid JSON" in str(problem)
    assert FILE_NAMES[MemberKind.QUALIFIER] in str(problem)


@pytest.mark.parametrize(
    "content",
    [b"\xff\xfe\x00garbage\x80", b"\x00" * 100, b"[\xc3\x28]"],
)
def test_a_file_that_is_no_text_is_reported(
    tmp_path: Path, content: bytes
) -> None:
    user = tmp_path / "user"
    user.mkdir()
    (user / FILE_NAMES[MemberKind.QUALIFIER]).write_bytes(content)

    loaded = load_presets(MemberKind.QUALIFIER, tmp_path, user)

    assert loaded.presets == ()
    assert any(p.source == "user" for p in loaded.problems)


def test_a_folder_in_place_of_a_file_is_reported(tmp_path: Path) -> None:
    user = tmp_path / "user"
    (user / FILE_NAMES[MemberKind.QUALIFIER]).mkdir(parents=True)

    loaded = load_presets(MemberKind.QUALIFIER, tmp_path, user)

    assert any("not a file" in str(p) for p in loaded.problems)


def test_a_file_with_a_byte_order_mark_is_read(tmp_path: Path) -> None:
    user = tmp_path / "user"
    user.mkdir()
    (user / FILE_NAMES[MemberKind.QUALIFIER]).write_bytes(
        b"\xef\xbb\xbf" + json.dumps([_qualifier("A")]).encode()
    )

    loaded = load_presets(MemberKind.QUALIFIER, tmp_path, user)

    assert [p.name for p in loaded.presets] == ["A"]


def test_an_oversized_file_is_refused_without_reading_it(
    tmp_path: Path,
) -> None:
    user = tmp_path / "user"
    user.mkdir()
    path = user / FILE_NAMES[MemberKind.QUALIFIER]
    with path.open("wb") as handle:
        handle.seek(8_000_001)
        handle.write(b"x")

    loaded = load_presets(MemberKind.QUALIFIER, tmp_path, user)

    assert any("too large" in str(p) for p in loaded.problems)


def test_the_user_folder_is_created_on_request(tmp_path: Path) -> None:
    target = tmp_path / "a" / "presets"

    assert ensure_user_dir(target)
    assert target.is_dir()
    assert ensure_user_dir(target)


def test_a_user_folder_that_cannot_be_made_is_reported_as_false(
    tmp_path: Path,
) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="utf-8")

    assert not ensure_user_dir(blocker / "presets")
