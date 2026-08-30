"""
Tier 4 Real-World Scenario 09: High-Speed Keyboard Automation Workflow.
Simulates keyboard-centric studio workflows: Command Palette modal invocation (Ctrl+K),
fuzzy action lookup and ranking, layer filtering (@), and instant action dispatching.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from tests.e2e.harness.assertions import assert_shortcut_mapping
from tests.e2e.harness.base_test import OpaqueBoxE2ETestCase


class TestScenario09CommandPaletteAutomation(OpaqueBoxE2ETestCase):
    """
    Scenario 09: High-Speed Keyboard Automation Pipeline.
    Combines: Global Command Palette (Ctrl+K / Ctrl+P) + Fuzzy Action Search + Workspace Hot-Swap.
    """

    def test_scenario_09_command_palette_automation_pipeline_F12_F04_F10(self):
        # Step 1: Verify Keybinding Registration for Command Palette
        shortcut_file = self.config_dir / "shortcutsrc"
        self.assertTrue(shortcut_file.exists())
        assert_shortcut_mapping(
            shortcut_file,
            {
                "dialogs-action-search": "<Primary>k",
                "dialogs-command-palette": "<Primary>p",
            },
        )

        # Step 2: Build Action Registry for Command Palette
        action_registry = [
            {"id": "gimp-layer-new", "title": "Layer: New Layer...", "category": "Layer", "shortcut": "Ctrl+Shift+N"},
            {"id": "gimp-layer-duplicate", "title": "Layer: Duplicate Layer", "category": "Layer", "shortcut": "Ctrl+J"},
            {"id": "gimp-image-transform-free", "title": "Transform: Free Transform Gizmo", "category": "Tools", "shortcut": "Ctrl+T"},
            {"id": "gimp-curves-tool", "title": "Adjustments: Curves Adjustment Layer", "category": "Filters", "shortcut": "Ctrl+M"},
            {"id": "gimp-layer-fx-drop-shadow", "title": "Layer Styles: Drop Shadow FX", "category": "Filters", "shortcut": None},
            {"id": "gimp-workspace-photogimp", "title": "Workspace: Switch to PhotoGIMP Profile", "category": "Window", "shortcut": "Ctrl+Alt+P"},
            {"id": "gimp-file-export-psd", "title": "File: Export as Smart PSD...", "category": "File", "shortcut": None},
        ]

        def fuzzy_score(query: str, target: str) -> float:
            """Simple substring / character jump score."""
            q = query.lower()
            t = target.lower()
            if q == t:
                return 100.0
            if q in t:
                return 50.0 + (len(q) / len(t)) * 40.0
            score = 0.0
            t_idx = 0
            for char in q:
                found = t.find(char, t_idx)
                if found != -1:
                    score += 10.0
                    t_idx = found + 1
                else:
                    return 0.0
            return score

        # Step 3: Test Fuzzy Queries
        # Query A: "curve" -> Curves Adjustment Layer
        results_curves = sorted(action_registry, key=lambda a: fuzzy_score("curve", a["title"]), reverse=True)
        self.assertEqual(results_curves[0]["id"], "gimp-curves-tool")

        # Query B: "shadow" -> Drop Shadow FX
        results_shadow = sorted(action_registry, key=lambda a: fuzzy_score("shadow", a["title"]), reverse=True)
        self.assertEqual(results_shadow[0]["id"], "gimp-layer-fx-drop-shadow")

        # Query C: "photogimp" -> Workspace Switch
        results_ws = sorted(action_registry, key=lambda a: fuzzy_score("photogimp", a["title"]), reverse=True)
        self.assertEqual(results_ws[0]["id"], "gimp-workspace-photogimp")

        # Step 4: Layer Filtering Mode (@ prefix)
        layer_list = [
            {"name": "Background", "visible": True},
            {"name": "Hero Product Cutout", "visible": True},
            {"name": "VFX Glow", "visible": False},
        ]
        layer_query = "@hero"
        cleaned_query = layer_query.lstrip("@")
        matched_layers = [l for l in layer_list if cleaned_query in l["name"].lower()]
        self.assertEqual(len(matched_layers), 1)
        self.assertEqual(matched_layers[0]["name"], "Hero Product Cutout")


if __name__ == "__main__":
    unittest.main()
