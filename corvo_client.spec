# -*- mode: python ; coding: utf-8 -*-
"""Build do executavel do CLIENTE (GUI) do Corvo Negro.

Gera dist/CorvoNegroClient.exe (onefile). Embute as fontes/imagens de
client/assets/ e os assets internos do customtkinter (temas JSON, icones),
que o PyInstaller nao detecta sozinho por serem carregados via path relativo
ao pacote em runtime, nao por import direto.

Uso: pyinstaller corvo_client.spec
"""

from PyInstaller.utils.hooks import collect_data_files

datas = [
    ("client/assets", "client/assets"),
]
datas += collect_data_files("customtkinter")

a = Analysis(
    ["client/main.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=["PIL._tkinter_finder"],
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
    a.binaries,
    a.datas,
    [],
    name="CorvoNegroClient",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
