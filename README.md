# Krapper

Function-level CRAP scores for Swift, Go, Rust and TypeScript, derived from [unclebob/crapper](https://github.com/unclebob/crapper) at `c757ec79a6c15dc815238bbd9c2f4601eb54d3cc`. Existing Clojure, Java, JavaScript and Python analyzers are retained. Licensed under 0BSD; see LICENSE.

```text
CRAP = CC² × (1 − coverage)³ + CC
```

Coverage in this formula is a fraction. Reports display percentages. Different language coverage tools measure different things; scores are triage signals, not proof of correctness.

## Install

Python 3.11+ required. Installation downloads dependencies; analysis uses bundled grammars and does not download them.

```sh
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
./krapper --help
```

The installed `krapper` command and legacy `crapper` alias use the same implementation. The Python package remains `crapper` to minimize upstream divergence.

## Analyze

Run from the project being measured, or supply its root:

```sh
/path/to/krapper/krapper --root /path/to/project
/path/to/krapper/krapper --root /path/to/project --no-coverage
/path/to/krapper/krapper --root /path/to/project --threshold 30
/path/to/krapper/krapper --root /path/to/project --changed
```

**The default only reads verified existing coverage.** It never invokes test runners or installs coverage tooling. A `.metrics/coverage-receipt.json` from a successful explicit Krapper coverage command is required; absent or mismatched provenance exits 1 without replacing the score snapshot. `--use-existing-coverage` is an explicit alias for this default. Missing file or function measurements show coverage and CRAP as N/A with a warning; EDN stores `nil`. Measured 0% remains numeric and produces a CRAP score. `--no-coverage` also shows N/A, without missing-data warnings. Exit 2 means a score exceeds the finite, nonnegative threshold; exit 1 means a requested threshold cannot be evaluated because any entry lacks coverage (including `--no-coverage`). No source files is a successful no-op only for nongating analysis; gates and recording commands fail on empty selection.

Output is a worst-first table and `.metrics/crap.edn`, compatible with upstream uml-viewer's namespace/name join. The snapshot replaces the previous one. TypeScript nested package paths retain package identity. Overloaded functions can still share namespace/name keys, including Swift overloads.

Only `--coverage-command '...'` executes a command, through a shell in the project root. On success, Krapper records hashes of non-generated checkout inputs (including tests/configuration), the exact report inventory/content and the checkout path. Every recognized report must have been rewritten during that command, and inputs must remain unchanged. Verification is repeated after analysis. Delete stale reports rather than mixing runs. A failed recording attempt invalidates the previous receipt. Use it only on trusted code. A failed custom command returns exit 1, does not read stale reports, and preserves the previous snapshot. An existing snapshot therefore is not evidence that the latest command succeeded. Prefer generating reports separately in CI and only running Krapper after successful tests.

## Record verified coverage

Run a trusted coverage-producing command through Krapper. A successful test run alone is insufficient: the command must regenerate all recognized reports. No packages or coverage tools are installed automatically.

```sh
krapper --coverage-command 'your-test-and-coverage-command' src
krapper --threshold 30 src
```

For old reports, `--allow-unverified-coverage` prints exploratory scores with a warning. It cannot be combined with `--threshold` or `--coverage-command`. Raw Python coverage/parser APIs remain unverified primitives; only the CLI enforces provenance.

Receipts detect accidental stale/mixed inputs, not malicious forgery. They do not prove test quality or that a successful command actually ran the intended tests, and do not bind toolchain/environment or dependencies outside the checkout. Copying a report inside a command can misrepresent its origin; use trusted commands. Absolute LCOV/Swift source paths from another checkout are rejected. Non-generated input changes (even documentation) conservatively require a new run. Generated output must stay under excluded build/coverage directories. Missing individual measurements remain N/A and prevent gates.

## Coverage command ingredients

Go, from each module:

```sh
mkdir -p target/coverage/go
go test ./... -coverprofile=target/coverage/go/coverage.out
```

Rust, with cargo-llvm-cov already installed:

```sh
mkdir -p target/coverage/rust
cargo llvm-cov --lcov --output-path target/coverage/rust/lcov.info
```

TypeScript: configure your existing test runner to emit LCOV under `coverage/lcov.info` or `target/coverage/typescript/lcov.info`. Krapper does not install or configure a test runner. For nested packages, copy reports into distinct subdirectories under the project root's `coverage/` or `target/coverage/`, retaining unambiguous source paths.

SwiftPM, from each package:

```sh
mkdir -p target/coverage/swift
swift package describe --type json > target/coverage/swift-package.json
swift test --enable-code-coverage
# Export merged profiles using llvm-cov with EVERY declared test binary.
# Write the resulting LLVM JSON to target/coverage/swift/coverage.json.
```

Run the ingredients above inside `--coverage-command` (use `&&` or a script with `set -e`). SwiftPM's automatic `--show-codecov-path` export can contain only one test binary: do not assume it is complete. Strict mode requires fresh `swift-package.json` metadata and LLVM JSON containing instrumented test-source records from every declared test target. Missing targets and cross-checkout Swift file paths are rejected. This is a representation check, not proof that every test executed. Nested Swift package layouts are explicitly unsupported in strict mode; use one package at `--root`. Swift packages using only LCOV cannot establish verified completeness yet.

SwiftPM LLVM JSON exports are read from `target/coverage/swift/*.json`; line segments determine coverage. Alternatively, supply Swift LCOV under `coverage/` or `target/coverage/`. Xcode `.xcresult`/`.profdata` conversion is not automated. Generate LCOV externally for those projects.

Swift entries include functions, initializers, deinitializers, subscripts and properties with bodies. Nested closures count toward their enclosing entry. Namespaces use `Sources/<Module>` and enclosing types; Xcode target identity is not inferred. Decisions include conditionals, guards, loops, non-default switch cases, catches, boolean/nil-coalescing operators, ternaries, optional chains and condition/where clauses. Grammar workarounds are inherited from [felipearpa's Swift contribution](https://github.com/unclebob/crapper/pull/35), head `06340dc840421ae0d47384a1360d9479f0a8b354`.

Build/dependency directories including `.build`, `Pods`, `Carthage`, `DerivedData`, `node_modules` and `target` are excluded, as are test directories, including SwiftPM's `Tests/` and custom `SwiftTests/`. Explicitly naming a test file includes it.

Exploratory reports are not freshness-checked. Do not combine stale and current reports: duplicate LCOV records are unioned, so stale hits can inflate coverage. Go report discovery retains upstream's limited nested-module depth.

## Development

```sh
.venv/bin/python -m pytest -q
```

The engineering target is **CRAP ≤5 for every implementation function, without exemptions**, measured using fresh branch coverage. The migration is in progress; this ceiling is not yet satisfied or enforced. CI runs branch-coverage self-analysis on both supported Python versions. [Migration status](docs/plans/crap-ceiling.md) records the remaining work.

To reproduce the measurement after installing the development dependencies and Babashka:

```sh
krapper --coverage-command 'mkdir -p target/coverage/python && COVERAGE_FILE=target/coverage/python/.coverage python -m coverage run --branch --source=src/crapper -m pytest -q && COVERAGE_FILE=target/coverage/python/.coverage python -m coverage lcov -o target/coverage/python/lcov.info' src/crapper
```

The inherited EDN compatibility test requires `bb` (Babashka). Without it, that test fails; other tests do not require it. Swift analyzer tests are adapted from the contribution above. No real Swift/Go/Rust/TypeScript test runners are required for fixture tests.
