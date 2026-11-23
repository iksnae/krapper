# CRAP ceiling migration

## Acceptance

Every implementation function must score CRAP ≤5 using verified fresh branch coverage, including inherited code and CLI dispatch. No exemptions, suppression lists, lowered complexity counts, artificial branches or arbitrary extractions. Tests must check behavior and error handling. CI must enforce the same ceiling once the implementation actually satisfies it.

## Initial measurement

At `69bde7a`, 201 tests passed. Fresh branch coverage measured all 279 functions: 69 exceeded five, with maximum CRAP 23.0625. This supersedes the earlier statement-coverage baseline for this work.

## First implementation sweep

- Replace handwritten argument dispatch with standard-library argparse, preserving interspersed paths, repeated source roots and option conflict validation. Restore rejection of empty root paths, covered by a regression.
- Separate receipt inventory, checkout identity, report freshness and Swift target evidence checks. Add trust-boundary tests for missing/invalid targets, wrong-checkout evidence, empty regions, symlink escape and altered receipt identity.
- Separate Swift LLVM export decoding, line-region mapping and count aggregation; characterize carried regions, skipped lines, gap regions and malformed exports.
- Reuse existing source-path normalization and consolidate discovery's filename rules. Separate CLI selection, measurement and reporting while retaining centralized error status handling.
- Run branch-coverage self-analysis in CI. The five-point gate is deliberately not enabled yet: measurement passing is not a claim that the ceiling is met.

## Remaining work

Continue against the freshly measured ranked list, addressing language readers, coverage matching and legacy runner functions. Improve missing branch assertions where needed; simplify responsibilities where complexity itself is too high. Re-measure after each cohesive sweep. Add the strict `--threshold 5` CI gate only after every implementation function is measured and the maximum is ≤5. The task remains open until that gate passes in CI without exemptions.

## Validation commands

See README Development for the fresh source-bound branch-coverage command. Use `.venv/bin/python -m pytest -q` for focused iteration. Babashka is required for the inherited EDN integration test. CI performs the full measurement on Python 3.11 and 3.13.
