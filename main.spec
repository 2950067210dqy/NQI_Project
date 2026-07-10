# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


project_root = Path(SPECPATH).resolve() if "SPECPATH" in globals() else Path(__file__).resolve().parent


def add_tree(source_dir, target_dir, skip_parts=None, skip_suffixes=None):
    """Collect project data files while skipping build caches and runtime logs."""
    skip_parts = set(skip_parts or [])
    skip_suffixes = set(skip_suffixes or [])
    source_path = project_root / source_dir
    datas = []
    if not source_path.exists():
        return datas

    for file_path in source_path.rglob("*"):
        if not file_path.is_file():
            continue
        relative_path = file_path.relative_to(source_path)
        if "__pycache__" in relative_path.parts:
            continue
        if any(part in skip_parts for part in relative_path.parts):
            continue
        if file_path.suffix.lower() in skip_suffixes:
            continue
        datas.append((str(file_path), str(Path(target_dir) / relative_path.parent)))
    return datas


datas = []
datas += add_tree("config", "config", skip_suffixes={".pyc", ".pyo"})
datas += add_tree("resource", "resource", skip_suffixes={".pyc", ".pyo"})
datas += add_tree("ui", "ui", skip_suffixes={".pyc", ".pyo"})

# MainWindow_index.load_modules scans Module/*.py from the filesystem, so keep
# these module files available next to the packaged executable.
datas += add_tree(
    "Module",
    "Module",
    skip_parts={"__pycache__"},
    skip_suffixes={".pyc", ".pyo"},
)

icon_file = project_root / "window_icon.ico"
if icon_file.exists():
    datas.append((str(icon_file), "."))


hiddenimports = []
hiddenimports += collect_submodules("Module")


a = Analysis(
    [str(project_root / "main.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "PySide2",
        "PySide6",
        "tkinter",
        "pytest",
        "websockets",
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="NQI_Upper_Client",
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
    icon=str(icon_file) if icon_file.exists() else None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="NQI_Upper_Client",
)
