# AAS Workingbench

A desktop editor for AASX files of the Asset Administration Shell, written in Python with PyQt6.

## Purpose

AAS Workingbench is a fork of [AAS Manager](https://github.com/rwth-iat/aas_manager) (`rwth-iat/aas_manager`), developed at RWTH Aachen.
It aims to edit AASX files with the same robustness as [AASX Package Explorer](https://github.com/eclipse-aaspe/package-explorer), with a more pleasant interface, and to do so on Linux, Windows and macOS.
Package Explorer is the reference, and the editor is not at parity with it yet: some features are missing, and a few are out of scope on purpose.
[Feature parity](docs/software/feature-parity.md) tracks the gap, and the [V1 editor plan](docs/planning/v1-editor-plan.md) lists what is out of scope.

The project also plans AI features that make modeling, verification and the use of industry standards easier, and an MCP server.
None of that exists yet.
The one LLM feature today is inherited from upstream: a [handover documentation tool](src/aas_editor/tools/handover_doc_llm/README.md) that drafts a Handover Documentation submodel from a PDF through a model provider that you configure.

Only Windows has been used to run the editor in the current work.
Continuous integration runs the checks on Ubuntu, and the release workflow builds for Ubuntu and Windows.
Nothing builds for macOS, so macOS is a goal and not a claim.

## What the editor does

It opens, edits and saves AASX, JSON and XML packages for metamodel V3.1.x, and reads V3.0 files as V3.1, as the SDK does.
Every edit, add, delete and paste can be undone, and a Read mode refuses changes.
Values are checked against their XSD type as you type, renames update the references that point at the renamed object, and the files stored in a package can be managed from a panel.
A set of validation rules covers constraints of the metamodel that the SDK does not enforce.
The [changelog](CHANGELOG.md) has the full list, including the known limits, and [`docs/`](docs/README.md) has the architecture, decision records and guides.

## Build

You need [uv](https://docs.astral.sh/uv/getting-started/installation/) and Git.
You do not need to install Python, because uv fetches the version the project asks for (3.11 or newer).

On Windows, some template paths exceed 260 characters, so clone with long paths enabled:

```sh
git clone -c core.longpaths=true https://github.com/ifonso/AAS-Workingbench.git
cd AAS-Workingbench
```

If you cloned without it, run `git config core.longpaths true` in the clone, then `git reset` and `git checkout -- .`.
On Debian and Ubuntu, Qt also needs two system libraries, which CI installs:

```sh
sudo apt-get install libegl1 libopengl0
```

Install the locked environment and start the editor from source:

```sh
uv sync --locked
uv run python -m aas_editor
```

Running the editor rewrites the tracked file `src/aas_editor/settings/settings.ini`.
Do not commit that change, and discard it with `git checkout -- src/aas_editor/settings/settings.ini`.

CI checks the code and runs the small and medium tests with these commands:

```sh
uv run ruff format --check
uv run ruff check
uv run pyright
uv run pytest -m "small or medium"
```

Pyright prints warnings for older modules, and they do not fail the check.
If GNU Make is installed, `make check` runs the same four commands, and `make` lists the other targets.

To build a stand-alone executable with PyInstaller:

```sh
uv run --group build pyinstaller --noconfirm aas_manager.spec
```

The result is the folder `dist/AAS_Manager`, which holds the executable `AAS_Manager` (`AAS_Manager.exe` on Windows).
`make build` runs the same command.

## Related projects

These are the standards and foundations that the editor builds on.

| Project | Why it matters |
|---|---|
| [eclipse-basyx/basyx-python-sdk](https://github.com/eclipse-basyx/basyx-python-sdk) | The Python SDK that holds the metamodel classes and reads and writes AASX, JSON and XML. The editor installs a fork, [`rwth-iat/basyx-python-sdk`](https://github.com/rwth-iat/basyx-python-sdk), pinned to a commit in `pyproject.toml`. |
| [admin-shell-io/aas-specs-metamodel](https://github.com/admin-shell-io/aas-specs-metamodel) | The specification of the metamodel, with the constraints that the editor validates. |
| [admin-shell-io/aas-specs-measurement-units](https://github.com/admin-shell-io/aas-specs-measurement-units) | The specification of how measurement units are described in the AAS. |

## Contact

Write to [contato@ifonso.com.br](mailto:contato@ifonso.com.br), or open an issue at [github.com/ifonso/AAS-Workingbench](https://github.com/ifonso/AAS-Workingbench/issues).

## Contributing

Issues and pull requests are welcome at [github.com/ifonso/AAS-Workingbench](https://github.com/ifonso/AAS-Workingbench/issues).
Start with [CONTRIBUTING.md](CONTRIBUTING.md), which points to the guides in [`docs/contributing/`](docs/contributing/development.md).

## License and notices

AAS Workingbench is licensed under the GNU General Public License v3.0. See [LICENSE](LICENSE).
Parts of the code descend from AAS Manager, copyright Igor Garmaev and contributors, which is licensed under the same terms.
[NOTICE](NOTICE) lists the third-party material that the repository contains or installs, with the license it names for each.

The Asset Administration Shell, its specifications and submodel templates, and the global dictionaries such as ECLASS and the IEC Common Data Dictionary belong to their owners.
This project is not affiliated with or endorsed by them.
The software includes no dictionary content, and grants no rights over any.
You are responsible for the licenses of the dictionaries and data that you load.
