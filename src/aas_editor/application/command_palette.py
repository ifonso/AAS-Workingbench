"""What the command palette lists, and how it orders it for what was typed.

The palette is one field over two lists: the commands of the editor, which are
its actions, and the elements of the open packages, which it jumps to. This
module holds the part that has no Qt: the entries, the match of a query with a
text, the order of the results, and the commands that were used last.

Example:
    Ordering the entries for what the user typed::

        results = rank(entries, "save as", recent.keys())
"""

from collections.abc import Callable
from collections.abc import Iterable
from collections.abc import Sequence
from dataclasses import dataclass
import enum
import re

# How many results the palette lists at most. The rest is one more letter away.
MAX_RESULTS = 50
# How many used commands it remembers.
MAX_RECENT = 8

_WORD = re.compile(r"[a-z0-9]+")


class EntryKind(enum.Enum):
    """What an entry does when the user picks it."""

    COMMAND = "command"
    """Runs an action of the editor."""
    ELEMENT = "element"
    """Selects an object of an open package in the tree."""


@dataclass(frozen=True, eq=False)
class PaletteEntry:
    """One line of the palette.

    Attributes:
        key: A stable name, to remember a command that was used.
        title: What the line reads, such as `Save` or the idShort of an element.
        kind: Whether the entry is a command or an element.
        detail: Where it is, such as the menu of a command or the place of an
            element. It is matched too.
        shortcut: The keys of a command, as the user reads them.
        enabled: False for a command that cannot run now.
        reason: Why it cannot run, if known.
        keywords: More text that a query can match, such as the id of an
            element. It is not shown.
        payload: What the caller needs to run the entry. The palette does not
            look at it.
    """

    key: str
    title: str
    kind: EntryKind = EntryKind.COMMAND
    detail: str = ""
    shortcut: str = ""
    enabled: bool = True
    reason: str = ""
    keywords: str = ""
    payload: object = None


def match_score(query: str, entry: PaletteEntry) -> int | None:
    """Tells how well an entry fits what the user typed.

    Every word of the query must match. A word fits best at the start of the
    title, then at the start of a word of the title, then inside the title, then
    as the first letters of its words (`sa` for `Save As`), and last in the
    detail or the keywords.

    Args:
        query: What the user typed.
        entry: The entry to try.

    Returns:
        A number where less is better, or None if a word does not match. An
        empty query matches everything with 0.
    """
    total = 0
    title = entry.title.lower()
    other = f"{entry.detail} {entry.keywords}".lower()
    for word in query.lower().split():
        tier = _word_tier(word, title, other)
        if tier is None:
            return None
        total += tier
    return total


def rank(
    entries: Iterable[PaletteEntry],
    query: str,
    recent: Sequence[str] = (),
    limit: int = MAX_RESULTS,
) -> list[PaletteEntry]:
    """Orders the entries for a query, best first.

    Without a query only the commands are listed: the ones used last, then
    the others in the order they were given. The elements wait for a word, because a list of every
    element says nothing. With a query, the entries that fit are listed by how
    well they fit, with a command before an element, an enabled command before
    a disabled one, a command used lately before the others, and a shorter
    title before a longer one.

    Args:
        entries: Every entry that the palette could list.
        query: What the user typed.
        recent: The keys of the commands used last, newest first.
        limit: The most entries to return.

    Returns:
        The entries to list.
    """
    ranking = {key: place for place, key in enumerate(recent)}
    scored: list[tuple[tuple[int, int, int, int, int, str], PaletteEntry]] = []
    searching = bool(query.split())
    for place, entry in enumerate(entries):
        if not searching and entry.kind is EntryKind.ELEMENT:
            continue
        score = match_score(query, entry)
        if score is None:
            continue
        order = (
            score,
            0 if entry.kind is EntryKind.COMMAND else 1,
            0 if entry.enabled else 1,
            ranking.get(entry.key, MAX_RECENT + 1),
            len(entry.title) if searching else place,
            entry.title.lower(),
        )
        scored.append((order, entry))
    if not searching:
        # Nothing was typed, so the order is use first, then the order of the
        # menus that the commands come from.
        scored.sort(key=lambda item: item[0][2:5])
    else:
        scored.sort(key=lambda item: item[0])
    return [entry for _, entry in scored[:limit]]


class RecentCommands:
    """Remembers the commands that were used last, newest first."""

    def __init__(
        self,
        load: Callable[[], list[str]] | None = None,
        save: Callable[[list[str]], None] | None = None,
    ) -> None:
        """Starts with what was stored, if there is a store.

        Args:
            load: Reads the stored keys, newest first.
            save: Writes the keys after each use.
        """
        self._save = save
        self._keys: list[str] = list(load()) if load is not None else []
        del self._keys[MAX_RECENT:]

    def keys(self) -> tuple[str, ...]:
        """Returns the keys of the commands used last, newest first."""
        return tuple(self._keys)

    def used(self, key: str) -> None:
        """Puts a command first, because the user just ran it."""
        if key in self._keys:
            self._keys.remove(key)
        self._keys.insert(0, key)
        del self._keys[MAX_RECENT:]
        if self._save is not None:
            self._save(list(self._keys))


def _word_tier(word: str, title: str, other: str) -> int | None:
    if title.startswith(word):
        return 0
    if any(found.startswith(word) for found in _WORD.findall(title)):
        return 1
    if word in title:
        return 2
    if len(word) > 1 and _initials(title).startswith(word):
        return 3
    if word in other:
        return 4
    return None


def _initials(text: str) -> str:
    return "".join(found[0] for found in _WORD.findall(text))
