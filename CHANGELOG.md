# Changelog

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
