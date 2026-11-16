# -*- mode: python ; coding: utf-8 -*-


block_cipher = None


a = Analysis(['src/aas_workingbench/__main__.py'],
             pathex=['src'],
             binaries=[],
             datas=[
                ('LICENSE', '.'),
                ('NOTICE', '.'),
                ('pyproject.toml', '.'),
                ('src/aas_workingbench/settings/settings.ini', 'aas_workingbench/settings'),
                ('src/aas_workingbench/custom_column_lists.json', 'aas_workingbench'),
                # The folder holds the logos and icons/tabler with its LICENSE.
                ('src/aas_workingbench/icons', 'aas_workingbench/icons'),
                # Inter, with OFL.txt, which the license asks to travel with it.
                ('src/aas_workingbench/fonts', 'aas_workingbench/fonts'),
                ('src/aas_workingbench/presets', 'aas_workingbench/presets'),
                ('src/aas_workingbench/ui/theme/app.qss.template', 'aas_workingbench/ui/theme'),
                ('src/aas_workingbench/submodel_templates', 'aas_workingbench/submodel_templates'),
                ('aas_test_engines', 'aas_test_engines'),
             ],
             hiddenimports=[],
             hookspath=[],
             hooksconfig={},
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
# On Linux the build leaves out the GTK platform theme of Qt and the GTK 3 stack
# that only it loads. PyInstaller copied them from the build machine, and the
# file dialog of that GTK, mixed with the GTK modules and settings of the user's
# system, froze the window on Ubuntu. The file dialogs use the dialog of Qt on
# Linux (ui/path_dialogs.py, ADR 0032), so nothing else needs them.
import sys

GTK_ONLY_LIBRARIES = (
    "libqgtk3.so",
    "libgtk-3.so", "libgdk-3.so", "libgdk_pixbuf-2.0.so", "libglycin-2.so",
    "libatk-1.0.so", "libatk-bridge-2.0.so", "libatspi.so",
    "libpango-1.0.so", "libpangocairo-1.0.so", "libpangoft2-1.0.so",
    "libcairo.so", "libcairo-gobject.so", "libpixman-1.so",
    "libharfbuzz.so", "libfribidi.so", "libthai.so", "libdatrie.so",
    "libepoxy.so", "libcloudproviders.so", "libtinysparql-3.0.so",
    "libjson-glib-1.0.so",
)


def _is_gtk_only(name):
    base = name.replace("\\", "/").rsplit("/", 1)[-1]
    return any(base.startswith(prefix) for prefix in GTK_ONLY_LIBRARIES)


if sys.platform.startswith("linux"):
    a.binaries = [entry for entry in a.binaries if not _is_gtk_only(entry[0])]

pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)

exe = EXE(pyz,
          a.scripts,
          [],
          exclude_binaries=True,
          name='AAS_Workingbench',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          console=False,
          disable_windowed_traceback=False,
          target_arch=None,
          codesign_identity=None,
          entitlements_file=None,
          icon='src/aas_workingbench/icons/logo.ico' )
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               upx_exclude=[],
               name='AAS_Workingbench')
