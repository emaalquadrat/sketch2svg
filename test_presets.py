import unittest
import config_manager
try:
    from main import Sketch2SVGApp
except ModuleNotFoundError:  # Dependencies for main (e.g., Pillow) may be missing in test env
    Sketch2SVGApp = None

class DummyVar:
    def __init__(self, value):
        self.value = value
    def get(self):
        return self.value
    def set(self, value):
        self.value = value

class DummyStatusBar:
    def __init__(self):
        self.text = ""
    def config(self, **kwargs):
        self.text = kwargs.get('text', self.text)

class DummyApp:
    def __init__(self):
        defaults = config_manager.DEFAULT_STANDARD_SETTINGS
        for key, value in defaults.items():
            setattr(self, key, DummyVar(value))
        self.status_bar = DummyStatusBar()
    def update_parameters_visibility(self):
        pass
    def preview_image(self):
        pass

class TestApplyPreset(unittest.TestCase):
    @unittest.skipUnless(Sketch2SVGApp is not None, "Sketch2SVGApp or dependencies not available")
    def test_presets_reset_defaults(self):
        defaults = config_manager.DEFAULT_STANDARD_SETTINGS
        for preset_name in config_manager.PRESETS.keys():
            app = DummyApp()
            # Change all values away from defaults
            for key, default_value in defaults.items():
                var = getattr(app, key)
                if isinstance(default_value, bool):
                    var.set(not default_value)
                elif isinstance(default_value, (int, float)):
                    var.set(default_value + 1)
                else:
                    var.set("CHANGED")
            # Apply preset
            Sketch2SVGApp.apply_preset(app, preset_name)
            expected = {**defaults, **config_manager.PRESETS[preset_name]}
            for key, expected_value in expected.items():
                self.assertEqual(getattr(app, key).get(), expected_value, f"{preset_name} did not reset {key}")

if __name__ == "__main__":
    unittest.main()
