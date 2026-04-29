"""
ota_validator.py — Step 6: Full OTA Validation Orchestrator

Runs the complete OTA validation pipeline end-to-end:
  1. Package creation and signing
  2. Download with integrity validation
  3. Signature verification
  4. A/B partition management
  5. Boot validation and rollback
  6. Structured report generation

This is what a CI/CD pipeline would run on every
firmware release before pushing to devices in the field.
"""

import json
import time
import shutil
from pathlib import Path

from ota_packager   import create_package
from ota_downloader import simulate_download
from ota_verifier   import verify_signature
from ota_partition  import (
    initialize_partitions, flash_package,
    mark_active, print_partition_state
)
from ota_bootloader import validate_boot

REPORTS_DIR = Path("reports")
REPORTS_DIR.mkdir(exist_ok=True)


def run_validation(
    version: str,
    force_boot_fail:    bool = False,
    inject_corruption:  bool = False,
    inject_truncation:  bool = False,
    inject_tamper:      bool = False,
    initial_version:    str  = "0.9.0"
) -> dict:
    """
    Run complete OTA validation for one firmware version.

    Args:
        version:           firmware version to validate
        force_boot_fail:   simulate boot failure
        inject_corruption: corrupt the download
        inject_truncation: truncate the download
        inject_tamper:     tamper with firmware after signing
        initial_version:   version already on device
    """
    report = {
        "version":       version,
        "started_at":    time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "scenarios":     {},
        "overall_pass":  True,
        "summary":       {}
    }

    total_steps  = 0
    passed_steps = 0

    def section(title):
        print(f"\n{'─'*55}")
        print(f"  {title}")
        print(f"{'─'*55}")

    def record(name, result, expected_pass=True):
        nonlocal total_steps, passed_steps
        passed = result.get("passed", False)
        correct = (passed == expected_pass)
        total_steps  += 1
        passed_steps += 1 if correct else 0
        report["scenarios"][name] = {
            "passed":        passed,
            "correct":       correct,
            "expected_pass": expected_pass,
            "result":        result
        }
        if not correct:
            report["overall_pass"] = False
        return result

    section("Step 1 — Package Creation")
    pkg_dir = create_package(version, force_boot_fail=force_boot_fail)
    record("package_creation", {"passed": pkg_dir.exists()})

    section("Step 2 — Download Validation")
    if inject_tamper:
        tampered_dir = Path("packages") / f"{pkg_dir.name}-tampered"
        tampered_dir.mkdir(exist_ok=True)
        shutil.copy(pkg_dir / "manifest.json", tampered_dir)
        shutil.copy(pkg_dir / "signature.bin", tampered_dir)
        original = (pkg_dir / "firmware.bin").read_bytes()
        tampered = original.replace(
            f'"version": "{version}"'.encode(),
            b'"version": "HACKED"'
        )
        (tampered_dir / "firmware.bin").write_bytes(tampered)
        verify_pkg = tampered_dir
        print("  [INJECTING] Package tampered after signing")
    else:
        verify_pkg = pkg_dir

    dl_result = simulate_download(
        pkg_dir,
        corrupt=inject_corruption,
        truncate=inject_truncation
    )
    expected_dl_pass = not (inject_corruption or inject_truncation)
    record("download_validation", dl_result, expected_pass=expected_dl_pass)

    if not dl_result["passed"]:
        print(f"\n  Pipeline stopped — download rejected")
        print(f"  Reason: {dl_result.get('reject_reason', 'unknown')}")
        report["stopped_at"]  = "download"
        report["stop_reason"] = dl_result.get("reject_reason")
        _finalize_report(report, total_steps, passed_steps, version)
        return report

    section("Step 3 — Signature Verification")
    sig_result = verify_signature(verify_pkg)
    expected_sig_pass = not inject_tamper
    record("signature_verification", sig_result,
           expected_pass=expected_sig_pass)

    if not sig_result["passed"]:
        print(f"\n  Pipeline stopped — signature invalid")
        print(f"  Reason: {sig_result.get('reject_reason', 'unknown')}")
        report["stopped_at"]  = "signature"
        report["stop_reason"] = sig_result.get("reject_reason")
        _finalize_report(report, total_steps, passed_steps, version)
        return report

    section("Step 4 — A/B Partition Flash")
    initialize_partitions(initial_version)
    flash_result = flash_package(pkg_dir)
    mark_active(flash_result["flashed_slot"])
    print_partition_state()
    record("partition_flash", flash_result)

    section("Step 5 — Boot Validation")
    boot_result = validate_boot()
    record("boot_validation", boot_result)
    print_partition_state()

    _finalize_report(report, total_steps, passed_steps, version)
    report["rollback_triggered"] = boot_result.get(
        "rollback_triggered", False)
    report["final_version"]      = boot_result.get("final_version")
    report["final_slot"]         = boot_result.get("final_slot")
    return report


def _finalize_report(report, total_steps, passed_steps, version):
    """Add summary stats and save report to disk."""
    report["completed_at"]  = time.strftime("%Y-%m-%dT%H:%M:%SZ")
    report["total_steps"]   = total_steps
    report["passed_steps"]  = passed_steps
    report["summary"] = {
        "total_steps":   total_steps,
        "passed_steps":  passed_steps,
        "pass_rate_pct": round(
            passed_steps / total_steps * 100 if total_steps else 0, 1),
        "overall_pass":  report["overall_pass"]
    }

    report_path = REPORTS_DIR / f"ota_report_{version}.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    report["report_path"] = str(report_path)


def print_final_summary(results: list):
    """Print a clean summary table of all validation runs."""
    print(f"\n{'='*55}")
    print(f"  OTA VALIDATION SUMMARY")
    print(f"{'='*55}")
    print(f"  {'Scenario':<35} {'Result':<10} {'Rollback'}")
    print(f"  {'─'*35} {'─'*10} {'─'*8}")

    for r in results:
        version   = r["version"]
        passed    = r["overall_pass"]
        rollback  = r.get("rollback_triggered", False)
        status    = "PASS" if passed else "FAIL"
        rb_str    = "YES" if rollback else "no"
        print(f"  {version:<35} {status:<10} {rb_str}")

    print(f"{'='*55}")
    all_pass = all(r["overall_pass"] for r in results)
    print(f"  Overall: {'ALL PASS' if all_pass else 'FAILURES DETECTED'}")
    print(f"  Reports: {REPORTS_DIR}/")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    print("\n" + "="*55)
    print("  OTA Validation Framework — Full Pipeline")
    print("="*55)

    results = []

    print("\n\nTEST 1: Normal update — should succeed")
    r1 = run_validation("1.0.0", initial_version="0.9.0")
    results.append(r1)

    print("\n\nTEST 2: Bad firmware — should rollback")
    r2 = run_validation("2.0.0-bad",
                        force_boot_fail=True,
                        initial_version="1.0.0")
    results.append(r2)

    print("\n\nTEST 3: Corrupted download — should reject at download")
    r3 = run_validation("1.0.0",
                        inject_corruption=True,
                        initial_version="0.9.0")
    results.append(r3)

    print("\n\nTEST 4: Tampered package — should reject at signature")
    r4 = run_validation("1.0.0",
                        inject_tamper=True,
                        initial_version="0.9.0")
    results.append(r4)

    print_final_summary(results)
