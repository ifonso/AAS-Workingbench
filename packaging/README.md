# Packaging

How to build the release files of AAS Workingbench by hand.
The release workflow (`.github/workflows/release.yaml`) and the manual build (`.github/workflows/manual_build.yaml`) run the same steps, through `.github/workflows/build.yaml`.

| File | Built on | Name |
|---|---|---|
| Windows zip | Windows | `AAS_Workingbench-<version>-windows-x64.zip` |
| Linux AppImage | Linux, x86_64 | `AAS_Workingbench-<version>-x86_64.AppImage` |

`<version>` is the `version` of `pyproject.toml`.
Neither file is built for macOS.
A build is large (about 1.5 GB as a folder, because of PyTorch and the LLM libraries), and takes several minutes.

## The PyInstaller build

Both files start from the same build, which `aas_workingbench.spec` describes.
From the root of the repository:

```sh
uv sync --locked
uv run --locked --group build pyinstaller --noconfirm aas_workingbench.spec
```

The result is the folder `dist/AAS_Workingbench`, with the program `AAS_Workingbench` (`AAS_Workingbench.exe` on Windows) and its `_internal` folder.
`make build` runs the second command.
To keep the output outside the repository, add `--distpath <folder>/dist --workpath <folder>/build`.
The spec file bundles `pyproject.toml` (the program reads its version and contacts at run time), `LICENSE`, `NOTICE`, the font, the icons, the theme template, the presets, and the submodel templates.

## Windows zip

After the PyInstaller build, zip the folder `dist/AAS_Workingbench`, so that the zip holds that folder:

```sh
cd dist
7z a AAS_Workingbench-0.1.0-windows-x64.zip AAS_Workingbench
```

The user unzips it anywhere that can be written and starts `AAS_Workingbench\AAS_Workingbench.exe`.
The program writes `settings.ini` into its own folder, so do not unzip it below `Program Files`.

## Linux AppImage

Build on Linux, x86_64, with the libraries that Qt needs installed, because PyInstaller copies them from the machine into the build.
On Ubuntu, the list is in the step "Install system libraries" of `.github/workflows/build.yaml`.
After the PyInstaller build:

```sh
bash packaging/linux/build_appimage.sh
```

The script puts the PyInstaller folder into an `AppDir` (`build/appimage/AppDir`) with:

- `AppRun`, which starts the program, and turns the sandbox of QtWebEngine off only on a system that forbids user namespaces (see below),
- `aas_workingbench.desktop`, with the name, the categories `Development;Engineering;`, and the icon,
- the icon, `aas_workingbench.png`, made from `src/aas_workingbench/icons/logo.png` on a square of 512 pixels by `packaging/linux/make_icon.py`,

downloads `appimagetool` (a pinned release, whose SHA-256 the script checks), and writes `dist/AAS_Workingbench-<version>-x86_64.AppImage`.
The environment variables `DIST_DIR`, `OUTPUT_DIR`, `WORK_DIR`, `VERSION`, and `APPIMAGETOOL` change the folders, the version, and the tool; the top of the script lists them.

To run it, the user makes the file executable and starts it (`libfuse2` must be installed on the system, or the AppImage must be started with `--appimage-extract-and-run`):

```sh
chmod +x AAS_Workingbench-0.1.0-x86_64.AppImage
./AAS_Workingbench-0.1.0-x86_64.AppImage
./AAS_Workingbench-0.1.0-x86_64.AppImage path/to/package.aasx
```

### QtWebEngine in the AppImage

Only the handover documentation tool and the AAS test tool show a web page.
PyInstaller bundles `QtWebEngineProcess` and the Chromium resources with the PyQt6 libraries, and the AppImage keeps that layout.
Chromium sandboxes its processes with user namespaces, which Ubuntu 23.10 and later restrict through AppArmor, and Debian can switch off.
On such a system Chromium refuses to start, so `AppRun` sets `QTWEBENGINE_DISABLE_SANDBOX=1` when it reads one of those restrictions from `/proc/sys`.
Set `QTWEBENGINE_DISABLE_SANDBOX` to `0` or `1` before the start to decide yourself.

### Known limits

- **Settings.** The program writes `settings.ini` (and the `presets` folder of the user) next to its modules, as it does today. An AppImage is mounted read-only, so on Linux the settings of the window, the theme, and the columns are not kept between runs. The recent files and the crash recovery are kept, because they are in the data folder of the user. Moving `settings.ini` to the data folder of the user fixes it, and is not done yet.
- **Not tested on Linux yet.** The AppImage and the Linux job were written without a Linux machine to run them on.
