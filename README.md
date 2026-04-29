# OTA Update Validation Framework

End-to-end validation framework for embedded device OTA updates.
Simulates the complete firmware delivery pipeline with security
validation and automatic rollback on boot failure.

## Pipeline
Package creation → Download validation → Signature verification
↓                   ↓                      ↓
RSA-2048 signing   SHA256 checksum        RSA-PSS verify
↓
A/B partition flash → Boot validation → Commit or rollback
↓                   ↓                   ↓
Inactive slot       5 system checks    Auto-recovery

## Test results

| Scenario | Result | Rollback |
|---|---|---|
| Normal update v1.0.0 | PASS | no |
| Bad firmware v2.0.0 | PASS | YES — recovered to v1.0.0 |
| Corrupted download | PASS | no — rejected at checksum |
| Tampered package | PASS | no — rejected at signature |

## Security

- RSA-2048 PSS signing with SHA256
- SHA256 checksum per package
- Corruption injection testing
- Tamper detection testing
- Wrong-key rejection testing

## A/B Partition

Device always runs from one slot while the other receives
the update. Bad update triggers automatic rollback to last
known good state. Device can never be permanently bricked.

## Files

| File | Purpose |
|---|---|
| `ota_packager.py` | Creates and signs firmware packages |
| `ota_downloader.py` | Validates download integrity |
| `ota_verifier.py` | Verifies RSA signatures |
| `ota_partition.py` | A/B partition management |
| `ota_bootloader.py` | Boot validation and rollback |
| `ota_validator.py` | Full pipeline orchestrator |

## Run locally

```bash
python3 -m venv venv
source venv/bin/activate
pip install cryptography
python3 ota_validator.py
```
