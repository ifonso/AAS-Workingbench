# Architecture decision records

An architecture decision record (ADR) captures one significant decision, why we made it, and what it costs.
ADRs are immutable: to change a decision, add a new ADR that supersedes the old one.

| ADR | Decision | Status |
|---|---|---|
| [0001](0001-project-layout.md) | `src/` layout and tests organized by size | Accepted |
| [0002](0002-layered-architecture.md) | Layered architecture, adopted incrementally | Accepted |
| [0003](0003-python-style.md) | Google Python style, with legacy code exempted | Accepted |
| [0004](0004-basyx-sdk-pin.md) | Pin the BaSyx SDK fork to a commit | Accepted |
| [0005](0005-metamodel-and-validation.md) | Target metamodel V3.1.x, with validation built on BaSyx | Accepted |
| [0006](0006-command-stack-and-change-observer.md) | Edits as commands on AAS objects, reported to an observer | Accepted |

To add one, copy the structure of an existing ADR, use the next number, and add it to this table.
Write an ADR for a decision that is expensive to reverse: a new dependency with wide reach, a change to layer boundaries, or a metamodel target.
