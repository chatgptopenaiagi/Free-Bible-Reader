# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[('workbench', 'workbench'), ('ui-core', 'ui-core'), ('data', 'data'), ('parser', 'parser'), ('runtime', 'runtime'), ('licenses', 'licenses'), ('engines/visual/component.js', 'engines/visual'), ('engines/visual/component.css', 'engines/visual')],
    hiddenimports=['engines.visual.engine', 'engines.visual.layout', 'engines.aggregate.engine', 'engines.phrase.engine'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='FreeBibleReader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets/brand.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='FreeBibleReader',
)
