# OTA Update Validation Framework

End-to-end validation framework for embedded device OTA updates.
Simulates the complete firmware delivery pipeline with security
validation and automatic rollback on boot failure.

## Pipeline stages

| Stage | What happens |
|---|---|
| 1. Package creation | Firmware built, signed with RSA-2048, SHA256 checksum generated |
| 2. Download validation | Checksum verified - corruption and incomplete downloads rejected |
| 3. Signature verification | RSA-PSS signature validated - tampered packages rejected |
| 4. A/B partition flash | New firmware written to inactive slot - active slot untouched |
| 5. Boot validation | 5 system checks run - CAN, camera, network, processes |
| 6. Commit or rollback | Success commits update, failure triggers automatic rollback |

## Test results

| Scenario | Result | Rollback |
|---|---|---|
| Normal update v1.0.0 | PASS | no |
| Bad firmware v2.0.0 | PASS | YES - recovered to v1.0.0 |
| Corrupted download | PASS | no - rejected at checksum |
| Tampered package | PASS | no - rejected at signature |

## Security

- RSA-2048 PSS signing with SHA256
- SHA256 checksum per package
- Corruption injection testing
- Tamper detection testing
- Wrong-key rejection testing

## A/B partition

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
