# To be fixed: opening and saving files

Found on branch `fix/file-dialog-freeze` while looking into the file dialog that
freezes on Ubuntu. Each entry says what was seen, where, and its state.

## Reported symptom

On Ubuntu (tested with the AppImage; Windows works), Open and Save As show the file
dialog behind the main window, or not at all, until the user switches to another
application. The dialog then does not respond, and the process has to be killed.

## Fixed on this branch

1. **The dialog of the desktop on Linux.** With the `xdgdesktopportal` theme, the
   dialog is another process: in a probe (Qt 6.12.0, Hyprland, Wayland and xcb)
   `QFileDialog.reject()` did not close it, `exec()` returned only when the
   application quit, and it showed with the theme of the portal, away from the
   window. With `gtk3`, the dialog is the GTK 3 that the AppImage carries.
   Every path dialog now goes through `ui/path_dialogs.py`, which uses the dialog
   of Qt on Linux outside a Flatpak or a Snap (ADR 0032).
2. **GTK 3 of the build machine in the AppImage.** PyInstaller copied `libqgtk3.so`
   with GTK 3, GDK, Pango, Cairo, ATK and more, with no schemas, loaders or GIO
   modules. The spec now leaves them out on Linux (`GTK_ONLY_LIBRARIES`).
3. **About 20 dialog calls, each its own.** All use the helper, and a test fails
   if a module calls `QFileDialog.get...` itself.
4. **Save As, New, Open, and Save media asked again in a loop.** A refused save
   opened the dialog again with each answer. They ask once now. Save media also
   built a wrong path on its second round.
5. **Save As returned `None`.** `savePackAsWithDialog` and
   `savePackInTypeWithDialog` return whether the package was written.
6. **Message boxes without a parent.** The question in `openPack`, the questions
   of `closeFileWithDialog` and `closeAllFilesWithDialog`, and the box of
   `utils/exceptionhook.py` belong to the window.
7. **The log in the current folder.** It goes to the data folder of the user
   (`infrastructure/app_log.py`), and to the standard error stream if that folder
   cannot be written.
8. **Save media did not catch `OSError`.** A folder without permission reached
   the box for an unexpected error.

## Still to do

- **Check the AppImage on a clean Ubuntu**, in a Wayland and in an Xorg session:
  Open, Save As, New, Save media, and the dialogs of the tools. Nothing here was
  tried on Ubuntu itself.
- **GLib is still in the bundle.** `libglib-2.0`, `libgobject-2.0`, `libgio-2.0`
  and `libgthread-2.0` stay, because `libQt6Core`, `libQt6Gui` and the xcb plugin
  link to them. They can still mix with the GIO modules of the system. Leave them
  out only after a test on a clean system shows that the system copies work.
- **No test for the message box parents or the media loop.** They are in legacy
  modules that no test builds yet.
