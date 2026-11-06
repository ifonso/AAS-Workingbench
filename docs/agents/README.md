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
| Type check the new layers, which must have no warnings | `uv run pyright src/aas_editor/domain src/aas_editor/application src/aas_editor/infrastructure src/aas_editor/ui` |
| Fast tests | `uv run pytest -m "small or medium"` |
| One test file | `uv run pytest tests/medium/test_package.py` |
| One test | `uv run pytest tests/medium/test_package.py::test_name`, or `-k part_of_the_name` |
| Large tests, about 10 minutes | `uv run pytest -m large` |
| Round trip of all 132 bundled templates | `AAS_CORPUS_TEMPLATES=all uv run pytest tests/medium/test_roundtrip_corpus.py` |
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

## How the code fits together

Two generations of code work together: the legacy Qt modules at the top of `src/aas_editor/`, and the four layers below them.

- **Legacy shell.** `editorApp.py`, `treeviews/`, `models/`, `widgets/`, `dialogs.py`, and `package.py` hold the window, the item models, and the generated forms. Rows and forms come from runtime introspection of the type hints of BaSyx classes (`utils/util_type.py`).
- **Layers.** `ui → application → domain`, and `infrastructure → application`. `tests/medium/test_layers.py` fails if `domain` or `application` loads PyQt.
- **All AAS access goes through BaSyx (plan decision D3).** The few narrow exceptions are in `infrastructure/package_io.py`. The SDK is pinned to one commit in `pyproject.toml`, and some tests depend on its internals and the text of its log messages.
- **An edit is a command.** Operations in `application/operations/` first make a plan, which can be shown or refused, and then give commands. `application/commands.py` keeps one history for each package, and a group is one undo step. A command reports to `observer_for(package)` in `application/changes.py`, and that is how every tab and tree updates. Do not change an AAS object from a view directly.
- **Actions are registered.** A feature adds its menu entries with `register_action` from `ui/actions.py`, and `__main__.py` calls its `register_*` function. Tests find an entry by its action id, also inside a submenu, with `tests/menus.py`.
- **What a row shows is not its key.** The display role has the words of the metamodel (`idShort`, `Submodels`), from `domain/attribute_vocabulary.py`, `domain/tree_names.py`, and `domain/readable_values.py`. `NAME_ROLE` has the SDK name (`id_short`, `submodels`), which is what edits, lookups, and tests must use. A new attribute without a vocabulary entry fails a test.
- **Saving.** `application/save.py` validates and warns, and `infrastructure/package_io.py` writes a temporary file and replaces the target, so a failed save leaves the original intact. A package that opened in failsafe mode is partial: its load report lists what the SDK left out, and it can only use Save As.
- **Validation.** Rules are in `domain/validation/rules/`. `ALL_RULES` feed the Validation dock and the save gate, and `HINT_RULES` only feed hints mode.

Plan decisions such as D3 are in the [V1 editor plan](../planning/v1-editor-plan.md), with what remains to be done. The [acceptance audit](../software/v1-acceptance-audit.md) says how each criterion of the specification is met.

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
| Running the app, the large tests, or a script that changes the theme rewrites the tracked `settings/settings.ini`, which is committed as an empty file | Run `git checkout -- src/aas_editor/settings/settings.ini` before every commit, and read `git diff --cached --stat` before you commit. Earlier work committed that file by accident, with the theme and window size of the machine. |
| To look at the UI without a display, text renders as boxes, and a modal dialog hangs the process forever | Run with `QT_QPA_PLATFORM=offscreen` and `QT_QPA_FONTDIR=C:/Windows/Fonts` (the second, on Linux a folder with a font). Import `PyQt6.QtWebEngineWidgets` before the `QApplication`. Replace `QApplication.exec` with a function that schedules steps with `QTimer.singleShot` and then calls the original, and `widget.grab().save(path)` writes a picture. Patch `QDialog.exec` and `QMessageBox.exec` to grab the dialog and return, and `QMessageBox.question`, `QInputDialog.getItem` and `QFileDialog.getOpenFileName` to return at once, because the static functions block too. Call `aas_editor.__main__.main` for the real entry point. Keep the script and the pictures out of the repository. The pictures show layout and text, not the behavior of a real display, and QtWebEngine shows black. Without `QT_QPA_PLATFORM`, the same script opens a real window that draws the preview, and `widget.grab()` still works. Do not capture the screen: it holds whatever the user has open. |
| A script that starts the app and quits it hides the exit code of a crash | Read the real exit code, for example with PowerShell `Start-Process -PassThru -Wait` and `$p.ExitCode`, and do not pipe the output through `tail` or a variable, which hides it and can keep a process that waits for a dialog alive. Check that no `python` process is left behind. |
| Hundreds of tracebacks in the log when opening a package | Most are handled introspection failures, and existed before your change. Compare before and after instead of assuming you caused them. |
| Generated files: `themes/breeze_resources.py`, `tools/handover_doc_llm/handover_submodel.py` | Do not edit them by hand. |
| `design.py` says it is generated, and it is not | It is the hand-written layout of the main window. `mainwindow_base.ui` does not give it back, so edit `design.py` ([ADR 0028](../software/adr/0028-main-window-layout.md)). |
| Wildcard imports in `treeviews` and `widgets` packages | Search for where a name is really defined before changing it. |
| `pyproject.toml` is read at runtime by `app_settings.py` | Keep `project.authors`, `project.urls`, `project.license.text`, and `project.description` in their current form. |
| Windows paths longer than 260 characters in `submodel_templates` | Keep `core.longpaths` enabled. |
| Large tests are slow and need WebEngine | Run them when a change affects the main window flow, and all of them after merging parallel work, because they caught what the fast tests did not. They are not in CI. |
| A large test passes alone and fails in the whole suite | Earlier large tests rewrite `settings.ini`. A test must set every setting that it depends on. |
| A test that selects a stored file in the package tree passes, and the process then ends with an access violation and no summary | It is the QtWebEngine preview in a test process. Replace the web view with a stand-in. The real application has not done this in the runs so far. |
| Parallel branches conflict in `CHANGELOG.md`, the ADR table, `feature-parity.md`, and the audit counts | Keep both sides. ADR numbers can clash, so renumber at the merge. The audit counts are recomputed from its rows. |

## Boundaries

Ask before doing any of these:

- Adding a dependency with wide reach, or changing the metamodel target
- Renaming or moving legacy modules outside the task
- Removing an existing feature, including those Package Explorer lacks
- Anything that affects remote branches, releases, or tags

Record decisions that are expensive to reverse as [ADRs](../software/adr/README.md).
