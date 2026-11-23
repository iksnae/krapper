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

def _line_counts(segments: list) -> dict[int, int]:
    """Each executable line's count, as `llvm-cov`'s line coverage iterator gives it.

    A segment is `[line, column, count, hasCount, isRegionEntry, isGapRegion]`.
    A line is executable when a counted region starts on it, or when the
    segment carried over from an earlier line has a count; its count is the
    highest of those. A line that starts a skipped region is not executable.
    """

    counts: dict[int, int] = {}
    if not segments:
        return counts
    by_line: dict[int, list] = {}
    for segment in segments:
        by_line.setdefault(segment[0], []).append(segment)
    wrapped = None
    for number in range(segments[0][0], segments[-1][0] + 1):
        starting = by_line.get(number, [])
        starts = [s for s in starting if s[3] and s[4] and not s[5]]
        skipped = bool(starting) and not starting[0][3] and starting[0][4]
        mapped = not skipped and (bool(wrapped and wrapped[3]) or bool(starts))
        mapped = mapped or any(s[3] and s[4] for s in starting)
        if mapped:
            counts[number] = max([wrapped[2] if wrapped else 0, *(s[2] for s in starts)])
        if starting:
            wrapped = starting[-1]
    return counts

def _merge_export(merged: dict[str, dict[int, int]], export: Path, sources: dict[str, str]) -> None:
    try:
        data = json.loads(export.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        _warn(f"{export}: not a swift test coverage export ({exc}); skipped.")
        return
    if not isinstance(data, dict) or data.get("type") != _EXPORT_TYPE:
        _warn(f"{export}: not a swift test coverage export (no type {_EXPORT_TYPE}); skipped.")
        return
    read: dict[str, dict[int, int]] = {}
    try:
        for unit in data.get("data", []):
            for file in unit.get("files", []):
                counts = _counts_for(read, file["filename"], sources)
                if counts is None:
                    continue
                for number, hits in _line_counts(file.get("segments", [])).items():
                    counts[number] = counts.get(number, 0) + hits
    except (AttributeError, IndexError, KeyError, TypeError) as exc:
        _warn(f"{export}: not a swift test coverage export ({exc!r}); skipped.")
        return
    for source, counts in read.items():
        target = merged.setdefault(source, {})
        for number, hits in counts.items():
            target[number] = target.get(number, 0) + hits

def load_swift_coverage(root: Path):
    from crapper.coverage import FileCoverage
    merged = {}
    from crapper.discover import iter_source_files
    folder = root / 'target/coverage/swift'
    if not folder.is_dir():
        return {}
    sources = {os.path.realpath(path): str(path.resolve()) for path in iter_source_files([root]) if path.suffix == '.swift'}
    for export in sorted((root / 'target/coverage/swift').glob('*.json')):
        _merge_export(merged, export, sources)
    result = {}
    for path, counts in merged.items():
        record = FileCoverage()
        record.update({line: (int(hits > 0), 1) for line, hits in counts.items()})
        result[path] = record
    return result
