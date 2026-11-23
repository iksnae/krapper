# Coverage integrity

The operator selected strict verification by default. Preserve the existing per-language metrics and EDN shape; change admission of coverage, not the CRAP formula.

## Contract

The CLI accepts coverage for scoring only with a versioned receipt bound to the same checkout, unchanged non-generated inputs and unchanged recognized report inventory/content. An explicit successful coverage command creates the receipt only when all reports were regenerated during the run and inputs stayed unchanged. Failed attempts invalidate the prior receipt, preserving the previous score snapshot without presenting it as current evidence. Verification runs before and after analysis.

Swift packages additionally provide fresh `swift package describe --type json` metadata. LLVM JSON must represent every declared test target, with file paths inside this checkout. Partial SwiftPM automatic exports are rejected when they omit targets. One Swift package at the root is supported; nested packages and LCOV-only Swift completeness are not silently accepted.

The explicit exploratory override warns and cannot be used for threshold gates. Complexity-only analysis remains available without coverage. Missing individual measurements remain N/A, never fabricated zeroes.

## Boundary

Local receipts catch accidental staleness and mixed reports. They are not signatures or a hostile-process security boundary. Successful commands remain trusted to execute the intended tests and report truthfully. Test-target representation does not prove all tests executed. Raw parser/coverage Python APIs are unverified primitives. No automatic tool installation, Swift export orchestration, Svelte support, new metrics or project modifications are included.

## Verification

Regression fixtures cover absent/corrupt receipts, source changes, report content/inventory changes, stale reports, command failure, modification during analysis, cross-checkout paths, partial Swift test-target exports, and nongating overrides. Real shell-command tests establish receipt creation and invalidation. Run the full pytest suite and CI before publication.
