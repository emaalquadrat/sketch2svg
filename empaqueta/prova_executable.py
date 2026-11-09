# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025-2026 Ema al quadrat
"""Prova l'executable empaquetat abans de publicar-lo.

Dibuixa un esbós de prova, el converteix amb els quatre perfils i comprova
que surten tots els fitxers esperats. Si alguna cosa falla, surt amb error
i la versió no es publica.

    python empaqueta/prova_executable.py dist/Sketch2SVG
"""

import os
import subprocess
import sys
import tempfile

import cv2
import numpy as np

ESPERATS = {
    "Dibuix / Modelat 3D (Extrusió)": ["esbos__outline.svg"],
    "Làser - Tall (CUT)": ["esbos__outline.svg", "esbos__outline.dxf"],
    "Làser - Marcat / Gravat (SCORE)": ["esbos__centerline.svg", "esbos__centerline.dxf"],
    "Brodat (Running Stitch)": ["esbos__centerline.svg", "esbos__centerline.csv"],
}


def main(executable):
    executable = os.path.abspath(executable)
    errors = []
    with tempfile.TemporaryDirectory() as carpeta:
        img = np.full((600, 800), 225, np.uint8)
        cv2.rectangle(img, (150, 200), (450, 450), 40, 5)
        cv2.circle(img, (600, 300), 90, 150, 3)   # traç fluix
        imatge = os.path.join(carpeta, "esbos.png")
        cv2.imwrite(imatge, img)

        res = subprocess.run([executable, "--version"], capture_output=True, text=True, timeout=300)
        print("Versió:", res.stdout.strip() or "(sense consola)")

        for perfil, fitxers in ESPERATS.items():
            sortida = os.path.join(carpeta, f"sortida-{len(os.listdir(carpeta))}")
            res = subprocess.run([executable, imatge, "--perfil", perfil, "--sortida", sortida],
                                 capture_output=True, text=True, timeout=300)
            falten = [f for f in fitxers if not os.path.isfile(os.path.join(sortida, f))]
            estat = "OK " if res.returncode == 0 and not falten else "ERR"
            print(f"{estat} {perfil}")
            if estat == "ERR":
                errors.append(f"{perfil}: codi {res.returncode}, falten {falten}\n{res.stdout}\n{res.stderr}")

    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("L'executable funciona amb els quatre perfils.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
