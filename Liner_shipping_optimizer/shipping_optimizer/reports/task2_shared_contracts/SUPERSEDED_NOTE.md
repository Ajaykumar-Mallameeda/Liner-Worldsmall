# Superseded items in this folder (added 2026-10-10)

- `changes.patch` is **not applicable**: paths are `a/a/…` / `b/b/…` and the last entry is a literal
  placeholder instead of the `tests/test_shared_contracts.py` diff. Use
  `../task1_reproducibility/changes_B0_to_M.patch` (applies to a fresh extraction of
  `Liner_shipping_optimizer.zip`, byte-identical result; see that folder's report).
- The "baseline (unmodified tree)" numbers here (258/264, six `profit > 0` failures, -146 M to -156 M)
  were measured on a tree that already carried the rewritten loader. Against the pristine zip the
  orchestrator passes 265/265 (+277 M weekly profit) because the zip loader inflates revenue about 4x.
  The six failures are a consequence of the unit-corrected loader, not of the original code.
- The statement that the zip is byte-identical to the working tree no longer holds.

No other file in this folder was modified.
