# Krapper

Find complex, under-tested functions in Swift, Go, Rust and TypeScript. Clojure, Java, JavaScript, Python and Svelte component scripts are also supported.

## Install

Install with [uv](https://docs.astral.sh/uv/). Krapper needs Python 3.11+; this command selects Python 3.12:

```sh
uv tool install --python 3.12 https://github.com/iksnae/krapper/releases/download/v0.3.1/krapper-0.3.1-py3-none-any.whl
```

Add `--reinstall` to upgrade an existing installation. [Release downloads](https://github.com/iksnae/krapper/releases/tag/v0.3.1) include checksums.

## Use

Run from the project root:

```sh
krapper --no-coverage                # complexity only; no tests run
krapper                             # score previously verified coverage
krapper --threshold 5                # fail if any function scores above 5
krapper --help                       # paths, filters and other options
```

To obtain verified scores, [record a coverage-producing command](docs/coverage.md). Krapper never runs tests or installs coverage tools implicitly.

Each run prints a worst-first table and writes `.metrics/crap.edn`. **CRAP is per function, not one score for the repository:**

```text
CRAP = complexity² × (1 − coverage)³ + complexity
```

Coverage is a fraction in the formula and a percentage in the report. Missing measurements show **N/A**, not 0%. Different languages use different coverage measures; a low score does not prove good tests.

Exit codes: **0** success, **1** invalid input or unverifiable/incomplete measurement, **2** threshold exceeded. Exploratory analysis of old reports is available with `--allow-unverified-coverage`, but cannot be used for threshold gates.

## Develop

From a fresh checkout:

```sh
uv venv --python 3.12
uv pip install -e '.[dev]'
.venv/bin/python -m pytest -q
```

Tests require [Babashka](https://babashka.org/) (`bb`) on PATH for the EDN compatibility check. Our [CI workflow](.github/workflows/test.yml) generates fresh branch coverage and enforces **CRAP ≤5 for every implementation function, without exemptions**.

## Reference

- [Coverage setup, verification and limitations](docs/coverage.md)
- [Release history and migration notes](CHANGELOG.md)

Derived from [Uncle Bob's crapper](https://github.com/unclebob/crapper), under the [0BSD license](LICENSE). The `crapper` command remains an alias; the Python package keeps its upstream name.
