"""Turn source files and coverage into CRAP entries."""

import sys
from pathlib import Path

from crapper.coverage import CoverageBundle
from crapper.crap import make_entry, sort_entries
from crapper.discover import language_of
from crapper.languages import functions_in_file
from crapper.model import Entry, Function


def _coverage(bundle: CoverageBundle | None, function: Function) -> float | None:
    """Percentage for one function.

    None means coverage was not requested or no measurement is available.
    Measured zero stays numeric; missing data must never invent a CRAP score.
    """

    if bundle is None:
        return None
    found = bundle.percent_for(function)
    if found is None:
        print(f"Coverage unavailable: {function.path}:{function.start_line}; CRAP is N/A.", file=sys.stderr)
        return None
    return found


def _source_path(file: Path, root: Path) -> str:
    try:
        return file.relative_to(root).as_posix()
    except ValueError:
        return file.as_posix()


def analyze_files(
    files: list[Path],
    project_root: Path,
    bundle: CoverageBundle | None,
) -> list[Entry]:
    root = project_root.resolve()
    if bundle is not None:
        bundle.bind_sources([_source_path(file.resolve(), root) for file in files])
    entries: list[Entry] = []
    for file in files:
        file = file.resolve()
        language = language_of(file)
        if language is None:
            continue
        source = file.read_text(encoding="utf-8", errors="replace")
        try:
            relative = file.relative_to(root).as_posix()
        except ValueError:
            relative = file.as_posix()
        for function in functions_in_file(language, source, relative, str(root)):
            entries.append(make_entry(function, _coverage(bundle, function)))
    return sort_entries(entries)
