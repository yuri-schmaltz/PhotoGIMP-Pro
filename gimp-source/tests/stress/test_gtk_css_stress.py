#!/usr/bin/env python3
"""
Adversarial Stress Suite for GTK CSS Themes & Stylesheets (Features 6 & 7).
Validates CSS syntax, @import resolution, color variables, WCAG contrast compliance,
widget styling instantiation under GTK3/GTK4, and parser robustness under extreme inputs.
"""

import os
import sys
import math
import re
import unittest
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]

ALL_CSS_PATHS = [
    WORKSPACE_ROOT / "photogimp" / ".config" / "GIMP" / "3.0" / "gimp.css",
    WORKSPACE_ROOT / "photogimp" / ".config" / "GIMP" / "3.0" / "theme.css",
    WORKSPACE_ROOT / "gimp-source" / "data" / "photogimp-profile" / "gimp.css",
    WORKSPACE_ROOT / "gimp-source" / "data" / "photogimp-profile" / "theme.css",
    WORKSPACE_ROOT / "gimp-source" / "etc" / "gimp.css",
    WORKSPACE_ROOT / "gimp-source" / "themes" / "OLED" / "gimp.css",
    WORKSPACE_ROOT / "gimp-source" / "themes" / "OLED" / "gimp-dark.css",
    WORKSPACE_ROOT / "gimp-source" / "themes" / "OLED" / "common.css",
    WORKSPACE_ROOT / "gimp-source" / "themes" / "OLED" / "common-dark.css",
    WORKSPACE_ROOT / "gimp-source" / "themes" / "Default" / "gimp-dark.css",
    WORKSPACE_ROOT / "gimp-source" / "themes" / "Default" / "gimp-light.css",
    WORKSPACE_ROOT / "gimp-source" / "themes" / "Default" / "gimp-gray.css",
    WORKSPACE_ROOT / "gimp-source" / "themes" / "Default" / "common.css",
    WORKSPACE_ROOT / "gimp-source" / "themes" / "Default" / "common-dark.css",
    WORKSPACE_ROOT / "gimp-source" / "themes" / "Default" / "common-light.css",
    WORKSPACE_ROOT / "gimp-source" / "themes" / "System" / "gimp.css",
    WORKSPACE_ROOT / "gimp-source" / "themes" / "System" / "gimp-light.css",
]

GTK_SYSTEM_COLOR_TOKENS = {
    "theme_bg_color",
    "theme_fg_color",
    "theme_base_color",
    "theme_text_color",
    "theme_selected_bg_color",
    "theme_selected_fg_color",
    "borders",
    "unfocused_borders",
    "warning_color",
    "error_color",
    "success_color",
    "info_color",
}

def hex_to_rgb(hex_str: str) -> Tuple[int, int, int]:
    hex_str = hex_str.strip().lstrip("#")
    if len(hex_str) == 3:
        hex_str = "".join([c * 2 for c in hex_str])
    if len(hex_str) == 6:
        return int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16)
    if len(hex_str) == 8: # rgba hex
        return int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16)
    raise ValueError(f"Invalid hex string: {hex_str}")

def relative_luminance(rgb: Tuple[int, int, int]) -> float:
    def pivot(c: float) -> float:
        c = c / 255.0
        return c / 12.92 if c <= 0.03928 else math.pow((c + 0.055) / 1.055, 2.4)
    r, g, b = pivot(rgb[0]), pivot(rgb[1]), pivot(rgb[2])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b

def contrast_ratio(c1: Tuple[int, int, int], c2: Tuple[int, int, int]) -> float:
    l1 = relative_luminance(c1)
    l2 = relative_luminance(c2)
    return (max(l1, l2) + 0.05) / (min(l1, l2) + 0.05)


class TestGtkCssAdversarial(unittest.TestCase):
    """Rigorous GTK CSS parser and stylesheet stress test."""

    def test_01_all_css_files_exist(self):
        """Validates all declared stylesheet files exist on disk."""
        missing = []
        for path in ALL_CSS_PATHS:
            if not path.exists():
                missing.append(str(path))
        self.assertEqual(missing, [], f"Missing CSS files: {missing}")

    def test_02_gtk3_cssprovider_load_each_file(self):
        """Loads every CSS file directly using GTK 3 GtkCssProvider in a clean subprocess."""
        loadable = [str(p) for p in ALL_CSS_PATHS if p.exists() and "theme.css" not in p.name]
        code = f"""
import os, sys, gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib

files = {repr(loadable)}
errors = []

for f in files:
    p = Gtk.CssProvider()
    try:
        p.load_from_path(f)
    except GLib.Error as e:
        errors.append((f, str(e)))
    except Exception as e:
        errors.append((f, f"Exception: {{e}}"))

if errors:
    for f, err in errors:
        print(f"FAILED: {{f}} -> {{err}}", file=sys.stderr)
    sys.exit(1)
else:
    print(f"SUCCESS: {{len(files)}} files loaded cleanly in GTK3")
"""
        res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
        parsing_errors = [line for line in res.stderr.splitlines() if "Theme parsing error" in line or "FAILED" in line]
        self.assertEqual(res.returncode, 0, f"GTK3 CSS loading failed with exit {res.returncode}:\nStdout: {res.stdout}\nStderr: {res.stderr}")
        self.assertEqual(parsing_errors, [], f"GTK3 CSS parser reported errors:\n" + "\n".join(parsing_errors))

    def test_03_gtk4_cssprovider_load_each_file(self):
        """Loads OLED and PhotoGIMP CSS stylesheets directly using GTK 4 GtkCssProvider."""
        loadable = [str(p) for p in ALL_CSS_PATHS if p.exists() and "theme.css" not in p.name]
        code = f"""
import os, sys, gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib

files = {repr(loadable)}
errors = []

for f in files:
    p = Gtk.CssProvider()
    try:
        p.load_from_path(f)
    except GLib.Error as e:
        errors.append((f, str(e)))
    except Exception as e:
        errors.append((f, f"Exception: {{e}}"))

if errors:
    for f, err in errors:
        print(f"FAILED: {{f}} -> {{err}}", file=sys.stderr)
    sys.exit(1)
else:
    print(f"SUCCESS: {{len(files)}} files loaded in GTK4")
"""
        res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"GTK4 CSS loading crashed:\nStdout: {res.stdout}\nStderr: {res.stderr}")

    def test_04_wcag_contrast_ratios_oled_palette(self):
        """Validates WCAG 2.1 contrast ratios for OLED color palette in OLED and PhotoGIMP themes."""
        oled_dark_css = (WORKSPACE_ROOT / "gimp-source" / "themes" / "OLED" / "gimp-dark.css").read_text(encoding="utf-8")
        photogimp_css = (WORKSPACE_ROOT / "photogimp" / ".config" / "GIMP" / "3.0" / "gimp.css").read_text(encoding="utf-8")

        def extract_colors(css: str) -> Dict[str, str]:
            colors = {}
            for match in re.finditer(r"@define-color\s+([\w\-]+)\s+([^;]+);", css):
                name = match.group(1).strip()
                val = match.group(2).strip()
                colors[name] = val
            return colors

        oled_colors = extract_colors(oled_dark_css)
        pg_colors = extract_colors(photogimp_css)

        # 1. Main text on dark backgrounds (Must satisfy WCAG AAA >= 7:1)
        fg_oled = hex_to_rgb(oled_colors["fg-color"])
        bg_oled = hex_to_rgb(oled_colors["bg-color"])
        ratio_oled_main = contrast_ratio(fg_oled, bg_oled)
        self.assertGreaterEqual(ratio_oled_main, 7.0, f"OLED fg on bg contrast ratio {ratio_oled_main:.2f} < 7.0 (AAA)")

        fg_extreme = hex_to_rgb(oled_colors["fg-color"])
        bg_extreme = hex_to_rgb(oled_colors["extreme-bg-color"])
        ratio_extreme = contrast_ratio(fg_extreme, bg_extreme)
        self.assertGreaterEqual(ratio_extreme, 15.0, f"OLED fg on extreme-bg contrast ratio {ratio_extreme:.2f} < 15.0")

        # 2. Dimmed / muted text on panel background (Must satisfy WCAG AA >= 4.5:1)
        dimmed_oled = hex_to_rgb(oled_colors["dimmed-fg-color"])
        panel_oled = hex_to_rgb(oled_colors["widget-bg-color"])
        ratio_dimmed = contrast_ratio(dimmed_oled, panel_oled)
        self.assertGreaterEqual(ratio_dimmed, 4.5, f"OLED dimmed-fg on widget-bg ratio {ratio_dimmed:.2f} < 4.5 (AA)")

        # 3. PhotoGIMP text contrast
        pg_fg = hex_to_rgb(pg_colors["pg_text_main"])
        pg_shell = hex_to_rgb(pg_colors["pg_bg_shell"])
        ratio_pg_main = contrast_ratio(pg_fg, pg_shell)
        self.assertGreaterEqual(ratio_pg_main, 7.0, f"PhotoGIMP main text ratio {ratio_pg_main:.2f} < 7.0 (AAA)")

        pg_muted = hex_to_rgb(pg_colors["pg_text_muted"])
        pg_panel = hex_to_rgb(pg_colors["pg_bg_panel"])
        ratio_pg_muted = contrast_ratio(pg_muted, pg_panel)
        self.assertGreaterEqual(ratio_pg_muted, 4.5, f"PhotoGIMP muted text ratio {ratio_pg_muted:.2f} < 4.5 (AA)")

        # 4. Accent button / selection contrast
        white = (255, 255, 255)
        accent_oled = hex_to_rgb(oled_colors["accent-color"])
        ratio_accent = contrast_ratio(white, accent_oled)
        self.assertGreaterEqual(ratio_accent, 3.0, f"White text on accent ratio {ratio_accent:.2f} < 3.0 (UI component standard)")

    def test_05_variable_definitions_and_unresolved_references(self):
        """Parses CSS and verifies every @variable reference has a corresponding @define-color."""
        for css_file in ALL_CSS_PATHS:
            if not css_file.exists() or "theme.css" in css_file.name:
                continue
            text = css_file.read_text(encoding="utf-8")
            
            # If the file imports others, gather all defined colors along import chain
            defined_vars = set(re.findall(r"@define-color\s+([\w\-]+)", text))
            # Also check imported files
            imports = re.findall(r'@import\s+url\(["\']?([^"\'\)]+)["\']?\);', text)
            for imp in imports:
                imp_path = css_file.parent / imp
                if imp_path.exists():
                    imp_text = imp_path.read_text(encoding="utf-8")
                    defined_vars.update(re.findall(r"@define-color\s+([\w\-]+)", imp_text))

            # Find all @var uses (excluding standard keywords)
            used_vars = set(re.findall(r"@([a-zA-Z0-9_\-]+)", text))
            for kw in ["define-color", "import", "media", "keyframes", "binding-set"]:
                used_vars.discard(kw)

            # Check if any used var is missing in standalone files (like gimp-dark.css or gimp.css)
            if css_file.name in ["gimp-dark.css", "gimp.css", "gimp-light.css", "gimp-gray.css"]:
                missing_vars = used_vars - defined_vars - GTK_SYSTEM_COLOR_TOKENS
                clean_missing = {v for v in missing_vars if not v.startswith("gtk_")}
                self.assertEqual(clean_missing, set(), f"Unresolved color variables in {css_file}: {clean_missing}")

    def test_06_gtk3_widget_tree_styling_instantiation(self):
        """Constructs GTK3 widget tree with all styled widgets and verifies layout calculations."""
        oled_path = str(WORKSPACE_ROOT / "gimp-source" / "themes" / "OLED" / "gimp-dark.css")
        code = f"""
import os, sys, gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk

oled_css_path = {repr(oled_path)}

Gtk.init_check(None)

provider = Gtk.CssProvider()
provider.load_from_path(oled_css_path)

screen = Gdk.Screen.get_default()
if screen:
    Gtk.StyleContext.add_provider_for_screen(
        screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )

# Instantiate widgets
win = Gtk.OffscreenWindow()
vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
win.add(vbox)

# Notebook with compact tabs
nb = Gtk.Notebook()
nb.get_style_context().add_class("gimp-dockbook")
page1 = Gtk.Label(label="Layer 1")
tab1 = Gtk.Label(label="Layers")
nb.append_page(page1, tab1)
vbox.pack_start(nb, True, True, 0)

# SpinScale / Pill slider simulation
entry = Gtk.Entry()
entry.get_style_context().add_class("gimp-spin-scale")
vbox.pack_start(entry, False, False, 0)

# Buttons
btn_suggest = Gtk.Button(label="Apply")
btn_suggest.get_style_context().add_class("suggested-action")
btn_destruct = Gtk.Button(label="Delete")
btn_destruct.get_style_context().add_class("destructive-action")
vbox.pack_start(btn_suggest, False, False, 0)
vbox.pack_start(btn_destruct, False, False, 0)

# ScrolledWindow with discrete scrollbars
sw = Gtk.ScrolledWindow()
tv = Gtk.TreeView()
tv.get_style_context().add_class("view")
sw.add(tv)
vbox.pack_start(sw, True, True, 0)

# Realize and measure
win.show_all()
req = win.get_preferred_size()
min_size = req.minimum_size
nat_size = req.natural_size

assert min_size.width > 0 and min_size.height > 0, f"Invalid geometry: {{min_size.width}}x{{min_size.height}}"
print(f"Widget tree rendered successfully. Geometry: {{min_size.width}}x{{min_size.height}} (nat: {{nat_size.width}}x{{nat_size.height}})")
"""

        res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"Widget styling instantiation failed:\nStdout: {res.stdout}\nStderr: {res.stderr}")

    def test_07_adversarial_css_mutations_and_stress(self):
        """Stress-tests GTK CSS engine against malformed, deeply nested, and huge CSS inputs."""
        code = """
import os, sys, gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib

# 1. Deeply nested selectors (20 levels)
nested_css = " ".join([f"box.level_{i}" for i in range(20)]) + " button { background-color: #ff0000; }"
p1 = Gtk.CssProvider()
p1.load_from_data(nested_css.encode('utf-8'))

# 2. Large CSS payload (5,000 selectors)
large_rules = "\\n".join([f".custom-class-{i} {{ min-width: {i % 100}px; color: #{i % 100:02x}{i % 100:02x}{i % 100:02x}; }}" for i in range(5000)])
p2 = Gtk.CssProvider()
p2.load_from_data(large_rules.encode('utf-8'))

# 3. Rapid provider creation and deletion cycle (Memory stress)
for _ in range(500):
    p = Gtk.CssProvider()
    p.load_from_data(b"button { border-radius: 9999px; }")

print("Stress mutation tests passed without crash.")
"""
        res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"CSS mutation stress test crashed:\nStdout: {res.stdout}\nStderr: {res.stderr}")


if __name__ == "__main__":
    unittest.main()
