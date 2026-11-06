# Testing guide

This guide adapts Google's public testing practices to a PyQt application.
The main sources are [Software Engineering at Google](https://abseil.io/resources/swe-book), chapters 11 to 14, and the [Google Testing Blog](https://testing.googleblog.com/).

## Running tests

| Command | Runs |
|---|---|
| `make test` | Small and medium tests, the same set CI runs |
| `make test-small` | Small tests |
| `make test-medium` | Medium tests |
| `make test-large` | Large tests, which drive the full application |
| `make coverage` | Small and medium tests with a coverage report |

To run one test directly:

```sh
uv run pytest tests/medium/test_package.py -k roundtrip
```

Tests use Qt's `offscreen` platform by default, so they need no display.
To watch a large test on screen, set `QT_QPA_PLATFORM=windows` (or `xcb` on Linux) first.

**Known issue:** `testEditCreate` in `tests/large/test_main_window.py` does not finish when run offscreen, so `make test-large` hangs.
It hangs with older SDK versions too, and it is probably waiting on a modal dialog.
Until it is fixed, run the other large tests with `uv run pytest -m large -k "testViews or testLinks"`.

## Test sizes

We classify tests by the resources they use, not by the code they cover.
A test's directory sets its size, and `tests/conftest.py` applies the matching marker automatically.
A test outside these directories fails collection.

| Size | Directory | May use | May not use | Target share |
|---|---|---|---|---|
| Small | `tests/small/` | One process, memory | Files, network, sleeps, event loop timing | About 80% |
| Medium | `tests/medium/` | One machine, temporary files, offscreen widgets | External network | About 15% |
| Large | `tests/large/` | The full application, including WebEngine | External network, unless a test states why | About 5% |

The target shares describe where we want to get to.
Today the suite leans on medium tests, because reading `aas_editor` settings requires a `QApplication`.
Separating the domain from Qt, as described in the [architecture guide](../software/architecture.md), is what makes more small tests possible.

## Layout

```text
tests/
├── conftest.py     # shared fixtures and size classification
├── data/           # read-only sample packages
├── small/
├── medium/
└── large/
```

Name files after the module under test, such as `test_package.py` for `aas_editor/package.py`.

## Principles

### Test behavior, not implementation

A test should break only when behavior a user or caller relies on has changed.
Refactoring should not break tests.

- Exercise the public API. Do not call `_private` methods.
- Write one test per behavior, not one test per method.
- Assert on the resulting state, not on which internal calls were made.

### Make each test obviously correct

- Put no logic in tests: no loops, conditionals, or computed expected values.
- Write literal expected values.
- Keep tests DAMP (descriptive and meaningful phrases), not DRY. Some repetition is fine if it lets the reader understand the test on its own.
- Use fixtures for setup that does not affect the outcome. Keep values that do affect it in the test body.

### Structure and name tests clearly

Follow Given, When, Then, separated by blank lines.
Name the test after the behavior, so that a failure explains itself: `test_<behavior>_when_<condition>`.

```python
def test_write_keeps_submodels_when_saving_as_aasx(
    qapp: QApplication, aasx_file: Path, tmp_path: Path
) -> None:
    package = Package(aasx_file)
    copy_path = tmp_path / "copy.aasx"

    package.write(copy_path)

    assert Package(copy_path).numOfSubmodels == package.numOfSubmodels
```

### Keep tests hermetic and deterministic

- Write only under pytest's `tmp_path`. Never change files in `tests/data/`.
- Do not depend on test order, the current directory, the clock, or the user's settings.
- Do not use `time.sleep`. In Qt tests, wait on a condition with `qtbot.waitUntil` or `qtbot.waitSignal`.
- Treat a flaky test as a bug: fix it or delete it. Do not retry it.

### Prefer real objects over test doubles

Choose in this order:

1. The real implementation, when it is fast and deterministic.
2. A fake: a lightweight working implementation.
3. A stub, when you need a specific return value.
4. A mock that verifies interactions, only when the interaction itself is the behavior, such as a call to an LLM provider.

Do not mock types you do not own, such as BaSyx models or Qt classes.
Use real BaSyx objects, which are cheap to create.

## Testing Qt code

- Request the `qapp` fixture in every test that imports `aas_editor` settings.
- Put logic in plain classes and test it without widgets whenever possible.
- Use [pytest-qt](https://pytest-qt.readthedocs.io/)'s `qtbot` for widgets:

```python
def test_line_edit_emits_text_when_user_types(qtbot: QtBot) -> None:
    line_edit = QLineEdit()
    qtbot.addWidget(line_edit)

    with qtbot.waitSignal(line_edit.textChanged):
        qtbot.keyClicks(line_edit, "nameplate")

    assert line_edit.text() == "nameplate"
```

- Test `QAbstractItemModel` subclasses through the model API, without a view.
- Modal dialogs block the event loop, so stub out `exec()` or have the code under test receive the answer as an argument.

## Testing AAS behavior

These checks matter most for parity work:

- **Round trips:** read, write, and read again for AASX, JSON, and XML, and compare the content.
- **Sample packages:** use the IDTA templates in `tests/data/`. Add a small new file there only if no existing file covers the case.
- **Spec constraints:** name the constraint in the test, such as `test_rejects_id_short_violating_constraint_aasd_002`.
- **Acceptance criteria:** each parity feature doc has an acceptance criteria section. Turn each criterion into at least one test.

## What every change needs

| Change | Required tests |
|---|---|
| New behavior | Tests for the normal path, edge cases, and error paths |
| Bug fix | A test that fails before the fix and passes after it |
| Refactoring | Existing tests pass without changes |
| New dependency on I/O or network | A fake at that boundary, so most tests stay small |

Coverage is a tool for finding untested code, not a goal in itself.
We enforce no percentage for now, but a pull request should not leave its new logic untested.
Do not write tests that execute code without asserting on what it does.

## Reviewing tests

Before approving a test, check that:

- It would fail if the behavior broke.
- It can be understood without opening other files.
- It would survive an internal refactoring.
- Its size directory matches the resources it uses.
