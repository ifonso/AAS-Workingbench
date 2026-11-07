# ADR 0002: Layered architecture, adopted incrementally

**Status:** Accepted

## Context

Parity with AASX Package Explorer adds repository and registry clients, validation, import and export formats, and plugins.
Today, widgets, tree views, and models mix UI with file handling and AAS logic.
Importing `aas_workingbench.package` also loads `app_settings`, which creates Qt objects at import time.
As a result, AAS logic cannot run or be tested without a `QApplication`.

## Decision

New features follow the layers in the [architecture guide](../architecture.md): `ui` depends on `application`, which depends on `domain`, and `infrastructure` implements the interfaces `application` needs.
The core rule is that `domain` and `application` never import PyQt.

We apply the [strangler fig pattern](https://martinfowler.com/bliki/StranglerFigApplication.html): new code goes in the new packages, and legacy code moves when a feature needs to change it.
We will not rewrite the application in one pass.

## Consequences

- New logic can have small tests and can be reused by a future CLI or web front end.
- Legacy and layered code will coexist for a long time, so contributors need to know which rules apply where.
- The first feature to use each layer creates its package, along with an automated check of the import rule. Phase 0 creates no empty packages.
