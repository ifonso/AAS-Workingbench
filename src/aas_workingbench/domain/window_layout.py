"""The size of the main window and of its two zones, before a session saved any.

A first run opened a window of 1194 by 624 pixels on every screen. On a screen
of 1920 by 1080 that left the tab under 720 pixels, so the preview of a file
started dragged shut. These functions choose the size from the room that the
screen has, and do not know Qt.

Example:
    >>> first_run_size(1920, 1032)
    (1632, 877)
    >>> zone_widths(1632)
    (653, 979)
"""

DEFAULT_SIZE = (1194, 624)
"""The smallest window that a first run opens, if the screen has the room."""

SCREEN_SHARE = 0.85
"""How much of the room of the screen a first run takes."""

LEFT_SHARE = 0.4
"""How much of the window the tree of packages gets."""

LEFT_MIN_WIDTH = 520
"""What the tree of packages needs for its object and type columns."""

TAB_MIN_WIDTH = 720
"""What a tab needs to show a preview beside its attributes."""


def first_run_size(
    available_width: int, available_height: int
) -> tuple[int, int]:
    """Returns the size of the window of a first run.

    Args:
        available_width: The width of the screen without the taskbar.
        available_height: The height of the screen without the taskbar.

    Returns:
        A share of the room of the screen, not smaller than the default size
        unless the screen is, and never larger than the screen.
    """
    return (
        _fit(available_width, DEFAULT_SIZE[0]),
        _fit(available_height, DEFAULT_SIZE[1]),
    )


def window_size(
    saved: tuple[int, int] | None, available_width: int, available_height: int
) -> tuple[int, int]:
    """Returns the size to open the window with.

    Args:
        saved: The size that the last session left, or None for a first run.
        available_width: The width of the screen without the taskbar.
        available_height: The height of the screen without the taskbar.

    Returns:
        The saved size if there is one, which the user chose, and else the
        size of a first run.
    """
    if saved is not None:
        return saved
    return first_run_size(available_width, available_height)


def zone_widths(window_width: int, toolbar_width: int = 0) -> tuple[int, int]:
    """Returns the widths of the tree of packages and of the tabs.

    Args:
        window_width: The width of the window.
        toolbar_width: The width that the toolbar of the tree needs to show
            all of its buttons, or 0 if it is not known.

    Returns:
        The tree gets a share of the window, what its columns need at least,
        and the width of its toolbar if the tabs keep room for a preview
        then. The tabs get the rest.
    """
    left = max(round(window_width * LEFT_SHARE), LEFT_MIN_WIDTH)
    if toolbar_width > left:
        left = min(toolbar_width, window_width - TAB_MIN_WIDTH)
        left = max(left, LEFT_MIN_WIDTH)
    left = min(left, window_width)
    return left, window_width - left


_ORIENTATIONS = {1: "horizontal", 2: "vertical"}
"""The numbers that Qt gives its two orientations."""


def saved_orientation(saved: object) -> str | None:
    """Reads the orientation of the two zones that a session saved.

    The store gives back whatever it was given, in a form that depends on how
    it was written: the member of the Qt enumeration, its number as an int, the
    number as text from a hand-edited file, or a name. All of them mean the
    same, and anything else is not an orientation.

    Args:
        saved: The value of the setting.

    Returns:
        "horizontal", "vertical", or None if the value is no orientation, in
        which case the window keeps its default layout.

    Example:
        >>> saved_orientation(2)
        'vertical'
        >>> saved_orientation("Orientation.Horizontal")
        'horizontal'
        >>> saved_orientation("diagonal") is None
        True
    """
    # A member of a Qt enumeration holds its number in `value`.
    value = getattr(saved, "value", saved)
    if isinstance(value, bool):
        return None
    if isinstance(value, str):
        text = value.strip().lower().removeprefix("orientation.")
        if not text.isdigit():
            return text if text in _ORIENTATIONS.values() else None
        value = int(text)
    if isinstance(value, int):
        return _ORIENTATIONS.get(value)
    return None


def _fit(available: int, default: int) -> int:
    wanted = max(round(available * SCREEN_SHARE), default)
    return min(wanted, available)
