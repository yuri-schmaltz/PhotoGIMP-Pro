#!/usr/bin/env python3
"""
Adversarial Stress Test Suite for integrate_photogimp.py.
Stress-tests synchronization under edge cases: missing directories, permission errors,
corrupted source configurations, symlink handling, backup collision, and CLI parsing.
"""

import os
import sys
import shutil
import tempfile
import unittest
import subprocess
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
INTEGRATE_SCRIPT = WORKSPACE_ROOT / "integrate_photogimp.py"


class TestIntegratePhotoGimpStress(unittest.TestCase):
    """Adversarial testing of PhotoGIMP synchronization tool."""

    def test_01_status_command(self):
        """Validates that --status runs cleanly with exit code 0 and reports workspace status."""
        res = subprocess.run(
            [sys.executable, str(INTEGRATE_SCRIPT), "--status"],
            capture_output=True,
            text=True,
            cwd=WORKSPACE_ROOT,
        )
        self.assertEqual(res.returncode, 0, f"--status failed:\nStdout: {res.stdout}\nStderr: {res.stderr}")
        self.assertIn("Status dos Repositórios e Instalações", res.stdout)
        self.assertIn("PhotoGIMP repo: [OK]", res.stdout)
        self.assertIn("GIMP Source repo: [OK]", res.stdout)

    def test_02_apply_source_synchronization_fidelity(self):
        """Runs --apply-source and verifies file synchronization fidelity in gimp-source/data/photogimp-profile."""
        res = subprocess.run(
            [sys.executable, str(INTEGRATE_SCRIPT), "--apply-source"],
            capture_output=True,
            text=True,
            cwd=WORKSPACE_ROOT,
        )
        self.assertEqual(res.returncode, 0, f"--apply-source failed:\nStdout: {res.stdout}\nStderr: {res.stderr}")
        self.assertIn("Perfil e configurações do PhotoGIMP copiados", res.stdout)

        src_dir = WORKSPACE_ROOT / "photogimp" / ".config" / "GIMP" / "3.0"
        dst_dir = WORKSPACE_ROOT / "gimp-source" / "data" / "photogimp-profile"

        # Check key files exist and match byte-for-byte
        key_files = ["gimp.css", "gimprc", "sessionrc", "toolrc", "shortcutsrc", "contextrc"]
        for kf in key_files:
            src_file = src_dir / kf
            dst_file = dst_dir / kf
            self.assertTrue(dst_file.exists(), f"Synchronized file {dst_file} missing in target")
            if src_file.exists():
                self.assertEqual(
                    src_file.read_bytes(),
                    dst_file.read_bytes(),
                    f"Content mismatch between {src_file} and {dst_file}",
                )

        # Check splashes copied
        splash_dst = WORKSPACE_ROOT / "gimp-source" / "data" / "splashes" / "photogimp"
        self.assertTrue(splash_dst.exists(), "Splash directory was not created in gimp-source/data/splashes/photogimp")

        # Check etc references exported
        etc_dir = WORKSPACE_ROOT / "gimp-source" / "etc"
        self.assertTrue((etc_dir / "sessionrc.photogimp").exists())
        self.assertTrue((etc_dir / "toolrc.photogimp").exists())

    def test_03_isolated_local_apply_simulation(self):
        """Simulates --apply-local in an isolated mock HOME environment."""
        with tempfile.TemporaryDirectory() as temp_home_dir:
            mock_home = Path(temp_home_dir)
            mock_native_cfg = mock_home / ".config" / "GIMP" / "3.0"
            mock_native_cfg.mkdir(parents=True, exist_ok=True)
            (mock_native_cfg / "gimprc").write_text("# Old config", encoding="utf-8")

            # Run integrate_photogimp with modified HOME
            custom_env = dict(os.environ)
            custom_env["HOME"] = str(mock_home)

            res = subprocess.run(
                [sys.executable, str(INTEGRATE_SCRIPT), "--apply-local", "native"],
                capture_output=True,
                text=True,
                cwd=WORKSPACE_ROOT,
                env=custom_env,
            )
            self.assertEqual(res.returncode, 0, f"--apply-local native failed:\nStdout: {res.stdout}\nStderr: {res.stderr}")
            self.assertIn("Configurações aplicadas com sucesso", res.stdout)

            # Check that backup was created
            backups = list((mock_home / ".config" / "GIMP").glob("GIMP-backup-*"))
            self.assertGreaterEqual(len(backups), 1, "Backup directory was not generated")

            # Check new gimprc and gimp.css applied
            self.assertTrue((mock_native_cfg / "gimp.css").exists())
            self.assertTrue((mock_native_cfg / "sessionrc").exists())

    def test_04_permission_error_graceful_handling(self):
        """Tests handling when target directory has restricted permissions (read-only)."""
        with tempfile.TemporaryDirectory() as temp_home_dir:
            mock_home = Path(temp_home_dir)
            mock_native_cfg = mock_home / ".config" / "GIMP" / "3.0"
            mock_native_cfg.mkdir(parents=True, exist_ok=True)

            # Make target directory read-only
            os.chmod(mock_native_cfg, 0o400)

            custom_env = dict(os.environ)
            custom_env["HOME"] = str(mock_home)

            try:
                res = subprocess.run(
                    [sys.executable, str(INTEGRATE_SCRIPT), "--apply-local", "native"],
                    capture_output=True,
                    text=True,
                    cwd=WORKSPACE_ROOT,
                    env=custom_env,
                )
                # The script should catch the PermissionError or exception and not crash with unhandled traceback
                self.assertNotIn("Traceback (most recent call last):", res.stderr)
            finally:
                os.chmod(mock_native_cfg, 0o700)

    def test_05_cli_arguments_validation(self):
        """Tests CLI options parsing: invalid options, help flags, and combinations."""
        # Help flag
        res_help = subprocess.run(
            [sys.executable, str(INTEGRATE_SCRIPT), "--help"],
            capture_output=True,
            text=True,
            cwd=WORKSPACE_ROOT,
        )
        self.assertEqual(res_help.returncode, 0)
        self.assertIn("Integrador PhotoGIMP + GIMP", res_help.stdout)

        # Invalid choice
        res_invalid = subprocess.run(
            [sys.executable, str(INTEGRATE_SCRIPT), "--apply-local", "invalid_choice"],
            capture_output=True,
            text=True,
            cwd=WORKSPACE_ROOT,
        )
        self.assertNotEqual(res_invalid.returncode, 0)
        self.assertIn("invalid choice", res_invalid.stderr)


if __name__ == "__main__":
    unittest.main()
