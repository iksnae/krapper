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
- Run branch-coverage self-analysis in CI. Initially measurement-only while violations remained; the final sweep enables `--threshold 5` without exemptions.

## Final sweep

The final local run passes 278 tests and measures all 358 explicitly written implementation functions: maximum CRAP 5.0, none unavailable, none above five. The CLI, inherited language readers, coverage matching and legacy runner functions are included; no suppression list or exemption was introduced. An AST audit compares every Python function definition with the measured function spans. Two pre-existing local closures were made explicit module-level policies so neither can hide within its parent’s measurement.

Simplifications include declarative decision/entry dispatch, standard-library sequence operations, separated lexical scanning and line accounting, package metadata resolution, explicit coverage matching stages, and per-package runner preparation. Failure tests cover literal boundaries, malformed exports, missing project metadata, unsuccessful installs, failed report generation and abstract Java methods. A threshold error regression preserves the actual offending score instead of rounding `5.0488 > 5.0` into `5.0 > 5.0`.

As an additional compatibility check, 7,551 comparisons against `420f8d9` passed: source snippets from the existing language test suites and deterministic Clojure lexical/reader inputs. This supplements, rather than replaces, behavior assertions.

The CI command now enforces `--threshold 5` using fresh source-bound branch coverage on Python 3.11 and 3.13. Completion requires both final CI jobs to pass; a local green run alone does not establish that.

## Validation commands

See README Development for the fresh source-bound branch-coverage command. Use `.venv/bin/python -m pytest -q` for focused iteration. Babashka is required for the inherited EDN integration test. CI performs the full measurement on Python 3.11 and 3.13.
