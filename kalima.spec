# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for Kalima — Arabic EPUB Dictionary Reader
# Build with:  pyinstaller kalima.spec

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

a = Analysis(
    ['guiapp.py'],
    pathex=[],
    binaries=[],
    datas=[
        *collect_data_files('ebooklib'),
        *collect_data_files('bs4'),
        ('assets', 'assets'),   # toolbar SVG icons and app icon
    ],
    hiddenimports=[
        # PyQt6 WebEngine internals
        'PyQt6.QtWebEngineCore',
        'PyQt6.QtWebEngineWidgets',
        'PyQt6.QtWebChannel',
        'PyQt6.QtNetwork',
        # macOS dictionary
        'DictionaryServices',
        # EPUB / HTML parsing
        'ebooklib',
        'ebooklib.epub',
        'ebooklib.utils',
        'bs4',
        'lxml',
        'lxml.etree',
        'lxml._elementpath',
        'lxml.html',
        'html.parser',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Kalima',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,          # UPX can break Qt binaries on macOS
    console=False,      # no terminal window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/app-icon/icon.icns',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='Kalima',
)

app = BUNDLE(
    coll,
    name='Kalima.app',
    icon='assets/app-icon/icon.icns',
    bundle_identifier='com.localtools.kalima',
    info_plist={
        'CFBundleName': 'Kalima',
        'CFBundleDisplayName': 'Kalima',
        'CFBundleShortVersionString': '1.0.0',
        'CFBundleVersion': '1.0.0',
        'NSPrincipalClass': 'NSApplication',
        'NSHighResolutionCapable': True,
        'NSRequiresAquaSystemAppearance': False,  # allows dark mode
        'NSAppleScriptEnabled': False,
        # Allow the app to open .epub files via Finder
        'CFBundleDocumentTypes': [
            {
                'CFBundleTypeName': 'EPUB Document',
                'CFBundleTypeExtensions': ['epub'],
                'CFBundleTypeRole': 'Viewer',
                'LSHandlerRank': 'Alternate',
            }
        ],
    },
)
