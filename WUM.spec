# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import copy_metadata, collect_data_files
import os

spec_dir = os.path.abspath(os.path.dirname(__file__))
icons_path = os.path.join(spec_dir, 'icons')


def _safe_copy_metadata(package_name, recursive=False):
    try:
        return copy_metadata(package_name, recursive=recursive)
    except Exception:
        return []


def _safe_collect_data_files(package_name):
    try:
        return collect_data_files(package_name)
    except Exception:
        return []

datas = []
datas += _safe_copy_metadata('apscheduler', recursive=True)
datas += _safe_collect_data_files('textblob.en')
datas += _safe_collect_data_files('tzdata')

block_cipher = None


a = Analysis(['var.py'],
             pathex=[spec_dir],
             binaries=[],
             datas=datas,
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)

if os.path.isdir(icons_path):
    a.datas += Tree(icons_path, prefix='icons')

pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)

icon_path = os.path.join(spec_dir, 'icons', 'icon.ico')

exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          [],
          name='WUM',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          upx_exclude=[],
          runtime_tmpdir=None,
          console=False,
          icon=icon_path if os.path.isfile(icon_path) else None)
