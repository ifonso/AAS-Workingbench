# Style guide

We follow the [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html).
Tools enforce most of it, and this page records our choices and additions.
Deviations are allowed in individual cases, after discussion in the pull request.

## Tooling

| Tool | Purpose | Command |
|---|---|---|
| ruff | Formatting | `make format` |
| ruff | Linting | `make lint` |
| pyright | Static type checking | `make typecheck` |

Configuration lives in `pyproject.toml`.
Run `make check` before opening a pull request.

## Where the rules apply

| Code | Formatting | Lint rules | Naming |
|---|---|---|---|
| New packages and `tests/` | ruff, 80 columns | Full set | Google style |
| Existing modules listed in `per-file-ignores` | ruff, 80 columns | Reduced set | Keep the surrounding `mixedCase` |
| Generated code (`handover_submodel.py`) | Excluded | Excluded | Not applicable |
| `design.py`, the layout of the main window, written by hand and kept out of the checks until it is rewritten | Excluded | Excluded | Keep the surrounding `mixedCase` |

[ADR 0003](../software/adr/0003-python-style.md) explains why.

## Python

### Naming

| Kind | Style |
|---|---|
| Packages and modules | `lower_with_under` |
| Classes and exceptions | `CapWords` |
| Functions, methods, variables, parameters | `lower_with_under` |
| Constants | `CAPS_WITH_UNDER` |
| Internal names | Leading underscore: `_internal_helper` |

Methods that override Qt keep their Qt names and carry a `# noqa: N802` comment:

```python
def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
    ...
```

### Imports

- Use absolute imports: `from aas_editor.package import Package`.
- Import one name per line. `ruff` sorts them.
- Do not use wildcard imports.

### Types

- Annotate all public functions and methods in new code.
- Use modern syntax: `list[str]` and `str | None`.
- Avoid `# type: ignore`. When it is necessary, use `# pyright: ignore[ruleName]` and explain why.

### Docstrings

Use Google-style docstrings on public modules, classes, and functions:

```python
def read_package(path: Path) -> Package:
    """Reads an AAS package from disk.

    Args:
        path: Location of an AASX, JSON, or XML file.

    Returns:
        The loaded package.

    Raises:
        ValueError: If the file extension is not supported.
    """
```

Comments explain why the code does something, and the code itself should show what it does.

### Language features

- Use f-strings to build strings.
- Use `pathlib` rather than `os.path` and bare `open()`.
- Catch specific exceptions. Bare `except:` is not allowed in new code.
- Use `logging`, not `print`. Pass arguments lazily: `logger.info("Opened: %s", path)`.
- Do not use mutable default arguments.
- Do not do significant work at import time, such as creating Qt objects or reading files.

### Errors and logs

Put the static part of a message first, so that output is easy to filter:

```python
raise ValueError(f"Malformed response: '{response}'")  # Good
raise ValueError(f"The response '{response}' was malformed.")  # Bad
```

## Dependencies

- Add them with `uv add <package>`, or `uv add --group dev <package>` for development tools.
- Commit `uv.lock` with `pyproject.toml`.
- Do not use `pip` or `requirements.txt`.
- Explain in the pull request why any new dependency is needed. Check that its license is compatible with GPLv3.

## Version control

- Follow the [branching guide](branching.md).
- Write commits as described in the [Conventional Commits guide](conventional-commits.md).
- Update [CHANGELOG.md](../../CHANGELOG.md) for changes users will notice.

## General

- Write code, comments, and commit messages in English.
- Prefer text formats such as JSON.
- Use [semantic linefeeds](https://rhodesmill.org/brandon/2012/one-sentence-per-line/) in documentation: one sentence per line.
