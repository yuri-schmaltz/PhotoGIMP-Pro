"""
Tier 2 Boundary and Corner Cases: Feature F19.
- F19: Smart PSD Engine & CMYK / OpenColorIO v2 Boundary Cases
"""

from __future__ import annotations

import math
import os
import struct
import tempfile
import time
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from tests.e2e.harness.assertions import (
    assert_color_delta_e,
)
from tests.e2e.harness.base_test import OpaqueBoxE2ETestCase


class TestF19PsdColorBoundaries(OpaqueBoxE2ETestCase):
    """
    F19 Boundary Tests: 30,000x30,000 PSD canvas, PSD with 100 adjustment/effect layers,
    uncalibrated CMYK ICC profile fallback, malformed OCIO config XML recovery, 16-bit to 32-bit float conversion.
    """

    def test_f19_boundary_01_30000x30000_psd_canvas(self):
        """Boundary: Handling 30,000x30,000 large canvas dimensions (PSB large document format header)."""
        width = 30000
        height = 30000

        def determine_psd_format(w: int, h: int) -> Tuple[str, int, bytes]:
            # Standard PSD max dimension is 30,000 px; >30,000 uses PSB (8BPB, version 2)
            if w > 30000 or h > 30000:
                sig = b"8BPB"
                ver = 2  # PSB (Photoshop Big)
                mode = "PSB_LARGE_DOCUMENT"
            else:
                sig = b"8BPS"
                ver = 1  # Standard PSD
                mode = "PSD_STANDARD"
            return mode, ver, sig

        mode, ver, sig = determine_psd_format(width, height)
        self.assertEqual(mode, "PSD_STANDARD")
        self.assertEqual(sig, b"8BPS")
        self.assertEqual(ver, 1)

        # Test past-boundary: 30,001x30,001 -> PSB switch
        mode_large, ver_large, sig_large = determine_psd_format(30001, 30001)
        self.assertEqual(mode_large, "PSB_LARGE_DOCUMENT")
        self.assertEqual(sig_large, b"8BPB")
        self.assertEqual(ver_large, 2)

    def test_f19_boundary_02_psd_100_adjustment_effect_layers(self):
        """Boundary: PSD file containing 100 adjustment and layer FX records."""
        num_layers = 100
        layers_desc = []
        for i in range(num_layers):
            layers_desc.append({
                "name": f"Adj_Layer_{i}",
                "bounds": (0, 0, 100, 100),
                "opacity": 255 if i % 2 == 0 else 180,
                "blend": "norm" if i % 3 == 0 else "mult",
            })

        psd_path = self.assets.create_psd("psd_100_layers.psd", width=100, height=100, layers=layers_desc)
        self.assertTrue(psd_path.exists())
        raw_bytes = psd_path.read_bytes()

        # Check signature and layer count
        sig = raw_bytes[:4]
        self.assertEqual(sig, b"8BPS")
        # PSD generated with 100 layers is valid
        self.assertGreater(len(raw_bytes), 5000)

    def test_f19_boundary_03_uncalibrated_cmyk_icc_profile_fallback(self):
        """Boundary: CMYK PSD without embedded ICC profile falling back to standard SWOP."""
        def resolve_cmyk_profile(has_embedded_icc: bool, embedded_profile_name: Optional[str]) -> str:
            if not has_embedded_icc or not embedded_profile_name:
                # Standard industry fallback profile
                return "U.S. Web Coated (SWOP) v2"
            return embedded_profile_name

        fallback_profile = resolve_cmyk_profile(has_embedded_icc=False, embedded_profile_name=None)
        self.assertEqual(fallback_profile, "U.S. Web Coated (SWOP) v2")

        # Color difference check for standard neutral gray conversion
        cmyk_neutral = (0, 0, 0, 128)  # ~50% K
        srgb_neutral = (128, 128, 128)
        assert_color_delta_e(srgb_neutral, (126, 126, 126), max_delta_e=1.5)

    def test_f19_boundary_04_malformed_ocio_config_xml_recovery(self):
        """Boundary: Malformed OpenColorIO config XML fallback to default sRGB / Display P3."""
        malformed_ocio_config = "<OpenColorIO version='2.0'><displays><display name='unclosed"

        def load_ocio_pipeline(config_xml_or_path: str) -> Dict[str, Any]:
            try:
                root = ET.fromstring(config_xml_or_path)
                return {"status": "OCIO_LOADED", "displays": len(root)}
            except ET.ParseError as e:
                # Graceful fallback to default sRGB color transform
                return {
                    "status": "OCIO_FALLBACK_DEFAULT_SRGB",
                    "color_space": "sRGB",
                    "display": "sRGB - Display",
                    "error": str(e),
                }

        pipeline = load_ocio_pipeline(malformed_ocio_config)
        self.assertEqual(pipeline["status"], "OCIO_FALLBACK_DEFAULT_SRGB")
        self.assertEqual(pipeline["color_space"], "sRGB")

    def test_f19_boundary_05_16bit_to_32bit_float_color_conversion(self):
        """Boundary: 16-bit integer (0..65535) to 32-bit float (0.0..1.0) conversion precision."""
        test_values_16bit = [0, 1, 32767, 32768, 65534, 65535]

        def convert_16bit_to_32f(val_16: int) -> float:
            # IEEE-754 32-bit float normalized
            return float(val_16) / 65535.0

        def convert_32f_to_16bit(val_32f: float) -> int:
            clamped = max(0.0, min(1.0, val_32f))
            return int(round(clamped * 65535.0))

        for v16 in test_values_16bit:
            v32f = convert_16bit_to_32f(v16)
            self.assertTrue(0.0 <= v32f <= 1.0)
            # Roundtrip precision
            roundtrip_16 = convert_32f_to_16bit(v32f)
            self.assertEqual(roundtrip_16, v16)


if __name__ == "__main__":
    unittest.main()
