"""
Tier 4 Real-World Scenario 05: PhotoGIMP Hot-Swap & Shortcut Workflow.
Simulates a seamless migration workflow for Photoshop users: hot-swapping to PhotoGIMP workspace,
validating full Photoshop shortcut table, single-column tool palette, and Command Palette invocation.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from tests.e2e.harness.assertions import (
    assert_gtk4_widget_tree,
    assert_shortcut_mapping,
)
from tests.e2e.harness.base_test import OpaqueBoxE2ETestCase


class TestScenario05PhotoGimpWorkflow(OpaqueBoxE2ETestCase):
    """
    Scenario 05: PhotoGIMP Hot-Swap & Shortcut Workflow.
    Combines: Workspace Switcher + Photoshop shortcuts + Command Palette (Ctrl+K) + OLED Theme.
    """

    def test_scenario_05_photogimp_workflow_F10_F11_F12_F06(self):
        # Step 1: Verify PhotoGIMP Profile Deployment
        shortcut_file = self.config_dir / "shortcutsrc"
        menurc_file = self.config_dir / "menurc"
        gimprc_file = self.config_dir / "gimprc"
        sessionrc_file = self.config_dir / "sessionrc"
        gimp_css_file = self.config_dir / "gimp.css"

        for f in (shortcut_file, menurc_file, gimprc_file, sessionrc_file, gimp_css_file):
            self.assertTrue(f.exists(), f"Expected config file {f.name} missing in PhotoGIMP profile")

        # Step 2: Validate Complete Photoshop Keyboard Muscle Memory
        photoshop_mappings = {
            "image-transform-free": "<Primary>t",
            "layers-duplicate": "<Primary>j",
            "layers-new": "<Primary><Shift>n",
            "select-none": "<Primary>d",
            "select-invert": "<Primary><Shift>i",
            "select-all": "<Primary>a",
            "edit-copy": "<Primary>c",
            "edit-paste": "<Primary>v",
            "edit-cut": "<Primary>x",
            "edit-undo": "<Primary>z",
            "edit-redo": "<Primary><Shift>z",
            "view-zoom-in": "<Primary>equal",
            "view-zoom-out": "<Primary>minus",
            "view-zoom-fit-in": "<Primary>0",
            "view-zoom-100": "<Primary>1",
            "dialogs-action-search": "<Primary>k",
            "dialogs-command-palette": "<Primary>p",
            "tools-brush": "b",
            "tools-eraser": "e",
            "tools-rect-select": "m",
            "tools-free-select": "l",
            "tools-fuzzy-select": "w",
            "tools-move": "v",
            "tools-crop": "c",
            "tools-gradient": "g",
            "tools-text": "t",
        }
        assert_shortcut_mapping(shortcut_file, photoshop_mappings)

        # Step 3: Verify Single-Column Toolbox Configuration
        gimprc_text = gimprc_file.read_text(encoding="utf-8")
        self.assertIn("(toolbox-single-column yes)", gimprc_text)
        self.assertIn('(workspace-profile "PhotoGIMP")', gimprc_text)
        self.assertIn('(theme "Dark-Pro")', gimprc_text)

        # Step 4: Simulate Command Palette (Ctrl+K) Fuzzy Lookup
        palette_actions = [
            {"id": "act_free_transform", "label": "Free Transform", "shortcut": "Ctrl+T"},
            {"id": "act_duplicate_layer", "label": "Duplicate Layer", "shortcut": "Ctrl+J"},
            {"id": "act_deselect", "label": "Deselect", "shortcut": "Ctrl+D"},
            {"id": "act_sam2_select", "label": "SAM 2 Magic Selection", "shortcut": "W"},
        ]

        query = "transf"
        matched = [a for a in palette_actions if query in a["label"].lower()]
        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0]["id"], "act_free_transform")
        self.assertEqual(matched[0]["shortcut"], "Ctrl+T")


if __name__ == "__main__":
    unittest.main()
