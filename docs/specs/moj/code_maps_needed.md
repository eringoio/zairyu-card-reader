# MOJ Code Maps Needed

The RC2 parser now preserves raw chip codes and adds best-effort labels for fields that have a safe local mapping.

Current implemented mappings:

- `nationality_code`: ISO alpha-3 country/region labels loaded from `resources/moj/trust-anchors/countries/countries_ja.json`; unknown codes remain explicit as `Unmapped nationality/region code: <code>`.
- `period_of_stay_raw`: interpreted as `0000` = indefinite, four digits = `YYMM`, and three digits = days.
- `residence_status_code`: preserved as raw code and shown with an explicit unmapped-code label.

The repository still needs an official or otherwise verified source for the full Japanese residence-status and period-code masters before the UI should display those values as authoritative human-readable statuses. Until then, unknown codes must be shown as `Unmapped ... code: <raw>` rather than as final labels.

Do not add code maps from guesses, personal card screenshots, raw APDU/TLV dumps, or unverified examples.
