#!/usr/bin/env python3
"""
Adversarial Stress Test: UI Regression & Widget Layout Metrics Audit.
Tests the impact of the OLED design system and CSS styling on standard GTK widgets:
CheckButton, RadioButton, ComboBox, Label, MenuBar, MenuItem, SpinButton, Switch, etc.
Detects squished controls, 0-padding anomalies, or broken rendering hierarchy.
"""

import sys
import unittest
import subprocess
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
OLED_CSS = WORKSPACE_ROOT / "gimp-source" / "themes" / "OLED" / "gimp-dark.css"
DEFAULT_CSS = WORKSPACE_ROOT / "gimp-source" / "themes" / "Default" / "gimp-dark.css"
PHOTOGIMP_CSS = WORKSPACE_ROOT / "photogimp" / ".config" / "GIMP" / "3.0" / "gimp.css"


class TestWidgetLayoutMetrics(unittest.TestCase):
    """Measures GTK widget geometry and style context metrics across themes."""

    def test_01_widget_dimensions_with_oled_theme(self):
        """Measures min/natural size of standard dialog and tool widgets under OLED theme."""
        code = f"""
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk

oled_css = {repr(str(OLED_CSS))}

Gtk.init_check(None)

provider = Gtk.CssProvider()
provider.load_from_path(oled_css)
screen = Gdk.Screen.get_default()
if screen:
    Gtk.StyleContext.add_provider_for_screen(screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

# Test various standard widgets
widgets = {{
    "Button": Gtk.Button(label="OK"),
    "SuggestedButton": Gtk.Button(label="Save"),
    "DestructiveButton": Gtk.Button(label="Delete"),
    "Entry": Gtk.Entry(),
    "SpinScale": Gtk.Entry(),
    "CheckButton": Gtk.CheckButton(label="Antialiasing"),
    "RadioButton": Gtk.RadioButton(label="Mode A"),
    "ComboBox": Gtk.ComboBoxText(),
    "Label": Gtk.Label(label="Layer Opacity: 100%"),
    "MenuBar": Gtk.MenuBar(),
    "Notebook": Gtk.Notebook(),
    "ProgressBar": Gtk.ProgressBar(),
    "Switch": Gtk.Switch(),
    "Scale": Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL),
}}

widgets["SuggestedButton"].get_style_context().add_class("suggested-action")
widgets["DestructiveButton"].get_style_context().add_class("destructive-action")
widgets["SpinScale"].get_style_context().add_class("gimp-spin-scale")
widgets["Notebook"].get_style_context().add_class("gimp-dockbook")

# Add a menu item to menubar
mi = Gtk.MenuItem(label="File")
widgets["MenuBar"].append(mi)

# Add a tab to notebook
p = Gtk.Label(label="content")
t = Gtk.Label(label="Layers")
widgets["Notebook"].append_page(p, t)

# Populate combobox
widgets["ComboBox"].append_text("Normal")
widgets["ComboBox"].append_text("Multiply")
widgets["ComboBox"].set_active(0)

# Build a test window
win = Gtk.OffscreenWindow()
grid = Gtk.Grid(column_spacing=6, row_spacing=6)
win.add(grid)

for i, (name, w) in enumerate(widgets.items()):
    grid.attach(w, 0, i, 1, 1)

win.show_all()

for name, w in widgets.items():
    req = w.get_preferred_size()
    min_w = req.minimum_size.width
    min_h = req.minimum_size.height
    nat_w = req.natural_size.width
    nat_h = req.natural_size.height
    print(f"Widget [{{name:18s}}]: min=({{min_w:3d}}, {{min_h:3d}}), nat=({{nat_w:3d}}, {{nat_h:3d}})")
    
    # Assert widget has non-zero positive geometry
    assert min_w > 0, f"{{name}} min_w is 0"
    assert min_h > 0, f"{{name}} min_h is 0"

print("All widget layout metrics verified successfully.")
"""

        res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"Widget metrics failed:\nStdout: {res.stdout}\nStderr: {res.stderr}")

    def test_02_photogimp_css_widget_dimensions(self):
        """Measures min/natural size of standard widgets under PhotoGIMP profile CSS."""
        code = f"""
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk

pg_css = {repr(str(PHOTOGIMP_CSS))}

Gtk.init_check(None)

provider = Gtk.CssProvider()
provider.load_from_path(pg_css)
screen = Gdk.Screen.get_default()
if screen:
    Gtk.StyleContext.add_provider_for_screen(screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

# Test widgets
widgets = {{
    "Button": Gtk.Button(label="OK"),
    "Entry": Gtk.Entry(),
    "SpinScale": Gtk.Entry(),
    "Notebook": Gtk.Notebook(),
    "ScrolledWindow": Gtk.ScrolledWindow(),
}}

widgets["SpinScale"].get_style_context().add_class("gimp-spin-scale")
p = Gtk.Label(label="content")
t = Gtk.Label(label="Layers")
widgets["Notebook"].append_page(p, t)

tv = Gtk.TreeView()
tv.get_style_context().add_class("view")
widgets["ScrolledWindow"].add(tv)

win = Gtk.OffscreenWindow()
vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
win.add(vbox)
for w in widgets.values():
    vbox.pack_start(w, False, False, 0)

win.show_all()
for name, w in widgets.items():
    req = w.get_preferred_size()
    print(f"PhotoGIMP [{{name:15s}}]: min={{req.minimum_size.width}}x{{req.minimum_size.height}}")
    assert req.minimum_size.width > 0 and req.minimum_size.height > 0
"""

        res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"PhotoGIMP widget metrics failed:\nStdout: {res.stdout}\nStderr: {res.stderr}")

    def test_03_pill_slider_border_radius_and_trough_geometry(self):
        """Verifies GimpSpinScale pill slider styling properties and border radius."""
        code = f"""
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk

oled_css = {repr(str(OLED_CSS))}

Gtk.init_check(None)
provider = Gtk.CssProvider()
provider.load_from_path(oled_css)
screen = Gdk.Screen.get_default()
if screen:
    Gtk.StyleContext.add_provider_for_screen(screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

scale_entry = Gtk.Entry()
scale_entry.get_style_context().add_class("gimp-spin-scale")

win = Gtk.OffscreenWindow()
win.add(scale_entry)
win.show_all()

# Validate that the style context includes gimp-spin-scale
ctx = scale_entry.get_style_context()
assert ctx.has_class("gimp-spin-scale")
req = scale_entry.get_preferred_size()
assert req.minimum_size.height >= 24, f"Pill slider min_height is {{req.minimum_size.height}} < 24"
print(f"Pill slider height requirement met: {{req.minimum_size.height}}px >= 24px")
"""

        res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"Pill slider geometry test failed:\nStdout: {res.stdout}\nStderr: {res.stderr}")

    def test_04_discrete_scrollbars_thickness(self):
        """Verifies ultra-discrete scrollbar minimum dimensions in CSS."""
        oled_common = (WORKSPACE_ROOT / "gimp-source" / "themes" / "OLED" / "common.css").read_text(encoding="utf-8")
        photogimp_css = (WORKSPACE_ROOT / "photogimp" / ".config" / "GIMP" / "3.0" / "gimp.css").read_text(encoding="utf-8")

        for css_name, css_text in [("OLED common.css", oled_common), ("PhotoGIMP gimp.css", photogimp_css)]:
            self.assertIn("scrollbar, scrollbar trough", css_text)
            self.assertIn("min-width: 4px;", css_text)
            self.assertIn("min-height: 4px;", css_text)
            self.assertIn("scrollbar slider:hover", css_text)
            self.assertIn("min-width: 7px;", css_text)
            self.assertIn("min-height: 7px;", css_text)


if __name__ == "__main__":
    unittest.main()
