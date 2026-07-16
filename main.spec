# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import shutil

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


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
# config/resource 是业务可见资源，构建完成后复制到 exe 同级目录；PyInstaller 依赖仍放 _internal。
datas += add_tree("ui", "ui", skip_suffixes={".pyc", ".pyo"})

# MainWindow_index.load_modules scans Module/*.py from the filesystem, so keep
# these module files available in the PyInstaller _internal directory.
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
# 动态菜单入口由源码文件扫描加载，显式列出可避免增量构建或包扫描差异导致 exe 中菜单静默缺失。
hiddenimports += [
    "Module.alarm_rule_config.main",
    "Module.data_search.main",
    "Module.device_registration_approval.main",
    "Module.device_status.main",
    "Module.excel_data_viewer.main",
    "Module.experiment_setting.main",
    "Module.fault_alarm.main",
    "Module.image_data_viewer.main",
    "Module.notification_history.main",
    "Module.search_accuracy_visualization.main",
    "Module.server_message_center.main",
    "PyQt6.sip",
    "charset_normalizer.md__mypyc",
    "multiprocessing.popen_spawn_win32",
]
# 设备配置等动态加载模块会延迟导入自定义弹窗；显式收集，避免 exe 中打开页面时报 No module named。
hiddenimports += collect_submodules("public.component.dialog")
hiddenimports += [
    "public.component.dialog.custom.InfoDialog",
]
# 电量数据页通过动态菜单入口加载；pandas/matplotlib 使用官方 hook，
# 这里只补充 pandas 动态选择的 Excel 引擎和明确使用的 QtAgg 后端。
hiddenimports += [
    "pandas",
    "openpyxl",
    "openpyxl.cell._writer",
    "openpyxl.worksheet._reader",
    "matplotlib",
    "matplotlib.backends.backend_qtagg",
    "matplotlib.backends.backend_qt",
    "matplotlib.backends.backend_agg",
]

datas += collect_data_files("matplotlib")


a = Analysis(
    [str(project_root / "main.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(project_root / "pyinstaller_runtime_hook.py")],
    excludes=[
        "PySide2",
        "PySide6",
        # Optional compatibility branches discovered by third-party hooks; the
        # upper-client source does not use them, so keep their large DLL trees out.
        "networkx",
        "scipy",
        "sympy",
        "tensorflow",
        "torch",
        "torchvision",
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
    name="NQI上位机",
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
    contents_directory="_internal",
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


def copy_to_exe_dir(source_name, target_name=None):
    """把用户需要直接看到/修改的业务资源复制到 dist/exe 同级目录。"""
    source = project_root / source_name
    if not source.exists():
        return
    target = Path(DISTPATH) / "NQI_Upper_Client" / (target_name or source_name)
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"))


copy_to_exe_dir("config")
copy_to_exe_dir("resource")
