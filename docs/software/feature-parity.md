# Feature parity with AASX Package Explorer

The goal of this project is to reach the functionality of [Eclipse AASX Package Explorer](https://github.com/eclipse-aaspe/package-explorer) in a cross-platform Python application.

## Reference material

The target is specified in a set of 95 feature documents, in a sibling checkout:

```text
../package-explorer/design-docs/
```

| Document | Use it to |
|---|---|
| `README.md` | Understand the scope and how far to trust the documents |
| `FEATURE-INDEX.md` | Browse features with priority and platform risk |
| `MENU-MAP.md` | Go from a menu item to its feature document |
| `SPEC-MATRIX.md` | See which features depend on which spec |
| `KNOWN-DEFECTS.md` | See what not to copy from the original |

These documents are not committed to any repository yet, so they exist only on the machine where they were written.
Feature IDs such as `F-NAV-02` refer to them.

## Roadmap

Phases 1 to 5 follow the build order the design documents suggest.
The current focus is the editing scope of phases 1 and 2, as described in the [V1 editor plan](../planning/v1-editor-plan.md).

| Phase | Goal | Features |
|---|---|---|
| 0 | Engineering foundation | Tooling, tests, documentation (this phase) |
| 1 | Open, view, and save a package | F-PKG-01, F-PKG-02, F-REP-01, F-SHL-01, F-SHL-02, F-SHL-03, F-NAV-01, F-NAV-05, F-NAV-06 |
| 2 | Edit every entity | F-EDT-01 to F-EDT-06, F-EDT-08 |
| 3 | Daily-use parity | Remaining P1: validation, repositories, API, search, history, presets, files, references, core exchange formats |
| 4 | Template ecosystem | SMT and SAMM, generic forms, nameplate, documents, technical data, contact, BOM, AID |
| 5 | Specialist and legacy | P2, then a decision on each P3 |

### Decisions needed before phase 1

1. **Metamodel target:** decided: V3.1.x. See [ADR 0005](adr/0005-metamodel-and-validation.md).
2. **F-SHL-03 (AnyUI):** the original uses a declarative UI so desktop and web can share panels. Decide whether to adopt something similar, or build directly on Qt.
3. **F-CMP-03 (web edition):** decide whether it is in scope. The layered architecture keeps this possible, but it is a large effort.

## Initial status of P0 and P1 features

**How reliable this is:** this first assessment comes from reading menus and searching the code on 2026-11-06.
The features were not run against their acceptance criteria.
Treat `Partial` as "something exists", and confirm the details when starting each feature.

| Status | Meaning |
|---|---|
| Present | Main capability found in the code |
| Partial | Part of the capability found |
| Not found | No sign of it in the code |
| Decision | Depends on a decision above |

### Shell and package

| ID | Feature | Priority | Status | Evidence or gap |
|---|---|---|---|---|
| F-SHL-01 | Main window and layout | P0 | Partial | Tree and tabs in `editorApp.py` |
| F-SHL-02 | Commands and menus | P0 | Partial | `QAction` menus, with no central command registry |
| F-SHL-03 | Declarative UI | P0 | Decision | Not found |
| F-SHL-04 | Options and configuration | P1 | Partial | Settings dialog |
| F-SHL-05 | Log and status | P1 | Partial | `log.log` and status tips, with no log panel |
| F-PKG-01 | Package lifecycle | P0 | Present | New, open, recent, save, save as, close, crash recovery |
| F-PKG-02 | AASX format | P0 | Present | Through BaSyx adapters, in `package.py` |
| F-PKG-03 | Auxiliary package | P1 | Not found | |
| F-PKG-04 | Check, validate, and fix | P1 | Partial | Validation through `aas-test-engines`, with no fixes |
| F-PKG-05 | Finalize and verify | P1 | Not found | |

### Repositories and API

| ID | Feature | Priority | Status | Evidence or gap |
|---|---|---|---|---|
| F-REP-01 | Package containers | P0 | Not found | Only local files. "Open from server" is commented out. |
| F-REP-02 | File repositories and recent list | P1 | Partial | Recent files only |
| F-REP-03 | Repository and Registry API | P1 | Not found | No HTTP client in the code |
| F-REP-04 | Upload to server | P1 | Not found | |
| F-REP-07 | Authentication and security | P1 | Not found | |

### Navigation

| ID | Feature | Priority | Status | Evidence or gap |
|---|---|---|---|---|
| F-NAV-01 | Entity tree | P0 | Partial | `treeview_pack.py` |
| F-NAV-02 | History and editing locations | P1 | Partial | Back and forward in tabs |
| F-NAV-03 | Find and replace | P1 | Partial | Search with regex and case filters, with no replace found |
| F-NAV-04 | Asset panel | P1 | Not found | |
| F-NAV-05 | View modes | P0 | Not found | Always editable, with no separate modes |
| F-NAV-06 | Right panel and content preview | P0 | Partial | Media preview in `widgets/tab.py` |

### Editors

| ID | Feature | Priority | Status | Evidence or gap |
|---|---|---|---|---|
| F-EDT-01 | Editor framework | P0 | Partial | Generic editors generated from type hints |
| F-EDT-02 | Environment, AAS, AssetInformation | P0 | Partial | Through the generic editors. New shells get a `urn:uuid:` id, an id that another object has is refused, and Rename id updates the references to the shell. Deleting a shell leaves its submodels. |
| F-EDT-03 | Submodel and SubmodelRef | P0 | Partial | Through the generic editors. Rename id updates the references, Delete shows the usages and offers to remove them, and Fix References repairs an idShort in the first key and wrong key types. Remove attributes in bulk and the SMT actions are not done. |
| F-EDT-04 | SubmodelElements | P0 | Partial | Through the generic editors |
| F-EDT-05 | ConceptDescription and IEC 61360 | P0 | Partial | Through the generic editors. Rename id updates the semantic ids, and Sync idShort fills the short name. The SDK allows no empty preferred name. |
| F-EDT-06 | Common attribute modules | P0 | Partial | Through the generic editors. The id is checked for duplicates, a new id is generated, and an invalid idShort gets a suggestion (Fix). Hints are not done. |
| F-EDT-07 | Qualifiers and Extensions | P1 | Partial | Through the generic editors |
| F-EDT-08 | Copy, paste, and reorder | P0 | Partial | Copy, cut, paste, and undo, with one history for each package. Cut removes the source from every kind of parent. Delete asks first when it is destructive, shows the usages, and is one undo step for a bulk delete. Reorder not confirmed. |
| F-EDT-09 | Multi-element editing | P1 | Partial | Multi-select with bulk cut, copy, and delete |
| F-EDT-10 | Supplementary files | P1 | Partial | `StoredFile` in `package.py` |
| F-EDT-11 | References, semantics, lookups | P1 | Partial | Reference links open in tabs, with no lookup. The index finds dangling references, but nothing lists them yet. |

### Templates, exchange, plugins, and companions

| ID | Feature | Priority | Status | Evidence or gap |
|---|---|---|---|---|
| F-SMT-01 | Submodel from known definitions | P1 | Partial | 43 groups of IDTA templates as data files |
| F-SMT-07 | Predefined concepts library | P1 | Partial | Same template files. This design already avoids a defect of the original, which compiles them into the code. |
| F-EXC-03 | Submodel via JSON and HTTP | P1 | Partial | "Add as JSON" and "Edit as JSON", with no HTTP |
| F-PLG-01 | Plugin framework | P1 | Not found | |
| F-PLG-02 | Digital Nameplate viewer | P1 | Not found | |
| F-PLG-04 | Document Shelf | P1 | Not found | The Handover tool generates documents, but does not browse them. |
| F-PLG-05 | Technical Data viewer | P1 | Not found | |
| F-PLG-09 | Generic Forms | P1 | Not found | |
| F-PLG-10 | Export Table | P1 | Not found | |
| F-CMP-03 | Web edition | P1 | Decision | Not found |

### Where this application is already ahead

These have no direct equivalent in the P0 and P1 list, so keep them while working toward parity:

- Crash recovery
- Undo and redo, with one history for each package that restores the position of what was deleted
- References that stay right: a rename updates them with a preview, and a delete shows what refers to the object
- Excel import with mappings
- LLM-assisted Handover Documentation
- Validation with AAS Test Engines
- Theme selection and split tabs

## Working on a feature

1. Read its feature document, and check `KNOWN-DEFECTS.md`, so a defect of the original does not get copied.
2. Update its status in this file.
3. Turn its acceptance criteria into tests, as the [testing guide](../contributing/testing-guide.md) describes.
4. Follow the [target architecture](architecture.md#target-structure).
5. Mention the ID in the commit footer: `Refs: F-NAV-02`.
