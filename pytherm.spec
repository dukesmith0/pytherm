# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for PyTherm
# Build with:  py -m PyInstaller pytherm.spec
#
# Output: dist/PyTherm.exe (Windows), dist/PyTherm (macOS/Linux)
# User data (preferences, user materials, recent files) is written to a
# 'data/' folder next to the executable -- not inside the bundle.

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('data/materials.json', 'data'),
        ('templates',           'templates'),
        ('CHANGELOG.md',        '.'),
    ],
    hiddenimports=[
        'PyQt6.sip',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='PyTherm',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico',
)
