# 2026-07-21 — Fix Test Failures

## Goal

Resolve the six failing unit tests caused by stale test assertions, modified launcher tick counts, altered signature-verification handling, and missing/deleted text-export fixtures.

## Context

Recent launcher, signature-verification, trust-store, and documentation cleanup changes left some test cases out of sync.

## Assumptions

- Stale/outdated assertions should be updated to align with the correct, strict production verification behaviors.
- Restoring the deleted documentation prompt pack solely for tests is not appropriate; instead, tests should own their fixtures under a stable location.

## Decisions

- **Launcher clock test:** Incremented the fake clock sequence to include an extra tick, allowing the grace-period loop to enter exactly once and verify one sleep.
- **Invalid certificate status:** Changed the assertion in `test_parse_rc2_residence_card_business_fields` from `certificate_unavailable` to `certificate_invalid` to properly reflect that the certificate is present but synthetically invalid.
- **Tampered printed entries:** Modified `test_tampered_printed_entries_fail_verification` to replace a specific authenticated value inside `PRINTED_ENTRIES` rather than wiping all TLV formatting, maintaining the expected 53-byte structure.
- **Unknown CA assertion:** Corrected `test_certificate_issued_by_an_unknown_ca_is_not_trusted` to expect `signature_verified` to be `None` rather than `False` since signatures are not verified when the certificate chain is untrusted.
- **Stable fixtures:** Restored the single and multi-card golden text-export fixtures to a new stable test directory (`tests/fixtures/text_export/`) and modified `tests/test_text_export.py` to resolve paths relative to `__file__`. Updated the expected labels from the old `署名検証: 確認済み` to the current `真正性確認: 確認済み` format to match the localized i18n changes in the codebase.

## Files changed

- [tests/test_launcher.py](../../tests/test_launcher.py)
- [tests/test_second_generation_fields.py](../../tests/test_second_generation_fields.py)
- [tests/test_signature.py](../../tests/test_signature.py)
- [tests/test_text_export.py](../../tests/test_text_export.py)
- [tests/fixtures/text_export/single_card_expected.txt](../../tests/fixtures/text_export/single_card_expected.txt)
- [tests/fixtures/text_export/multi_card_expected.txt](../../tests/fixtures/text_export/multi_card_expected.txt)

## Checks run

None (the sandbox container has no Python dependencies/packages installed for running `pytest`).

## Checks skipped

- Complete `pytest` suite execution.
- Windows build verification script `scripts\build_windows.ps1`.
- Node.js check on `static/local.js`.

## Results

Manual code alignment and resolution of the stale assertions, matching the exact specifications described in `docs/prompts/fix.md`.

## Risks / follow-up

Ensure that when the Windows build or full tests run on the host system, they pass successfully.

## Suggested next step

Run `scripts\build_windows.ps1` on a compatible Windows host to verify that all 271 tests pass successfully and the packaging succeeds.
