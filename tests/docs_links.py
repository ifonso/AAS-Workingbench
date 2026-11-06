"""Finds relative links in markdown files that lead nowhere."""

from pathlib import Path
import re

_LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
_DEFINITION = re.compile(r"^\[[^\]]+\]:\s*(\S+)", re.MULTILINE)
_FENCE = re.compile(r"```.*?```", re.DOTALL)
_HEADING = re.compile(r"^#{1,6}\s+(.*?)\s*#*\s*$")
_EXTERNAL = re.compile(r"^(https?:|mailto:)")


def _slug(heading: str) -> str:
    """Turns a heading into the anchor that GitHub gives it."""
    text = re.sub(r"[`*_]", "", heading.strip().lower())
    return re.sub(r"[^\w\- ]", "", text).replace(" ", "-")


def anchors_of(path: Path) -> set[str]:
    """Returns the anchors that the headings of a markdown file make."""
    found: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        match = _HEADING.match(line)
        if match:
            found.add(_slug(match.group(1)))
    return found


def _targets(text: str) -> list[str]:
    without_code = _FENCE.sub("", text)
    return _LINK.findall(without_code) + _DEFINITION.findall(without_code)


def broken_links(path: Path) -> list[str]:
    """Lists the links of a markdown file to a missing file or heading.

    Args:
        path: The markdown file.

    Returns:
        One text for each broken link, such as "missing: ../x.md".
    """
    broken: list[str] = []
    for target in _targets(path.read_text(encoding="utf-8")):
        if _EXTERNAL.match(target):
            continue
        name, _, anchor = target.partition("#")
        linked = (path.parent / name).resolve() if name else path
        if not linked.exists():
            broken.append(f"missing: {target}")
        elif (
            anchor
            and linked.suffix == ".md"
            and anchor not in anchors_of(linked)
        ):
            broken.append(f"no heading: {target}")
    return broken
