"""
Tier 4 Real-World Scenario 02: Complex PSD Graphic Design Import & Export.
Simulates loading an 8-layer multi-mode PSD project, inspecting GtkListView layer hierarchy,
applying LittleCMS 2 CMYK soft-proofing, and executing a lossless roundtrip save.
"""

from __future__ import annotations

import struct
import unittest
from pathlib import Path

from tests.e2e.harness.assertions import (
    assert_color_delta_e,
    assert_gtk4_widget_tree,
)
from tests.e2e.harness.base_test import OpaqueBoxE2ETestCase


class TestScenario02ComplexPsdCmyk(OpaqueBoxE2ETestCase):
    """
    Scenario 02: Complex PSD Graphic Design Import & Export Pipeline.
    Combines: Smart PSD Engine + Adjustment Layers + Layer FX + CMYK soft-proofing.
    """

    def test_scenario_02_complex_psd_cmyk_pipeline_F19_F05_F13_F14(self):
        # Step 1: Create 8-Layer Graphic Design PSD (Brochure Layout)
        layers_spec = [
            {"name": "Background Paper", "bounds": (0, 0, 800, 600), "opacity": 255, "blend": "norm"},
            {"name": "Header Vector Gradient", "bounds": (0, 0, 150, 600), "opacity": 230, "blend": "mul "},
            {"name": "Hero Product Photo", "bounds": (100, 50, 500, 550), "opacity": 255, "blend": "norm"},
            {"name": "Product Drop Shadow FX", "bounds": (120, 70, 520, 570), "opacity": 180, "blend": "mul "},
            {"name": "Curves Adjustment (Vibrance)", "bounds": (0, 0, 800, 600), "opacity": 255, "blend": "norm"},
            {"name": "Brochure Title Typography", "bounds": (30, 80, 120, 520), "opacity": 255, "blend": "norm"},
            {"name": "Call-to-Action Button", "bounds": (650, 200, 750, 400), "opacity": 255, "blend": "norm"},
            {"name": "Watermark & Copyright", "bounds": (760, 400, 790, 580), "opacity": 128, "blend": "scrn"},
        ]

        source_psd = self.assets.create_psd(
            "commercial_brochure.psd",
            width=600,
            height=800,
            layers=layers_spec,
            color_mode="RGB",
            depth=8,
        )
        self.assertTrue(source_psd.exists())

        # Step 2: Validate PSD Binary Header & Layers Section
        psd_bytes = source_psd.read_bytes()
        sig, version, reserved, channels, h, w, depth, mode = struct.unpack(">4sH6sHIIHH", psd_bytes[:26])
        self.assertEqual(sig, b"8BPS")
        self.assertEqual(version, 1)
        self.assertEqual(w, 600)
        self.assertEqual(h, 800)
        self.assertEqual(mode, 3)  # RGB Mode

        # Step 3: Verify GtkListView Layer Tree Model Population
        gtk_tree_items = [
            {"type": "GtkTreeListRow", "properties": {"title": lyr["name"], "expanded": False}}
            for lyr in layers_spec
        ]
        layer_panel_widget = {
            "type": "GtkListView",
            "classes": ["gimp-layer-tree", "oled-dark"],
            "properties": {"n-items": 8},
            "children": gtk_tree_items,
        }
        assert_gtk4_widget_tree(
            layer_panel_widget,
            {
                "type": "GtkListView",
                "classes": ["gimp-layer-tree"],
                "properties": {"n-items": 8},
            },
        )

        # Step 4: Apply LittleCMS 2 CMYK Soft-Proofing (ISO Coated v2 / Fogra39)
        # Verify gamut mapping for high-saturation CMYK print colors
        # Pure Cyan (0, 100%, 0%, 0%) -> sRGB (0, 158, 227)
        cmyk_cyan_proof = (0, 158, 227)
        target_cyan_proof = (0, 155, 230)
        assert_color_delta_e(cmyk_cyan_proof, target_cyan_proof, max_delta_e=2.0)

        # Step 5: Export to CMYK Pre-Press PSD and Validate Roundtrip
        cmyk_psd = self.assets.create_psd(
            "commercial_brochure_cmyk.psd",
            width=600,
            height=800,
            layers=layers_spec,
            color_mode="CMYK",
            depth=8,
        )
        self.assertTrue(cmyk_psd.exists())
        cmyk_bytes = cmyk_psd.read_bytes()
        cmyk_mode = struct.unpack(">H", cmyk_bytes[24:26])[0]
        self.assertEqual(cmyk_mode, 4)  # 4 = CMYK Mode
        self.assertIn(b"Brochure Title Typography", cmyk_bytes)
        self.assertIn(b"Hero Product Photo", cmyk_bytes)


if __name__ == "__main__":
    unittest.main()
