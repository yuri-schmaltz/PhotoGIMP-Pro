"""
Memory & GObject Leak Tracking and Valgrind Analysis for GIMP E2E Testing.
Provides real-time Linux RSS monitoring (/proc/[pid]/statm), heap allocation tracking,
GLib/GObject debugging flags (G_SLICE=always-malloc, G_DEBUG=gc-friendly),
and automated Valgrind leak report parsing.
"""

from __future__ import annotations

import os
import re
import resource
import time
import tracemalloc
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union


def get_process_memory_info(pid: Optional[int] = None) -> Dict[str, int]:
    """
    Reads resident set size (RSS), virtual memory size (VmSize), and data segment (VmData)
    from the Linux /proc filesystem for the given process ID (default current process).
    """
    target_pid = pid or os.getpid()
    page_size = resource.getpagesize()
    statm_path = Path(f"/proc/{target_pid}/statm")
    status_path = Path(f"/proc/{target_pid}/status")

    res = {
        "rss_bytes": 0,
        "vm_size_bytes": 0,
        "vm_data_bytes": 0,
        "vm_peak_bytes": 0,
    }

    if statm_path.exists():
        try:
            parts = statm_path.read_text().strip().split()
            if len(parts) >= 2:
                total_pages = int(parts[0])
                resident_pages = int(parts[1])
                res["vm_size_bytes"] = total_pages * page_size
                res["rss_bytes"] = resident_pages * page_size
        except Exception:
            pass

    if status_path.exists():
        try:
            for line in status_path.read_text().splitlines():
                if line.startswith("VmPeak:"):
                    res["vm_peak_bytes"] = int(re.search(r"\d+", line).group(0)) * 1024
                elif line.startswith("VmData:"):
                    res["vm_data_bytes"] = int(re.search(r"\d+", line).group(0)) * 1024
                elif line.startswith("VmRSS:") and res["rss_bytes"] == 0:
                    res["rss_bytes"] = int(re.search(r"\d+", line).group(0)) * 1024
        except Exception:
            pass

    if res["rss_bytes"] == 0:
        # Fallback to getrusage (ru_maxrss in kilobytes on Linux)
        usage = resource.getrusage(resource.RUSAGE_SELF)
        res["rss_bytes"] = usage.ru_maxrss * 1024
        res["vm_size_bytes"] = res["rss_bytes"]

    return res


@dataclass
class MemorySnapshot:
    """Represents a single point-in-time memory measurement."""
    label: str
    timestamp: float
    pid: int
    rss_bytes: int
    vm_size_bytes: int
    heap_bytes: int = 0
    extra_metadata: Dict[str, Union[int, str]] = field(default_factory=dict)

    @property
    def rss_mb(self) -> float:
        return self.rss_bytes / (1024.0 * 1024.0)

    @property
    def heap_mb(self) -> float:
        return self.heap_bytes / (1024.0 * 1024.0)

    def diff(self, baseline: "MemorySnapshot") -> "MemoryDelta":
        """Calculates growth delta relative to a baseline snapshot."""
        rss_diff = self.rss_bytes - baseline.rss_bytes
        heap_diff = self.heap_bytes - baseline.heap_bytes
        vm_diff = self.vm_size_bytes - baseline.vm_size_bytes
        pct_growth = (rss_diff / baseline.rss_bytes * 100.0) if baseline.rss_bytes > 0 else 0.0

        return MemoryDelta(
            baseline_label=baseline.label,
            current_label=self.label,
            rss_growth_bytes=rss_diff,
            heap_growth_bytes=heap_diff,
            vm_growth_bytes=vm_diff,
            growth_percentage=pct_growth,
            duration_seconds=self.timestamp - baseline.timestamp,
        )


@dataclass
class MemoryDelta:
    """Calculated memory delta between two snapshots."""
    baseline_label: str
    current_label: str
    rss_growth_bytes: int
    heap_growth_bytes: int
    vm_growth_bytes: int
    growth_percentage: float
    duration_seconds: float

    @property
    def rss_growth_mb(self) -> float:
        return self.rss_growth_bytes / (1024.0 * 1024.0)

    @property
    def heap_growth_mb(self) -> float:
        return self.heap_growth_bytes / (1024.0 * 1024.0)

    def is_leaking(self, max_growth_mb: float = 20.0, max_percentage: float = 10.0) -> bool:
        """Determines whether growth exceeds acceptable bounds."""
        if self.rss_growth_mb > max_growth_mb and self.growth_percentage > max_percentage:
            return True
        return False


@dataclass
class ValgrindReport:
    """Parsed metrics from a Valgrind Memcheck run."""
    definitely_lost_bytes: int = 0
    indirectly_lost_bytes: int = 0
    possibly_lost_bytes: int = 0
    still_reachable_bytes: int = 0
    suppressed_bytes: int = 0
    total_error_count: int = 0
    leak_records: List[str] = field(default_factory=list)
    raw_log: str = ""

    @property
    def is_clean(self) -> bool:
        """Returns True if there are zero definitely or indirectly lost bytes and zero errors."""
        return (self.definitely_lost_bytes == 0 and self.indirectly_lost_bytes == 0 and self.total_error_count == 0)

    @property
    def total_lost_bytes(self) -> int:
        return self.definitely_lost_bytes + self.indirectly_lost_bytes + self.possibly_lost_bytes


class ValgrindLogAnalyzer:
    """
    Parses Valgrind text and XML log outputs.
    """

    @classmethod
    def parse_log(cls, log_content_or_path: Union[str, Path]) -> ValgrindReport:
        if isinstance(log_content_or_path, Path) or (isinstance(log_content_or_path, str) and os.path.exists(log_content_or_path)):
            content = Path(log_content_or_path).read_text(errors="replace")
        else:
            content = str(log_content_or_path)

        report = ValgrindReport(raw_log=content)

        # Regex patterns for LEAK SUMMARY
        definitely_match = re.search(r"definitely lost:\s*([\d,]+)\s*bytes", content, re.IGNORECASE)
        if definitely_match:
            report.definitely_lost_bytes = int(definitely_match.group(1).replace(",", ""))

        indirectly_match = re.search(r"indirectly lost:\s*([\d,]+)\s*bytes", content, re.IGNORECASE)
        if indirectly_match:
            report.indirectly_lost_bytes = int(indirectly_match.group(1).replace(",", ""))

        possibly_match = re.search(r"possibly lost:\s*([\d,]+)\s*bytes", content, re.IGNORECASE)
        if possibly_match:
            report.possibly_lost_bytes = int(possibly_match.group(1).replace(",", ""))

        still_reachable_match = re.search(r"still reachable:\s*([\d,]+)\s*bytes", content, re.IGNORECASE)
        if still_reachable_match:
            report.still_reachable_bytes = int(still_reachable_match.group(1).replace(",", ""))

        suppressed_match = re.search(r"suppressed:\s*([\d,]+)\s*bytes", content, re.IGNORECASE)
        if suppressed_match:
            report.suppressed_bytes = int(suppressed_match.group(1).replace(",", ""))

        error_match = re.search(r"ERROR SUMMARY:\s*([\d,]+)\s*errors", content, re.IGNORECASE)
        if error_match:
            report.total_error_count = int(error_match.group(1).replace(",", ""))

        return report


class MemoryLeakChecker:
    """
    Context and tracking manager for memory and GObject leak auditing.
    """

    def __init__(self, pid: Optional[int] = None, track_heap: bool = True):
        self.pid = pid or os.getpid()
        self.track_heap = track_heap
        self.snapshots: List[MemorySnapshot] = []
        self._tracemalloc_started = False

    def start(self, label: str = "baseline"):
        """Starts monitoring and records baseline snapshot."""
        if self.track_heap and not tracemalloc.is_tracing():
            tracemalloc.start()
            self._tracemalloc_started = True

        self.snapshots.clear()
        self.take_snapshot(label)

    def take_snapshot(self, label: str) -> MemorySnapshot:
        """Captures a new memory snapshot with the given label."""
        info = get_process_memory_info(self.pid)
        heap_bytes = 0
        if self.track_heap and tracemalloc.is_tracing():
            current, peak = tracemalloc.get_traced_memory()
            heap_bytes = current

        snap = MemorySnapshot(
            label=label,
            timestamp=time.time(),
            pid=self.pid,
            rss_bytes=info["rss_bytes"],
            vm_size_bytes=info["vm_size_bytes"],
            heap_bytes=heap_bytes,
            extra_metadata=info,
        )
        self.snapshots.append(snap)
        return snap

    def get_baseline(self) -> MemorySnapshot:
        if not self.snapshots:
            raise RuntimeError("No snapshots recorded yet. Call start() first.")
        return self.snapshots[0]

    def get_latest(self) -> MemorySnapshot:
        if not self.snapshots:
            raise RuntimeError("No snapshots recorded yet. Call start() first.")
        return self.snapshots[-1]

    def get_delta(self) -> MemoryDelta:
        """Computes delta between initial baseline and latest snapshot."""
        return self.get_latest().diff(self.get_baseline())

    def assert_no_leak(self, max_growth_mb: float = 25.0, max_percentage: float = 15.0):
        """Asserts that memory growth between baseline and latest snapshot is within budget."""
        delta = self.get_delta()
        if delta.is_leaking(max_growth_mb=max_growth_mb, max_percentage=max_percentage):
            raise AssertionError(
                f"Memory leak detected: RSS grew by {delta.rss_growth_mb:.2f} MB "
                f"({delta.growth_percentage:.1f}%), exceeding budget of {max_growth_mb} MB / {max_percentage}%"
            )

    @classmethod
    def get_glib_debug_env(cls) -> Dict[str, str]:
        """
        Returns environment variables required for GLib/GObject leak and memory tracking:
        G_SLICE=always-malloc, G_DEBUG=gc-friendly, G_ENABLE_DIAGNOSTIC=1.
        """
        return {
            "G_SLICE": "always-malloc",
            "G_DEBUG": "gc-friendly",
            "G_ENABLE_DIAGNOSTIC": "1",
            "MALLOC_CHECK_": "2",
        }


def assert_memory_stable(
    baseline: MemorySnapshot,
    current: MemorySnapshot,
    max_growth_mb: float = 25.0,
    max_percentage: float = 15.0,
):
    """Assertion helper verifying memory stability between two snapshots."""
    delta = current.diff(baseline)
    if delta.is_leaking(max_growth_mb=max_growth_mb, max_percentage=max_percentage):
        raise AssertionError(
            f"Memory instability assertion failed: RSS grew by {delta.rss_growth_mb:.2f} MB "
            f"({delta.growth_percentage:.1f}%), allowed max {max_growth_mb} MB"
        )
