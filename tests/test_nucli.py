import csv
import os
import sys
import xml.etree.ElementTree as ET

import cv2
import ezdxf
import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config_manager  # noqa: E402
import nucli  # noqa: E402

cal_potrace = pytest.mark.skipif(not nucli.potrace_disponible(), reason="potrace no instal·lat")


def esbos(w=400, h=300):
    """Full blanc amb un cercle i una línia dibuixats en negre, com una foto d'esbós."""
    img = np.full((h, w), 235, np.uint8)
    cv2.circle(img, (120, 150), 70, 30, 6)
    cv2.line(img, (250, 60), (360, 240), 30, 6)
    return img


def params(preset="Dibuix / Modelat 3D (Extrusió)", **canvis):
    p = config_manager.get_preset_settings(preset)
    p.update(canvis)
    return p


def desa(tmp_path, img, nom="esbos.png"):
    path = os.path.join(tmp_path, nom)
    cv2.imwrite(path, img)
    return path


# --- Preprocés -------------------------------------------------------------

def test_preprocessa_deixa_el_traç_en_blanc():
    binaria = nucli.preprocessa(esbos(), params())
    assert binaria.dtype == np.uint8
    assert set(np.unique(binaria)) <= {0, 255}
    assert binaria[150, 50] == 255      # sobre el cercle
    assert binaria[20, 20] == 0         # fons
    assert binaria[150, 120] == 0       # dins del cercle


def test_traç_gruixut_no_queda_buit():
    img = np.full((200, 300), 230, np.uint8)
    cv2.line(img, (30, 100), (270, 100), 40, 15)
    binaria = nucli.preprocessa(img, params())
    assert binaria[100, 150] == 255   # el centre del traç és ple
    assert binaria[94:107, 150].all()  # i ho és en tot el gruix


def test_invertir_colors():
    normal = nucli.preprocessa(esbos(), params(min_area_var=0))
    invertida = nucli.preprocessa(esbos(), params(min_area_var=0, invert_var=True))
    assert normal[150, 50] == 255 and invertida[150, 50] == 0


def test_area_minima_elimina_taques():
    img = esbos()
    cv2.circle(img, (350, 280), 2, 30, -1)
    binaria = nucli.preprocessa(img, params(min_area_var=100))
    assert binaria[280, 350] == 0


def test_llegeix_ruta_amb_accents(tmp_path):
    path = desa(str(tmp_path), esbos(), "dibuix_ocell_à.png")
    assert nucli.llegeix_gris(path).shape == (300, 400)


def test_imatge_il_legible(tmp_path):
    path = os.path.join(tmp_path, "no.png")
    open(path, "w").write("no és una imatge")
    with pytest.raises(nucli.Sketch2SVGError):
        nucli.llegeix_gris(path)


# --- Escala ----------------------------------------------------------------

def test_escala_per_dpi():
    assert nucli.mm_per_px(100, 50, 254, "Cap") == pytest.approx(0.1)


def test_escala_amplada_fixa():
    assert 400 * nucli.mm_per_px(400, 300, 96, "Amplada 20mm") == pytest.approx(20)


def test_escala_alcada_fixa():
    assert 300 * nucli.mm_per_px(400, 300, 96, "Alçada 30mm") == pytest.approx(30)


# --- Traç únic ---------------------------------------------------------------

def test_traca_centre_troba_cercle_i_linia():
    p = params("Làser - Marcat / Gravat (SCORE)")
    camins = nucli.traca_centre(nucli.preprocessa(esbos(), p), p)
    llargs = sorted((nucli.longitud(c) for c in camins), reverse=True)
    assert len(camins) <= 4
    assert llargs[0] == pytest.approx(2 * np.pi * 70, rel=0.1)   # cercle
    assert llargs[1] == pytest.approx(np.hypot(110, 180), rel=0.1)  # línia


def test_pixel_solt_no_penja():
    binaria = np.zeros((20, 20), np.uint8)
    binaria[10, 10] = 255
    p = params("Làser - Marcat / Gravat (SCORE)", prune_short_var=0)
    assert nucli.traca_centre(binaria, p) == []


def test_simplifica_no_destrueix_camins_tancats():
    angles = np.linspace(0, 2 * np.pi, 200)
    cercle = [(50 + 40 * np.cos(a), 50 + 40 * np.sin(a)) for a in angles]
    cercle[-1] = cercle[0]
    simple = nucli.simplifica(cercle, 1.0)
    assert 8 < len(simple) < 100
    assert nucli.longitud(simple) == pytest.approx(2 * np.pi * 40, rel=0.05)


def test_simplifica_linia_recta():
    assert nucli.simplifica([(0, 0), (1, 0.01), (2, 0), (3, 0)], 0.5) == [(0, 0), (3, 0)]


def test_remostreja_amb_pas_fix():
    punts = nucli.remostreja([(0, 0), (10, 0)], 2.5)
    assert len(punts) == 5
    assert punts[1] == pytest.approx((2.5, 0))


# --- Fitxers de sortida -----------------------------------------------------

def test_brodat_genera_svg_i_csv(tmp_path):
    preset = "Brodat (Running Stitch)"
    path = desa(str(tmp_path), esbos())
    creats = nucli.processa_fitxer(path, params(preset), str(tmp_path / "sortida"), preset)
    assert [os.path.splitext(c)[1] for c in creats] == [".svg", ".csv"]
    files = list(csv.reader(open(creats[1], encoding="utf-8")))
    assert files[0] == ["X_mm", "Y_mm", "tipus"]
    assert files[1][2] == "JUMP"
    a, b = files[2], files[3]
    dist = np.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))
    assert dist == pytest.approx(2.5, abs=0.4)


def test_gravat_genera_dxf_en_mm(tmp_path):
    preset = "Làser - Marcat / Gravat (SCORE)"
    path = desa(str(tmp_path), esbos())
    p = params(preset, scale_preset_var="Amplada 30mm")
    creats = nucli.processa_fitxer(path, p, str(tmp_path / "sortida"), preset)
    svg = ET.parse(creats[0]).getroot()
    assert svg.get("width") == "30.000mm"
    doc = ezdxf.readfile(creats[1])
    linies = doc.modelspace().query("LWPOLYLINE")
    assert len(linies) >= 2
    xs = [pt[0] for l in linies for pt in l.get_points()]
    assert 0 <= min(xs) and max(xs) <= 30
    assert all(l.dxf.layer == "SCORE" for l in linies)


def test_full_en_blanc_dona_error_clar(tmp_path):
    path = desa(str(tmp_path), np.full((50, 50), 240, np.uint8))
    p = params("Brodat (Running Stitch)")
    with pytest.raises(nucli.Sketch2SVGError, match="cap traç"):
        nucli.processa_fitxer(path, p, str(tmp_path), "Brodat (Running Stitch)")


# --- Contorn (potrace) --------------------------------------------------------

@cal_potrace
def test_contorn_coordenades_en_pixels():
    binaria = nucli.preprocessa(esbos(), params())
    camins_d, transf, polilinies = nucli.traca_contorn(binaria)
    assert camins_d
    tots = np.concatenate([np.asarray(p) for p in polilinies])
    # El cercle va de x≈47 a x≈193 i la línia arriba fins a x≈363.
    assert tots[:, 0].min() == pytest.approx(47, abs=6)
    assert tots[:, 0].max() == pytest.approx(363, abs=6)
    assert tots[:, 1].min() == pytest.approx(57, abs=6)   # Y no ha d'estar invertida
    assert tots[:, 1].max() == pytest.approx(243, abs=6)


@cal_potrace
def test_tall_laser_genera_svg_i_dxf(tmp_path):
    preset = "Làser - Tall (CUT)"
    path = desa(str(tmp_path), esbos())
    creats = nucli.processa_fitxer(path, params(preset), str(tmp_path / "sortida"), preset)
    assert [os.path.splitext(c)[1] for c in creats] == [".svg", ".dxf"]
    svg = ET.parse(creats[0]).getroot()
    assert svg.get("width") == "20.000mm"
    assert 'stroke="#FF0000"' in open(creats[0], encoding="utf-8").read()
    linies = ezdxf.readfile(creats[1]).modelspace().query("LWPOLYLINE")
    xs = [pt[0] for l in linies for pt in l.get_points()]
    assert 0 <= min(xs) and max(xs) <= 20


# --- Presets -------------------------------------------------------------------

def test_presets_tenen_totes_les_claus():
    for nom in config_manager.PRESETS:
        cfg = config_manager.get_preset_settings(nom)
        assert set(config_manager.DEFAULT_STANDARD_SETTINGS) <= set(cfg)
        assert cfg["scale_preset_var"] in nucli.ESCALES


def test_preset_inexistent_dona_valors_per_defecte():
    cfg = config_manager.get_preset_settings("Preset Inexistent")
    assert cfg == config_manager.DEFAULT_STANDARD_SETTINGS
    assert cfg is not config_manager.DEFAULT_STANDARD_SETTINGS


# --- Proves amb fotos reals (2026-11-09) --------------------------------------

def esbos_amb_traç_fluix():
    """Paper gris amb un traç fosc i un altre de llapis molt fluix."""
    img = np.full((300, 400), 200, np.uint8)
    cv2.line(img, (40, 80), (360, 80), 60, 4)     # traç fosc
    cv2.line(img, (40, 220), (360, 220), 165, 3)  # traç fluix
    return img


@pytest.mark.parametrize("preset", config_manager.get_preset_names())
def test_traç_fluix_no_es_perd(preset):
    binaria = nucli.preprocessa(esbos_amb_traç_fluix(), params(preset, silhouette_var=False))
    assert binaria[80, 200] == 255    # el fosc hi és
    assert binaria[220, 200] == 255   # i el fluix també


def test_combinat_no_buida_traços_gruixuts():
    img = np.full((200, 300), 230, np.uint8)
    cv2.line(img, (30, 100), (270, 100), 40, 31)
    binaria = nucli.preprocessa(img, params(bin_method_var="combinat"))
    assert binaria[88:113, 150].all()


def test_escala_mesura_el_dibuix_no_la_foto(tmp_path):
    img = np.full((1000, 1000), 235, np.uint8)
    cv2.rectangle(img, (400, 400), (600, 500), 30, 6)   # dibuix petit al mig del full
    path = desa(tmp_path, img)
    p = params("Làser - Marcat / Gravat (SCORE)", scale_preset_var="Amplada 20mm")
    svg = nucli.processa_fitxer(path, p, os.path.join(tmp_path, "out"), "Làser - Marcat / Gravat (SCORE)")[0]
    arrel = ET.parse(svg).getroot()
    assert arrel.get("width") == "20.000mm"
    alcada = float(arrel.get("height").removesuffix("mm"))
    assert 9.5 < alcada < 11   # proporció del rectangle (~206 x 106 px), no la del full


def test_silueta_omple_l_interior():
    img = np.full((300, 300), 235, np.uint8)
    cv2.rectangle(img, (50, 50), (250, 250), 30, 5)
    cv2.line(img, (50, 150), (250, 150), 30, 5)          # línia interior
    binaria = nucli.preprocessa(img, params("Làser - Tall (CUT)"))
    assert binaria[100, 150] == 255   # l'interior queda ple: només es talla la vora
    assert binaria[20, 20] == 0


def test_tall_laser_dona_un_sol_contorn_per_peça(tmp_path):
    if not nucli.potrace_disponible():
        pytest.skip("potrace no instal·lat")
    img = np.full((300, 300), 235, np.uint8)
    cv2.rectangle(img, (50, 50), (250, 250), 30, 5)
    cv2.line(img, (50, 150), (250, 150), 30, 5)
    binaria = nucli.preprocessa(img, params("Làser - Tall (CUT)"))
    polilinies, _ = nucli.vectoritza(binaria, params("Làser - Tall (CUT)"))
    assert len(polilinies) == 1


@pytest.mark.parametrize("preset", config_manager.get_preset_names())
def test_textura_del_paper_no_fa_soroll(preset):
    """Paper amb gra (com una foto de mòbil): només ha de quedar el dibuix."""
    rng = np.random.default_rng(1)
    img = np.clip(rng.normal(200, 6, (600, 600)), 0, 255).astype(np.uint8)
    cv2.rectangle(img, (250, 250), (350, 350), 60, 4)
    binaria = nucli.preprocessa(img, params(preset))
    files, columnes = np.nonzero(binaria)
    assert files.min() >= 240 and files.max() <= 360
    assert columnes.min() >= 240 and columnes.max() <= 360
