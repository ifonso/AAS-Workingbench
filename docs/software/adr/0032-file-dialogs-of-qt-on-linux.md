# ADR 0032: The file dialogs on Linux are the dialogs of Qt

**Status:** Accepted

## Context

On Ubuntu the AppImage of 0.1.0 showed the dialog of Open and Save As behind the main window, or only after the user switched to another application. The dialog then did not respond, the main window was blocked as modal, and the process had to be killed. Windows had no such problem.

By default the static functions of `QFileDialog` show the dialog of the desktop, through the platform theme that Qt picks at start:

| Theme | Who draws the dialog | What went wrong |
|---|---|---|
| `gtk3` | GTK 3, loaded into the process | PyInstaller copied GTK 3, GDK, Pango, Cairo and ATK of the build machine into the AppImage, with none of their schemas, loaders or modules. They run with the GTK modules, settings and theme of the user's system. |
| `xdgdesktopportal` | `xdg-desktop-portal`, another process | The application cannot place, raise or close the dialog. In a probe (Qt 6.12, Wayland and xcb), `QFileDialog.reject()` did not close it, and `exec()` returned only when the application quit. It shows with the theme of the portal, away from the window. |

About 20 calls asked for a path, each with its own arguments.

## Decision

- Every dialog that asks for a path goes through `ui/path_dialogs.py`: `get_open_file_name`, `get_save_file_name` and `get_existing_directory`. A test fails if a module calls `QFileDialog.get...` itself.
- On Linux and the other Unix systems these pass `QFileDialog.Option.DontUseNativeDialog`, so the dialog is a widget of Qt: in the process, modal to its window, in the theme of the application.
- In a Flatpak or a Snap (`FLATPAK_ID` or `SNAP` in the environment) the dialog of the desktop stays, because the portal is the only way to reach the files of the user there.
- Windows and macOS keep the dialog of the system. On macOS this also keeps the access that the system gives to a file chosen in its own dialog.
- The Linux build leaves out `libqgtk3.so` and the GTK 3 stack that only it loads (`GTK_ONLY_LIBRARIES` in `aas_workingbench.spec`).

## Consequences

- On Linux the file dialog no longer looks like the one of the desktop: no bookmarks of GTK and no recent places of the desktop.
- The AppImage is smaller, and no longer mixes a GTK of the build machine with the one of the system.
- Without the GTK theme, Qt on GNOME uses its generic theme or the portal one for the palette and the fonts. The application sets its own theme and font, so this changes nothing that it shows.
- To go back, `uses_native_dialog` decides in one place, and the list in the spec is removed.

## Alternatives considered

- **Pick the `gtk3` theme in `AppRun`.** The GTK of the bundle is the one that may be at fault, and a system without GTK 3 falls back to the portal.
- **Leave GTK out of the bundle and use the one of the system.** It keeps the desktop dialog, but it depends on the GTK of each distribution matching the plugin that Qt was built against, and it still leaves the portal on systems that pick it.
