# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

Phase 0 prepares the project for [feature parity with AASX Package Explorer](docs/software/feature-parity.md).

### Added

- A Makefile as the single entry point for development tasks.
- Linting and formatting with ruff, and type checking with pyright, both enforced in CI.
- Project documentation in `docs/`: architecture, decision records, guides for testing, style, commits, and branching, and instructions for AI agents.
- `python -m aas_editor` as a way to start the application.
- A round-trip test that saves a corpus of packages and compares their objects and file parts, with an optional local mode for packages outside the repository.
- A test that `domain` and `application` do not import PyQt, and helpers in `tests/factories.py` that build BaSyx objects.

### Changed

- The project is now managed only with uv, including CI and release builds, and `uv.lock` pins all dependencies.
- The code moved to `src/aas_editor/`, and tests moved to `tests/`, organized by size.
- All non-generated code is formatted with ruff, using Google's 80-column limit.
- `basyx-python-sdk` now uses the `aas_manager/develop` branch of the fork, pinned to a commit. This moves the SDK to metamodel V3.1.
- Python 3.11 is now the minimum version, as the SDK requires.
- `torch` now comes from the CPU-only index on Windows and Linux, which also applies to Linux release builds.
- `pyinstaller` moved from runtime dependencies to the `build` dependency group.
- The default branch is `main`, and integration happens on `development`.
- The application now names metamodel V3.1 in its title and About dialog. The AAS Test tool is labeled V3.0, because `aas-test-engines` checks only that version.
- An uncaught exception now shows an error with its traceback, and the application keeps running. It no longer exits.

### Fixed

- Installation failed because the `aas_manager/v301` branch of the SDK fork no longer exists.
- The Excel import tool raised `NameError` instead of showing an error dialog when an operation failed.
- Invalid escape sequences in regular expressions produced `SyntaxWarning`.
- Entering the text "None" in an attribute set it to nothing. The text is now kept, and a real clear still works with Delete.
- A value that did not fit a Property, such as text for an integer, silently changed its `value_type`. The edit is now refused with an error.
- Clearing a mandatory attribute, such as `asset_information` of a shell, left an invalid object or crashed the application. It is now refused with an error.
- The Blob editor ran the entered text as Python code. It now accepts only a bytes literal such as `b'text'`.
- A failure while saving, such as an unwritable folder, closed the application. It now shows an error.
- The AAS Test tool could not check an AASX file, because it opened the file as text. It now opens files in binary mode.
- `testEditCreate` hung the large tests because a modal dialog blocked it. The large tests now stub modal dialogs.

### Removed

- `Guidelines.md`, replaced by `docs/contributing/style-guide.md`.

## 0.4.13 - 2026-08-28

The last version inherited from upstream [rwth-iat/aas_manager](https://github.com/rwth-iat/aas_manager).
See the [upstream releases](https://github.com/rwth-iat/aas_manager/releases) for earlier changes.
