# -*- mode: python ; coding: utf-8 -*-


block_cipher = None


a = Analysis(['src/aas_editor/__main__.py'],
             pathex=['src'],
             binaries=[],
             datas=[
                ('LICENSE', '.'),
                ('NOTICE', '.'),
                ('pyproject.toml', '.'),
                ('src/aas_editor/settings/settings.ini', 'aas_editor/settings'),
                ('src/aas_editor/custom_column_lists.json', 'aas_editor'),
                # The folder holds the logos and icons/tabler with its LICENSE.
                ('src/aas_editor/icons', 'aas_editor/icons'),
                # Inter, with OFL.txt, which the license asks to travel with it.
                ('src/aas_editor/fonts', 'aas_editor/fonts'),
                ('src/aas_editor/presets', 'aas_editor/presets'),
                ('src/aas_editor/ui/theme/app.qss.template', 'aas_editor/ui/theme'),
                ('src/aas_editor/submodel_templates', 'aas_editor/submodel_templates'),
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
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)

exe = EXE(pyz,
          a.scripts,
          [],
          exclude_binaries=True,
          name='AAS_Manager',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          console=False,
          disable_windowed_traceback=False,
          target_arch=None,
          codesign_identity=None,
          entitlements_file=None,
          icon='src/aas_editor/icons/logo.ico' )
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               upx_exclude=[],
               name='AAS_Manager')
