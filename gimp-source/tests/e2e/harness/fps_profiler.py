"""
Viewport Benchmarking & 60 FPS Profiling Tool for GIMP E2E Testing.
Measures frame rendering durations, average/min/max FPS, 95th & 99th percentile latency,
frame jitter (standard deviation), and dropped frame budgets for smooth 60 FPS canvas interactions.
"""

from __future__ import annotations

import math
import statistics
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterator, List, Optional, Union


@dataclass
class FrameMetrics:
    """Calculated metrics from a frame profiling session."""
    total_frames: int
    total_duration_sec: float
    avg_fps: float
    min_fps: float
    max_fps: float
    avg_frame_time_ms: float
    median_frame_time_ms: float
    p95_frame_time_ms: float
    p99_frame_time_ms: float
    jitter_ms: float  # standard deviation of frame times
    dropped_frames: int  # frames taking longer than budget (e.g., > 16.67ms)
    dropped_percentage: float
    target_budget_ms: float = 16.67
    raw_frame_times_ms: List[float] = field(default_factory=list, repr=False)

    @property
    def is_60fps_compliant(self) -> bool:
        """Checks if average FPS is at least 55 and p99 frame latency is <= 22.0ms."""
        return self.avg_fps >= 55.0 and self.p99_frame_time_ms <= 22.0 and self.dropped_percentage <= 10.0

    def to_dict(self) -> Dict[str, Union[int, float]]:
        return {
            "total_frames": self.total_frames,
            "total_duration_sec": round(self.total_duration_sec, 4),
            "avg_fps": round(self.avg_fps, 2),
            "min_fps": round(self.min_fps, 2),
            "max_fps": round(self.max_fps, 2),
            "avg_frame_time_ms": round(self.avg_frame_time_ms, 2),
            "median_frame_time_ms": round(self.median_frame_time_ms, 2),
            "p95_frame_time_ms": round(self.p95_frame_time_ms, 2),
            "p99_frame_time_ms": round(self.p99_frame_time_ms, 2),
            "jitter_ms": round(self.jitter_ms, 3),
            "dropped_frames": self.dropped_frames,
            "dropped_percentage": round(self.dropped_percentage, 2),
            "target_budget_ms": round(self.target_budget_ms, 2),
        }

    def summary_table(self) -> str:
        lines = [
            "----------------- VIEWPORT FPS BENCHMARK REPORT -----------------",
            f"  Total Frames Rendered   : {self.total_frames}",
            f"  Elapsed Benchmark Time  : {self.total_duration_sec:.3f} s",
            f"  Average Frame Rate      : {self.avg_fps:.2f} FPS (Target: 60.0 FPS)",
            f"  Min / Max Frame Rate    : {self.min_fps:.1f} / {self.max_fps:.1f} FPS",
            f"  Mean Frame Interval     : {self.avg_frame_time_ms:.2f} ms",
            f"  Median Frame Interval   : {self.median_frame_time_ms:.2f} ms",
            f"  95th Percentile Latency : {self.p95_frame_time_ms:.2f} ms",
            f"  99th Percentile Latency : {self.p99_frame_time_ms:.2f} ms",
            f"  Frame Jitter (Std Dev)  : {self.jitter_ms:.3f} ms",
            f"  Dropped Frames (>16.6ms): {self.dropped_frames} ({self.dropped_percentage:.1f}%)",
            f"  60 FPS Budget Compliant : {'[PASS]' if self.is_60fps_compliant else '[FAIL]'}",
            "-----------------------------------------------------------------",
        ]
        return "\n".join(lines)


class FPSProfiler:
    """
    Precision frame profiler utilizing high-resolution monotonic clocks.
    """

    def __init__(self, target_fps: float = 60.0):
        self.target_fps = target_fps
        self.target_budget_ms = 1000.0 / target_fps
        self.timestamps_ns: List[int] = []
        self._start_time_ns: Optional[int] = None
        self._is_running = False

    def start(self):
        """Starts a new profiling session."""
        self.timestamps_ns.clear()
        self._start_time_ns = time.perf_counter_ns()
        self.timestamps_ns.append(self._start_time_ns)
        self._is_running = True

    def record_frame(self, timestamp_ns: Optional[int] = None):
        """Records a completed frame event."""
        if not self._is_running:
            self.start()
            return
        ts = timestamp_ns if timestamp_ns is not None else time.perf_counter_ns()
        self.timestamps_ns.append(ts)

    @contextmanager
    def frame_context(self) -> Iterator[None]:
        """Context manager timing a single render pass."""
        t0 = time.perf_counter_ns()
        try:
            yield
        finally:
            t1 = time.perf_counter_ns()
            self.record_frame(t1)

    def stop(self) -> FrameMetrics:
        """Stops profiling and calculates comprehensive statistics."""
        self._is_running = False
        if len(self.timestamps_ns) < 2:
            return FrameMetrics(
                total_frames=len(self.timestamps_ns),
                total_duration_sec=0.0,
                avg_fps=0.0,
                min_fps=0.0,
                max_fps=0.0,
                avg_frame_time_ms=0.0,
                median_frame_time_ms=0.0,
                p95_frame_time_ms=0.0,
                p99_frame_time_ms=0.0,
                jitter_ms=0.0,
                dropped_frames=0,
                dropped_percentage=0.0,
                target_budget_ms=self.target_budget_ms,
                raw_frame_times_ms=[],
            )

        # Compute interval between consecutive frames
        intervals_ms = []
        for i in range(1, len(self.timestamps_ns)):
            delta_ns = self.timestamps_ns[i] - self.timestamps_ns[i - 1]
            intervals_ms.append(max(0.0001, delta_ns / 1_000_000.0))

        total_frames = len(intervals_ms)
        total_duration_sec = (self.timestamps_ns[-1] - self.timestamps_ns[0]) / 1_000_000_000.0
        avg_fps = (total_frames / total_duration_sec) if total_duration_sec > 0 else 0.0

        sorted_intervals = sorted(intervals_ms)
        avg_frame_time = statistics.mean(intervals_ms)
        median_frame_time = statistics.median(intervals_ms)
        jitter = statistics.stdev(intervals_ms) if len(intervals_ms) > 1 else 0.0

        def get_percentile(data: List[float], p: float) -> float:
            if not data:
                return 0.0
            idx = min(len(data) - 1, max(0, int(math.ceil(p * len(data))) - 1))
            return data[idx]

        p95 = get_percentile(sorted_intervals, 0.95)
        p99 = get_percentile(sorted_intervals, 0.99)

        min_interval = sorted_intervals[0]
        max_interval = sorted_intervals[-1]
        max_fps = (1000.0 / min_interval) if min_interval > 0 else 0.0
        min_fps = (1000.0 / max_interval) if max_interval > 0 else 0.0

        dropped = sum(1 for dt in intervals_ms if dt > self.target_budget_ms)
        dropped_pct = (dropped / total_frames * 100.0) if total_frames > 0 else 0.0

        return FrameMetrics(
            total_frames=total_frames,
            total_duration_sec=total_duration_sec,
            avg_fps=avg_fps,
            min_fps=min_fps,
            max_fps=max_fps,
            avg_frame_time_ms=avg_frame_time,
            median_frame_time_ms=median_frame_time,
            p95_frame_time_ms=p95,
            p99_frame_time_ms=p99,
            jitter_ms=jitter,
            dropped_frames=dropped,
            dropped_percentage=dropped_pct,
            target_budget_ms=self.target_budget_ms,
            raw_frame_times_ms=intervals_ms,
        )

    def benchmark_workload(
        self,
        iterations: int,
        workload_fn: Callable[..., None],
        *args,
        target_fps: float = 60.0,
        **kwargs,
    ) -> FrameMetrics:
        """
        Executes a callable across multiple iterations, recording each frame duration.
        """
        self.target_fps = target_fps
        self.target_budget_ms = 1000.0 / target_fps
        self.start()

        for _ in range(iterations):
            t0 = time.perf_counter_ns()
            workload_fn(*args, **kwargs)
            t1 = time.perf_counter_ns()
            self.record_frame(t1)

        return self.stop()


class ViewportBenchmark:
    """
    Simulation and profiling tool for GIMP canvas viewport operations
    such as pan, zoom, transform manipulation, and filter updates.
    """

    @staticmethod
    def simulate_canvas_pan(num_steps: int = 60, step_delay_sec: float = 0.016) -> FrameMetrics:
        """Simulates smooth inertial pan on the canvas viewport."""
        profiler = FPSProfiler(target_fps=60.0)
        profiler.start()

        for i in range(num_steps):
            t_frame_start = time.perf_counter()
            # Simulate canvas dirty region calculation and GSK node snapshot
            _ = [math.sin(i * 0.1 + j) * math.cos(j) for j in range(1500)]
            # Sleep remainder of frame time
            elapsed = time.perf_counter() - t_frame_start
            sleep_time = max(0.0, step_delay_sec - elapsed)
            time.sleep(sleep_time)
            profiler.record_frame()

        return profiler.stop()

    @staticmethod
    def simulate_canvas_zoom(num_steps: int = 60, step_delay_sec: float = 0.016) -> FrameMetrics:
        """Simulates smooth multi-touch pinch-to-zoom on the canvas viewport."""
        profiler = FPSProfiler(target_fps=60.0)
        profiler.start()

        for i in range(num_steps):
            t_frame_start = time.perf_counter()
            # Simulate matrix transformation and tile mipmap lookup
            scale = 1.0 + (i * 0.05)
            _ = [x * scale for x in range(2000)]
            elapsed = time.perf_counter() - t_frame_start
            sleep_time = max(0.0, step_delay_sec - elapsed)
            time.sleep(sleep_time)
            profiler.record_frame()

        return profiler.stop()


def assert_fps_budget(
    metrics: FrameMetrics,
    target_fps: float = 60.0,
    min_acceptable_fps: float = 55.0,
    max_p99_latency_ms: float = 22.0,
    max_dropped_percent: float = 10.0,
):
    """
    Asserts that the provided frame metrics satisfy 60 FPS performance criteria.
    """
    if metrics.avg_fps < min_acceptable_fps:
        raise AssertionError(
            f"FPS budget failure: Average frame rate {metrics.avg_fps:.2f} FPS fell below minimum "
            f"acceptable {min_acceptable_fps:.1f} FPS (Target: {target_fps} FPS)\n{metrics.summary_table()}"
        )

    if metrics.p99_frame_time_ms > max_p99_latency_ms:
        raise AssertionError(
            f"Latency budget failure: 99th percentile frame interval {metrics.p99_frame_time_ms:.2f} ms "
            f"exceeded maximum budget of {max_p99_latency_ms:.2f} ms\n{metrics.summary_table()}"
        )

    if metrics.dropped_percentage > max_dropped_percent:
        raise AssertionError(
            f"Dropped frame budget failure: Dropped frames {metrics.dropped_percentage:.1f}% "
            f"exceeded maximum allowed {max_dropped_percent:.1f}%\n{metrics.summary_table()}"
        )
