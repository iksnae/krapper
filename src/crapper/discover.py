"""Find source files and decide which language each one is written in."""

import os
from fnmatch import fnmatchcase
from pathlib import Path

EXTENSIONS = {
    ".clj": "clojure",
    ".cljc": "clojure",
    ".cljs": "clojure",
    ".bb": "clojure",
    ".java": "java",
    ".go": "go",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".mts": "typescript",
    ".cts": "typescript",
    ".js": "typescript",
    ".jsx": "typescript",
    ".mjs": "typescript",
    ".cjs": "typescript",
    ".svelte": "typescript",
    ".rs": "rust",
    ".swift": "swift",
    ".py": "python",
}

SKIP_DIRS = {
    ".git",
    ".build",
    "Pods",
    "Carthage",
    "DerivedData",
    ".hg",
    ".svn",
    ".idea",
    ".venv",
    ".pytest_cache",
    "venv",
    "node_modules",
    "vendor",
    "target",
    "dist",
    "build",
    "out",
    "coverage",
    ".metrics",
    "testdata",
    "__pycache__",
    ".clj-kondo",
}

TEST_DIRS = {"SwiftTests", "Tests", "test", "tests", "spec", "specs", "__tests__"}

GO_TEST_SUFFIX = "_test.go"
CLOJURE_TEST_SUFFIXES = ("_test.clj", "_test.cljc", "_test.cljs", "_test.bb")
JS_TEST_SUFFIXES = (
    ".test.ts",
    ".spec.ts",
    ".test.tsx",
    ".spec.tsx",
    ".test.mts",
    ".spec.mts",
    ".test.cts",
    ".spec.cts",
    ".test.js",
    ".spec.js",
    ".test.jsx",
    ".spec.jsx",
    ".test.mjs",
    ".spec.mjs",
    ".test.cjs",
    ".spec.cjs",
    ".test.svelte",
    ".spec.svelte",
)


def language_of(path: str | Path) -> str | None:
    file_path = Path(path)
    name = file_path.name
    if name.endswith(".d.ts"):
        return None
    return EXTENSIONS.get(file_path.suffix)


def is_test_file(path: str | Path) -> bool:
    file_path = Path(path)
    name = file_path.name
    suffixes = (GO_TEST_SUFFIX, *CLOJURE_TEST_SUFFIXES, *JS_TEST_SUFFIXES, "_test.py")
    if name == "conftest.py" or name.endswith(suffixes) or fnmatchcase(name, "test_*.py"):
        return True
    return any(part in TEST_DIRS for part in file_path.parts)


def _sources_in(directory: str, names: list[str]) -> list[Path]:
    paths = (Path(directory) / name for name in names)
    return [path for path in paths if language_of(path) is not None and not is_test_file(path)]


def _walk(root: Path) -> list[Path]:
    if not root.exists():
        return []
    if root.is_file():
        return [root]
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            name for name in dirnames if name not in SKIP_DIRS | TEST_DIRS
        ]
        found.extend(_sources_in(dirpath, filenames))
    return found


def iter_source_files(roots: list[Path]) -> list[Path]:
    files: set[Path] = set()
    for root in roots:
        for path in _walk(root):
            files.add(path.resolve())
    return sorted(files, key=lambda path: path.as_posix())
