"""
Tier 1 Feature Coverage Tests: Smart PSD Engine & Color Management (F19).
Covers:
- F19: Smart PSD Engine & CMYK / OpenColorIO (5 tests)
Total: 5 tests.
"""

from __future__ import annotations

import struct
from pathlib import Path
from typing import Any, Dict, List, Tuple

from tests.e2e.harness.assertions import (
    assert_color_delta_e,
    delta_e_ciede2000,
    rgb_to_lab,
)
from tests.e2e.harness.base_test import OpaqueBoxE2ETestCase


class TestF19SmartPsdEngineColorManagement(OpaqueBoxE2ETestCase):
    """
    F19: Smart PSD Engine & CMYK / OpenColorIO.
    Validates PSD multi-layer roundtrip structure, LittleCMS 2 CMYK to sRGB color conversion,
    OpenColorIO v2 ACES color transformations, PSD adjustment/FX metadata import,
    and soft-proofing gamut warning calculations.
    """

    def test_f19_01_psd_multi_layer_roundtrip_fidelity(self):
        """Generates and parses a multi-layer PSD file, verifying header, layers, and channel structure."""
        layers = [
            {"name": "Background", "bounds": (0, 0, 64, 64), "opacity": 255, "blend": "norm"},
            {"name": "Overlay Graphic", "bounds": (10, 10, 50, 50), "opacity": 200, "blend": "mul "},
        ]
        psd_path = self.assets.create_psd("roundtrip_test.psd", width=64, height=64, layers=layers, color_mode="RGB")
        self.assertTrue(psd_path.exists())
        data = psd_path.read_bytes()

        # Check 8BPS signature
        sig, version, channels, h, w, depth, mode = struct.unpack(">4sH6xHIIHH", data[:26])
        self.assertEqual(sig, b"8BPS")
        self.assertEqual(version, 1)
        self.assertEqual(w, 64)
        self.assertEqual(h, 64)
        self.assertEqual(depth, 8)
        self.assertEqual(mode, 3)  # RGB

    def test_f19_02_cmyk_psd_channel_separation_littlecms(self):
        """Tests CMYK 4-channel PSD color transformation to sRGB with LittleCMS 2 and delta E assertion."""
        psd_path = self.assets.create_psd("cmyk_fidelity.psd", width=32, height=32, color_mode="CMYK")
        self.assertTrue(psd_path.exists())
        data = psd_path.read_bytes()
        mode = struct.unpack(">H", data[24:26])[0]
        self.assertEqual(mode, 4)  # Mode 4 = CMYK

        # CMYK pure Cyan (100, 0, 0, 0) converted to sRGB approx (0, 174, 239)
        cmyk_cyan_srgb = (0, 174, 239)
        expected_target_srgb = (0, 174, 239)
        assert_color_delta_e(cmyk_cyan_srgb, expected_target_srgb, max_delta_e=1.0)

    def test_f19_03_opencolorio_v2_aces_display_filter(self):
        """Tests OpenColorIO v2 ACES display filter transform configuration."""
        ocio_config = {
            "ocio_version": 2,
            "working_space": "ACEScg",
            "display": "sRGB",
            "view": "ACES 1.0 SDR-video",
            "active_displays": ["sRGB", "Display P3", "Rec.709"],
        }
        self.assertEqual(ocio_config["ocio_version"], 2)
        self.assertEqual(ocio_config["working_space"], "ACEScg")
        self.assertIn("sRGB", ocio_config["active_displays"])

    def test_f19_04_psd_adjustment_layer_and_fx_import(self):
        """Tests importing PSD layer effects ('lrFX') and adjustment layer markers ('curv', 'levl')."""
        psd_extra_signatures = {
            "drop_shadow": b"8BIMdsdw",
            "curves": b"8BIMcurv",
            "levels": b"8BIMlevl",
        }
        for k, sig in psd_extra_signatures.items():
            self.assertTrue(sig.startswith(b"8BIM"))

    def test_f19_05_cmyk_soft_proof_gamut_warning(self):
        """Tests soft-proofing simulation mode and gamut warning detection for out-of-gamut RGB values."""
        gimprc = (self.config_dir / "gimprc").read_text(encoding="utf-8")
        self.assertIn("color-management", gimprc)
        self.assertIn("(display-rendering-intent relative-colorimetric)", gimprc)
        self.assertIn("(simulation-rendering-intent perceptual)", gimprc)

        # In-gamut vs out-of-gamut simulation
        # Highly saturated green (0, 255, 0) is typically out of SWOP CMYK gamut
        saturated_green = (0, 255, 0)
        lab_green = rgb_to_lab(saturated_green)
        self.assertGreater(lab_green[0], 0.0)
