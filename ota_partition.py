"""
ota_partition.py — Step 4: A/B Partition Management

Simulates the A/B partition system used by OpenPilot,
Android, and all serious embedded OTA systems.

Two slots exist at all times:
  Slot A — currently running version (never touched during update)
  Slot B — receives the new version

Device always boots from one slot while the other is updated.
This means the device is never in a broken state mid-update.
"""

import json
import shutil
import time
from pathlib import Path


SLOTS_DIR   = Path("slots")
SLOT_A      = SLOTS_DIR / "slot_a"
SLOT_B      = SLOTS_DIR / "slot_b"
BOOT_CONFIG = SLOTS_DIR / "boot_config.json"


def initialize_partitions(initial_version: str = "0.9.0"):
    """
    Set up initial A/B partition state.
    Slot A gets the current running version.
    Slot B starts empty.
    Called once at device manufacture.
    """
    SLOTS_DIR.mkdir(exist_ok=True)
    SLOT_A.mkdir(exist_ok=True)
    SLOT_B.mkdir(exist_ok=True)

    initial_firmware = json.dumps({
        "version":    initial_version,
        "installed":  time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "boot_fail":  False,
        "data":       "A" * 512
    }, indent=2).encode()

    (SLOT_A / "firmware.bin").write_bytes(initial_firmware)
    (SLOT_A / "version.txt").write_text(initial_version)
    (SLOT_B / "version.txt").write_text("empty")

    boot_config = {
        "active_slot":        "a",
        "slot_a_version":     initial_version,
        "slot_b_version":     "empty",
        "slot_a_boot_count":  0,
        "slot_b_boot_count":  0,
        "last_updated":       time.strftime("%Y-%m-%dT%H:%M:%SZ")
    }
    BOOT_CONFIG.write_text(json.dumps(boot_config, indent=2))

    print(f"  Partitions initialized")
    print(f"  Slot A: v{initial_version} (active)")
    print(f"  Slot B: empty")
    return boot_config


def get_boot_config() -> dict:
    """Read current boot configuration."""
    return json.loads(BOOT_CONFIG.read_text())


def save_boot_config(config: dict):
    """Save boot configuration."""
    config["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
    BOOT_CONFIG.write_text(json.dumps(config, indent=2))


def get_active_slot() -> str:
    """Return which slot is currently active: 'a' or 'b'."""
    return get_boot_config()["active_slot"]


def get_inactive_slot() -> str:
    """Return the slot NOT currently running — this gets the update."""
    return "b" if get_active_slot() == "a" else "a"


def flash_package(package_dir: Path) -> dict:
    """
    Flash new firmware to the inactive slot.
    The active slot is never touched — device keeps running.

    This is the core safety guarantee of A/B partitions.
    """
    inactive = get_inactive_slot()
    slot_dir = SLOT_A if inactive == "a" else SLOT_B

    manifest = json.loads((package_dir / "manifest.json").read_text())
    version  = manifest["version"]

    print(f"  Active slot:    {get_active_slot().upper()} "
          f"(running — untouched)")
    print(f"  Flashing to:    slot {inactive.upper()}")

    shutil.copy(package_dir / "firmware.bin", slot_dir / "firmware.bin")
    shutil.copy(package_dir / "manifest.json", slot_dir / "manifest.json")
    (slot_dir / "version.txt").write_text(version)

    config = get_boot_config()
    if inactive == "a":
        config["slot_a_version"] = version
    else:
        config["slot_b_version"] = version
    save_boot_config(config)

    print(f"  Flash complete: v{version} written to slot {inactive.upper()}")
    return {
        "flashed_slot":   inactive,
        "version":        version,
        "slot_dir":       str(slot_dir),
        "passed":         True
    }


def mark_active(slot: str):
    """
    Mark a slot as the next boot target.
    Called after successful flash — before reboot.
    """
    config = get_boot_config()
    config["active_slot"] = slot
    save_boot_config(config)
    print(f"  Boot config updated: will boot from slot {slot.upper()}")


def simulate_reboot() -> dict:
    """
    Simulate device reboot — reads boot config and loads firmware.
    Returns the firmware that would run after reboot.
    """
    config   = get_boot_config()
    slot     = config["active_slot"]
    slot_dir = SLOT_A if slot == "a" else SLOT_B

    firmware_path = slot_dir / "firmware.bin"
    firmware      = json.loads(firmware_path.read_bytes())

    if slot == "a":
        config["slot_a_boot_count"] += 1
    else:
        config["slot_b_boot_count"] += 1
    save_boot_config(config)

    print(f"  Booting from slot {slot.upper()}: v{firmware['version']}")
    return {
        "booted_slot":    slot,
        "version":        firmware["version"],
        "boot_fail_flag": firmware.get("boot_fail", False),
        "firmware":       firmware
    }


def rollback():
    """
    Roll back to the previous slot.
    Called when new version fails to boot.
    """
    config          = get_boot_config()
    current         = config["active_slot"]
    previous        = "a" if current == "b" else "b"
    config["active_slot"] = previous
    save_boot_config(config)
    print(f"  ROLLBACK: slot {current.upper()} → slot {previous.upper()}")
    return previous


def print_partition_state():
    """Print current state of both partitions."""
    config = get_boot_config()
    active = config["active_slot"]
    print(f"\n  Partition state:")
    print(f"    Slot A: v{config['slot_a_version']:<12} "
          f"{'← ACTIVE' if active == 'a' else ''}")
    print(f"    Slot B: v{config['slot_b_version']:<12} "
          f"{'← ACTIVE' if active == 'b' else ''}")


if __name__ == "__main__":
    print("\n OTA Partition Manager — Step 4: A/B Partitions")
    print("=" * 55)

    print("\n  Initializing partitions...")
    initialize_partitions("0.9.0")
    print_partition_state()

    print("\n  Flashing new firmware to inactive slot...")
    flash_result = flash_package(Path("packages/firmware-1.0.0"))
    print_partition_state()

    print("\n  Marking new slot as active...")
    mark_active(flash_result["flashed_slot"])
    print_partition_state()

    print("\n  Simulating reboot...")
    boot = simulate_reboot()
    print(f"  Running: v{boot['version']} on slot {boot['booted_slot'].upper()}")
    print_partition_state()

    print("\n" + "=" * 55)
    print("  A/B partition simulation complete")
