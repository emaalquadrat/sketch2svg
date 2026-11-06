# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025-2026 Ema al quadrat
"""Sketch2SVG des de la terminal (sense interfície gràfica).

Exemples:
    python cli.py esbossos/ --perfil "Làser - Tall (CUT)"
    python cli.py dibuix.jpg --perfil "Brodat (Running Stitch)" --escala "Amplada 30mm"
"""

import argparse
import os
import sys

import config_manager
import nucli


def main(argv=None):
    perfils = config_manager.get_preset_names()
    ap = argparse.ArgumentParser(description="Converteix fotos d'esbossos a SVG (i DXF o CSV segons el perfil).")
    ap.add_argument("entrada", help="Una imatge o una carpeta amb imatges")
    ap.add_argument("--perfil", default=perfils[0], choices=perfils, help="Perfil d'ús")
    ap.add_argument("--escala", choices=list(nucli.ESCALES), help="Mida final (substitueix la del perfil)")
    ap.add_argument("--dpi", type=int, help="Resolució de la foto si l'escala és «Cap»")
    ap.add_argument("--sortida", help="Carpeta de sortida (per defecte, «output_vector» al costat de les imatges)")
    args = ap.parse_args(argv)

    p = config_manager.get_preset_settings(args.perfil)
    if args.escala:
        p["scale_preset_var"] = args.escala
    if args.dpi:
        p["dpi_var"] = args.dpi

    if os.path.isdir(args.entrada):
        fitxers, base = nucli.llista_imatges(args.entrada), args.entrada
    elif os.path.isfile(args.entrada):
        fitxers, base = [args.entrada], os.path.dirname(os.path.abspath(args.entrada))
    else:
        ap.error(f"No existeix: {args.entrada}")
    if not fitxers:
        ap.error("No hi ha cap imatge per convertir.")

    sortida = args.sortida or os.path.join(base, "output_vector")
    errors = 0
    for path in fitxers:
        try:
            creats = nucli.processa_fitxer(path, p, sortida, args.perfil)
            print(f"OK  {os.path.basename(path)} -> {', '.join(os.path.basename(c) for c in creats)}")
        except nucli.Sketch2SVGError as e:
            errors += 1
            print(f"ERR {os.path.basename(path)}: {e}", file=sys.stderr)
    print(f"\n{len(fitxers) - errors}/{len(fitxers)} imatges convertides a {sortida}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
