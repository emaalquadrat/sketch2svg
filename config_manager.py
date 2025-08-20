import json
import os

CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".sketch2svgrc.json")

DEFAULT_STANDARD_SETTINGS = {
    "mode_var": "outline",
    "batch_aggressive_var": False,
    "illum_sigma_var": 50.0,
    "median_filter_var": False,
    "clahe_var": False,
    "bin_method_var": "adaptive",
    "threshold_var": 127,
    "block_size_var": 11,
    "C_var": 2,
    "invert_var": False,
    "opening_radius_var": 0,
    "min_area_var": 100,
    "prune_short_var": 5.0,
    "simplification_epsilon_var": 2.0,
    "stroke_mm_var": 0.1,
    "dpi_var": 96,
    "scale_preset_var": "Cap",
    "last_folder": ""
}

PRESETS = {
    "Dibuix / Modelat 3D (Extrusió)": {
        "mode_var": "outline",
        "illum_sigma_var": 70.0,
        "median_filter_var": True,
        "clahe_var": False,
        "bin_method_var": "adaptive",
        "block_size_var": 15,
        "C_var": 5,
        "invert_var": False,
        "opening_radius_var": 1,
        "min_area_var": 200,
        "scale_preset_var": "Cap"
    },
    "Làser - Tall (CUT)": {
        "mode_var": "outline",
        "illum_sigma_var": 60.0, # Una mica més de neteja
        "median_filter_var": True,
        "clahe_var": False,
        "bin_method_var": "adaptive",
        "block_size_var": 13, # Bloc una mica més gran
        "C_var": 3,
        "invert_var": False,
        "opening_radius_var": 0, # No opening per no tancar buits de tall
        "min_area_var": 100, # Neteja de soroll
        "scale_preset_var": "Amplada 20mm"
    },
    "Làser - Marcat / Gravat (SCORE)": {
        "mode_var": "centerline",
        "illum_sigma_var": 50.0, # Augmentem sigma per netejar més el fons
        "median_filter_var": True, # Activem filtre median per reduir soroll
        "clahe_var": True,
        "bin_method_var": "adaptive",
        "block_size_var": 11, # Mantenim un bloc raonable
        "C_var": 2, # Mantenim C neutre
        "invert_var": False,
        "opening_radius_var": 0, # No opening per no afectar línies fines
        "min_area_var": 30, # Augmentem per eliminar petits punts de soroll
        "prune_short_var": 2.0,
        "simplification_epsilon_var": 1.0,
        "stroke_mm_var": 0.05,
        "scale_preset_var": "Cap"
    },
    "Brodat (Running Stitch)": {
        "mode_var": "centerline",
        "illum_sigma_var": 50.0, # Augmentem sigma per netejar més el fons
        "median_filter_var": True, # Activem filtre median
        "clahe_var": False,
        "bin_method_var": "adaptive",
        "block_size_var": 13,
        "C_var": 3,
        "invert_var": False,
        "opening_radius_var": 1,
        "min_area_var": 50, # Augmentem per eliminar petits fragments
        "prune_short_var": 3.0,
        "simplification_epsilon_var": 1.5,
        "stroke_mm_var": 0.2,
        "scale_preset_var": "Cap"
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
    """Retorna els paràmetres d'un preset donat."""
    if preset_name in PRESETS:
        return PRESETS[preset_name]
    return DEFAULT_STANDARD_SETTINGS.copy()

def get_preset_names():
    return list(PRESETS.keys())

def get_default_standard_settings():
    return DEFAULT_STANDARD_SETTINGS.copy()

