# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller recipe for the standalone Windows study application."""

from pathlib import Path
import os
import shutil

from PyInstaller.utils.hooks import collect_all


project_root = Path(SPECPATH).parent
source_root = project_root / "src"
package_root = source_root / "konspekt"
block_cipher = None
datas: list[tuple[str, str]] = [
    (str(project_root / "assets" / "konspekt.png"), "assets"),
]
binaries: list[tuple[str, str]] = []
hiddenimports: list[str] = []

for package in (
    "imageio_ffmpeg",
    "faster_whisper",
    "ctranslate2",
    "av",
    "tokenizers",
    "huggingface_hub",
):
    package_datas, package_binaries, package_hiddenimports = collect_all(package)
    datas.extend(package_datas)
    binaries.extend(package_binaries)
    hiddenimports.extend(package_hiddenimports)

hiddenimports.extend(
    [
        "faster_whisper",
        "ctranslate2",
        "av",
        "tokenizers",
        "huggingface_hub",
        "imageio_ffmpeg",
    ]
)

tesseract_executable = shutil.which("tesseract")
if not tesseract_executable:
    candidate = (
        Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        / "Tesseract-OCR"
        / "tesseract.exe"
    )
    tesseract_executable = str(candidate) if candidate.is_file() else None
if not tesseract_executable:
    raise SystemExit("Tesseract is required to build Konspekt. Run setup_local_ai.ps1 first.")

tesseract_root = Path(tesseract_executable).parent
for file_path in tesseract_root.rglob("*"):
    if file_path.is_file():
        destination = Path("tesseract") / file_path.relative_to(tesseract_root).parent
        datas.append((str(file_path), str(destination)))

a = Analysis(
    [str(package_root / "__main__.py")],
    pathex=[str(source_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Konspekt",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon=str(project_root / "assets" / "konspekt.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    name="Konspekt",
    upx=False,
)
