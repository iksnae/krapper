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

**The default only reads existing coverage.** It never invokes test runners or installs coverage tooling. `--use-existing-coverage` is an explicit alias for this default. Missing file or function measurements show coverage and CRAP as N/A with a warning; EDN stores `nil`. Measured 0% remains numeric and produces a CRAP score. `--no-coverage` also shows N/A, without missing-data warnings. Exit 2 means a score exceeds the finite, nonnegative threshold; exit 1 means a requested threshold cannot be evaluated because any entry lacks coverage (including `--no-coverage`). No source files is a successful no-op.

Output is a worst-first table and `.metrics/crap.edn`, compatible with upstream uml-viewer's namespace/name join. The snapshot replaces the previous one. TypeScript nested package paths retain package identity. Overloaded functions can still share namespace/name keys, including Swift overloads.

Only `--coverage-command '...'` executes a command, through a shell in the project root. Use it only on trusted code. A failed custom command returns exit 1, does not read stale reports, and preserves the previous snapshot. An existing snapshot therefore is not evidence that the latest command succeeded. Prefer generating reports separately in CI and only running Krapper after successful tests.

## Generate coverage separately

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
swift test --enable-code-coverage
mkdir -p target/coverage/swift
cp "$(swift test --show-codecov-path)" target/coverage/swift/package.json
```

SwiftPM LLVM JSON exports are read from `target/coverage/swift/*.json`; line segments determine coverage. Alternatively, supply Swift LCOV under `coverage/` or `target/coverage/`. Xcode `.xcresult`/`.profdata` conversion is not automated. Generate LCOV externally for those projects.

Swift entries include functions, initializers, deinitializers, subscripts and properties with bodies. Nested closures count toward their enclosing entry. Namespaces use `Sources/<Module>` and enclosing types; Xcode target identity is not inferred. Decisions include conditionals, guards, loops, non-default switch cases, catches, boolean/nil-coalescing operators, ternaries, optional chains and condition/where clauses. Grammar workarounds are inherited from [felipearpa's Swift contribution](https://github.com/unclebob/crapper/pull/35), head `06340dc840421ae0d47384a1360d9479f0a8b354`.

Build/dependency directories including `.build`, `Pods`, `Carthage`, `DerivedData`, `node_modules` and `target` are excluded, as are test directories, including SwiftPM's `Tests/` and custom `SwiftTests/`. Explicitly naming a test file includes it.

Existing reports are not freshness-checked. Do not combine stale and current reports: duplicate LCOV records are unioned, so stale hits can inflate coverage. Go report discovery retains upstream's limited nested-module depth.

## Development

```sh
.venv/bin/python -m pytest -q
```

The inherited EDN compatibility test requires `bb` (Babashka). Without it, that test fails; other tests do not require it. Swift analyzer tests are adapted from the contribution above. No real Swift/Go/Rust/TypeScript test runners are required for fixture tests.
