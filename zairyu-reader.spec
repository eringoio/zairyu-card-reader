# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for the local residence-card reader.

Build with:

    pyinstaller --clean --noconfirm zairyu-reader.spec

Produces `dist/zairyu-reader/zairyu-reader.exe`, a one-folder build. One-folder is chosen
over one-file because a one-file build re-extracts the whole bundle into %TEMP% on every
launch, which antivirus scanners repeatedly re-inspect.

Runtime resources are addressed through `reader/runtime_paths.py`, which resolves them under
`sys._MEIPASS` when frozen. Local settings never land inside this bundle; they go to
`%APPDATA%/ZairyuReader`.

Nothing under `tools/` is packaged: those are build-time developer utilities. The bundle
carries no script payload for an external interpreter, and the application never spawns one.
"""

from PyInstaller.utils.hooks import collect_dynamic_libs, collect_submodules


datas = [
    ("static", "static"),
    ("resources/ocr", "resources/ocr"),
    ("resources/moj/trust-anchors", "resources/moj/trust-anchors"),
]

hiddenimports = [
    # Imported lazily by the reader stack, so PyInstaller cannot see them statically.
    "smartcard",
    "smartcard.System",
    "smartcard.CardConnection",
    "smartcard.Exceptions",
    "Crypto.Cipher.AES",
    "Crypto.Hash.CMAC",
    "PIL.Image",
    "PIL.ImageFilter",
    "PIL.ImageOps",
    "onnxruntime",
    "cryptography.hazmat.primitives.asymmetric.ec",
    "cryptography.hazmat.primitives.asymmetric.rsa",
    "cryptography.hazmat.primitives.asymmetric.padding",
    "cryptography.hazmat.primitives.asymmetric.utils",
    "cryptography.x509",
    "app",
    "reader",
]
# uvicorn resolves its protocol/loop implementations by name at runtime.
hiddenimports += collect_submodules("uvicorn")
hiddenimports += collect_submodules("webview")
hiddenimports += collect_submodules("pyasn1")
hiddenimports += collect_submodules("pyasn1_modules")
# ONNX Runtime loads its CPU provider and supporting DLLs dynamically.
binaries = collect_dynamic_libs("onnxruntime")


analysis = Analysis(
    ["launch_reader.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "tkinter"],
    noarchive=False,
)

pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="zairyu-reader",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=True,
    icon="assets/zairyu-reader.ico",
    version="windows-version-info.txt",
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="zairyu-reader",
)
