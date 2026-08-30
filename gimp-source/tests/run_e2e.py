#!/usr/bin/env python3
"""
E2E Test Runner for GIMP + PhotoGIMP Modernization & Gauntlet Loop.
Supports 5-tier test execution, feature filtering (F01-F19), headless Xvfb automation,
memory leak auditing, viewport FPS profiling, and structured reporting (Console, JSON, JUnit XML, TAP).
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import time
import unittest
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union

# Add tests directory and workspace root to sys.path
TESTS_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = TESTS_DIR.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from tests.e2e.harness.fps_profiler import FPSProfiler
from tests.e2e.harness.leak_checker import MemoryLeakChecker, get_process_memory_info
from tests.e2e.harness.xvfb_runner import XvfbContext, is_display_available


# ANSI Terminal Colors
class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    DIM = "\033[2m"
    RESET = "\033[0m"


@dataclass
class TestCaseResult:
    test_id: str
    tier: str
    feature: str
    status: str  # 'PASS', 'FAIL', 'ERROR', 'SKIP'
    duration_sec: float
    error_message: Optional[str] = None
    stack_trace: Optional[str] = None


class StructuredTestResult(unittest.TestResult):
    """
    Custom TestResult collector capturing timing, tier classifications,
    feature mappings, and failure traces.
    """

    def __init__(self, stream=None, descriptions=None, verbosity=1, progress_stream=None):
        super().__init__(stream=stream, descriptions=descriptions, verbosity=verbosity)
        self.verbosity = verbosity
        self.progress_stream = progress_stream or sys.stdout
        self.test_records: List[TestCaseResult] = []
        self._test_start_time: float = 0.0

    def startTest(self, test: unittest.TestCase):
        super().startTest(test)
        self._test_start_time = time.perf_counter()
        if self.verbosity >= 2:
            self.progress_stream.write(f"  • Running {test.id()}... ")
            self.progress_stream.flush()

    def _extract_tier_and_feature(self, test_id: str) -> Tuple[str, str]:
        tier = "Tier 1"
        if "tier2" in test_id or "boundaries" in test_id:
            tier = "Tier 2"
        elif "tier3" in test_id or "pairwise" in test_id:
            tier = "Tier 3"
        elif "tier4" in test_id or "realworld" in test_id:
            tier = "Tier 4"
        elif "tier5" in test_id or "adversarial" in test_id:
            tier = "Tier 5"
        elif "harness" in test_id:
            tier = "Harness"

        f_match = re.search(r"F\d{2}", test_id, re.IGNORECASE)
        feature = f_match.group(0).upper() if f_match else "General"
        return tier, feature

    def addSuccess(self, test: unittest.TestCase):
        super().addSuccess(test)
        dur = time.perf_counter() - self._test_start_time
        tier, feature = self._extract_tier_and_feature(test.id())
        self.test_records.append(
            TestCaseResult(test_id=test.id(), tier=tier, feature=feature, status="PASS", duration_sec=dur)
        )
        if self.verbosity >= 2:
            print(f"{Colors.GREEN}[PASS]{Colors.RESET} ({dur:.3f}s)", file=self.progress_stream)

    def addFailure(self, test: unittest.TestCase, err):
        super().addFailure(test, err)
        dur = time.perf_counter() - self._test_start_time
        tier, feature = self._extract_tier_and_feature(test.id())
        exc_msg = self._exc_info_to_string(err, test)
        self.test_records.append(
            TestCaseResult(
                test_id=test.id(),
                tier=tier,
                feature=feature,
                status="FAIL",
                duration_sec=dur,
                error_message=str(err[1]),
                stack_trace=exc_msg,
            )
        )
        if self.verbosity >= 2:
            print(f"{Colors.RED}[FAIL]{Colors.RESET} ({dur:.3f}s)", file=self.progress_stream)

    def addError(self, test: unittest.TestCase, err):
        super().addError(test, err)
        dur = time.perf_counter() - self._test_start_time
        tier, feature = self._extract_tier_and_feature(test.id())
        exc_msg = self._exc_info_to_string(err, test)
        self.test_records.append(
            TestCaseResult(
                test_id=test.id(),
                tier=tier,
                feature=feature,
                status="ERROR",
                duration_sec=dur,
                error_message=str(err[1]),
                stack_trace=exc_msg,
            )
        )
        if self.verbosity >= 2:
            print(f"{Colors.RED}[ERROR]{Colors.RESET} ({dur:.3f}s)", file=self.progress_stream)

    def addSkip(self, test: unittest.TestCase, reason: str):
        super().addSkip(test, reason)
        dur = time.perf_counter() - self._test_start_time
        tier, feature = self._extract_tier_and_feature(test.id())
        self.test_records.append(
            TestCaseResult(
                test_id=test.id(),
                tier=tier,
                feature=feature,
                status="SKIP",
                duration_sec=dur,
                error_message=reason,
            )
        )
        if self.verbosity >= 2:
            print(f"{Colors.YELLOW}[SKIP]{Colors.RESET} ({reason})", file=self.progress_stream)


def filter_suite(
    suite: unittest.TestSuite,
    tier_filter: Optional[str] = None,
    feature_filter: Optional[str] = None,
) -> unittest.TestSuite:
    """Filters discovered tests by tier or feature code."""
    new_suite = unittest.TestSuite()

    for item in suite:
        if isinstance(item, unittest.TestSuite):
            sub_suite = filter_suite(item, tier_filter=tier_filter, feature_filter=feature_filter)
            if sub_suite.countTestCases() > 0:
                new_suite.addTest(sub_suite)
        elif isinstance(item, unittest.TestCase):
            test_id = item.id()
            # Tier check
            tier_match = True
            if tier_filter and tier_filter.lower() != "all":
                t_str = f"tier{tier_filter.lower().replace('tier', '').strip()}"
                if t_str not in test_id.lower():
                    tier_match = False

            # Feature check
            feature_match = True
            if feature_filter and feature_filter.lower() != "all":
                f_code = feature_filter.upper()
                if f_code not in test_id.upper():
                    feature_match = False

            if tier_match and feature_match:
                new_suite.addTest(item)

    return new_suite


def generate_json_report(
    results: List[TestCaseResult],
    total_time: float,
    leak_info: Optional[Dict[str, Any]] = None,
    fps_info: Optional[Dict[str, Any]] = None,
) -> str:
    """Generates structured JSON report."""
    passed = sum(1 for r in results if r.status == "PASS")
    failed = sum(1 for r in results if r.status == "FAIL")
    errors = sum(1 for r in results if r.status == "ERROR")
    skipped = sum(1 for r in results if r.status == "SKIP")

    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "summary": {
            "total": len(results),
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "skipped": skipped,
            "pass_rate": round((passed / max(1, len(results) - skipped)) * 100.0, 2),
            "total_duration_sec": round(total_time, 3),
        },
        "memory_leak_audit": leak_info or {},
        "fps_profiler_audit": fps_info or {},
        "tests": [asdict(r) for r in results],
    }
    return json.dumps(report, indent=2)


def generate_junit_xml(results: List[TestCaseResult], total_time: float) -> str:
    """Generates JUnit XML compatible report."""
    testsuite = ET.Element("testsuite")
    testsuite.set("name", "GIMP-PhotoGIMP-E2E")
    testsuite.set("tests", str(len(results)))
    testsuite.set("failures", str(sum(1 for r in results if r.status == "FAIL")))
    testsuite.set("errors", str(sum(1 for r in results if r.status == "ERROR")))
    testsuite.set("skipped", str(sum(1 for r in results if r.status == "SKIP")))
    testsuite.set("time", f"{total_time:.3f}")

    for r in results:
        tc = ET.SubElement(testsuite, "testcase")
        tc.set("name", r.test_id)
        tc.set("classname", r.tier)
        tc.set("time", f"{r.duration_sec:.3f}")

        if r.status == "FAIL":
            fail_elem = ET.SubElement(tc, "failure")
            fail_elem.set("message", r.error_message or "Test failed")
            fail_elem.text = r.stack_trace or ""
        elif r.status == "ERROR":
            err_elem = ET.SubElement(tc, "error")
            err_elem.set("message", r.error_message or "Test error")
            err_elem.text = r.stack_trace or ""
        elif r.status == "SKIP":
            skip_elem = ET.SubElement(tc, "skipped")
            skip_elem.set("message", r.error_message or "Skipped")

    return ET.tostring(testsuite, encoding="unicode")


def generate_tap_report(results: List[TestCaseResult]) -> str:
    """Generates Test Anything Protocol (TAP) v13 report."""
    lines = ["TAP version 13", f"1..{len(results)}"]
    for idx, r in enumerate(results, start=1):
        if r.status == "PASS":
            lines.append(f"ok {idx} - {r.test_id}")
        elif r.status == "SKIP":
            lines.append(f"ok {idx} - {r.test_id} # SKIP {r.error_message}")
        else:
            lines.append(f"not ok {idx} - {r.test_id} # {r.error_message or 'Failed'}")
    return "\n".join(lines)


def print_console_summary(
    results: List[TestCaseResult],
    total_time: float,
    leak_delta_mb: float = 0.0,
    fps_metrics: Optional[Dict[str, Any]] = None,
):
    """Outputs colorized terminal summary."""
    passed = sum(1 for r in results if r.status == "PASS")
    failed = sum(1 for r in results if r.status == "FAIL")
    errors = sum(1 for r in results if r.status == "ERROR")
    skipped = sum(1 for r in results if r.status == "SKIP")
    total = len(results)

    print("\n" + "=" * 70)
    print(f" {Colors.BOLD}GIMP + PhotoGIMP Modernization — E2E Test Execution Summary{Colors.RESET}")
    print("=" * 70)

    # Group by tier
    tiers: Dict[str, Dict[str, int]] = {}
    for r in results:
        if r.tier not in tiers:
            tiers[r.tier] = {"PASS": 0, "FAIL": 0, "ERROR": 0, "SKIP": 0}
        tiers[r.tier][r.status] += 1

    print(f"\n{Colors.BOLD}{'Tier / Category':<25} {'Total':<8} {'Pass':<8} {'Fail':<8} {'Error':<8} {'Skip':<8}{Colors.RESET}")
    print("-" * 70)
    for t_name, counts in sorted(tiers.items()):
        p_str = f"{Colors.GREEN}{counts['PASS']}{Colors.RESET}" if counts["PASS"] > 0 else "0"
        f_str = f"{Colors.RED}{counts['FAIL']}{Colors.RESET}" if counts["FAIL"] > 0 else "0"
        e_str = f"{Colors.RED}{counts['ERROR']}{Colors.RESET}" if counts["ERROR"] > 0 else "0"
        s_str = f"{Colors.YELLOW}{counts['SKIP']}{Colors.RESET}" if counts["SKIP"] > 0 else "0"
        t_total = sum(counts.values())
        print(f"{t_name:<25} {t_total:<8} {p_str:<17} {f_str:<17} {e_str:<17} {s_str:<17}")

    print("-" * 70)
    print(
        f"Total Tests : {Colors.BOLD}{total}{Colors.RESET} | "
        f"Passed: {Colors.GREEN}{passed}{Colors.RESET} | "
        f"Failed: {Colors.RED}{failed}{Colors.RESET} | "
        f"Errors: {Colors.RED}{errors}{Colors.RESET} | "
        f"Skipped: {Colors.YELLOW}{skipped}{Colors.RESET}"
    )
    print(f"Total Execution Time : {total_time:.2f} s")
    print(f"Process Memory Delta : {leak_delta_mb:+.2f} MB (RSS)")

    if fps_metrics:
        print(f"Canvas Viewport FPS  : {fps_metrics.get('avg_fps', 0):.1f} FPS (p99: {fps_metrics.get('p99_frame_time_ms', 0):.1f} ms)")

    # Print failures details
    failures = [r for r in results if r.status in ("FAIL", "ERROR")]
    if failures:
        print(f"\n{Colors.RED}{Colors.BOLD}FAILURES & ERRORS ({len(failures)}):{Colors.RESET}")
        for f in failures:
            print(f"\n[{f.status}] {Colors.BOLD}{f.test_id}{Colors.RESET}")
            if f.error_message:
                print(f"  Message: {f.error_message}")
            if f.stack_trace:
                print(f"{Colors.DIM}{f.stack_trace}{Colors.RESET}")

    print("=" * 70 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="GIMP + PhotoGIMP E2E Test Suite Orchestrator & Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--tier",
        choices=["1", "2", "3", "4", "all"],
        default="all",
        help="Filter execution by test tier (1: Features, 2: Boundaries, 3: Pairwise, 4: Real-world, all: All)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all tiers (equivalent to --tier all)",
    )
    parser.add_argument(
        "--feature",
        type=str,
        default="all",
        help="Filter execution by feature code (e.g. F01, F11, F11_FREE_TRANSFORM, all)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=True,
        help="Run GUI tests in headless Xvfb virtual frame buffer (default: True)",
    )
    parser.add_argument(
        "--no-headless",
        action="store_false",
        dest="headless",
        help="Run tests directly against active desktop display without Xvfb",
    )
    parser.add_argument(
        "--check-leaks",
        action="store_true",
        default=False,
        help="Perform process memory leak auditing during test suite execution",
    )
    parser.add_argument(
        "--profile-fps",
        action="store_true",
        default=False,
        help="Run viewport 60 FPS performance benchmark during suite execution",
    )
    parser.add_argument(
        "--output-format",
        choices=["console", "json", "junit", "tap"],
        default="console",
        help="Structured report format (default: console)",
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        default=None,
        help="Save report output to specified file path",
    )
    parser.add_argument(
        "--pattern",
        type=str,
        default="test_*.py",
        help="Pattern to match test filenames during discovery (default: test_*.py)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="count",
        default=1,
        help="Increase output verbosity (-v for standard, -vv for per-test output)",
    )
    parser.add_argument(
        "-f", "--failfast",
        action="store_true",
        default=False,
        help="Stop test execution on first failure or error",
    )

    args = parser.parse_args()

    # Discover tests
    loader = unittest.TestLoader()
    start_dir = str(TESTS_DIR / "e2e")
    if not os.path.exists(start_dir):
        start_dir = str(TESTS_DIR)

    full_suite = loader.discover(start_dir=start_dir, pattern=args.pattern, top_level_dir=str(TESTS_DIR.parent))
    suite = filter_suite(full_suite, tier_filter=args.tier, feature_filter=args.feature)

    total_discovered = suite.countTestCases()
    diag_stream = sys.stdout if args.output_format == "console" else sys.stderr
    if args.verbose >= 1:
        print(
            f"{Colors.CYAN}[>] Discovered {total_discovered} test cases matching filters (Tier: {args.tier}, Feature: {args.feature}){Colors.RESET}",
            file=diag_stream,
        )

    # Set up memory leak auditing
    leak_checker = None
    if args.check_leaks:
        leak_checker = MemoryLeakChecker()
        leak_checker.start("suite_start")

    # Set up headless Xvfb environment context if requested
    use_xvfb = args.headless and not is_display_available()
    t_start = time.perf_counter()

    with XvfbContext(force_xvfb=use_xvfb):
        progress_stream = sys.stdout if args.output_format == "console" else sys.stderr
        runner_result = StructuredTestResult(verbosity=args.verbose, progress_stream=progress_stream)
        if args.failfast:
            runner_result.failfast = True

        suite.run(runner_result)

    t_duration = time.perf_counter() - t_start

    # Leak metrics
    leak_info = None
    leak_delta_mb = 0.0
    if leak_checker:
        leak_checker.take_snapshot("suite_end")
        delta = leak_checker.get_delta()
        leak_delta_mb = delta.rss_growth_mb
        leak_info = {
            "rss_start_mb": round(leak_checker.get_baseline().rss_mb, 2),
            "rss_end_mb": round(leak_checker.get_latest().rss_mb, 2),
            "rss_growth_mb": round(delta.rss_growth_mb, 2),
            "growth_percentage": round(delta.growth_percentage, 2),
            "is_leaking": delta.is_leaking(),
        }

    # FPS metrics
    fps_info = None
    if args.profile_fps:
        profiler = FPSProfiler(target_fps=60.0)
        from tests.e2e.harness.fps_profiler import ViewportBenchmark
        bench_metrics = ViewportBenchmark.simulate_canvas_pan(num_steps=60)
        fps_info = bench_metrics.to_dict()

    # Reporting
    if args.output_format == "console":
        print_console_summary(runner_result.test_records, t_duration, leak_delta_mb=leak_delta_mb, fps_metrics=fps_info)
    elif args.output_format == "json":
        json_out = generate_json_report(runner_result.test_records, t_duration, leak_info=leak_info, fps_info=fps_info)
        if args.output_file:
            args.output_file.parent.mkdir(parents=True, exist_ok=True)
            args.output_file.write_text(json_out, encoding="utf-8")
        else:
            print(json_out)
    elif args.output_format == "junit":
        xml_out = generate_junit_xml(runner_result.test_records, t_duration)
        if args.output_file:
            args.output_file.parent.mkdir(parents=True, exist_ok=True)
            args.output_file.write_text(xml_out, encoding="utf-8")
        else:
            print(xml_out)
    elif args.output_format == "tap":
        tap_out = generate_tap_report(runner_result.test_records)
        if args.output_file:
            args.output_file.parent.mkdir(parents=True, exist_ok=True)
            args.output_file.write_text(tap_out, encoding="utf-8")
        else:
            print(tap_out)

    has_failures = any(r.status in ("FAIL", "ERROR") for r in runner_result.test_records)
    sys.exit(1 if has_failures else 0)


if __name__ == "__main__":
    main()
