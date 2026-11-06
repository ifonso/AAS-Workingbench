# Branching guide

## Long-lived branches

| Branch | Purpose | Rules |
|---|---|---|
| `main` | Released code. Each push here creates a release. | Only accepts merges from `development`, and urgent fixes. |
| `development` | Integration of finished work, and the next release. | Default target for pull requests. Must always work. |

## Short-lived branches

Create a branch for each change, from `development`.
Name it `<type>/<short-description>`, using a type from the [Conventional Commits guide](conventional-commits.md):

| Prefix | Use it for | Example |
|---|---|---|
| `feat/` | New behavior | `feat/navigation-history` |
| `fix/` | Bug fixes | `fix/aasx-save-supplementary-files` |
| `refactor/` | Code changes with no change in behavior | `refactor/extract-package-domain` |
| `docs/` | Documentation | `docs/testing-guide` |
| `test/` | Tests | `test/aasx-round-trip` |
| `build/` | Dependencies and packaging | `build/bump-basyx-sdk` |
| `ci/` | GitHub Actions workflows | `ci/add-windows-tests` |
| `perf/` | Performance | `perf/lazy-tree-loading` |
| `style/` | Formatting only | `style/apply-ruff-format` |
| `chore/` | Other maintenance | `chore/phase-0-foundation` |

Use lowercase words separated by hyphens.
Parity work may include the feature ID: `feat/f-nav-02-navigation-history`.

## Workflow

```sh
git switch development
git pull
git switch -c feat/navigation-history
# work and commit
make check
git push -u origin feat/navigation-history
```

1. Open a pull request into `development`, with a Conventional Commit as its title.
2. Get it reviewed, and make sure CI passes.
3. Merge it, and delete the branch.

## Releases

1. Set the version with `uv version <version>`, and move the `Unreleased` entries in [CHANGELOG.md](../../CHANGELOG.md) under that version.
2. Open a pull request from `development` into `main`.
3. Merging it creates the release and builds the executables. Make sure the version is new, because the release workflow creates a tag from it.

## Urgent fixes

Branch from `main` using `fix/...`, and open the pull request into `main`.
Then merge `main` back into `development`, so that the fix is not lost.
