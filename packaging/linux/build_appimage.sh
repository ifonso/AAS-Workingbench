#!/usr/bin/env bash
# Builds the AppImage of AAS Workingbench from the PyInstaller output.
#
# Run it on Linux (x86_64), from anywhere, after the PyInstaller build:
#
#   uv run --group build pyinstaller --noconfirm aas_workingbench.spec
#   bash packaging/linux/build_appimage.sh
#
# Options, as environment variables:
#   DIST_DIR     The PyInstaller output folder. Default: dist/AAS_Workingbench.
#   OUTPUT_DIR   Where to write the AppImage. Default: dist.
#   WORK_DIR     Scratch folder for the AppDir and the tool. Default: build/appimage.
#   VERSION      The version in the file name. Default: read from pyproject.toml.
#   APPIMAGETOOL Path of an appimagetool you already have. Default: download the
#                pinned release below and check its checksum.
#
# The result is OUTPUT_DIR/AAS_Workingbench-<version>-x86_64.AppImage.
set -euo pipefail

# The pinned release of appimagetool, and the SHA-256 of its x86_64 AppImage.
# To move to a new release, download it, read the checksum, and change both.
APPIMAGETOOL_VERSION="1.9.1"
APPIMAGETOOL_SHA256="ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0"
APPIMAGETOOL_URL="https://github.com/AppImage/appimagetool/releases/download/${APPIMAGETOOL_VERSION}/appimagetool-x86_64.AppImage"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PACKAGING_DIR="${REPO_ROOT}/packaging/linux"
DIST_DIR="${DIST_DIR:-${REPO_ROOT}/dist/AAS_Workingbench}"
OUTPUT_DIR="${OUTPUT_DIR:-${REPO_ROOT}/dist}"
WORK_DIR="${WORK_DIR:-${REPO_ROOT}/build/appimage}"

fail() {
    echo "error: $*" >&2
    exit 1
}

[ "$(uname -s)" = "Linux" ] || fail "an AppImage can only be built on Linux."
[ "$(uname -m)" = "x86_64" ] || fail "only x86_64 is supported, this is $(uname -m)."
[ -x "${DIST_DIR}/AAS_Workingbench" ] ||
    fail "${DIST_DIR}/AAS_Workingbench not found. Run PyInstaller first."

if [ -z "${VERSION:-}" ]; then
    VERSION="$(sed -n 's/^version = "\(.*\)"$/\1/p' "${REPO_ROOT}/pyproject.toml" | head -n 1 | tr -d '\r')"
fi
[ -n "${VERSION}" ] || fail "cannot read the version from pyproject.toml."

APPDIR="${WORK_DIR}/AppDir"
OUTPUT_FILE="${OUTPUT_DIR}/AAS_Workingbench-${VERSION}-x86_64.AppImage"

echo "Building ${OUTPUT_FILE}"
rm -rf "${APPDIR}"
mkdir -p "${APPDIR}/usr/lib" "${APPDIR}/usr/share/applications" "${OUTPUT_DIR}"

# The program: the whole PyInstaller folder, with its _internal folder.
cp -a "${DIST_DIR}" "${APPDIR}/usr/lib/AAS_Workingbench"

# AppRun starts it.
install -m 755 "${PACKAGING_DIR}/AppRun" "${APPDIR}/AppRun"

# The menu entry, at the root of the AppDir as appimagetool wants it, and where
# a desktop looks for it once the AppImage is integrated.
install -m 644 "${PACKAGING_DIR}/aas_workingbench.desktop" "${APPDIR}/aas_workingbench.desktop"
install -m 644 "${PACKAGING_DIR}/aas_workingbench.desktop" \
    "${APPDIR}/usr/share/applications/aas_workingbench.desktop"

# The icon: the logo on a square, 512 pixels. The name matches `Icon=` of the
# .desktop file, and `.DirIcon` is the one that file managers show.
ICON_DIR="${APPDIR}/usr/share/icons/hicolor/512x512/apps"
mkdir -p "${ICON_DIR}"
(cd "${REPO_ROOT}" && uv run python packaging/linux/make_icon.py \
    src/aas_workingbench/icons/logo.png "${ICON_DIR}/aas_workingbench.png" 512)
cp "${ICON_DIR}/aas_workingbench.png" "${APPDIR}/aas_workingbench.png"
cp "${ICON_DIR}/aas_workingbench.png" "${APPDIR}/.DirIcon"

# appimagetool.
if [ -z "${APPIMAGETOOL:-}" ]; then
    APPIMAGETOOL="${WORK_DIR}/appimagetool-${APPIMAGETOOL_VERSION}-x86_64.AppImage"
    if [ ! -f "${APPIMAGETOOL}" ]; then
        echo "Downloading appimagetool ${APPIMAGETOOL_VERSION}"
        curl --fail --location --silent --show-error --output "${APPIMAGETOOL}" "${APPIMAGETOOL_URL}"
    fi
    echo "${APPIMAGETOOL_SHA256}  ${APPIMAGETOOL}" | sha256sum --check --status ||
        fail "the checksum of appimagetool does not match the pinned one."
    chmod +x "${APPIMAGETOOL}"
fi

# appimagetool is an AppImage itself and needs FUSE to run. This makes it unpack
# itself and run from there, which also works where FUSE is missing (CI, containers).
export APPIMAGE_EXTRACT_AND_RUN=1
rm -f "${OUTPUT_FILE}"
ARCH=x86_64 "${APPIMAGETOOL}" "${APPDIR}" "${OUTPUT_FILE}"

echo "Done: ${OUTPUT_FILE} ($(du -h "${OUTPUT_FILE}" | cut -f1))"
