"""PyInstaller 启动钩子：统一打包程序的相对路径根目录。"""
import os
import sys
from pathlib import Path


if getattr(sys, "frozen", False):
    # 日志、缓存等历史相对路径统一落到 exe 目录，避免从快捷方式启动时写到未知工作目录。
    os.chdir(Path(sys.executable).resolve().parent)
