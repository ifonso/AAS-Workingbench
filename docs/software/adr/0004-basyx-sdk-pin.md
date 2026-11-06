# ADR 0004: Pin the BaSyx SDK fork to a commit

**Status:** Accepted

## Context

The project depended on the `aas_manager/v301` branch of `rwth-iat/basyx-python-sdk`.
That branch no longer exists, so the project could not be installed at all.
The same could happen to any branch we depend on by name.

The closest replacement is `aas_manager/develop`.
It implements metamodel V3.1 and requires Python 3.11.
AASX Package Explorer, our parity target, also implements V3.1.

## Decision

Depend on `aas_manager/develop`, pinned to commit `412a53f` in `pyproject.toml`.
Raise `requires-python` to `>=3.11`.

## Evidence

We could not test against the deleted branch.
We used commit `b9ef3a4`, from before the SDK's V3.1 update, as the closest available reference:

- All small and medium tests pass with `412a53f`.
- Opening `tests/data/TestPackage.aasx` logs the same kinds of tracebacks with both commits, and fewer with `412a53f` (366, compared with 425).

These checks do not show that every editor works correctly with V3.1.

## Consequences

- Installs no longer depend on a branch that can move or disappear. Upgrading the SDK is a deliberate one-line change.
- The application still reports `Metamodel V3.0` (`AAS_METAMODEL_VERSION` in `app_settings.py`), and `aas-test-engines` 1.0.3 validates against V3.0.
- Phase 1 must settle the metamodel target, including whether to go on to V3.2, and align these two items with that decision.
- `SetObjectStore` is deprecated in this SDK version, and `package.py` should move to `SetIdentifiableStore`.
