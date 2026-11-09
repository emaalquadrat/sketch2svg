#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025-2026 Ema al quadrat
#
# Fa el paquet .deb (Ubuntu, Linkat, Debian...) a partir de l'executable
# construït amb PyInstaller.
#
#   empaqueta/fes-deb.sh 1.0.0 dist/Sketch2SVG
set -euo pipefail
umask 022

versio="$1"
executable="$2"
arrel="$(mktemp -d)"
trap 'rm -rf "$arrel"' EXIT
chmod 755 "$arrel"

install -Dm755 "$executable" "$arrel/opt/sketch2svg/Sketch2SVG"
install -Dm644 LICENSE "$arrel/usr/share/doc/sketch2svg/copyright"
install -Dm644 icons/trama_pont_2d.png "$arrel/usr/share/icons/hicolor/256x256/apps/sketch2svg.png"
mkdir -p "$arrel/usr/bin"
ln -s /opt/sketch2svg/Sketch2SVG "$arrel/usr/bin/sketch2svg"

install -Dm644 /dev/stdin "$arrel/usr/share/applications/sketch2svg.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Sketch2SVG
GenericName=De l'esbós al vector
Comment=Converteix fotos de dibuixos fets a mà en fitxers per a la làser, el plotter o la brodadora
Exec=/opt/sketch2svg/Sketch2SVG
Icon=sketch2svg
Terminal=false
Categories=Graphics;Education;
Keywords=svg;dxf;làser;laser;vector;esbós;dibuix;brodat;
StartupWMClass=Sketch2SVG
DESKTOP

mida_kb=$(du -sk "$arrel" | cut -f1)
install -Dm644 /dev/stdin "$arrel/DEBIAN/control" <<CONTROL
Package: sketch2svg
Version: ${versio}
Section: graphics
Priority: optional
Architecture: amd64
Installed-Size: ${mida_kb}
Maintainer: Ema al quadrat <nosaltres@emaalquadrat.cat>
Homepage: https://github.com/emaalquadrat/sketch2svg
Description: De l'esbós al vector, per a aules i tallers maker
 Fes una foto d'un dibuix fet a mà i converteix-lo en un fitxer vectorial
 (SVG, DXF o CSV) llest per a la talladora làser, el plotter, la brodadora
 o un programa de modelat 3D. Funciona sense internet.
CONTROL

mkdir -p dist
dpkg-deb --root-owner-group --build "$arrel" "dist/sketch2svg_${versio}_amd64.deb"
echo "Fet: dist/sketch2svg_${versio}_amd64.deb"
