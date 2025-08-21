import tkinter as tk
import os
import sys
import types

sys.path.append(os.path.dirname(os.path.dirname(__file__)))


def _stub_module(name, attrs=None):
    module = types.ModuleType(name)
    attrs = attrs or {}
    for key, value in attrs.items():
        setattr(module, key, value)
    sys.modules[name] = module
    return module

_stub_module('PIL', {'Image': object(), 'ImageTk': object()})
_stub_module('cv2')
_stub_module('numpy')
_stub_module('bs4', {'BeautifulSoup': object()})
_stub_module('ezdxf')
skimage_module = _stub_module('skimage')
_stub_module('skimage.morphology', {'skeletonize': lambda *a, **k: None})
skimage_module.morphology = sys.modules['skimage.morphology']
svg_module = _stub_module('svg')
_stub_module('svg.path', {
    'parse_path': lambda *a, **k: None,
    'Line': object(),
    'CubicBezier': object(),
    'QuadraticBezier': object(),
    'Arc': object(),
})
svg_module.path = sys.modules['svg.path']

import config_manager
from main import TramaMakerConversor2dApp


def create_app_without_gui():
    tcl = tk.Tcl()
    app = TramaMakerConversor2dApp.__new__(TramaMakerConversor2dApp)
    app.mode_var = tk.StringVar(master=tcl)
    app.batch_aggressive_var = tk.BooleanVar(master=tcl)
    app.preset_profile_var = tk.StringVar(master=tcl)
    app.bin_method_var = tk.StringVar(master=tcl)
    app.threshold_var = tk.IntVar(master=tcl)
    app.block_size_var = tk.IntVar(master=tcl)
    app.C_var = tk.IntVar(master=tcl)
    app.illum_sigma_var = tk.DoubleVar(master=tcl)
    app.clahe_var = tk.BooleanVar(master=tcl)
    app.median_filter_var = tk.BooleanVar(master=tcl)
    app.opening_radius_var = tk.IntVar(master=tcl)
    app.min_area_var = tk.IntVar(master=tcl)
    app.invert_var = tk.BooleanVar(master=tcl)
    app.prune_short_var = tk.DoubleVar(master=tcl)
    app.simplification_epsilon_var = tk.DoubleVar(master=tcl)
    app.stroke_mm_var = tk.DoubleVar(master=tcl)
    app.stitch_length_mm_var = tk.DoubleVar(master=tcl)
    app.dpi_var = tk.IntVar(master=tcl)
    app.scale_preset_var = tk.StringVar(master=tcl)
    app.update_parameters_visibility = lambda: None
    app.preview_image = lambda: None
    class DummyStatusBar:
        def config(self, **kwargs):
            pass
    app.status_bar = DummyStatusBar()
    return app


def test_existing_preset_resets_unspecified_to_defaults():
    app = create_app_without_gui()
    defaults = config_manager.get_default_standard_settings()
    app.batch_aggressive_var.set(True)
    app.apply_preset("Làser - Tall (CUT)")
    assert app.batch_aggressive_var.get() == defaults["batch_aggressive_var"]


def test_unknown_preset_uses_defaults():
    app = create_app_without_gui()
    defaults = config_manager.get_default_standard_settings()
    app.mode_var.set("centerline")
    app.apply_preset("Preset Inexistent")
    assert app.mode_var.get() == defaults["mode_var"]
