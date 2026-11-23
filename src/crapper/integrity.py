"""Local coverage provenance: accidental stale/mixed inputs, not hostile forgery."""
import hashlib
import json
import os
from dataclasses import dataclass
from tempfile import NamedTemporaryFile
from pathlib import Path

from crapper.discover import SKIP_DIRS

RECEIPT = Path('.metrics/coverage-receipt.json')
DESCRIPTION = Path('target/coverage/swift-package.json')


class CoverageIntegrityError(Exception):
    """Coverage cannot be bound to this source/run."""


def report_paths(root: Path) -> list[Path]:
    patterns = (
        'target/coverage/**/lcov.info', 'coverage/**/lcov.info',
        'target/coverage/swift/*.json', str(DESCRIPTION),
        'coverage.out', 'target/coverage/coverage.out',
        'target/coverage/go/coverage.out', '*/target/coverage/go/coverage.out',
        '*/*/target/coverage/go/coverage.out', 'target/site/jacoco/jacoco.xml',
        '*/target/site/jacoco/jacoco.xml', '*/*/target/site/jacoco/jacoco.xml',
        'target/coverage/**/*.html',
    )
    return sorted({p for pattern in patterns for p in root.glob(pattern) if p.is_file()})


def _hashes(root: Path, paths) -> dict[str, str]:
    result = {}
    for path in paths:
        if not path.resolve().is_relative_to(root.resolve()):
            raise CoverageIntegrityError(f'Input escapes checkout: {path}')
        result[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def _is_input_file(path: Path, reports: set[Path]) -> bool:
    return path not in reports and path.name != '.DS_Store'


def inputs(root: Path) -> dict[str, str]:
    """Bind source, tests, manifests and configuration, not generated output."""
    reports = set(report_paths(root))
    paths = []
    for folder, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in names:
            path = Path(folder) / name
            if _is_input_file(path, reports):
                paths.append(path)
    return _hashes(root, paths)


def _validate_lcov_sources(root: Path, report: Path) -> None:
    from crapper.coverage import normalize_path, parse_lcov

    for name in parse_lcov(report.read_text()):
        path = Path(normalize_path(name))
        resolved = (root / path).resolve()
        if not resolved.is_relative_to(root.resolve()):
            raise CoverageIntegrityError(f'LCOV source escapes measured checkout: {name}')


def _report_locations(root: Path, reports: list[Path]) -> None:
    for report in reports:
        if report.name == 'lcov.info':
            _validate_lcov_sources(root, report)


def _swift_test_targets(root: Path, packages: list[str]) -> list[dict]:
    if packages != ['Package.swift']:
        raise CoverageIntegrityError('Strict Swift coverage currently requires one package at --root.')
    description = json.loads((root / DESCRIPTION).read_text())
    targets = [target for target in description['targets'] if target['type'] == 'test']
    if not targets:
        raise CoverageIntegrityError('Swift package description declares no test targets.')
    return targets


def _read_swift_export(path: Path) -> dict:
    data = json.loads(path.read_text())
    if data.get('type') != 'llvm.coverage.json.export' or not data.get('data'):
        raise CoverageIntegrityError(f'Invalid Swift export: {path}')
    return data


def _swift_source(root: Path, record: dict) -> Path:
    name = Path(record['filename'])
    if not name.is_absolute() or not name.resolve().is_relative_to(root):
        raise CoverageIntegrityError(f'Swift export belongs to another checkout: {name}')
    return name.resolve()


def _swift_export_sources(root: Path, path: Path) -> set[Path]:
    names = set()
    for unit in _read_swift_export(path)['data']:
        for record in unit['files']:
            name = _swift_source(root, record)
            if record.get('segments'):
                names.add(name)
    return names


def _represented_targets(root: Path, targets: list[dict], names: set[Path]) -> None:
    for target in targets:
        folder = (root / target['path']).resolve()
        if not folder.is_relative_to(root) or not any(p.is_relative_to(folder) for p in names):
            raise CoverageIntegrityError(f'Swift export omits test target {target["name"]}.')


def _swift_complete(root: Path) -> None:
    packages = [p for p in inputs(root) if Path(p).name == 'Package.swift']
    if not packages:
        return
    targets = _swift_test_targets(root, packages)
    exports = list((root / 'target/coverage/swift').glob('*.json'))
    if not exports:
        raise CoverageIntegrityError('Strict Swift coverage requires LLVM JSON exports, not LCOV alone.')
    names = set()
    for path in exports:
        names.update(_swift_export_sources(root, path))
    _represented_targets(root, targets, names)

def invalidate(root: Path) -> None:
    (root / RECEIPT).unlink(missing_ok=True)


@dataclass(frozen=True)
class CoverageRun:
    started_ns: int
    reports: dict[str, tuple]


def _report_signature(path: Path) -> tuple:
    stat = path.stat()
    return stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size, stat.st_ino


def begin_coverage(root: Path) -> CoverageRun:
    previous = {path.relative_to(root).as_posix(): _report_signature(path) for path in report_paths(root)}
    folder = root / RECEIPT.parent
    folder.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=folder) as clock:
        clock.write(b"coverage clock")
        clock.flush()
        started = Path(clock.name).stat().st_mtime_ns
    return CoverageRun(started, previous)


def _fresh_report_paths(root: Path, run: CoverageRun) -> list[Path]:
    reports = report_paths(root)
    if not reports or reports == [root / DESCRIPTION]:
        raise CoverageIntegrityError('Coverage command produced no recognized reports.')
    for path in reports:
        _require_fresh_report(root, path, run)
    return reports


def _require_fresh_report(root: Path, path: Path, run: CoverageRun) -> None:
    signature = _report_signature(path)
    if signature[0] < run.started_ns:
        raise CoverageIntegrityError(f'Stale report was not regenerated: {path}')
    if signature == run.reports.get(path.relative_to(root).as_posix()):
        raise CoverageIntegrityError(f'Report rewrite cannot be established: {path}')


def _write_receipt(root: Path, receipt: dict) -> None:
    dest = root / RECEIPT
    dest.parent.mkdir(parents=True, exist_ok=True)
    temp = dest.with_suffix('.tmp')
    temp.write_text(json.dumps(receipt, sort_keys=True, indent=2) + '\n')
    temp.replace(dest)


def _require_unchanged_inputs(root: Path, before: dict) -> None:
    after = inputs(root)
    changed = sorted(path for path in before.keys() | after.keys() if before.get(path) != after.get(path))
    if changed:
        raise CoverageIntegrityError('Source/test/config inputs changed during coverage execution: ' + ', '.join(changed))


def seal(root: Path, before: dict, run: CoverageRun, command: str) -> None:
    """Only called after an explicit coverage command exits zero."""
    invalidate(root)
    _require_unchanged_inputs(root, before)
    reports = _fresh_report_paths(root, run)
    try:
        _report_locations(root, reports)
        _swift_complete(root)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise CoverageIntegrityError(f'Invalid coverage metadata/export: {exc}') from exc
    receipt = {'version': 1, 'checkout': str(root.resolve()), 'command': command,
               'inputs': before, 'reports': _hashes(root, reports)}
    _write_receipt(root, receipt)

def _verify_checkout(root: Path, receipt: dict) -> None:
    if receipt['version'] != 1 or receipt['checkout'] != str(root.resolve()):
        raise CoverageIntegrityError('Coverage receipt version/checkout mismatch.')


def _verify_measurement(root: Path, receipt: dict) -> None:
    if not receipt['reports'] or receipt['inputs'] != inputs(root):
        raise CoverageIntegrityError('Coverage sources, tests or configuration changed.')
    if receipt['reports'] != _hashes(root, report_paths(root)):
        raise CoverageIntegrityError('Coverage report inventory/content changed.')


def verify(root: Path) -> None:
    try:
        receipt = json.loads((root / RECEIPT).read_text())
        _verify_checkout(root, receipt)
        _verify_measurement(root, receipt)
        _report_locations(root, report_paths(root))
        _swift_complete(root)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise CoverageIntegrityError(f'Coverage receipt unavailable or invalid: {exc}') from exc
