# ADR 0036: The editor has one package open at a time

**Status:** Accepted

## Context

The editor could hold several packages at once, each a root of the package tree, with Save All and Close All, and copies of submodels and concept descriptions from one to another. The owner decided that several open packages cause more problems than they solve for the people who use the editor: which package an action, a save or an undo is about is not always clear, and the tree has a level for the package above every row.

The UI proposals (`design/ui-proposals.md`, 2.2) ask for the groups of the tree (`Submodels`, `Asset Administration Shells`) to be the titles at its top, with no level for the package above them.

## Decision

- **One package at a time.** Opening a package, creating one, opening a recent file, or dropping files closes the package that is open first, through `PackTreeView.makeRoomForPackage`. A package with changes asks whether to save them, discard them, or cancel, and Cancel, or a save that did not happen, leaves the open package as it was and opens nothing. A file is read before the open package closes, so a file that cannot be read leaves the work as it was.
- **A drop opens one file:** the first that has the extension of a package (`application.save.first_package_file`), or else the first file, which says why it does not open.
- **The tree starts at the groups.** `PackTreeView.fitRoot` makes the row of the only package the root of the view, so the groups are the top rows. The row of the package is still in the model, and code finds it as before (`packageIndex`).
- **The menu of the package is in the header of the pane.** The "…" button makes the package the current row and shows its context menu, which has Save, Save As, Close, the load report, the package thumbnail, and the files.
- **Save All and Close All are not offered.** The actions stay, for the code that closes what is open, and are hidden from the menus.
- **A session of an earlier release** that left several packages open restores the first. The recovery files of the others are kept, so no unsaved work is deleted.
- The model of the tree can still hold several packages. Tests build such trees, and the rule is kept by the paths that open and create a package.

## Consequences

- Copying between packages works through the clipboard and a second package opened after the first, but the files of a copied element come along only while the package it came from is open, which it no longer is.
- A person who compared two packages side by side opens a second window of the editor.
- The tree is one level less deep, and the name of the package is in the header of the pane.

## Alternatives considered

- **Hide the row of the package only while one is open.** It keeps several packages, which is what the owner wants to stop, and the tree changes its shape when a second package opens.
- **Refuse to open a second package.** It makes the person close the first by hand, while asking about its changes does the same in one step.
