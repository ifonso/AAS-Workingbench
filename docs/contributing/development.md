# Development guide

## Prerequisites

| Tool | Notes |
|---|---|
| [uv](https://docs.astral.sh/uv/getting-started/installation/) | Manages Python, dependencies, and tools. You do not need to install Python yourself. |
| Git | On Windows, enable long paths, because some template paths exceed 260 characters. |
| GNU Make | Optional. Each target is a short `uv` command that you can also run directly. |

On Windows, you can install Make with `winget install ezwinports.make`.

On Linux, Qt also needs some system libraries.
For Debian and Ubuntu, run `sudo apt-get install libegl1 libopengl0`.

## Setup

On Windows, clone with long paths enabled:

```sh
git clone -c core.longpaths=true https://github.com/ifonso/AAS-Workingbench.git
```

If a clone fails with `Filename too long`, the index can end up empty, with every file listed as deleted.
To repair it, run this inside the clone:

```sh
git config core.longpaths true
git reset
git checkout -- .
```

Then install the environment and start the application:

```sh
make install
make run
```

## Daily commands

| Command | What it does |
|---|---|
| `make run` | Starts the application |
| `make format` | Formats the code |
| `make lint` | Runs the linter |
| `make lint-fix` | Runs the linter and applies safe fixes |
| `make typecheck` | Runs pyright |
| `make test` | Runs small and medium tests |
| `make coverage` | Runs those tests with a coverage report |
| `make check` | Runs everything CI runs. Do this before opening a pull request. |
| `make build` | Builds the stand-alone executable in `dist/` |

Run `make` with no target to list all of them.

## Dependencies

```sh
uv add <package>               # runtime dependency
uv add --group dev <package>   # development tool
uv lock --upgrade-package <package>
```

Commit `pyproject.toml` and `uv.lock` together.
CI installs with `--locked`, and fails if they disagree.
Do not use `pip`.

## Type checking debt

`make typecheck` prints many warnings from legacy code.
They do not fail the build, and each one shows existing debt.
Do not add warnings to code you change, and fix nearby ones when it is cheap.
Layered packages are `strict`, so anything there is an error.

## Settings file

`src/aas_editor/settings/settings.ini` is tracked by Git, and the application rewrites it whenever it runs.
Do not commit those changes.
To discard them, run:

```sh
git checkout -- src/aas_editor/settings/settings.ini
```

## Merging from upstream

This repository descends from [rwth-iat/aas_manager](https://github.com/rwth-iat/aas_manager).
Upstream code has a different layout and formatting, so expect conflicts.
Before resolving them, format the incoming files with `make format`.

## Related guides

- [Style guide](style-guide.md)
- [Testing guide](testing-guide.md)
- [Branching guide](branching.md)
- [Conventional Commits guide](conventional-commits.md)
