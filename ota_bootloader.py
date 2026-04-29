"""
ota_bootloader.py — Step 5: Boot Validation and Rollback

Simulates the boot validation process after an OTA update.
Two scenarios:
  1. New version boots successfully → commit update
  2. New version fails to boot     → automatic rollback to previous slot

This is the safety net that makes OTA updates recoverable.
A device in the field can never be permanently bricked
by a bad update as long as rollback works correctly.
"""

import json
import time
from pathlib import Path
from ota_partition import (
    get_active_slot, get_boot_config,
    simulate_reboot, rollback,
    print_partition_state, save_boot_config
)


MAX_BOOT_ATTEMPTS = 3


def commit_update():
    """
    Commit the update — mark current slot as permanently active.
    Called after successful boot validation.
    """
    config = get_boot_config()
    config["committed_slot"]  = config["active_slot"]
    config["committed_at"]    = time.strftime("%Y-%m-%dT%H:%M:%SZ")
    save_boot_config(config)
    print(f"  Update committed — slot {config['active_slot'].upper()} "
          f"is now permanent")


def validate_boot() -> dict:
    """
    Simulate boot validation after OTA update.

    Real validation would check:
    - Kernel boots without panic
    - Critical processes start
    - CAN bus initializes
    - Camera feeds come up
    - Network connectivity established

    We simulate by reading the boot_fail flag from firmware.
    """
    result = {
        "steps":            [],
        "rollback_triggered": False,
        "final_slot":       None,
        "final_version":    None
    }

    def step(name, passed, detail=""):
        result["steps"].append({
            "name":   name,
            "passed": passed,
            "detail": detail
        })
        status = "PASS" if passed else "FAIL"
        print(f"    [{status}] {name}")
        if detail:
            print(f"           {detail}")
        return passed

    print(f"  Simulating boot sequence...")
    time.sleep(0.1)

    boot = simulate_reboot()
    version    = boot["version"]
    boot_fail  = boot["boot_fail_flag"]
    booted_slot = boot["booted_slot"]

    step("kernel_load",
         not boot_fail,
         f"v{version} on slot {booted_slot.upper()}")

    if boot_fail:
        print(f"\n  Boot validation FAILED for v{version}")
        print(f"  Triggering automatic rollback...")
        previous_slot = rollback()
        result["rollback_triggered"] = True

        print(f"\n  Booting from previous slot {previous_slot.upper()}...")
        recovery_boot = simulate_reboot()

        step("rollback_boot",
             not recovery_boot["boot_fail_flag"],
             f"v{recovery_boot['version']} on slot "
             f"{recovery_boot['booted_slot'].upper()}")

        step("system_stable",
             not recovery_boot["boot_fail_flag"],
             "device recovered to last known good state")

        result["final_slot"]    = recovery_boot["booted_slot"]
        result["final_version"] = recovery_boot["version"]
        result["passed"]        = True
        return result

    time.sleep(0.05)
    step("critical_processes", True,
         "controlsd, modeld, sensord — all started")

    time.sleep(0.05)
    step("can_bus_init", True,
         "CAN interface can0 up — 500kbps")

    time.sleep(0.05)
    step("camera_feed", True,
         "road-facing camera stream active")

    time.sleep(0.05)
    step("network_check", True,
         "LTE connected — Quectel modem responsive")

    commit_update()
    result["final_slot"]    = booted_slot
    result["final_version"] = version
    result["passed"]        = True
    return result


if __name__ == "__main__":
    from ota_partition import (
        initialize_partitions, flash_package, mark_active
    )

    print("\n OTA Bootloader — Step 5: Boot Validation")
    print("=" * 55)

    print("\nScenario 1: Successful update — v1.0.0")
    print("-" * 40)
    initialize_partitions("0.9.0")
    flash_result = flash_package(Path("packages/firmware-1.0.0"))
    mark_active(flash_result["flashed_slot"])
    print_partition_state()
    print()
    r1 = validate_boot()
    print_partition_state()
    print(f"\n  Result: {'PASS' if r1['passed'] else 'FAIL'}")
    print(f"  Rollback: {r1['rollback_triggered']}")
    print(f"  Final:    v{r1['final_version']} on slot "
          f"{r1['final_slot'].upper()}")

    print("\n" + "=" * 55)
    print("\nScenario 2: Failed update — v2.0.0-bad triggers rollback")
    print("-" * 40)
    initialize_partitions("1.0.0")
    flash_result = flash_package(Path("packages/firmware-2.0.0-bad"))
    mark_active(flash_result["flashed_slot"])
    print_partition_state()
    print()
    r2 = validate_boot()
    print_partition_state()
    print(f"\n  Result: {'PASS' if r2['passed'] else 'FAIL'}")
    print(f"  Rollback: {r2['rollback_triggered']}")
    print(f"  Final:    v{r2['final_version']} on slot "
          f"{r2['final_slot'].upper()}")

    print("\n" + "=" * 55)
    print("  Boot validation complete")
