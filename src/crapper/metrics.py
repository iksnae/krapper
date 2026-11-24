"""Write the crap4clj snapshot uml-viewer reads."""

import os
from pathlib import Path

from crapper.model import Entry


def metrics_path(root: Path) -> Path:
    return root / ".metrics" / "crap.edn"


def _edn_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _edn_number(value: float) -> str:
    text = f"{value:.4f}".rstrip("0").rstrip(".")
    if "." not in text:
        text += ".0"
    return text


def _edn_value(value: float | None) -> str:
    if value is None:
        return "nil"
    return _edn_number(value)


def _edn_line(line: int | None) -> str:
    return "nil" if line is None else str(line)


def _file(path: str, root: Path | None) -> str:
    """Path from `root`, with `/` separators. A file outside the root is reached
    with `..`, so the snapshot never records where the checkout lives.
    """

    if root is None or not os.path.isabs(path):
        return path.replace("\\", "/")
    return Path(os.path.relpath(path, root)).as_posix()


def render_edn(entries: list[Entry], root: Path | None = None) -> str:
    """EDN map `{:entries [...]}` with crap4clj's keys, in crap4clj's order.

    uml-viewer groups this file by `:namespace` and joins each operation on
    `:name`. Coverage is a percentage. `nil` coverage and CRAP mean coverage
    was disabled or unavailable. Measured zero coverage remains `0.0`.

    `:file` and `:line` follow crap4clj's keys. `:namespace` and `:name` can
    repeat; with `:file` and `:line` an entry is unique in its snapshot.
    `:line` moves when the file is edited, so it locates a function and does
    not identify it across snapshots.
    """

    rows = []
    for entry in entries:
        rows.append(
            "  {"
            f":name {_edn_string(entry.name)}, "
            f":namespace {_edn_string(entry.namespace)}, "
            f":complexity {entry.complexity}, "
            f":coverage {_edn_value(entry.coverage)}, "
            f":crap {_edn_value(entry.crap)}, "
            f":file {_edn_string(_file(entry.path, root))}, "
            f":line {_edn_line(entry.line)}"
            "}"
        )
    body = "\n".join(rows)
    if body:
        return "{:entries [\n" + body + "\n]}\n"
    return "{:entries []}\n"


def write_metrics(entries: list[Entry], root: Path) -> Path:
    path = metrics_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_edn(entries, root), encoding="utf-8")
    return path
