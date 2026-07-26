# Standalone refactor through prompt 07

> Historical note. The clipboard/text-export workflow described below was removed on
> 2026-07-26. The current application displays results for review only.

The runtime was reduced to local reader selection and manual scan. Remote integration and
the advanced browser surface were removed. The new config migrates an old JSON file by
preserving reader ID only and overwriting it with local-only settings; this is replacement,
not forensic erasure.

The current environment did not contain Python or pytest, so full automated and Windows hardware/build verification remains documented as pending.
