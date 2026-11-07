# ADR 0005: Target metamodel V3.1.x, with validation built on BaSyx

**Status:** Accepted

## Context

Different parts of the project disagreed about the metamodel:

| Part | Version |
|---|---|
| BaSyx SDK at the pinned commit | V3.1.2 |
| Application title | V3.0 |
| `aas-test-engines` 1.0.3, the latest release | V3.0 only |
| AASX Package Explorer | V3.1 |
| Local copy of the specifications | V3.2 |

The SDK does not implement V3.2 additions such as `AssetKind.Batch` and `createdAt`.

The editor also has no validation before saving, and the SDK enforces only part of the constraints when values are set.
For example, it does not raise errors for AASd-006, 007, 012, 013, 077, 119, 129, 133, or 134, or for invalid BCP47 language tags.

## Decision

- Target metamodel V3.1.x for v1, and label the application accordingly.
- Use the BaSyx SDK for all reading, writing, and mutation of AAS content.
- Write our own validation rules over BaSyx objects, in `aas_workingbench.domain.validation`.
- Keep `aas-test-engines` as an optional tool, clearly labeled V3.0. Do not use it to decide whether a V3.1 file is valid.

## Consequences

- Validation works offline and has small tests, and we maintain the rules ourselves. V3.2 can be a later decision that starts with an SDK upgrade.
- Where local specification text differs because it is V3.2, each rule should cite the constraint and be checked against V3.1 behavior in the SDK.
- Features that V3.2 adds are not available.
- If `aas-test-engines` releases V3.1 support, we can use it to cross-check our rules.
