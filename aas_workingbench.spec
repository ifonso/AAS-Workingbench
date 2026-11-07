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
