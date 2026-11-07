"""The relative links in the documentation lead to a file and a heading."""

from pathlib import Path

import pytest
from tests.docs_links import broken_links

ROOT = Path(__file__).parents[2]
DOCUMENTS = sorted(
    [
        *(ROOT / "docs").rglob("*.md"),
        ROOT / "README.md",
        ROOT / "CHANGELOG.md",
    ]
)


@pytest.mark.parametrize(
    "document",
    DOCUMENTS,
    ids=[str(path.relative_to(ROOT)) for path in DOCUMENTS],
)
def test_every_relative_link_leads_somewhere(document: Path) -> None:
    assert broken_links(document) == []
