"""
Headless Display & D-Bus Session Runner for GIMP E2E GUI Testing.
Provides lifecycle management for Xvfb (X Virtual Framebuffer) and dbus-run-session,
handling headless display allocation, resolution configuration (1920x1080x24), and fallback to native display servers.
"""

from __future__ import annotations

import os
import shutil
import signal
import socket
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union


def is_display_available() -> bool:
    """
    Checks if a functional graphical display server ($DISPLAY or $WAYLAND_DISPLAY) is currently accessible.
    """
    display = os.environ.get("DISPLAY")
    wayland_display = os.environ.get("WAYLAND_DISPLAY")

    if not display and not wayland_display:
        return False

    if display:
        # Check if X11 socket or connection works
        try:
            # Try xdpyinfo or xset if available
            if shutil.which("xdpyinfo"):
                res = subprocess.run(["xdpyinfo"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)
                return res.returncode == 0
            # Test socket existence if local display like :0 or :1
            if display.startswith(":"):
                disp_num = display[1:].split(".")[0]
                sock_path = f"/tmp/.X11-unix/X{disp_num}"
                if os.path.exists(sock_path):
                    return True
        except Exception:
            pass

    if wayland_display:
        xdg_runtime = os.environ.get("XDG_RUNTIME_DIR", "/tmp")
        wayland_sock = Path(xdg_runtime) / wayland_display
        if wayland_sock.exists():
            return True

    return bool(display or wayland_display)


def has_xvfb() -> bool:
    """Returns True if xvfb-run or Xvfb executable is available."""
    return bool(shutil.which("xvfb-run") or shutil.which("Xvfb"))


def has_dbus_session() -> bool:
    """Returns True if dbus-run-session executable is available."""
    return bool(shutil.which("dbus-run-session"))


def find_free_display(start_display: int = 99, max_display: int = 200) -> int:
    """
    Finds an unused X11 display number by checking locks, sockets, and ports.
    """
    for d in range(start_display, max_display):
        lock_file = Path(f"/tmp/.X{d}-lock")
        sock_file = Path(f"/tmp/.X11-unix/X{d}")
        port = 6000 + d

        if lock_file.exists() or sock_file.exists():
            continue

        # Check TCP port binding
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.1)
                result = s.connect_ex(("127.0.0.1", port))
                if result == 0:
                    # Port is open/in use
                    continue
        except Exception:
            pass

        return d

    return start_display


class XvfbRunner:
    """
    Manages the lifecycle of an X Virtual Framebuffer (Xvfb) and D-Bus session.
    """

    def __init__(
        self,
        width: int = 1920,
        height: int = 1080,
        depth: int = 24,
        dpi: int = 96,
        display_num: Optional[int] = None,
        use_dbus: bool = True,
    ):
        self.width = width
        self.height = height
        self.depth = depth
        self.dpi = dpi
        self.display_num = display_num
        self.use_dbus = use_dbus
        self.proc: Optional[subprocess.Popen] = None
        self.display_str: Optional[str] = None
        self._is_active = False

    def start(self, timeout: float = 10.0) -> str:
        """
        Starts the Xvfb server process and waits for it to become ready.
        Returns the allocated DISPLAY string (e.g., ':99').
        """
        if self._is_active:
            return self.display_str or ":99"

        if self.display_num is None:
            self.display_num = find_free_display()

        self.display_str = f":{self.display_num}"
        screen_cfg = f"{self.width}x{self.height}x{self.depth}"

        xvfb_bin = shutil.which("Xvfb")
        if not xvfb_bin:
            # Fallback if Xvfb binary is not directly found
            self._is_active = True
            return self.display_str

        cmd = [
            xvfb_bin,
            self.display_str,
            "-screen",
            "0",
            screen_cfg,
            "-dpi",
            str(self.dpi),
            "-ac",
            "+extension",
            "GLX",
            "+extension",
            "RANDR",
            "+render",
            "-noreset",
        ]

        try:
            self.proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=os.setsid if hasattr(os, "setsid") else None,
            )

            # Wait for X11 socket to appear or timeout
            start_time = time.time()
            sock_path = Path(f"/tmp/.X11-unix/X{self.display_num}")
            while time.time() - start_time < timeout:
                if sock_path.exists():
                    break
                if self.proc.poll() is not None:
                    # Process died unexpectedly
                    break
                time.sleep(0.05)

            self._is_active = True
            return self.display_str

        except Exception as err:
            self._cleanup()
            raise RuntimeError(f"Failed to start Xvfb on {self.display_str}: {err}") from err

    def stop(self):
        """Stops the Xvfb server process and cleans up lock files."""
        self._cleanup()

    def _cleanup(self):
        if self.proc:
            try:
                if self.proc.poll() is None:
                    os.killpg(os.getpgid(self.proc.pid), signal.SIGTERM)
                    try:
                        self.proc.wait(timeout=2.0)
                    except subprocess.TimeoutExpired:
                        os.killpg(os.getpgid(self.proc.pid), signal.SIGKILL)
            except Exception:
                pass
            self.proc = None

        if self.display_num is not None:
            lock_file = Path(f"/tmp/.X{self.display_num}-lock")
            sock_file = Path(f"/tmp/.X11-unix/X{self.display_num}")
            try:
                if lock_file.exists():
                    lock_file.unlink()
            except Exception:
                pass
            try:
                if sock_file.exists():
                    sock_file.unlink()
            except Exception:
                pass

        self._is_active = False

    def get_env(self, base_env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """Returns environment dictionary configured with the active DISPLAY and rendering flags."""
        env = dict(os.environ) if base_env is None else dict(base_env)
        if self.display_str:
            env["DISPLAY"] = self.display_str
        env["GDK_BACKEND"] = "x11"
        env["GSK_RENDERER"] = "cairo"  # Software / GL fallback for xvfb headless
        env["LIBGL_ALWAYS_SOFTWARE"] = "1"
        return env


class XvfbContext:
    """
    Context manager for executing blocks under an Xvfb display.
    If a display is already present and force_xvfb is False, reuses the existing display.
    """

    def __init__(self, force_xvfb: bool = False, width: int = 1920, height: int = 1080, depth: int = 24):
        self.force_xvfb = force_xvfb
        self.width = width
        self.height = height
        self.depth = depth
        self.runner: Optional[XvfbRunner] = None
        self.active_display: Optional[str] = None
        self._prev_env: Dict[str, Optional[str]] = {}

    def __enter__(self) -> Dict[str, str]:
        if not self.force_xvfb and is_display_available():
            self.active_display = os.environ.get("DISPLAY", ":0")
            return dict(os.environ)

        self.runner = XvfbRunner(width=self.width, height=self.height, depth=self.depth)
        try:
            self.active_display = self.runner.start()
        except Exception:
            # Fallback to existing or mock display
            self.active_display = os.environ.get("DISPLAY", ":99")

        # Set environment
        self._prev_env = {
            "DISPLAY": os.environ.get("DISPLAY"),
            "GDK_BACKEND": os.environ.get("GDK_BACKEND"),
            "GSK_RENDERER": os.environ.get("GSK_RENDERER"),
        }
        os.environ["DISPLAY"] = self.active_display
        os.environ["GDK_BACKEND"] = "x11"
        os.environ["GSK_RENDERER"] = "cairo"
        return dict(os.environ)

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.runner:
            self.runner.stop()
            self.runner = None

        # Restore environment
        for k, v in self._prev_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def run_in_xvfb(
    cmd: Union[List[str], str],
    env: Optional[Dict[str, str]] = None,
    screen: str = "1920x1080x24",
    timeout: float = 60.0,
    cwd: Optional[Union[str, Path]] = None,
    check: bool = False,
    force_xvfb: bool = False,
) -> subprocess.CompletedProcess:
    """
    Executes a command headless. If xvfb-run and dbus-run-session are available,
    wraps the command with `xvfb-run -a -s "-screen 0 <screen>" dbus-run-session`.
    Otherwise executes within an active display or Xvfb context.
    """
    if isinstance(cmd, str):
        cmd_list = cmd.split()
    else:
        cmd_list = list(cmd)

    full_env = dict(os.environ)
    if env:
        full_env.update(env)

    # Use xvfb-run wrapper if available and headless requested or no display
    needs_headless = force_xvfb or not is_display_available()

    if needs_headless and shutil.which("xvfb-run"):
        wrapper = ["xvfb-run", "-a", "-s", f"-screen 0 {screen} -ac +extension GLX +render"]
        if has_dbus_session():
            wrapper.append("dbus-run-session")
        final_cmd = wrapper + cmd_list
        return subprocess.run(final_cmd, env=full_env, timeout=timeout, cwd=cwd, capture_output=True, text=True, check=check)

    # Run in context manager
    with XvfbContext(force_xvfb=needs_headless) as ctx_env:
        if env:
            ctx_env.update(env)
        return subprocess.run(cmd_list, env=ctx_env, timeout=timeout, cwd=cwd, capture_output=True, text=True, check=check)
