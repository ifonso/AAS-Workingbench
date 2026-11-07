# ADR 0001: `src/` layout and tests organized by size

**Status:** Accepted

## Context

The package sat at the repository root, next to `main.py`, with tests in `aas_editor_test/`.
Because the root was on the import path, tests could pass against the source tree even when the installed package was broken.
`[tool.setuptools.packages.find]` also pointed at the wrong directory, so a built package would not have contained the code.

## Decision

- Move the code to `src/aas_editor/`, as the [Python Packaging User Guide](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/) recommends.
- Replace `main.py` with `src/aas_editor/__main__.py`, so the application starts with `python -m aas_editor`.
- Move tests to `tests/small`, `tests/medium`, and `tests/large`, following Google's test sizes.
- Manage the environment only with uv, using `pyproject.toml` and `uv.lock`.

## Consequences

- Tests import the installed package, the same way users do.
- Size is visible from the path and cannot be forgotten, because `tests/conftest.py` rejects tests outside these directories.
- Merging from upstream `rwth-iat/aas_manager` relies on Git's rename detection, and will conflict more often.
- `app_settings.py` now looks for `pyproject.toml` in two places, because the file is in a different location in source checkouts and frozen builds.
- Paths grew by four characters. Some template paths already exceed the Windows limit of 260 characters, so Windows contributors must enable `core.longpaths`.

## Later change

The package was renamed as_workingbench for the first release of AAS Workingbench (0.1.0), and python -m aas_workingbench starts it. This record keeps the names of its time.
