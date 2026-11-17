# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025-2026 Ema al quadrat
"""Nucli de Sketch2SVG: processament d'imatge i vectorització, sense interfície.

Totes les funcions treballen amb un diccionari de paràmetres amb les mateixes
claus que `config_manager` (p. ex. ``illum_sigma_var``). Així la interfície, la
línia d'ordres i els tests comparteixen exactament el mateix codi.

Convenció interna: la imatge binària de treball té el traç BLANC (255) sobre
fons NEGRE (0), i les coordenades dels camins són (x, y) en píxels, amb
l'origen a dalt a l'esquerra.
"""

import csv
import os
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

import cv2
import ezdxf
import numpy as np
from scipy.spatial import cKDTree
from skimage.morphology import skeletonize
from svg.path import Move, parse_path

VERSIO = "1.1.0"

EXTENSIONS_IMATGE = (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff")

# Sempre hi ha una mida final (2026-11-17): sense mida, una foto de mòbil
# sortia de 400-800 mm. Les claus són el text que es veu al selector.
ESCALES = {
    "Amplada 20mm": ("width", 20),
    "Amplada 25mm": ("width", 25),
    "Amplada 30mm": ("width", 30),
    "Amplada 40mm": ("width", 40),
    "Amplada 50mm": ("width", 50),
    "Amplada 100mm": ("width", 100),
    "Alçada 20mm": ("height", 20),
    "Alçada 25mm": ("height", 25),
    "Alçada 30mm": ("height", 30),
    "Alçada 40mm": ("height", 40),
    "Alçada 50mm": ("height", 50),
    "Alçada 100mm": ("height", 100),
}
ESCALA_PER_DEFECTE = "Amplada 30mm"

# Detall del contorn, en píxels per mil·límetre de la peça final. Una foto de
# mòbil en dona 50-100: les corbes resseguien el gra del paper i Fusion 360
# patia per extruir-les (400-600 segments). Amb 10 px/mm (0,1 mm, el límit
# real d'una impressora 3D o d'una làser) en surten unes 60.
DETALLS = {
    "Normal": 10,
    "Fi": 20,
    "Màxim": None,
}
DETALL_PER_DEFECTE = "Normal"

# Colors habituals als programes de làser (p. ex. LightBurn): vermell = tall,
# blau = marcat. Els codis DXF són els índexs ACI equivalents.
COLOR_TALL, ACI_TALL = "#FF0000", 1
COLOR_MARCAT, ACI_MARCAT = "#0000FF", 5
COLOR_GENERAL, ACI_GENERAL = "#000000", 7


class Sketch2SVGError(Exception):
    """Error amb un missatge pensat per mostrar a la persona usuària."""


# --------------------------------------------------------------------------
# Lectura i preprocés
# --------------------------------------------------------------------------

def llista_imatges(carpeta):
    """Imatges suportades d'una carpeta, ordenades i sense fitxers ocults."""
    return sorted(
        os.path.join(carpeta, f)
        for f in os.listdir(carpeta)
        if f.lower().endswith(EXTENSIONS_IMATGE) and not f.startswith(".")
    )


def llegeix_gris(path):
    """Llegeix una imatge en escala de grisos (funciona amb accents a Windows)."""
    dades = np.fromfile(path, dtype=np.uint8)
    img = cv2.imdecode(dades, cv2.IMREAD_GRAYSCALE) if dades.size else None
    if img is None:
        raise Sketch2SVGError(f"No es pot llegir la imatge: {os.path.basename(path)}")
    return img


def preprocessa(img_gray, p):
    """Converteix una foto d'esbós en una imatge binària (traç blanc, fons negre)."""
    img = img_gray.copy()
    if p["median_filter_var"]:
        img = cv2.medianBlur(img, 5)
    sigma = float(p["illum_sigma_var"])
    if sigma > 0:
        fons = cv2.GaussianBlur(img, (0, 0), sigmaX=sigma, sigmaY=sigma)
        img = cv2.divide(img, fons, scale=255)
    if p["clahe_var"]:
        img = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(img)

    metode = p["bin_method_var"]
    if metode == "combinat":
        # Proves amb fotos reals (2026-11-09): Otsu sol perd el llapis fluix i
        # l'adaptatiu sol buida els traços gruixuts. Junts, un cobreix l'altre.
        binaria = cv2.bitwise_or(_otsu(img), _adaptativa(img, p))
    elif metode == "otsu":
        # Després de corregir la il·luminació, un llindar automàtic (Otsu) separa
        # bé traç i paper i no buida els traços gruixuts com l'adaptatiu.
        binaria = _otsu(img)
    elif metode == "adaptive":
        binaria = _adaptativa(img, p)
    else:
        _, binaria = cv2.threshold(img, int(p["threshold_var"]), 255, cv2.THRESH_BINARY_INV)

    # THRESH_BINARY_INV ja deixa el traç fosc en blanc.
    if p["invert_var"]:
        binaria = cv2.bitwise_not(binaria)

    radi = int(p["opening_radius_var"])
    if radi > 0:
        nucli = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * radi + 1, 2 * radi + 1))
        binaria = cv2.morphologyEx(binaria, cv2.MORPH_OPEN, nucli)

    area_min = int(p["min_area_var"])
    if area_min > 0:
        n, etiquetes, stats, _ = cv2.connectedComponentsWithStats(binaria, 8, cv2.CV_32S)
        petits = np.where(stats[1:, cv2.CC_STAT_AREA] < area_min)[0] + 1
        if petits.size:
            binaria[np.isin(etiquetes, petits)] = 0
        # També omplim els forats petits dins dels traços (soroll del paper).
        fons = cv2.bitwise_not(binaria)
        n, etiquetes, stats, _ = cv2.connectedComponentsWithStats(fons, 4, cv2.CV_32S)
        forats = np.where(stats[1:, cv2.CC_STAT_AREA] < area_min)[0] + 1
        if forats.size:
            binaria[np.isin(etiquetes, forats)] = 255

    if p.get("ignora_vores_var", True):
        binaria = treu_vores(binaria)

    if p.get("silhouette_var"):
        binaria = silueta(binaria)
    return binaria


def treu_vores(binaria):
    """Treu els elements que toquen la vora de la foto.

    Proves del 2026-11-17: en fotografiar un dibuix, sovint hi entra un tros del
    dibuix del costat, tallat per la vora. Si tot el que hi ha toca la vora (el
    dibuix omple la foto), no es treu res.
    """
    n, etiquetes, _, _ = cv2.connectedComponentsWithStats(binaria, 8, cv2.CV_32S)
    if n <= 1:
        return binaria
    vora = np.unique(np.concatenate([
        etiquetes[0, :], etiquetes[-1, :], etiquetes[:, 0], etiquetes[:, -1]]))
    vora = vora[vora != 0]
    if vora.size == 0 or vora.size == n - 1:
        return binaria
    neta = binaria.copy()
    neta[np.isin(etiquetes, vora)] = 0
    return neta


def _extrems_esquelet(esquelet):
    """Píxels de l'esquelet amb un veí o cap: on s'acaba cada tros de línia
    (un punt solt, com els d'una línia discontínua, també compta)."""
    e = esquelet.astype(np.uint8)
    veins = cv2.filter2D(e, -1, np.ones((3, 3), np.float32), borderType=cv2.BORDER_CONSTANT) - e
    files, columnes = np.nonzero((e == 1) & (veins <= 1))
    return np.column_stack([columnes, files])  # (x, y)


def uneix_extrems(binaria, dist_max):
    """Uneix amb una línia els extrems de traç que queden a menys de `dist_max` px.

    Proves amb fotos reals (2026-11-17): amb llapis fluix o llum desigual, la
    vora d'una lletra surt a trossos (línia discontínua) i la forma no es pot
    omplir. Tancar amb morfologia no n'hi ha prou sense inflar el dibuix; en
    canvi, unir els extrems dels trossos és el que faria una persona repassant
    el traç.

    Només s'uneixen extrems de trossos diferents, o del mateix tros si per dins
    del traç són molt més lluny que en línia recta (una forma que gairebé es
    tanca). Així no s'uneixen, per exemple, les puntes de dues potes.
    """
    from scipy.sparse import csr_matrix
    from scipy.sparse.csgraph import dijkstra

    # Es treballa en petit (~1000 px): és més ràpid i el gra del llapis no
    # omple l'esquelet de branquetes falses. Les branquetes que queden es
    # poden escurçant els extrems unes quantes vegades; els extrems reals
    # també s'escurcen, i per això s'afegeix el doble de la poda a la distància.
    original = binaria
    f = min(1.0, 1000.0 / max(binaria.shape))
    if f < 1.0:
        binaria = cv2.resize(binaria, None, fx=f, fy=f, interpolation=cv2.INTER_AREA)
        binaria = np.where(binaria > 64, 255, 0).astype(np.uint8)
    binaria = cv2.morphologyEx(binaria, cv2.MORPH_CLOSE,
                               cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
    poda = 3
    esquelet = skeletonize(binaria > 0)
    for _ in range(poda):
        # Només es poden les puntes de branca (un veí); els punts solts es
        # queden, perquè poden ser trossos d'una línia discontínua.
        e = esquelet.astype(np.uint8)
        veins = cv2.filter2D(e, -1, np.ones((3, 3), np.float32),
                             borderType=cv2.BORDER_CONSTANT) - e
        esquelet[(e == 1) & (veins == 1)] = False
    # Les taques petites (un punt d'una línia discontínua) poden haver quedat
    # sense esquelet: en conservem un punt, al mig de la taca.
    n, etiq_taques, _, centres = cv2.connectedComponentsWithStats(binaria, 8, cv2.CV_32S)
    amb_esquelet = np.unique(etiq_taques[esquelet])
    for t in range(1, n):
        if t not in amb_esquelet:
            fs, cs = np.nonzero(etiq_taques == t)
            k = int(np.argmin(np.hypot(fs - centres[t][1], cs - centres[t][0])))
            esquelet[fs[k], cs[k]] = True
    dist_max = dist_max * f + 2 * poda
    extrems = _extrems_esquelet(esquelet)
    if len(extrems) < 2:
        return original
    _, etiquetes = cv2.connectedComponents(esquelet.astype(np.uint8), connectivity=8)
    comp = etiquetes[extrems[:, 1], extrems[:, 0]]
    parelles = cKDTree(extrems).query_pairs(dist_max, output_type="ndarray")
    if len(parelles) == 0:
        return original
    dist = np.hypot(*(extrems[parelles[:, 0]] - extrems[parelles[:, 1]]).T)

    # Distància per dins del traç, només per als extrems del mateix tros.
    mateix = comp[parelles[:, 0]] == comp[parelles[:, 1]]
    geodesica = {}
    if mateix.any():
        punts = np.argwhere(esquelet)  # (fila, columna)
        index = -np.ones(esquelet.shape, np.int64)
        index[punts[:, 0], punts[:, 1]] = np.arange(len(punts))
        origens, destins, pesos = [], [], []
        for df, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
            f2, c2 = punts[:, 0] + df, punts[:, 1] + dc
            dins = (f2 >= 0) & (f2 < esquelet.shape[0]) & (c2 >= 0) & (c2 < esquelet.shape[1])
            j = np.full(len(punts), -1)
            j[dins] = index[f2[dins], c2[dins]]
            ok = j >= 0
            origens.append(np.nonzero(ok)[0])
            destins.append(j[ok])
            pesos.append(np.full(ok.sum(), np.hypot(df, dc)))
        graf = csr_matrix((np.concatenate(pesos), (np.concatenate(origens), np.concatenate(destins))),
                          shape=(len(punts), len(punts)))
        implicats = np.unique(parelles[mateix].ravel())
        nodes = index[extrems[implicats, 1], extrems[implicats, 0]]
        distancies = dijkstra(graf, directed=False, indices=nodes)
        fila = {e: k for k, e in enumerate(implicats)}
        for a, b in parelles[mateix]:
            geodesica[(a, b)] = distancies[fila[a], index[extrems[b, 1], extrems[b, 0]]]

    # Gruix del traç, perquè el pont tingui el mateix gruix que la línia.
    dt = cv2.distanceTransform((binaria > 0).astype(np.uint8), cv2.DIST_L2, 3)
    gruix = max(2, int(round(2 * float(np.median(dt[esquelet])) / f)))

    # Un extrem de línia s'uneix una vegada; un punt solt, dues (un per banda).
    mida_comp = np.bincount(etiquetes.ravel())
    capacitat = np.where(mida_comp[comp] == 1, 2, 1)
    unida = original.copy()
    unions = set()  # parelles de trossos ja unides: no s'uneixen dues vegades
    for k in np.argsort(dist):
        a, b = parelles[k]
        if capacitat[a] == 0 or capacitat[b] == 0:
            continue
        if mateix[k] and geodesica.get((a, b), 0) < 10 * dist[k]:
            continue
        clau = (min(comp[a], comp[b]), max(comp[a], comp[b]))
        if not mateix[k] and clau in unions:
            continue
        cv2.line(unida, tuple(int(round(v / f)) for v in extrems[a]),
                 tuple(int(round(v / f)) for v in extrems[b]), 255, gruix)
        capacitat[a] -= 1
        capacitat[b] -= 1
        unions.add(clau)
    return unida


def _otsu(img):
    _, binaria = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    return binaria


def _adaptativa(img, p):
    bloc = max(3, int(p["block_size_var"]))
    if bloc % 2 == 0:
        bloc += 1
    return cv2.adaptiveThreshold(
        img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV,
        bloc, int(p["C_var"]))


def silueta(binaria, radi_tancament=None, dist_unio=None):
    """Omple cada forma tancada perquè només en quedi la vora exterior.

    Per al tall làser i per a l'extrusió 3D: la peça és sencera i les línies
    interiors no compten (per gravar-les hi ha el perfil de marcat). Abans
    d'omplir s'uneixen els extrems de traç propers (`dist_unio`, en px) i es
    tanquen els petits forats, perquè una línia mal tancada no deixi la forma
    oberta.
    """
    if radi_tancament is None:
        # Proporcional a la foto: uns 10 px en una foto de mòbil de 1920 px.
        radi_tancament = max(3, round(0.005 * max(binaria.shape)))
    if dist_unio is None:
        dist_unio = round(0.025 * max(binaria.shape))
    if dist_unio > 0:
        binaria = uneix_extrems(binaria, dist_unio)
    nucli_m = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (2 * radi_tancament + 1, 2 * radi_tancament + 1))
    tancada = cv2.morphologyEx(binaria, cv2.MORPH_CLOSE, nucli_m)
    contorns, _ = cv2.findContours(tancada, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    plena = np.zeros_like(binaria)
    cv2.drawContours(plena, contorns, -1, 255, thickness=cv2.FILLED)
    return treu_taques(plena)


def treu_taques(plena, proporcio=0.02):
    """Treu les taques molt més petites que la peça principal.

    Proves del 2026-11-17: un punt de brutícia lluny del dibuix no és una peça,
    però feia que el dibuix es mesurés malament (l'escarabat sortia el doble
    d'alt).
    """
    n, etiquetes, stats, _ = cv2.connectedComponentsWithStats(plena, 8, cv2.CV_32S)
    if n <= 2:
        return plena
    arees = stats[1:, cv2.CC_STAT_AREA]
    petites = np.where(arees < proporcio * arees.max())[0] + 1
    if petites.size:
        plena = plena.copy()
        plena[np.isin(etiquetes, petites)] = 0
    return plena


def retalla_al_dibuix(binaria):
    """Retalla el paper buit del voltant perquè l'escala es mesuri sobre el dibuix."""
    files, columnes = np.nonzero(binaria)
    if files.size == 0:
        return binaria
    return binaria[files.min():files.max() + 1, columnes.min():columnes.max() + 1]


# --------------------------------------------------------------------------
# Escala
# --------------------------------------------------------------------------

def mm_per_px(w_px, h_px, escala=ESCALA_PER_DEFECTE):
    """Factor de conversió de píxels a mil·límetres perquè el dibuix faci la mida triada.

    Una escala desconeguda (p. ex. l'antiga «Cap» d'una configuració desada)
    fa servir la mida per defecte.
    """
    dimensio, mm = ESCALES.get(escala) or ESCALES[ESCALA_PER_DEFECTE]
    px = w_px if dimensio == "width" else h_px
    return mm / float(px) if px > 0 else 1.0


def redueix_al_detall(binaria, p):
    """Redueix la imatge a la resolució que demana el detall (només mode contorn).

    La mida es calcula sobre el dibuix (no el full), com a `retalla_al_dibuix`,
    així que serveix també per a la previsualització, que no retalla.
    """
    px_mm = DETALLS.get(p.get("detail_var", DETALL_PER_DEFECTE), DETALLS[DETALL_PER_DEFECTE])
    if p["mode_var"] != "outline" or not px_mm:
        return binaria
    files, columnes = np.nonzero(binaria)
    if files.size == 0:
        return binaria
    w = columnes.max() - columnes.min() + 1
    h = files.max() - files.min() + 1
    k = px_mm * mm_per_px(w, h, p["scale_preset_var"])
    if k >= 1.0:
        return binaria
    petita = cv2.resize(binaria, None, fx=k, fy=k, interpolation=cv2.INTER_AREA)
    return np.where(petita >= 128, 255, 0).astype(np.uint8)


# --------------------------------------------------------------------------
# Mode contorn (potrace)
# --------------------------------------------------------------------------

def ruta_potrace():
    """potrace al costat del programa (o dins l'executable empaquetat) o al PATH."""
    nom = "potrace.exe" if os.name == "nt" else "potrace"
    carpetes = [getattr(sys, "_MEIPASS", ""), os.path.dirname(os.path.abspath(__file__))]
    for carpeta in carpetes:
        candidat = os.path.join(carpeta, nom) if carpeta else ""
        if candidat and os.path.isfile(candidat):
            return candidat
    return shutil.which("potrace")


def _opcions_potrace():
    """Opcions per executar potrace dins de l'executable empaquetat.

    - Windows: sense obrir una finestra de terminal a cada imatge.
    - Linux: que trobi la seva llibreria (libpotrace) dins del paquet.
    """
    opcions = {}
    if os.name == "nt":
        opcions["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    paquet = getattr(sys, "_MEIPASS", "")
    if paquet and sys.platform.startswith("linux"):
        entorn = dict(os.environ)
        entorn["LD_LIBRARY_PATH"] = os.pathsep.join(
            c for c in (paquet, entorn.get("LD_LIBRARY_PATH", "")) if c)
        opcions["env"] = entorn
    return opcions


def potrace_disponible():
    return ruta_potrace() is not None


_RE_TRANSLATE = re.compile(r"translate\(\s*([-\d.eE]+)[\s,]+([-\d.eE]+)\s*\)")
_RE_SCALE = re.compile(r"scale\(\s*([-\d.eE]+)(?:[\s,]+([-\d.eE]+))?\s*\)")


def _transformacio(text):
    tx = ty = 0.0
    sx = sy = 1.0
    m = _RE_TRANSLATE.search(text or "")
    if m:
        tx, ty = float(m.group(1)), float(m.group(2))
    m = _RE_SCALE.search(text or "")
    if m:
        sx = float(m.group(1))
        sy = float(m.group(2)) if m.group(2) else sx
    return tx, ty, sx, sy


def _mostreja_path(d, transf, pas=1.0):
    """Converteix un atribut `d` en polilínies (una per subcamí), en píxels."""
    tx, ty, sx, sy = transf
    escala = max(abs(sx), abs(sy)) or 1.0
    poligons, actual = [], []
    for seg in parse_path(d):
        if isinstance(seg, Move):
            if len(actual) > 1:
                poligons.append(actual)
            actual = []
            continue
        # Longitud aproximada pel polígon de control: molt més ràpid que
        # seg.length() i suficient per decidir quants punts cal mostrejar.
        ctrl = [seg.start] + [getattr(seg, a) for a in ("control", "control1", "control2")
                              if hasattr(seg, a)] + [seg.end]
        llarg = sum(abs(b - a) for a, b in zip(ctrl, ctrl[1:])) * escala
        passos = max(1, int(llarg / pas))
        inici = 0 if not actual else 1
        for i in range(inici, passos + 1):
            pt = seg.point(i / passos)
            actual.append((pt.real * sx + tx, pt.imag * sy + ty))
    if len(actual) > 1:
        poligons.append(actual)
    return poligons


def traca_contorn(binaria):
    """Vectoritza els contorns amb potrace.

    Retorna (camins_d, transformacio, polilinies): els `d` originals de potrace
    (corbes de Bézier), la transformació que els porta a píxels i una versió en
    polilínies per a la previsualització i el DXF.
    """
    if not potrace_disponible():
        raise Sketch2SVGError(
            "Falta el programa «potrace». A Linux: sudo apt install potrace. "
            "A Windows: descarrega'l de potrace.sourceforge.net i posa'l al PATH.")
    fd, tmp = tempfile.mkstemp(suffix=".pgm")
    os.close(fd)
    try:
        # potrace vectoritza el negre: invertim perquè el traç sigui negre.
        ok, buf = cv2.imencode(".pgm", cv2.bitwise_not(binaria))
        if not ok:
            raise Sketch2SVGError("No s'ha pogut preparar la imatge per a potrace.")
        buf.tofile(tmp)
        res = subprocess.run([ruta_potrace(), tmp, "-b", "svg", "-o", "-"],
                             capture_output=True, text=True, **_opcions_potrace())
        if res.returncode != 0:
            raise Sketch2SVGError(f"potrace ha fallat: {res.stderr.strip()}")
    finally:
        os.remove(tmp)

    arrel = ET.fromstring(res.stdout)
    ns = "{http://www.w3.org/2000/svg}"
    grup = arrel.find(f".//{ns}g")
    transf = _transformacio(grup.get("transform") if grup is not None else "")
    camins_d = [p.get("d") for p in arrel.iter(f"{ns}path") if p.get("d")]
    polilinies = []
    for d in camins_d:
        polilinies.extend(_mostreja_path(d, transf))
    return camins_d, transf, polilinies


# --------------------------------------------------------------------------
# Mode traç únic (esquelet)
# --------------------------------------------------------------------------

_ORTOGONALS = [(-1, 0), (1, 0), (0, -1), (0, 1)]
_DIAGONALS = [(-1, -1), (-1, 1), (1, -1), (1, 1)]


def _graf_esquelet(esquelet):
    """Graf de veïnatge dels píxels de l'esquelet.

    Una diagonal només es connecta si no hi ha cap píxel ortogonal que ja faci
    de pont: així les cantonades no es converteixen en falses cruïlles.
    """
    punts = set(map(tuple, np.argwhere(esquelet)))
    graf = {}
    for r, c in punts:
        veins = [(r + dr, c + dc) for dr, dc in _ORTOGONALS if (r + dr, c + dc) in punts]
        for dr, dc in _DIAGONALS:
            if (r + dr, c + dc) in punts and (r + dr, c) not in punts and (r, c + dc) not in punts:
                veins.append((r + dr, c + dc))
        graf[(r, c)] = veins
    return graf


def _treu_aresta(graf, a, b):
    if b in graf.get(a, []):
        graf[a].remove(b)
    if a in graf.get(b, []):
        graf[b].remove(a)


def _camins_del_graf(graf):
    camins = []
    # 1) Camins que surten d'extrems o cruïlles (grau diferent de 2).
    for inici in [n for n, v in graf.items() if len(v) != 2]:
        for vei in list(graf.get(inici, [])):
            if vei not in graf[inici]:
                continue
            cami = [inici, vei]
            _treu_aresta(graf, inici, vei)
            actual = vei
            while len(graf.get(actual, [])) == 1:
                seguent = graf[actual][0]
                _treu_aresta(graf, actual, seguent)
                cami.append(seguent)
                actual = seguent
            camins.append(cami)
    # 2) El que queda són bucles tancats (o píxels solts).
    for inici in list(graf.keys()):
        if not graf.get(inici):
            continue
        cami, actual = [inici], inici
        while graf.get(actual):
            seguent = graf[actual][0]
            _treu_aresta(graf, actual, seguent)
            cami.append(seguent)
            actual = seguent
        camins.append(cami)
    return [[(float(c), float(r)) for r, c in cami] for cami in camins if len(cami) > 1]


def _uneix_camins(camins, dist_max):
    """Uneix camins els extrems dels quals queden a menys de `dist_max` píxels."""
    camins = [list(c) for c in camins]
    while len(camins) > 1:
        n = len(camins)
        extrems = np.array([c[0] for c in camins] + [c[-1] for c in camins], float)
        parelles = cKDTree(extrems).query_pairs(dist_max, output_type="ndarray")
        if len(parelles) == 0:
            break
        dist = np.hypot(*(extrems[parelles[:, 0]] - extrems[parelles[:, 1]]).T)
        usats, nous = set(), []
        for a, b in parelles[np.argsort(dist)]:
            i, j = a % n, b % n
            if i == j or i in usats or j in usats:
                continue
            # Orientem els dos camins perquè l'extrem que s'uneix quedi al mig.
            ci = camins[i] if a >= n else camins[i][::-1]
            cj = camins[j] if b < n else camins[j][::-1]
            nous.append(ci + cj)
            usats.update((i, j))
        if not nous:
            break
        camins = [c for k, c in enumerate(camins) if k not in usats] + nous
    return camins


def longitud(cami):
    if len(cami) < 2:
        return 0.0
    arr = np.asarray(cami, dtype=float)
    return float(np.sum(np.hypot(*np.diff(arr, axis=0).T)))


def simplifica(punts, epsilon):
    """Ramer-Douglas-Peucker. Els camins tancats es parteixen per no perdre'ls."""
    if len(punts) < 3 or epsilon <= 0:
        return list(punts)
    p0, pn = np.asarray(punts[0], float), np.asarray(punts[-1], float)
    if np.allclose(p0, pn):
        # Camí tancat: el partim pel punt més llunyà de l'inici.
        arr = np.asarray(punts, float)
        k = int(np.argmax(np.hypot(*(arr - p0).T)))
        if k == 0 or k == len(punts) - 1:
            return list(punts)
        return simplifica(punts[:k + 1], epsilon)[:-1] + simplifica(punts[k:], epsilon)
    dir_ = pn - p0
    llarg = np.hypot(*dir_)
    arr = np.asarray(punts[1:-1], float)
    dist = np.abs(dir_[0] * (p0[1] - arr[:, 1]) - dir_[1] * (p0[0] - arr[:, 0])) / llarg
    k = int(np.argmax(dist))
    if dist[k] > epsilon:
        k += 1
        return simplifica(punts[:k + 1], epsilon)[:-1] + simplifica(punts[k:], epsilon)
    return [punts[0], punts[-1]]


def traca_centre(binaria, p):
    """Vectoritza la línia central dels traços (per a gravat, plotter i brodat)."""
    esquelet = skeletonize(binaria > 0)
    camins = _camins_del_graf(_graf_esquelet(esquelet))
    camins = _uneix_camins(camins, dist_max=3)
    poda = float(p["prune_short_var"])
    if poda > 0:
        camins = [c for c in camins if longitud(c) >= poda]
    eps = float(p["simplification_epsilon_var"])
    return [simplifica(c, eps) for c in camins]


# --------------------------------------------------------------------------
# Escriptura de fitxers
# --------------------------------------------------------------------------

def _capcalera_svg(w_px, h_px, mmpp):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w_px * mmpp:.3f}mm" '
            f'height="{h_px * mmpp:.3f}mm" viewBox="0 0 {w_px} {h_px}">\n')


def escriu_svg_polilinies(path, polilinies, w_px, h_px, mmpp, color, gruix_mm):
    gruix_px = gruix_mm / mmpp
    with open(path, "w", encoding="utf-8") as f:
        f.write(_capcalera_svg(w_px, h_px, mmpp))
        f.write(f'<g fill="none" stroke="{color}" stroke-width="{gruix_px:.3f}" '
                f'stroke-linecap="round" stroke-linejoin="round">\n')
        for cami in polilinies:
            pts = " ".join(f"{x:.2f},{y:.2f}" for x, y in cami)
            f.write(f'<polyline points="{pts}"/>\n')
        f.write("</g>\n</svg>\n")


def escriu_svg_contorn(path, camins_d, transf, w_px, h_px, mmpp, color, gruix_mm):
    tx, ty, sx, sy = transf
    gruix = gruix_mm / mmpp / (max(abs(sx), abs(sy)) or 1.0)
    with open(path, "w", encoding="utf-8") as f:
        f.write(_capcalera_svg(w_px, h_px, mmpp))
        f.write(f'<g transform="translate({tx},{ty}) scale({sx},{sy})" fill="none" '
                f'stroke="{color}" stroke-width="{gruix:.3f}">\n')
        for d in camins_d:
            f.write(f'<path d="{d}"/>\n')
        f.write("</g>\n</svg>\n")


def escriu_dxf(path, polilinies, h_px, mmpp, capa, color_aci):
    """DXF en mil·límetres, amb l'eix Y cap amunt com esperen els programes CAD."""
    doc = ezdxf.new("R2010")
    doc.units = ezdxf.units.MM
    doc.layers.add(capa, color=color_aci)
    msp = doc.modelspace()
    for cami in polilinies:
        pts = [(x * mmpp, (h_px - y) * mmpp) for x, y in cami]
        if len(pts) > 1:
            msp.add_lwpolyline(pts, dxfattribs={"layer": capa})
    doc.saveas(path)


def remostreja(cami, pas):
    """Punts equiespaiats cada `pas` unitats al llarg d'un camí."""
    arr = np.asarray(cami, float)
    if len(arr) < 2 or pas <= 0:
        return [tuple(p) for p in arr]
    trams = np.hypot(*np.diff(arr, axis=0).T)
    acum = np.concatenate([[0.0], np.cumsum(trams)])
    total = acum[-1]
    if total == 0:
        return [tuple(arr[0])]
    n = max(1, int(round(total / pas)))
    dist = np.linspace(0, total, n + 1)
    xs = np.interp(dist, acum, arr[:, 0])
    ys = np.interp(dist, acum, arr[:, 1])
    return list(zip(xs, ys))


def escriu_csv_brodat(path, polilinies, h_px, mmpp, puntada_mm):
    """Llista de puntades (mm). Cada camí comença amb un salt (JUMP)."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["X_mm", "Y_mm", "tipus"])
        for cami in polilinies:
            mm = [(x * mmpp, (h_px - y) * mmpp) for x, y in cami]
            for i, (x, y) in enumerate(remostreja(mm, puntada_mm)):
                w.writerow([f"{x:.3f}", f"{y:.3f}", "JUMP" if i == 0 else "STITCH"])


# --------------------------------------------------------------------------
# Procés complet d'un fitxer
# --------------------------------------------------------------------------

def vectoritza(binaria, p):
    """Retorna (polilinies, dades_contorn). dades_contorn és None en mode traç únic."""
    if p["mode_var"] == "outline":
        camins_d, transf, polilinies = traca_contorn(binaria)
        return polilinies, (camins_d, transf)
    return traca_centre(binaria, p), None


def forma_oberta(traç, plena):
    """Cert si, a la peça més gran, omplir la silueta gairebé no ha afegit res.

    Es mira la peça més gran perquè una forma petita ben tancada (p. ex. un cor
    dins d'una lletra) no amagui que la forma principal ha quedat oberta.
    """
    n, etiquetes, stats, _ = cv2.connectedComponentsWithStats(plena, 8, cv2.CV_32S)
    if n <= 1:
        return False
    gran = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    peça = etiquetes == gran
    n_traç = int(np.count_nonzero(traç[peça]))
    return n_traç > 0 and np.count_nonzero(peça) < 1.5 * n_traç


def processa_fitxer(path_imatge, p, carpeta_sortida, preset="", avisos=None):
    """Converteix una imatge i desa els fitxers. Retorna la llista de fitxers creats.

    Si es passa una llista a `avisos`, s'hi afegeixen els avisos per a la
    persona usuària (el fitxer es crea igualment).
    """
    nom = os.path.basename(path_imatge)
    if p.get("silhouette_var"):
        traç = preprocessa(llegeix_gris(path_imatge), dict(p, silhouette_var=False))
        binaria = silueta(traç)
        if avisos is not None and forma_oberta(traç, binaria):
            avisos.append(f"{nom}: el contorn no es tanca i la peça no surt plena. "
                          "Repassa el traç (millor amb retolador) i torna a fer la foto.")
    else:
        binaria = preprocessa(llegeix_gris(path_imatge), p)
    binaria = retalla_al_dibuix(redueix_al_detall(retalla_al_dibuix(binaria), p))
    h, w = binaria.shape
    mmpp = mm_per_px(w, h, p["scale_preset_var"])
    polilinies, contorn = vectoritza(binaria, p)
    if not polilinies:
        raise Sketch2SVGError(
            f"No s'ha trobat cap traç a {nom}. "
            "Prova d'ajustar el llindar o d'invertir els colors.")

    if "Tall" in preset:
        color, aci, capa = COLOR_TALL, ACI_TALL, "CUT"
    elif "Làser" in preset:
        color, aci, capa = COLOR_MARCAT, ACI_MARCAT, "SCORE"
    else:
        color, aci, capa = COLOR_GENERAL, ACI_GENERAL, "TRACAT"

    os.makedirs(carpeta_sortida, exist_ok=True)
    base = os.path.splitext(os.path.basename(path_imatge))[0]
    mode = p["mode_var"]
    creats = []

    svg = os.path.join(carpeta_sortida, f"{base}__{mode}.svg")
    if contorn:
        escriu_svg_contorn(svg, contorn[0], contorn[1], w, h, mmpp, color, 0.1)
    else:
        escriu_svg_polilinies(svg, polilinies, w, h, mmpp, color, float(p["stroke_mm_var"]))
    creats.append(svg)

    if "Làser" in preset:
        dxf = os.path.join(carpeta_sortida, f"{base}__{mode}.dxf")
        escriu_dxf(dxf, polilinies, h, mmpp, capa, aci)
        creats.append(dxf)
    elif "Brodat" in preset:
        csv_path = os.path.join(carpeta_sortida, f"{base}__{mode}.csv")
        escriu_csv_brodat(csv_path, polilinies, h, mmpp, float(p["stitch_length_mm_var"]))
        creats.append(csv_path)
    return creats
