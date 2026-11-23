"""Local coverage provenance: accidental stale/mixed inputs, not hostile forgery."""
import hashlib
import json
import os
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


def inputs(root: Path) -> dict[str, str]:
    """Bind source, tests, manifests and configuration, not generated output."""
    reports = set(report_paths(root))
    paths = []
    for folder, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in names:
            path = Path(folder) / name
            if path not in reports and name != '.DS_Store':
                paths.append(path)
    return _hashes(root, paths)


def _report_locations(root: Path, reports: list[Path]) -> None:
    from crapper.coverage import normalize_path, parse_lcov

    for report in reports:
        if report.name != 'lcov.info':
            continue
        for name in parse_lcov(report.read_text()):
            path = Path(normalize_path(name))
            resolved = path.resolve() if path.is_absolute() else (root / path).resolve()
            if not resolved.is_relative_to(root.resolve()):
                raise CoverageIntegrityError(f'LCOV source escapes measured checkout: {name}')


def _swift_complete(root: Path) -> None:
    packages = [p for p in inputs(root) if Path(p).name == 'Package.swift']
    if not packages:
        return
    if packages != ['Package.swift']:
        raise CoverageIntegrityError('Strict Swift coverage currently requires one package at --root.')
    description = json.loads((root / DESCRIPTION).read_text())
    targets = [t for t in description['targets'] if t['type'] == 'test']
    if not targets:
        raise CoverageIntegrityError('Swift package description declares no test targets.')
    names = set()
    exports = list((root / 'target/coverage/swift').glob('*.json'))
    if not exports:
        raise CoverageIntegrityError('Strict Swift coverage requires LLVM JSON exports, not LCOV alone.')
    for path in exports:
        data = json.loads(path.read_text())
        if data.get('type') != 'llvm.coverage.json.export' or not data.get('data'):
            raise CoverageIntegrityError(f'Invalid Swift export: {path}')
        for unit in data['data']:
            for file in unit['files']:
                name = Path(file['filename'])
                if not name.is_absolute() or not name.resolve().is_relative_to(root):
                    raise CoverageIntegrityError(f'Swift export belongs to another checkout: {name}')
                if file.get('segments'):
                    names.add(name.resolve())
    for target in targets:
        folder = (root / target['path']).resolve()
        if not folder.is_relative_to(root) or not any(p.is_relative_to(folder) for p in names):
            raise CoverageIntegrityError(f'Swift export omits test target {target["name"]}.')


def invalidate(root: Path) -> None:
    (root / RECEIPT).unlink(missing_ok=True)


def seal(root: Path, before: dict, started_ns: int, command: str) -> None:
    """Only called after an explicit coverage command exits zero."""
    invalidate(root)
    if inputs(root) != before:
        raise CoverageIntegrityError('Source/test/config inputs changed during coverage execution.')
    reports = report_paths(root)
    if not reports or reports == [root / DESCRIPTION]:
        raise CoverageIntegrityError('Coverage command produced no recognized reports.')
    for path in reports:
        if path.stat().st_mtime_ns < started_ns:
            raise CoverageIntegrityError(f'Stale report was not regenerated: {path}')
    try:
        _report_locations(root, reports)
        _swift_complete(root)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise CoverageIntegrityError(f'Invalid coverage metadata/export: {exc}') from exc
    receipt = {'version': 1, 'checkout': str(root.resolve()), 'command': command,
               'inputs': before, 'reports': _hashes(root, reports)}
    dest = root / RECEIPT
    dest.parent.mkdir(parents=True, exist_ok=True)
    temp = dest.with_suffix('.tmp')
    temp.write_text(json.dumps(receipt, sort_keys=True, indent=2) + '\n')
    temp.replace(dest)


def verify(root: Path) -> None:
    try:
        receipt = json.loads((root / RECEIPT).read_text())
        if receipt['version'] != 1 or receipt['checkout'] != str(root.resolve()):
            raise CoverageIntegrityError('Coverage receipt version/checkout mismatch.')
        if not receipt['reports'] or receipt['inputs'] != inputs(root):
            raise CoverageIntegrityError('Coverage sources, tests or configuration changed.')
        if receipt['reports'] != _hashes(root, report_paths(root)):
            raise CoverageIntegrityError('Coverage report inventory/content changed.')
        _report_locations(root, report_paths(root))
        _swift_complete(root)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise CoverageIntegrityError(f'Coverage receipt unavailable or invalid: {exc}') from exc
