# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025-2026 Ema al quadrat
#
# Recepta de PyInstaller per fer l'executable de Sketch2SVG (un sol fitxer).
#
#   pyinstaller sketch2svg.spec
#
# potrace s'empaqueta a dins perquè la persona usuària no l'hagi d'instal·lar.
# Es busca a la variable d'entorn POTRACE o, si no hi és, al PATH.
import os
import shutil
import sys

potrace = os.environ.get("POTRACE") or shutil.which("potrace")
if not potrace or not os.path.isfile(potrace):
    sys.exit("No trobo potrace: instal·la'l o indica'n la ruta amb la variable POTRACE.")

windows = sys.platform.startswith("win")

a = Analysis(
    ["main.py"],
    binaries=[(potrace, ".")],
    datas=[("icons/trama_pont_2d.png", "icons"), ("LICENSE", ".")],
    hiddenimports=["cli"],
    excludes=["matplotlib", "pytest", "IPython", "pandas"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    name="Sketch2SVG",
    console=False,
    icon="icons/trama_pont_2d.ico" if windows else None,
    upx=False,
)
