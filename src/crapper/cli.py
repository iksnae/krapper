"""Command line for the multi-language CRAP tool."""

from __future__ import annotations

import argparse
import subprocess
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path

from crapper.analyze import analyze_files
from crapper.coverage import load_bundle
from crapper.discover import (
    CLOJURE_TEST_SUFFIXES,
    GO_TEST_SUFFIX,
    JS_TEST_SUFFIXES,
    SKIP_DIRS,
    TEST_DIRS,
    is_test_file,
    iter_source_files,
    language_of,
)
from crapper.integrity import CoverageIntegrityError, begin_coverage, inputs, invalidate, seal, verify
from crapper.metrics import write_metrics
from crapper.report import format_report
from crapper.runners import run_coverage

_SKIPPED_DIRS = ", ".join(sorted(SKIP_DIRS | TEST_DIRS))
_TEST_PATTERNS = ", ".join(
    [
        f"*{GO_TEST_SUFFIX}",
        *[f"*{suffix}" for suffix in CLOJURE_TEST_SUFFIXES],
        *[f"*{suffix}" for suffix in JS_TEST_SUFFIXES],
        "test_*.py",
        "*_test.py",
        "conftest.py",
    ]
)

HELP = f"""\
Usage: krapper [options] [path-or-filter ...]

Detect the language of each source file and score it with the CRAP metric
CRAP = CC² × (1 − coverage)³ + CC. Writes .metrics/crap.edn for uml-viewer
and prints a report sorted worst first.

Languages: Clojure (.clj .cljc .cljs .bb), Java (.java), Go (.go),
TypeScript and JavaScript (.ts .tsx .mts .cts .js .jsx .mjs .cjs),
Svelte component scripts (.svelte), Rust (.rs), Python (.py), Swift (.swift).

Options:
  -h, --help                    Print this help and exit.
  --root <path>                 Project root. Metrics are written here.
                                Default: the current directory.
  -s, --source-root <path>      Walk this tree instead of the project root.
                                May be repeated.
  --changed                     Analyze added and modified source files from
                                git status.
  --no-coverage                 Score complexity only. Coverage and CRAP are N/A.
  --use-existing-coverage       Read source-bound coverage (the default).
  --allow-unverified-coverage   Exploratory old reports only; cannot gate.
  --coverage-command <cmd>      Explicitly run this shell command, then read
                                the reports it wrote (trusted projects only).
  --threshold <number>          Exit 2 when a CRAP score is above this;
                                exit 1 if any entry has unavailable coverage.

Arguments:
  path              File or directory to analyze. Test paths are included when
                    you name them explicitly.
  filter            When the argument is not a path, only source files whose
                    path contains this text are analyzed.

With no paths, source files under the project root are analyzed. Directories
named {_SKIPPED_DIRS} are skipped, as are {_TEST_PATTERNS}.

Coverage formats (generate separately; default analysis executes no tools):
  Clojure      clj -M:cov --lcov, then Cloverage form counts or LCOV
  Java         Maven JaCoCo instruction coverage, for each pom.xml module
  Go           go test ./... -coverprofile=...
  TypeScript   npm run coverage, Vitest's own LCOV, or c8 around npm test
  Rust         cargo llvm-cov, or cargo tarpaulin, in the nearest Cargo.toml
  Python       coverage.py LCOV, via pytest or unittest, per project
  Swift        SwiftPM LLVM JSON in target/coverage/swift/*.json, or LCOV

uml-viewer joins .metrics/crap.edn on :namespace and :name.
  Clojure      the ns, and the defn name
  Java         package.Class, and the method name
  Go           import path, or import.path.Receiver for methods
  TypeScript   dotted module path, or module.Class for methods
  Rust         crate::module, or crate::module::Type for methods
  Python       dotted module path, or module.Class for methods
  Swift        Sources module and enclosing type chain
"""


@dataclass
class Options:
    action: str
    message: str = ""
    exit_code: int = 0
    project_root: Path = field(default_factory=lambda: Path("."))
    source_roots: list[str] = field(default_factory=list)
    positionals: list[str] = field(default_factory=list)
    no_coverage: bool = False
    use_existing_coverage: bool = False
    coverage_command: str | None = None
    threshold: float | None = None
    changed: bool = False
    allow_unverified_coverage: bool = False


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


def _threshold(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError("--threshold must be finite and nonnegative")
    return number


def _option_value(value: str) -> str:
    if not value or value.startswith("-"):
        raise argparse.ArgumentTypeError("option requires a value")
    return value


def _root_path(value: str) -> Path:
    return Path(_option_value(value))


def _argument_parser():
    parser = _ArgumentParser(add_help=False, allow_abbrev=False)
    parser.add_argument("--root", dest="project_root", type=_root_path, default=Path("."))
    parser.add_argument("-s", "--source-root", dest="source_roots", action="append", default=[], type=_option_value)
    parser.add_argument("--coverage-command", type=_option_value)
    parser.add_argument("--threshold", type=_threshold)
    for flag in ("no-coverage", "use-existing-coverage", "allow-unverified-coverage", "changed"):
        parser.add_argument("--" + flag, action="store_true")
    parser.add_argument("positionals", nargs="*")
    return parser


def _validate_integrity_options(options: Options) -> None:
    if options.allow_unverified_coverage and (options.threshold is not None or options.coverage_command):
        raise ValueError("Unverified coverage cannot gate or record a run.")


def _validate_coverage_options(options: Options) -> None:
    if options.no_coverage and options.coverage_command:
        raise ValueError("--no-coverage cannot be combined with --coverage-command")


def parse_args(argv: list[str] | None = None) -> Options:
    args = list(sys.argv[1:] if argv is None else argv)
    if any(arg in {"-h", "--help"} for arg in args):
        return Options(action="help", message=HELP, exit_code=0)
    try:
        parsed = _argument_parser().parse_intermixed_args(args)
        options = Options(action="analyze", **vars(parsed))
        _validate_integrity_options(options)
        _validate_coverage_options(options)
        return options
    except ValueError as exc:
        return Options(action="help", message=f"{exc}\n\n{HELP}", exit_code=1)

class GitError(Exception):
    """git could not describe the working tree. `code` is git's status."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code


def _git(root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _repository_root(root: Path) -> Path:
    result = _git(root, ["rev-parse", "--show-toplevel"])
    if result.returncode != 0:
        raise GitError(result.returncode, result.stderr.strip() or "git status failed")
    return Path(result.stdout.strip())


def _changed_paths(status: str, top: Path, limit: Path) -> list[Path]:
    found: list[Path] = []
    for entry in status.split("\0"):
        if len(entry) < 4:
            continue
        path = (top / entry[3:]).resolve()
        if path.is_file() and path.is_relative_to(limit):
            found.append(path)
    return found


def _changed_files(root: Path) -> list[Path]:
    """Added/modified paths from NUL-delimited Git status, confined to root."""
    top = _repository_root(root)
    status = _git(root, ["status", "--porcelain", "-z", "--no-renames", "--untracked-files=all", "--", "."])
    if status.returncode != 0:
        raise GitError(status.returncode, status.stderr.strip() or "git status failed")
    return _changed_paths(status.stdout, top, root.resolve())

def _positionals(root: Path, args: list[str]) -> tuple[list[Path], list[str]]:
    existing: list[Path] = []
    filters: list[str] = []
    for arg in args:
        candidate = Path(arg)
        if not candidate.is_absolute():
            candidate = root / arg
        if candidate.exists():
            existing.append(candidate.resolve())
        else:
            filters.append(arg)
    return existing, filters


def _changed_source(root: Path) -> list[Path]:
    return [
        path
        for path in _changed_files(root)
        if language_of(path) is not None and not is_test_file(path)
    ]


def _explicit_files(existing: list[Path]) -> list[Path]:
    files: list[Path] = []
    for path in existing:
        if path.is_dir():
            files.extend(iter_source_files([path]))
        elif language_of(path) is not None:
            files.append(path)
    return files


def _selected(options: Options, root: Path, existing: list[Path]) -> list[Path]:
    if options.changed:
        return _changed_source(root)
    if options.source_roots:
        return iter_source_files([(root / path).resolve() for path in options.source_roots])
    if existing:
        return _explicit_files(existing)
    return iter_source_files([root])


def _apply_filters(files: list[Path], filters: list[str]) -> list[Path]:
    if not filters:
        return files
    return [path for path in files if any(item in path.as_posix() for item in filters)]


def select_files(options: Options) -> list[Path]:
    root = options.project_root.resolve()
    existing, filters = _positionals(root, options.positionals)
    files = _apply_filters(_selected(options, root, existing), filters)
    return sorted({path.resolve() for path in files}, key=lambda path: path.as_posix())


def _show_help(options: Options) -> int:
    stream = sys.stdout if options.exit_code == 0 else sys.stderr
    print(options.message, file=stream, end="" if options.message.endswith("\n") else "\n")
    return options.exit_code


class CoverageCommandError(Exception):
    """An explicitly requested coverage command failed."""


def _record_coverage(options: Options, root: Path, files: list[Path]) -> None:
    invalidate(root)
    before = inputs(root)
    started = begin_coverage(root)
    status = run_coverage(root, files, options.coverage_command)
    if status != 0:
        raise CoverageCommandError(f"Coverage command exited {status}; snapshot not updated.")
    seal(root, before, started, options.coverage_command)


def _require_internal_sources(root: Path, files: list[Path]) -> None:
    if any(not path.resolve().is_relative_to(root) for path in files):
        raise CoverageIntegrityError('Strict coverage sources must be inside --root.')


def _require_bound_sources(root: Path, files: list[Path]) -> None:
    bound = inputs(root)
    if any(path.resolve().relative_to(root).as_posix() not in bound for path in files):
        raise CoverageIntegrityError('Selected sources are excluded from receipt inputs.')


def _coverage_bundle(options: Options, root: Path, files: list[Path]):
    if options.no_coverage:
        return None
    if options.coverage_command:
        _require_internal_sources(root, files)
        _record_coverage(options, root, files)
    elif options.allow_unverified_coverage:
        print('WARNING: exploratory UNVERIFIED coverage; not valid gate evidence.', file=sys.stderr)
        return load_bundle(root)
    else:
        _require_internal_sources(root, files)
        verify(root)
    _require_bound_sources(root, files)
    return load_bundle(root)

def _threshold_status(options: Options, entries) -> int:
    if options.threshold is None:
        return 0
    if not entries:
        print('Cannot evaluate CRAP threshold: no scorable entries.', file=sys.stderr)
        return 1
    if any(entry.crap is None for entry in entries):
        print("Cannot evaluate CRAP threshold: coverage is unavailable for some entries.", file=sys.stderr)
        return 1
    worst = max(entry.crap for entry in entries)
    if worst > options.threshold:
        print(
            f"CRAP threshold exceeded: {worst} > {options.threshold}",
            file=sys.stderr,
        )
        return 2
    return 0


def _analyze_selection(options: Options, root: Path, files: list[Path]):
    bundle = _coverage_bundle(options, root, files)
    entries = analyze_files(files, root, bundle)
    if not options.no_coverage and not options.allow_unverified_coverage:
        verify(root)
    return entries


def _run_selection(options: Options, root: Path, files: list[Path]) -> int:
    if not files:
        print("No source files to analyze.")
        return 1 if options.threshold is not None or options.coverage_command else 0
    entries = _analyze_selection(options, root, files)
    metrics = write_metrics(entries, root)
    print(format_report(entries), end="", flush=True)
    print(f"Wrote {metrics}", file=sys.stderr)
    return _threshold_status(options, entries)


def run(argv: list[str] | None = None) -> int:
    options = parse_args(argv)
    if options.action == "help":
        return _show_help(options)
    root = options.project_root.resolve()
    try:
        return _run_selection(options, root, select_files(options))
    except GitError as exc:
        print(str(exc), file=sys.stderr)
        return exc.code
    except (CoverageCommandError, CoverageIntegrityError, OSError, ValueError, KeyError, TypeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

def main(argv: list[str] | None = None) -> None:
    sys.exit(run(argv))
