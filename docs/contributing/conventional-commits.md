# Conventional Commits guide

Every commit on `main` and `development` follows [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/).
History stays searchable, and the type of each commit tells us which version to release next.

## Format

```text
<type>(<optional scope>)!: <description>

<optional body>

<optional footers>
```

- Write the description in English, in the imperative mood: `add`, not `added`.
- Start the description in lowercase and do not end it with a period.
- Keep the first line to 72 characters or fewer.
- Wrap the body at 72 characters, and use it to explain what changed and why.
- Keep each commit to one logical change.

## Types

| Type | Use it for | Version bump |
|---|---|---|
| `feat` | New user-visible behavior | Minor |
| `fix` | A bug fix | Patch |
| `docs` | Documentation only | None |
| `style` | Formatting with no change in behavior | None |
| `refactor` | Code change with no change in behavior | None |
| `perf` | A performance improvement | Patch |
| `test` | Adding or correcting tests | None |
| `build` | Dependencies, packaging, `pyproject.toml`, `uv.lock` | None |
| `ci` | GitHub Actions workflows | None |
| `chore` | Maintenance that fits nothing above | None |
| `revert` | Reverting an earlier commit | Depends on the reverted commit |

## Scopes

A scope is optional. When you use one, pick the area that changed:

`package`, `models`, `treeviews`, `widgets`, `settings`, `tools`, `import`, `handover`, `themes`, `deps`, `tests`, `docs`.

Add a new scope when a new area appears, and list it here in the same commit.

## Breaking changes

Mark a breaking change with `!` after the type or scope, and describe it in a `BREAKING CHANGE:` footer.
A breaking change bumps the major version.
While the version is `0.y.z`, it bumps the minor version instead.

```text
feat(package)!: read metamodel 3.1 files only

BREAKING CHANGE: files written with metamodel 2.x no longer open.
```

## Traceability

Commits that implement package-explorer parity name the feature ID in a footer, so the [parity tracker](../software/feature-parity.md) can link to them:

```text
feat(treeviews): add back and forward navigation history

Refs: F-NAV-02
```

Link issues in the same way: `Refs: #123` or `Closes: #123`.

## Examples

```text
fix(package): keep supplementary files when saving as JSON
build(deps): pin basyx-python-sdk to a commit
test(package): cover the AASX round trip
docs: add the testing guide
style: apply ruff format
```

These do not follow the convention:

```text
Fixed bug                       # no type, past tense, too vague
feat: Add history.              # capitalized, ends with a period
fix: save and also new themes   # two unrelated changes
```

## Pull requests

Use a Conventional Commit as the pull request title, because it becomes the commit subject when the pull request is squashed.

## Changelog

Commits record how the code changed, and [CHANGELOG.md](../../CHANGELOG.md) records what users will notice.
A `feat`, a `fix`, or a breaking change also needs an entry under `Unreleased` in the same pull request.
