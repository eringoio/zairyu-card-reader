# Standalone refactor through prompt 07

The runtime was reduced to local reader selection, manual scan, and fixed text copy. Remote integration and the advanced browser surface were removed. The new config migrates an old JSON file by preserving reader ID only and overwriting it with local-only settings; this is replacement, not forensic erasure.

Copy text is generated only on the backend from an allowlisted raw-field input and backend-derived display values. It has the fixed 17-field order, is batch-capable, and rejects unsupported/forbidden content before output.

The current environment did not contain Python or pytest, so full automated and Windows hardware/build verification remains documented as pending.
