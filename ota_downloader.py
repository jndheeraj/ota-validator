"""
ota_downloader.py — Step 2: Download Validation

Simulates downloading a firmware package and validates:
  1. Complete download — all bytes received
  2. Checksum verification — no corruption
  3. Corruption injection — detects tampered data
  4. Incomplete download — truncated file rejected
"""

import hashlib
import json
import random
import shutil
import time
from pathlib import Path

DOWNLOAD_DIR = Path("downloads")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def simulate_download(
    package_dir: Path,
    corrupt: bool = False,
    truncate: bool = False,
    corrupt_byte_count: int = 5
) -> dict:
    """
    Simulate downloading a firmware package.

    Args:
        package_dir:       source package to download
        corrupt:           inject random byte corruption
        truncate:          simulate incomplete download
        corrupt_byte_count: how many bytes to corrupt

    Returns:
        dict with download result and validation status
    """
    DOWNLOAD_DIR.mkdir(exist_ok=True)
    version     = package_dir.name
    dest_dir    = DOWNLOAD_DIR / version
    dest_dir.mkdir(exist_ok=True)

    result = {
        "version":        version,
        "source":         str(package_dir),
        "destination":    str(dest_dir),
        "corrupt":        corrupt,
        "truncate":       truncate,
        "steps":          []
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

    print(f"\n  Downloading {version}...")
    start = time.time()

    firmware_src  = package_dir / "firmware.bin"
    manifest_src  = package_dir / "manifest.json"
    signature_src = package_dir / "signature.bin"

    firmware_data  = firmware_src.read_bytes()
    manifest_data  = manifest_src.read_bytes()
    signature_data = signature_src.read_bytes()

    if truncate:
        truncate_at   = len(firmware_data) // 2
        firmware_data = firmware_data[:truncate_at]
        print(f"  [INJECTING] Truncated firmware to {len(firmware_data)} bytes")

    if corrupt:
        firmware_list = bytearray(firmware_data)
        corrupted_positions = random.sample(
            range(len(firmware_list)),
            min(corrupt_byte_count, len(firmware_list))
        )
        for pos in corrupted_positions:
            firmware_list[pos] = firmware_list[pos] ^ 0xFF
        firmware_data = bytes(firmware_list)
        print(f"  [INJECTING] Corrupted {corrupt_byte_count} bytes "
              f"at positions {corrupted_positions[:3]}...")

    (dest_dir / "firmware.bin").write_bytes(firmware_data)
    (dest_dir / "manifest.json").write_bytes(manifest_data)
    (dest_dir / "signature.bin").write_bytes(signature_data)

    elapsed = time.time() - start
    print(f"  Transfer complete in {elapsed*1000:.1f}ms")

    manifest = json.loads(manifest_data)

    expected_size = manifest["firmware_size"]
    actual_size   = len(firmware_data)
    size_ok       = actual_size == expected_size
    step(
        "size_check",
        size_ok,
        f"expected={expected_size} bytes  actual={actual_size} bytes"
    )

    if not size_ok:
        result["passed"] = False
        result["reject_reason"] = "incomplete download"
        print(f"\n  Download REJECTED — incomplete")
        return result

    expected_checksum = manifest["firmware_checksum"]
    actual_checksum   = sha256(firmware_data)
    checksum_ok       = actual_checksum == expected_checksum
    step(
        "checksum_verify",
        checksum_ok,
        f"expected={expected_checksum[:16]}...  "
        f"actual={actual_checksum[:16]}..."
    )

    if not checksum_ok:
        result["passed"] = False
        result["reject_reason"] = "checksum mismatch — corruption detected"
        print(f"\n  Download REJECTED — corruption detected")
        return result

    result["passed"] = True
    result["reject_reason"] = None
    print(f"\n  Download ACCEPTED — package integrity verified")
    return result


if __name__ == "__main__":
    from pathlib import Path

    print("\n OTA Downloader — Step 2: Download Validation")
    print("=" * 55)

    pkg = Path("packages/firmware-1.0.0")

    print("\nScenario 1: Clean download")
    print("-" * 40)
    r1 = simulate_download(pkg, corrupt=False, truncate=False)
    print(f"  Result: {'ACCEPTED' if r1['passed'] else 'REJECTED'}")

    print("\nScenario 2: Corrupted download")
    print("-" * 40)
    r2 = simulate_download(pkg, corrupt=True, truncate=False)
    print(f"  Result: {'ACCEPTED' if r2['passed'] else 'REJECTED'}")
    if not r2["passed"]:
        print(f"  Reason: {r2['reject_reason']}")

    print("\nScenario 3: Incomplete download")
    print("-" * 40)
    r3 = simulate_download(pkg, corrupt=False, truncate=True)
    print(f"  Result: {'ACCEPTED' if r3['passed'] else 'REJECTED'}")
    if not r3["passed"]:
        print(f"  Reason: {r3['reject_reason']}")

    print("\n" + "=" * 55)
    print("  All download scenarios complete")
