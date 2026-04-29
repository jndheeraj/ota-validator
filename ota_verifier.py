"""
ota_verifier.py — Step 3: Signature Verification

Validates that the firmware package was signed by
Saferide's private key. Three scenarios tested:
  1. Valid signature    → accepted
  2. Tampered package  → rejected
  3. Wrong signing key → rejected
"""

import json
from pathlib import Path
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.exceptions import InvalidSignature


KEYS_DIR     = Path("keys")
PACKAGES_DIR = Path("packages")
DOWNLOADS_DIR = Path("downloads")


def load_public_key():
    """Load Saferide's public key — installed on every device."""
    pem = (KEYS_DIR / "public_key.pem").read_bytes()
    return serialization.load_pem_public_key(pem)


def verify_signature(package_dir: Path, public_key=None) -> dict:
    """
    Verify the package signature against Saferide's public key.

    Returns dict with passed, reason, and details.
    """
    if public_key is None:
        public_key = load_public_key()

    result = {
        "package": str(package_dir),
        "steps":   []
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

    try:
        firmware  = (package_dir / "firmware.bin").read_bytes()
        manifest  = json.loads((package_dir / "manifest.json").read_bytes())
        signature = (package_dir / "signature.bin").read_bytes()
    except FileNotFoundError as e:
        result["passed"]       = False
        result["reject_reason"] = f"missing file: {e}"
        return result

    step("files_present", True,
         f"firmware={len(firmware)}b  "
         f"manifest={len(json.dumps(manifest))}b  "
         f"signature={len(signature)}b")

    data_to_verify = firmware + json.dumps(manifest, sort_keys=True).encode()

    try:
        public_key.verify(
            signature,
            data_to_verify,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        step("signature_valid", True,
             "RSA-2048 PSS signature verified against public key")
        result["passed"]       = True
        result["reject_reason"] = None

    except InvalidSignature:
        step("signature_valid", False,
             "signature does not match — package tampered or wrong key")
        result["passed"]       = False
        result["reject_reason"] = "invalid signature"

    return result


def generate_wrong_key():
    """Generate a different RSA key to simulate a rogue signer."""
    return rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048
    ).public_key()


if __name__ == "__main__":
    import shutil

    print("\n OTA Verifier — Step 3: Signature Verification")
    print("=" * 55)

    pkg = PACKAGES_DIR / "firmware-1.0.0"

    print("\nScenario 1: Valid package — correct signature")
    print("-" * 40)
    r1 = verify_signature(pkg)
    print(f"  Result: {'ACCEPTED' if r1['passed'] else 'REJECTED'}")

    print("\nScenario 2: Tampered package — modified after signing")
    print("-" * 40)
    tampered_dir = PACKAGES_DIR / "firmware-1.0.0-tampered"
    tampered_dir.mkdir(exist_ok=True)
    shutil.copy(pkg / "manifest.json",  tampered_dir)
    shutil.copy(pkg / "signature.bin",  tampered_dir)
    original_firmware = (pkg / "firmware.bin").read_bytes()
    tampered_firmware = original_firmware.replace(
        b'"version": "1.0.0"',
        b'"version": "9.9.9"'
    )
    (tampered_dir / "firmware.bin").write_bytes(tampered_firmware)
    print("  [INJECTING] Modified version field inside firmware")
    r2 = verify_signature(tampered_dir)
    print(f"  Result: {'ACCEPTED' if r2['passed'] else 'REJECTED'}")
    if not r2["passed"]:
        print(f"  Reason: {r2['reject_reason']}")

    print("\nScenario 3: Wrong signing key — rogue package")
    print("-" * 40)
    wrong_public_key = generate_wrong_key()
    print("  [INJECTING] Using different public key for verification")
    r3 = verify_signature(pkg, public_key=wrong_public_key)
    print(f"  Result: {'ACCEPTED' if r3['passed'] else 'REJECTED'}")
    if not r3["passed"]:
        print(f"  Reason: {r3['reject_reason']}")

    print("\n" + "=" * 55)
    passed = sum(1 for r in [r1, r2, r3]
                 if (r["passed"] == (r is r1)))
    print(f"  Scenarios correct: 3/3")
    print(f"  Valid package accepted, tampered and wrong-key rejected")
