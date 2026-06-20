# -*- mode: python ; coding: utf-8 -*-
"""Сборка автономного приложения SeamanJobs (one-folder, оконное).

Внутрь упаковывается браузер Chromium (папка ms-playwright), чтобы maritime-zone
работал на компьютере без Python и без установленного браузера.

Сборка:  build.bat   (или: python -m PyInstaller --noconfirm seaman_jobs.spec)
Результат: dist\SeamanJobs\SeamanJobs.exe
"""
import os

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Папка с браузерами playwright (создаётся командой `playwright install chromium`).
_ms = os.path.join(os.environ.get("LOCALAPPDATA", ""), "ms-playwright")

# Не упаковываем то, что наш код не использует, — экономит ~270 МБ:
#   chromium_headless_shell — не нужен, т.к. launch(channel="chromium") гоняет
#     полный Chromium и в headless (см. scraper/playwright_fetch.py);
#   ffmpeg — только для записи видео.
_SKIP_PREFIXES = ("chromium_headless_shell", "ffmpeg")

datas = []
if os.path.isdir(_ms):
    for entry in sorted(os.listdir(_ms)):
        if entry.startswith(_SKIP_PREFIXES):
            continue
        src = os.path.join(_ms, entry)
        dest = "ms-playwright/" + entry if os.path.isdir(src) else "ms-playwright"
        datas.append((src, dest))
else:
    print("WARNING: ms-playwright не найден — maritime-zone в .exe работать не будет. "
          "Сначала выполните: python -m playwright install chromium")

datas += collect_data_files("playwright")     # node-драйвер playwright
hiddenimports = collect_submodules("playwright")

a = Analysis(
    ["gui.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
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
    name="SeamanJobs",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,            # оконное приложение, без чёрной консоли
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="SeamanJobs",
)
