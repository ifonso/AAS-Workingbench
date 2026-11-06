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

### Changed

- The project is now managed only with uv, including CI and release builds, and `uv.lock` pins all dependencies.
- The code moved to `src/aas_editor/`, and tests moved to `tests/`, organized by size.
- All non-generated code is formatted with ruff, using Google's 80-column limit.
- `basyx-python-sdk` now uses the `aas_manager/develop` branch of the fork, pinned to a commit. This moves the SDK to metamodel V3.1.
- Python 3.11 is now the minimum version, as the SDK requires.
- `torch` now comes from the CPU-only index on Windows and Linux, which also applies to Linux release builds.
- `pyinstaller` moved from runtime dependencies to the `build` dependency group.
- The default branch is `main`, and integration happens on `development`.

### Fixed

- Installation failed because the `aas_manager/v301` branch of the SDK fork no longer exists.
- The Excel import tool raised `NameError` instead of showing an error dialog when an operation failed.
- Invalid escape sequences in regular expressions produced `SyntaxWarning`.

### Removed

- `Guidelines.md`, replaced by `docs/contributing/style-guide.md`.

## 0.4.13 - 2026-08-28

The last version inherited from upstream [rwth-iat/aas_manager](https://github.com/rwth-iat/aas_manager).
See the [upstream releases](https://github.com/rwth-iat/aas_manager/releases) for earlier changes.
