"""
ota_packager.py — Step 1: Firmware Package Creation and Signing

Creates a signed firmware package ready for OTA delivery.
Simulates what Saferide's build system would produce before
pushing an update to devices in the field.

Package structure:
  package/
  ├── firmware.bin      ← the actual firmware payload
  ├── manifest.json     ← version, checksum, metadata
  └── signature.bin     ← RSA signature of manifest + firmware
"""

import os
import json
import hashlib
import time
from pathlib import Path
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding

KEYS_DIR     = Path("keys")
PACKAGES_DIR = Path("packages")


def generate_keys():
    """Generate RSA-2048 key pair and save to disk."""
    KEYS_DIR.mkdir(exist_ok=True)

    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048
    )

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption()
    )

    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )

    (KEYS_DIR / "private_key.pem").write_bytes(private_pem)
    (KEYS_DIR / "public_key.pem").write_bytes(public_pem)

    print(f"  Generated RSA-2048 key pair")
    print(f"  Private key: {KEYS_DIR}/private_key.pem")
    print(f"  Public key:  {KEYS_DIR}/public_key.pem")
    return private_key


def load_private_key():
    """Load existing private key from disk."""
    pem = (KEYS_DIR / "private_key.pem").read_bytes()
    return serialization.load_pem_private_key(pem, password=None)


def create_firmware(version: str, force_boot_fail: bool = False) -> bytes:
    """
    Create a fake firmware binary payload.
    In production this would be a real Linux kernel image.
    """
    payload = {
        "version":        version,
        "build_time":     time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "target":         "saferide-device-v1",
        "boot_fail":      force_boot_fail,
        "data":           "A" * 1024
    }
    return json.dumps(payload, indent=2).encode()


def sha256(data: bytes) -> str:
    """Generate SHA256 checksum of data."""
    return hashlib.sha256(data).hexdigest()


def sign_package(private_key, firmware: bytes, manifest: dict) -> bytes:
    """
    Sign the firmware + manifest using RSA-PSS.
    This proves the package came from Saferide and was not tampered with.
    """
    data_to_sign = firmware + json.dumps(manifest, sort_keys=True).encode()
    signature = private_key.sign(
        data_to_sign,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256()
    )
    return signature


def create_package(version: str, force_boot_fail: bool = False) -> Path:
    """
    Create a complete signed firmware package.
    Returns the path to the package directory.
    """
    print(f"\n{'='*55}")
    print(f"  Creating firmware package v{version}")
    print(f"{'='*55}")

    PACKAGES_DIR.mkdir(exist_ok=True)
    package_dir = PACKAGES_DIR / f"firmware-{version}"
    package_dir.mkdir(exist_ok=True)

    if not (KEYS_DIR / "private_key.pem").exists():
        print("\n  Generating new key pair...")
        private_key = generate_keys()
    else:
        print("\n  Loading existing key pair...")
        private_key = load_private_key()

    print("\n  Building firmware payload...")
    firmware = create_firmware(version, force_boot_fail)
    firmware_checksum = sha256(firmware)
    print(f"  Firmware size:     {len(firmware):,} bytes")
    print(f"  Firmware checksum: {firmware_checksum[:16]}...")

    manifest = {
        "version":           version,
        "firmware_checksum": firmware_checksum,
        "firmware_size":     len(firmware),
        "created_at":        time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "target_device":     "saferide-device-v1",
        "force_boot_fail":   force_boot_fail
    }

    print("\n  Signing package...")
    signature = sign_package(private_key, firmware, manifest)
    print(f"  Signature size:    {len(signature)} bytes")
    print(f"  Algorithm:         RSA-2048 PSS + SHA256")

    (package_dir / "firmware.bin").write_bytes(firmware)
    (package_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2)
    )
    (package_dir / "signature.bin").write_bytes(signature)

    print(f"\n  Package saved to: {package_dir}/")
    print(f"  Files:")
    for f in sorted(package_dir.iterdir()):
        print(f"    {f.name:<20} {f.stat().st_size:>8,} bytes")

    print(f"\n  Package v{version} created successfully")
    return package_dir


if __name__ == "__main__":
    print("\n OTA Packager — Step 1: Package Creation")

    pkg = create_package("1.0.0")
    print(f"\n  Normal package:      {pkg}")

    pkg_fail = create_package("2.0.0-bad", force_boot_fail=True)
    print(f"  Boot-fail package:   {pkg_fail}")

    print("\n  Done. Packages ready for OTA delivery.")
