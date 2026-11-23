"""Read existing SwiftPM LLVM coverage JSON without executing tools."""
import json
import os
import sys
from pathlib import Path

_EXPORT_TYPE = "llvm.coverage.json.export"


def _warn(message: str) -> None:
    print(message, file=sys.stderr)


def _counts_for(merged: dict[str, dict[int, int]], path: str, sources: dict[str, str]) -> dict[int, int] | None:
    source = sources.get(os.path.realpath(path))
    return None if source is None else merged.setdefault(source, {})


def _segments_by_line(segments: list) -> dict[int, list]:
    by_line: dict[int, list] = {}
    for segment in segments:
        by_line.setdefault(segment[0], []).append(segment)
    return by_line


def _counted_region(segment: list) -> bool:
    return segment[3] and segment[4] and not segment[5]


def _has_counted_entry(starting: list) -> bool:
    return any(segment[3] and segment[4] for segment in starting)


def _skipped_region(starting: list) -> bool:
    return bool(starting) and not starting[0][3] and starting[0][4]


def _line_mapped(starting: list, carried) -> bool:
    if _has_counted_entry(starting):
        return True
    if _skipped_region(starting):
        return False
    return bool(carried and carried[3])


def _line_hits(starting: list, carried) -> int | None:
    if not _line_mapped(starting, carried):
        return None
    starts = [segment for segment in starting if _counted_region(segment)]
    carried_hits = carried[2] if carried else 0
    return max([carried_hits, *(segment[2] for segment in starts)])


def _line_counts(segments: list) -> dict[int, int]:
    """Executable-line hits from LLVM regions, carrying the last region forward."""
    counts: dict[int, int] = {}
    if not segments:
        return counts
    by_line = _segments_by_line(segments)
    carried = None
    for number in range(segments[0][0], segments[-1][0] + 1):
        starting = by_line.get(number, [])
        hits = _line_hits(starting, carried)
        if hits is not None:
            counts[number] = hits
        if starting:
            carried = starting[-1]
    return counts


def _read_export(export: Path) -> dict | None:
    try:
        data = json.loads(export.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        _warn(f"{export}: not a swift test coverage export ({exc}); skipped.")
        return None
    if not isinstance(data, dict) or data.get("type") != _EXPORT_TYPE:
        _warn(f"{export}: not a swift test coverage export (no type {_EXPORT_TYPE}); skipped.")
        return None
    return data


def _merge_counts(target: dict[int, int], incoming: dict[int, int]) -> None:
    for number, hits in incoming.items():
        target[number] = target.get(number, 0) + hits


def _record_file(read: dict, record: dict, sources: dict) -> None:
    counts = _counts_for(read, record['filename'], sources)
    if counts is not None:
        _merge_counts(counts, _line_counts(record.get('segments', [])))


def _export_counts(data: dict, sources: dict) -> dict:
    read: dict[str, dict[int, int]] = {}
    for unit in data.get('data', []):
        for record in unit.get('files', []):
            _record_file(read, record, sources)
    return read


def _merge_export(merged: dict[str, dict[int, int]], export: Path, sources: dict[str, str]) -> None:
    data = _read_export(export)
    if data is None:
        return
    try:
        read = _export_counts(data, sources)
    except (AttributeError, IndexError, KeyError, TypeError) as exc:
        _warn(f"{export}: not a swift test coverage export ({exc!r}); skipped.")
        return
    for source, counts in read.items():
        _merge_counts(merged.setdefault(source, {}), counts)


def load_swift_coverage(root: Path):
    from crapper.coverage import FileCoverage
    from crapper.discover import iter_source_files

    merged = {}
    folder = root / 'target/coverage/swift'
    if not folder.is_dir():
        return {}
    sources = {os.path.realpath(path): str(path.resolve()) for path in iter_source_files([root]) if path.suffix == '.swift'}
    for export in sorted(folder.glob('*.json')):
        _merge_export(merged, export, sources)
    result = {}
    for path, counts in merged.items():
        record = FileCoverage()
        record.update({line: (int(hits > 0), 1) for line, hits in counts.items()})
        result[path] = record
    return result
