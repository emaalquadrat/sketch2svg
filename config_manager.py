# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025-2026 Ema al quadrat
import json
import os

# Còpia de les claus de `nucli.ESCALES` i `nucli.DETALLS` (sense importar
# nucli, que carrega OpenCV); un test comprova que coincideixen.
ESCALES_VALIDES = ("Amplada 20mm", "Amplada 25mm", "Amplada 30mm", "Amplada 40mm",
                   "Amplada 50mm", "Amplada 100mm", "Alçada 20mm", "Alçada 25mm",
                   "Alçada 30mm", "Alçada 40mm", "Alçada 50mm", "Alçada 100mm")
DETALLS_VALIDS = ("Normal", "Fi", "Màxim")

CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".trama_maker_conversor_2drc.json")

DEFAULT_STANDARD_SETTINGS = {
    "mode_var": "outline",
    "batch_aggressive_var": False,
    "illum_sigma_var": 50.0,
    "median_filter_var": False,
    "clahe_var": False,
    "bin_method_var": "combinat",
    "threshold_var": 127,
    "block_size_var": 25,
    "C_var": 8,
    "invert_var": False,
    "opening_radius_var": 0,
    "min_area_var": 100,
    "silhouette_var": False,
    "ignora_vores_var": True,
    "prune_short_var": 5.0,
    "simplification_epsilon_var": 2.0,
    "stroke_mm_var": 0.1,
    "scale_preset_var": "Amplada 30mm",
    "detail_var": "Normal",
    "last_folder": "",
    "stitch_length_mm_var": 1.0 # Nou paràmetre per a brodat
}

PRESETS = {
    "Dibuix / Modelat 3D (Extrusió)": {
        "mode_var": "outline",
        "illum_sigma_var": 70.0,
        "median_filter_var": False,
        "clahe_var": False,
        "bin_method_var": "combinat",
        "block_size_var": 25,
        "C_var": 8,
        "invert_var": False,
        "opening_radius_var": 0,
        "min_area_var": 100,
        # Per extruir cal la peça plena, no les dues vores de cada línia (proves
        # amb fotos reals, 2026-11-17), i una mida real.
        "silhouette_var": True,
        "scale_preset_var": "Amplada 30mm",
        "stitch_length_mm_var": 1.0 # Afegim a tots els presets per tenir-lo sempre
    },
    "Làser - Tall (CUT)": {
        "mode_var": "outline",
        "illum_sigma_var": 60.0,
        "median_filter_var": False,
        "clahe_var": False,
        "bin_method_var": "combinat",
        "block_size_var": 25,
        "C_var": 8,
        "invert_var": False,
        "opening_radius_var": 0,
        "min_area_var": 100,
        "silhouette_var": True,
        "scale_preset_var": "Amplada 30mm",
        "stitch_length_mm_var": 1.0 # Afegim a tots els presets
    },
    "Làser - Marcat / Gravat (SCORE)": {
        "mode_var": "centerline",
        "illum_sigma_var": 50.0,
        "median_filter_var": False,
        "clahe_var": False,
        "bin_method_var": "combinat",
        "block_size_var": 25,
        "C_var": 8,
        "invert_var": False,
        "opening_radius_var": 0,
        "min_area_var": 50,
        "prune_short_var": 2.0,
        "simplification_epsilon_var": 1.0,
        "stroke_mm_var": 0.05,
        "scale_preset_var": "Amplada 30mm",
        "stitch_length_mm_var": 1.0 # Afegim a tots els presets
    },
    "Brodat (Running Stitch)": {
        "mode_var": "centerline",
        "illum_sigma_var": 50.0,
        "median_filter_var": False,
        "clahe_var": False,
        "bin_method_var": "combinat",
        "block_size_var": 25,
        "C_var": 8,
        "invert_var": False,
        "opening_radius_var": 0,
        "min_area_var": 50,
        "prune_short_var": 3.0,
        "simplification_epsilon_var": 1.5,
        "stroke_mm_var": 0.2,
        "scale_preset_var": "Amplada 30mm",
        "stitch_length_mm_var": 2.5 # Valor recomanat per a brodat bàsic
    }
}

def load_config():
    """Carrega la configuració de l'usuari des del fitxer o els valors per defecte."""
    config = DEFAULT_STANDARD_SETTINGS.copy()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                saved_config = json.load(f)
                config.update(saved_config)
                # Valors d'una versió antiga (p. ex. l'escala «Cap»): els per defecte.
                for clau, valides in (("scale_preset_var", ESCALES_VALIDES),
                                      ("detail_var", DETALLS_VALIDS)):
                    if config.get(clau) not in valides:
                        config[clau] = DEFAULT_STANDARD_SETTINGS[clau]
        except json.JSONDecodeError:
            print(f"Error llegint el fitxer de configuració '{CONFIG_FILE}'. Es carregarà la configuració per defecte.")
        except Exception as e:
            print(f"Error inesperat carregant la configuració: {e}. Es carregarà la configuració per defecte.")
    return config

def save_config(current_settings):
    """Guarda la configuració actual de l'aplicació al fitxer."""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(current_settings, f, indent=4)
    except Exception as e:
        print(f"Error guardant la configuració: {e}")

def get_preset_settings(preset_name):

    """Retorna els paràmetres d'un preset donat.

    Si el nom del preset no es troba, es retorna una còpia de
    ``DEFAULT_STANDARD_SETTINGS``.

    Exemples:
        >>> get_preset_settings("Làser - Tall (CUT)")["mode_var"]
        'outline'
        >>> cfg = get_preset_settings("Preset Inexistent")
        >>> cfg == DEFAULT_STANDARD_SETTINGS
        True
        >>> cfg is DEFAULT_STANDARD_SETTINGS
        False
    """
    settings = DEFAULT_STANDARD_SETTINGS.copy()
    if preset_name in PRESETS:
        settings.update(PRESETS[preset_name])
    return settings

def get_preset_names():
    return list(PRESETS.keys())

def get_default_standard_settings():
    return DEFAULT_STANDARD_SETTINGS.copy()

