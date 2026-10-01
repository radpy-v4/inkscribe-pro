# -*- mode: python ; coding: utf-8 -*-
import os
import glob
from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = []

# Pystray (System Tray Icon)
tmp_ret = collect_all('pystray')
datas += tmp_ret[0]
binaries += tmp_ret[1]
hiddenimports += tmp_ret[2]

# Pynput (Global Keyboard & Mouse Hooks)
tmp_ret = collect_all('pynput')
datas += tmp_ret[0]
binaries += tmp_ret[1]
hiddenimports += tmp_ret[2]

# PIL (Pillow)
tmp_ret = collect_all('PIL')
datas += tmp_ret[0]
binaries += tmp_ret[1]
hiddenimports += tmp_ret[2]

# WinRT Native API (Windows Ink & OCR)
try:
    import winrt
    winrt_dir = list(winrt.__path__)[0]
    for p in glob.glob(os.path.join(winrt_dir, "*.pyd")):
        binaries.append((p, 'winrt'))
    for d in glob.glob(os.path.join(winrt_dir, "*.dll")):
        binaries.append((d, 'winrt'))

    for sub in ['windows', 'runtime', 'system']:
        sub_path = os.path.join(winrt_dir, sub)
        if os.path.exists(sub_path):
            datas.append((sub_path, f'winrt/{sub}'))
except Exception as e:
    print(f"WinRT toplama uyarısı: {e}")

# Uygulama kaynak kodları ve varsayılan konfigürasyon
datas += [('src', 'src')]
if os.path.exists('config.example.json'):
    datas += [('config.example.json', '.')]

# Eksik kalabilecek dinamik bağımlılıklar
hiddenimports += [
    'winrt',
    'winrt._winrt',
    'winrt._winrt_windows_foundation',
    'winrt._winrt_windows_foundation_collections',
    'winrt._winrt_windows_globalization',
    'winrt._winrt_windows_graphics_imaging',
    'winrt._winrt_windows_media_ocr',
    'winrt._winrt_windows_storage_streams',
    'winrt._winrt_windows_ui_input_inking',
    'winrt.system',
    'winrt.runtime',
    'winrt.windows',
    'winrt.windows.foundation',
    'winrt.windows.foundation.collections',
    'winrt.windows.globalization',
    'winrt.windows.graphics',
    'winrt.windows.graphics.imaging',
    'winrt.windows.media',
    'winrt.windows.media.ocr',
    'winrt.windows.storage',
    'winrt.windows.storage.streams',
    'winrt.windows.ui',
    'winrt.windows.ui.input',
    'winrt.windows.ui.input.inking',
    'pystray',
    'pystray._win32',
    'pystray._util',
    'pystray._util.win32',
    'pystray._base',
    'six',
    'six.moves',
    'six.moves.queue',
    'queue',
    'pynput.keyboard._win32',
    'pynput.mouse._win32',
]

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['torch', 'torchvision', 'transformers', 'scipy', 'sympy', 'easyocr'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='TabletNotAlici',
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
)
