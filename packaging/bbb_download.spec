# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_all

block_cipher = None
project_root = Path(SPECPATH).parent
source_root = project_root / "src"
package_root = source_root / "konspekt"

imageio_ffmpeg_datas, imageio_ffmpeg_binaries, imageio_ffmpeg_hiddenimports = collect_all(
    "imageio_ffmpeg"
)

a = Analysis(
    [str(package_root / "bbb_download.py")],
    pathex=[str(source_root)],
    binaries=imageio_ffmpeg_binaries,
    datas=imageio_ffmpeg_datas,
    hiddenimports=['requests', 'tqdm', 'certifi', 'imageio_ffmpeg', *imageio_ffmpeg_hiddenimports],
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
    name='bbb-download',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(project_root / 'assets' / 'konspekt.ico'),
)
