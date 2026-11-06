# ADR 0003: Google Python style, with legacy code exempted

**Status:** Accepted

## Context

The old `Guidelines.md` required Qt-style `mixedCase` names and 88-character lines, and the code used them inconsistently.
We want to follow the [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html).

Renaming every legacy symbol would be a large and risky change with little user value.
Reordering legacy imports is also unsafe, because some modules depend on import side effects. For example, QtWebEngine must load before `QApplication` is created.

## Decision

- Format all non-generated code with `ruff format` at 80 columns.
- Apply the full lint rule set, including naming, docstrings, and import order, to new packages and tests.
- Exempt existing modules from the stylistic rules through `per-file-ignores` in `pyproject.toml`. Rules that find real bugs stay on, except where the exemption list says otherwise.
- Shrink that list over time. Removing an entry is welcome, and adding an entry for new code is not.
- Keep double quotes. The Google guide accepts either if the choice is consistent, and this is the ruff default.
- In new code, methods that override Qt keep their Qt names, marked `# noqa: N802`. This matches the guide's advice to stay consistent with the surrounding framework.

## Consequences

- The formatter run touches almost every Python file once. Commit it separately and list it in `.git-blame-ignore-revs`.
- Legacy and new code use different naming, and the directory tells you which applies.
- Merges from upstream will conflict in reformatted files. Run `make format` on the upstream version before resolving them.
