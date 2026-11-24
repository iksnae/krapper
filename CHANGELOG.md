# Changelog

## [0.3.0] - 2026-11-24

### Added

- Each `.metrics/crap.edn` entry has `:file` (path relative to `--root`) and `:line` (first line of the function), after the existing keys. Entries that share `:namespace` and `:name` can now be told apart.

### Changed

- **Behavior change:** directories named `build`, `coverage`, `dist`, `out` or `target` are no longer skipped at any depth. They are skipped as build output only when git ignores them or they sit directly under the project root; anywhere else they are source. Packages such as `internal/coverage/` are now scored and bound into coverage receipts, so reports gain entries and a `--threshold` gate can change result. Nested output directories that git does not ignore are scored too; add them to `.gitignore`. Outside a git checkout the old any-depth rule applies.
- A warning lists directories skipped by name alone that hold source files.

### Fixed

- Coverage receipts did not bind source in packages named like output directories, so edits there left a receipt valid.
- A `Package.swift` below `--root` no longer fails every strict coverage run. A package at the root is verified as before. Functions in a nested package are reported N/A in strict runs, even when a report covers them, and a notice names the package.

### Migration notes

Receipts sealed by 0.2.x can fail verification under 0.3.0, because the set of bound inputs changed. Re-run your coverage command.

## [0.2.1] - 2026-11-24

### Added

- Svelte components (`.svelte`): functions in the instance and module `<script>` blocks are scored with the TypeScript/JavaScript rules, under the component's module path (`src/lib/Widget.svelte` is `lib.Widget`), and matched to Vitest LCOV by their lines in the component. `*.test.svelte` and `*.spec.svelte` are treated as tests. Markup and rune callbacks are not scored.

## [0.2.0] - 2026-11-23

First published Krapper release, derived from unclebob/crapper under 0BSD.

### Added

- Swift, Go, Rust and TypeScript function-level complexity and CRAP analysis; existing Clojure, Java, JavaScript and Python readers retained.
- SwiftPM LLVM JSON coverage import and compatible EDN snapshots.
- Strict coverage receipts binding reports to unchanged checkout inputs and a successful explicit command.
- Swift test-target export representation checks and rejection of stale, changed or cross-checkout evidence.
- Branch-coverage CI gate enforcing CRAP <=5 for every implementation function, without exemptions.

### Changed

- **Breaking:** coverage is verified by default. Existing unbound reports require `--allow-unverified-coverage` for exploration; this override cannot be used with threshold gates.
- Coverage tooling is never installed or executed implicitly. Use `--coverage-command` with a trusted report-producing command to create a receipt.
- Every explicitly written implementation function is accounted for by an AST audit. The release baseline has 360 measured functions, maximum CRAP 5.0, and 281 passing tests.

### Fixed

- Missing coverage remains unavailable rather than being substituted with 0%.
- Incomplete gates and failed coverage commands return nonzero; failed commands preserve the prior score snapshot but invalidate its run receipt.
- Duplicate LCOV records merge coverage without overwriting earlier hits.
- TypeScript package identities remain distinct, and nonfinite thresholds are rejected.
- Swift test/build directories and generated pytest caches are excluded from production/input discovery.
- Freshness checks use the filesystem clock and reject unchanged report metadata, avoiding wall-clock/filesystem timestamp skew.

### Migration notes

Older coverage producers, including workflows that invoke Krapper internally, must be adapted before using strict mode. The command being recorded should produce reports, not recursively invoke strict Krapper before its receipt exists. Swift packages also need fresh `target/coverage/swift-package.json` metadata and exports representing every declared test target.

Receipts detect accidental stale or mixed inputs; they are not proof of test quality or protection against a deliberately dishonest coverage command. Svelte component analysis and automatic Xcode coverage conversion are not included.
