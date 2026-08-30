"""
Base E2E Test Case and Isolated XDG Environment Context for GIMP + PhotoGIMP.
Provides requirement-driven opaque-box testing foundations, temporary isolated filesystem trees,
automatic environment variable injection, and subprocess execution helpers.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from .assertions import (
    assert_color_delta_e,
    assert_fps_budget,
    assert_gegl_graph_valid,
    assert_gtk4_widget_tree,
    assert_memory_stable,
    assert_non_destructive_stack,
    assert_shortcut_mapping,
)
from .fps_profiler import FPSProfiler, FrameMetrics, ViewportBenchmark
from .leak_checker import MemoryLeakChecker, MemorySnapshot
from .mock_assets import MockAssetGenerator, create_photogimp_profile
from .xvfb_runner import XvfbContext, is_display_available, run_in_xvfb


class GimpEnvContext:
    """
    Context manager that provisions a fully isolated XDG runtime environment
    for GIMP 3.0 / PhotoGIMP testing, preventing any interference with host user configurations.
    """

    def __init__(
        self,
        profile: str = "photogimp",  # 'photogimp', 'default', 'clean', 'custom'
        base_temp_dir: Optional[Union[str, Path]] = None,
        custom_config_src: Optional[Union[str, Path]] = None,
        keep_temp: bool = False,
    ):
        self.profile = profile
        self.base_temp_dir = Path(base_temp_dir) if base_temp_dir else Path(tempfile.mkdtemp(prefix="gimp_e2e_env_"))
        self.custom_config_src = Path(custom_config_src) if custom_config_src else None
        self.keep_temp = keep_temp

        # Directory layout
        self.xdg_config_home = self.base_temp_dir / "config"
        self.xdg_data_home = self.base_temp_dir / "data"
        self.xdg_cache_home = self.base_temp_dir / "cache"
        self.xdg_runtime_dir = self.base_temp_dir / "runtime"
        self.gimp_config_dir = self.xdg_config_home / "GIMP" / "3.0"
        self.gimp_data_dir = self.xdg_data_home / "gimp" / "3.0"

        self._saved_env: Dict[str, Optional[str]] = {}
        self.env: Dict[str, str] = {}

    def setup(self) -> Dict[str, str]:
        """Creates directories and populates initial profile structure."""
        self.xdg_config_home.mkdir(parents=True, exist_ok=True)
        self.xdg_data_home.mkdir(parents=True, exist_ok=True)
        self.xdg_cache_home.mkdir(parents=True, exist_ok=True)
        self.xdg_runtime_dir.mkdir(parents=True, exist_ok=True)
        self.gimp_config_dir.mkdir(parents=True, exist_ok=True)
        self.gimp_data_dir.mkdir(parents=True, exist_ok=True)

        # Populate profile
        if self.custom_config_src and self.custom_config_src.exists():
            shutil.copytree(self.custom_config_src, self.gimp_config_dir, dirs_exist_ok=True)
        elif self.profile == "photogimp":
            create_photogimp_profile(self.xdg_config_home)
        elif self.profile == "default":
            # Standard GIMP 3 default config
            (self.gimp_config_dir / "gimprc").write_text("# GIMP 3.0 Default Preferences\n(theme 'System')\n", encoding="utf-8")
            (self.gimp_config_dir / "menurc").write_text("# GIMP Default Menurc\n", encoding="utf-8")

        # Build isolated environment variables
        env_vars = {
            "XDG_CONFIG_HOME": str(self.xdg_config_home),
            "XDG_DATA_HOME": str(self.xdg_data_home),
            "XDG_CACHE_HOME": str(self.xdg_cache_home),
            "XDG_RUNTIME_DIR": str(self.xdg_runtime_dir),
            "GIMP3_DIRECTORY": str(self.gimp_config_dir),
            "GIMP_TESTING_ENV": "1",
            "G_SLICE": "always-malloc",
            "G_DEBUG": "gc-friendly",
            "G_ENABLE_DIAGNOSTIC": "1",
            "LC_ALL": "C.UTF-8",
        }

        # Save previous environment and set new vars
        for k, v in env_vars.items():
            self._saved_env[k] = os.environ.get(k)
            os.environ[k] = v

        self.env = dict(os.environ)
        return self.env

    def teardown(self):
        """Restores environment variables and cleans temporary folder."""
        for k, v in self._saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

        if not self.keep_temp and self.base_temp_dir.exists():
            shutil.rmtree(self.base_temp_dir, ignore_errors=True)

    def __enter__(self) -> "GimpEnvContext":
        self.setup()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Retain directory if test threw an exception and keep_temp was requested
        if exc_type is not None and self.keep_temp:
            return
        self.teardown()


class OpaqueBoxE2ETestCase(unittest.TestCase):
    """
    Standard base test case for all GIMP + PhotoGIMP E2E tiers (Tier 1-4).
    Enforces opaque-box requirement validation, XDG directory isolation,
    memory snapshotting, and safe subprocess execution.
    """

    profile: str = "photogimp"
    auto_headless: bool = True

    def setUp(self):
        super().setUp()
        self.env_ctx = GimpEnvContext(profile=self.profile)
        self.env = self.env_ctx.setup()
        self.temp_dir = self.env_ctx.base_temp_dir
        self.config_dir = self.env_ctx.gimp_config_dir
        self.data_dir = self.env_ctx.gimp_data_dir

        self.assets = MockAssetGenerator(output_dir=self.temp_dir / "assets")
        self.leak_checker = MemoryLeakChecker(track_heap=True)
        self.leak_checker.start("test_setup")
        self.fps_profiler = FPSProfiler(target_fps=60.0)

    def tearDown(self):
        self.leak_checker.take_snapshot("test_teardown")
        self.assets.cleanup()
        self.env_ctx.teardown()
        super().tearDown()

    def run_subproc(
        self,
        cmd: Union[List[str], str],
        timeout: float = 30.0,
        extra_env: Optional[Dict[str, str]] = None,
        check: bool = False,
        input_text: Optional[str] = None,
        cwd: Optional[Union[str, Path]] = None,
    ) -> subprocess.CompletedProcess:
        """
        Executes a subprocess in the isolated XDG environment.
        """
        if isinstance(cmd, str):
            cmd_list = cmd.split()
        else:
            cmd_list = list(cmd)

        proc_env = dict(self.env)
        if extra_env:
            proc_env.update(extra_env)

        working_dir = cwd or self.temp_dir

        try:
            return subprocess.run(
                cmd_list,
                input=input_text,
                env=proc_env,
                timeout=timeout,
                cwd=working_dir,
                capture_output=True,
                text=True,
                check=check,
            )
        except subprocess.TimeoutExpired as e:
            raise AssertionError(f"Subprocess timed out after {timeout} seconds: {' '.join(cmd_list)}") from e

    def run_gui_subproc(
        self,
        cmd: Union[List[str], str],
        timeout: float = 30.0,
        extra_env: Optional[Dict[str, str]] = None,
        check: bool = False,
    ) -> subprocess.CompletedProcess:
        """
        Executes a GUI subprocess under Xvfb / dbus-run-session if headless.
        """
        proc_env = dict(self.env)
        if extra_env:
            proc_env.update(extra_env)

        return run_in_xvfb(
            cmd=cmd,
            env=proc_env,
            timeout=timeout,
            cwd=self.temp_dir,
            check=check,
            force_xvfb=self.auto_headless and not is_display_available(),
        )

    def find_gimp_binary(self) -> Optional[Path]:
        """Searches for built GIMP binary in workspace or PATH."""
        workspace = Path(__file__).resolve().parents[2]
        candidates = [
            workspace / "gimp-source" / "build" / "app" / "gimp-3.0",
            workspace / "gimp-source" / "app" / "gimp-3.0",
            Path("/usr/bin/gimp-3.0"),
            Path("/usr/bin/gimp"),
        ]
        for c in candidates:
            if c.exists() and os.access(c, os.X_OK):
                return c
        path_bin = shutil.which("gimp-3.0") or shutil.which("gimp")
        return Path(path_bin) if path_bin else None
