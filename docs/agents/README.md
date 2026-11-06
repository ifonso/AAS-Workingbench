# Guide for AI agents

Instructions for AI coding agents working in this repository.
Follow them unless the user says otherwise.

## Project goal

Bring this PyQt6 AAS editor to functional parity with AASX Package Explorer.
Read [feature-parity.md](../software/feature-parity.md) before starting feature work.
The specification for each feature is in `../package-explorer/design-docs/`, outside this repository, and may not exist on every machine.
If it is missing, say so instead of guessing what a feature should do.

## Commands

| Task | Command |
|---|---|
| Install | `uv sync --locked` |
| Format | `uv run ruff format` |
| Lint | `uv run ruff check` |
| Type check | `uv run pyright` |
| Fast tests | `uv run pytest -m "small or medium"` |
| One test file | `uv run pytest tests/medium/test_package.py` |
| Run the app | `uv run python -m aas_editor` |

`make check` runs the same checks as CI, but Make may not be installed.
Always use `uv`. Never use `pip`, or call `python` outside `uv run`.

## Definition of done

1. `uv run ruff format --check`, `uv run ruff check`, and `uv run pyright` report no errors.
2. `uv run pytest -m "small or medium"` passes.
3. New behavior has tests, and bug fixes have a test that failed before the fix.
4. Changes users will notice are in `CHANGELOG.md`.
5. Docs affected by the change are updated, including the status in `feature-parity.md`.

Report what you ran and what happened.
If a check could not run, say so. Do not claim a GUI change works unless you ran it.

## Where code goes

Read the [architecture guide](../software/architecture.md) first.

- New features go in `src/aas_editor/{domain,application,infrastructure,ui}/`.
- `domain` and `application` must not import PyQt.
- Change legacy modules as little as the task allows, and match their `mixedCase` naming.
- New code uses Google-style names, type annotations, and docstrings. See the [style guide](../contributing/style-guide.md).

## Tests

Read the [testing guide](../contributing/testing-guide.md).
A test's directory sets its size: `tests/small`, `tests/medium`, or `tests/large`.
Test behavior through public APIs, and do not put logic in tests.

## Git

- `main` holds releases, and `development` is the integration branch. Do not commit directly to either.
- Create branches from `development`, as `feat/...`, `fix/...`, `refactor/...`, and so on. See the [branching guide](../contributing/branching.md).
- Write commits as described in the [Conventional Commits guide](../contributing/conventional-commits.md).
- Commit or push only when the user asks.

## Pitfalls

| Pitfall | What to do |
|---|---|
| Importing `aas_editor` needs a `QApplication` for many modules | Request the `qapp` fixture in tests. Import `aas_editor.dialogs` and modules that depend on it only after the application exists. |
| QtWebEngine must be imported before `QApplication` is created | Keep the import order in `__main__.py`. Do not let tooling reorder it. |
| Running the app rewrites the tracked `settings/settings.ini` | Run `git checkout -- src/aas_editor/settings/settings.ini` before committing. |
| Hundreds of tracebacks in the log when opening a package | Most are handled introspection failures, and existed before your change. Compare before and after instead of assuming you caused them. |
| Generated files: `design.py`, `themes/breeze_resources.py`, `tools/handover_doc_llm/handover_submodel.py` | Do not edit them by hand. |
| Wildcard imports in `treeviews` and `widgets` packages | Search for where a name is really defined before changing it. |
| `pyproject.toml` is read at runtime by `app_settings.py` | Keep `project.authors`, `project.urls`, `project.license.text`, and `project.description` in their current form. |
| Windows paths longer than 260 characters in `submodel_templates` | Keep `core.longpaths` enabled. |
| Large tests are slow and need WebEngine | Run them only when a change affects the main window flow. They are not in CI. |

## Boundaries

Ask before doing any of these:

- Adding a dependency with wide reach, or changing the metamodel target
- Renaming or moving legacy modules outside the task
- Removing an existing feature, including those Package Explorer lacks
- Anything that affects remote branches, releases, or tags

Record decisions that are expensive to reverse as [ADRs](../software/adr/README.md).
