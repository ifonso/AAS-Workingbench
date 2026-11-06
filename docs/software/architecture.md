# Architecture

AAS Manager is a desktop viewer and editor for Asset Administration Shell packages, built on PyQt6 and the Eclipse BaSyx Python SDK.
This page describes the code as it is today, and the structure that new code should follow.

## Repository layout

```text
.
├── src/aas_editor/        # application package
├── tests/                 # tests, organized by size
├── docs/                  # this documentation
├── aas_test_engines/      # data files bundled into frozen builds
├── aas_manager.spec       # PyInstaller build definition
├── Makefile               # development tasks
├── pyproject.toml         # metadata, dependencies, tool configuration
├── uv.lock                # exact dependency versions
└── CHANGELOG.md
```

## Current structure

| Module | Responsibility |
|---|---|
| `__main__.py` | Entry point. Creates `QApplication`, loads icons, and opens `EditorApp`. |
| `editorApp.py` | Main window, menus, toolbars, session save and restore. |
| `design.py` | Generated main window layout, from `mainwindow_base.ui`. |
| `package.py` | `Package`: reads and writes AASX, JSON, and XML through BaSyx, and handles crash recovery files. |
| `models/` | Qt item models that adapt packages and AAS objects to tree views. |
| `treeviews/` | Tree views and their actions: `base.py` is shared, `treeview_pack.py` shows open packages, and `treeview_detailed.py` shows object attributes. |
| `widgets/` | Tabs, editors, search bar, message boxes. `tab.py` also previews media content. |
| `dialogs.py`, `delegates.py` | Add and edit dialogs generated from type hints, and inline cell editors. |
| `settings/` | Application constants, AAS type metadata, icons, shortcuts, and persistent settings. |
| `utils/` | Type hint introspection (`util_type.py`), general helpers, recovery, and the exception hook. |
| `additional/` | Extra AAS classes used by the editor. |
| `tools/aas_test/` | Validates files with `aas-test-engines`. |
| `tools/handover_doc_llm/` | Generates Handover Documentation from PDFs using LLMs. |
| `tools/import_feature/` | Generates AAS files from Excel using mappings. |
| `submodel_templates/` | IDTA templates, available when adding Submodels. |
| `themes/` | Qt stylesheets and their generated resources. |

### How the editor works

1. `PackTreeView` opens a file as a `Package`, and BaSyx loads its objects into an object store.
2. `models/` wraps the objects in tree items. Selecting one opens its attributes in a tab, shown by `AttrsTreeView`.
3. Attributes and editors come from **runtime type introspection**: `utils/util_type.py` and `getAttrTypeHint` read the type hints of BaSyx classes.
   This is why the editor handles new SDK attributes with little code, and also why it relies heavily on SDK internals.
4. Edits go through the model, which supports undo and redo, and mark the package as changed.
5. Crash recovery writes changed packages to `settings/recovery/`, and the next start offers to restore them.

### Known structural problems

| Problem | Consequence |
|---|---|
| Importing `app_settings.py` creates Qt objects, and `dialogs.py` reads the primary screen at class definition. | Modules cannot be imported without a `QApplication`, and most tests are not small. |
| Domain logic is inside models, views, and widgets. | Logic cannot be reused, and is hard to test. |
| Application state is in `settings/settings.ini`, which is tracked by Git, inside the package. | Running the app modifies a tracked file, and an installed copy would write inside its own package. |
| `pyproject.toml` is read at runtime for metadata. | A wheel would not run, so frozen builds must bundle this file. |
| LLM and PDF dependencies are always installed. | Installs and builds are large, even for users who never open the Handover tool. |
| Introspection logs hundreds of handled tracebacks when opening a package. | Real errors are hard to find in the log. |
| `aas_editor` is a large module-level dependency web, with circular imports worked around at the end of `package.py`. | Import order is fragile. |

## Target structure

New features use four layers, as decided in [ADR 0002](adr/0002-layered-architecture.md).
Dependencies point only in the direction shown:

```text
ui ───────────► application ───────► domain
                     ▲
infrastructure ──────┘
```

| Layer | Package | Holds | May import |
|---|---|---|---|
| Domain | `aas_editor/domain/` | AAS rules and validation, without I/O | Standard library, BaSyx |
| Application | `aas_editor/application/` | Use cases, such as "connect to a repository". Defines interfaces (`typing.Protocol`) for external systems. | Domain |
| Infrastructure | `aas_editor/infrastructure/` | Implementations of those interfaces: file formats, HTTP clients, credential storage | Application, domain, external libraries |
| UI | `aas_editor/ui/` | Qt widgets and models that call use cases | Application, domain |

`__main__.py` is the composition root, where implementations are connected to the use cases that need them.

### Rules

- `domain` and `application` never import PyQt, so their tests can be small.
- UI code holds no business logic, and only translates between user events and use cases.
- Code does no significant work at import time.
- Long-running work, such as network calls, must not block the UI thread.
- The first feature to use a layer creates its package, and adds an automated check of these import rules.

### Working with legacy code

- Put new features in the layers, and connect them to the legacy UI with a thin adapter.
- When a change requires substantial work in a legacy module, move the affected logic to a layer first, in a separate `refactor` commit.
- Do not rewrite legacy code that no planned feature needs to change.

Type checking and lint rules are strict in the new packages, and relaxed in legacy ones.
See [ADR 0003](adr/0003-python-style.md).

## Key dependencies

| Dependency | Used for |
|---|---|
| PyQt6, PyQt6-WebEngine, PyQt6-QScintilla | User interface, content preview, JSON editor |
| basyx-python-sdk | AAS metamodel and AASX, JSON, and XML adapters ([ADR 0004](adr/0004-basyx-sdk-pin.md)) |
| aas-test-engines | File validation |
| openpyxl | Excel import |
| langchain and related packages, sentence-transformers, faiss-cpu, pypdf | Handover Documentation tool |

## Related documents

- [Decision records](adr/README.md)
- [Feature parity roadmap](feature-parity.md)
