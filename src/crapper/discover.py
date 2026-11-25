"""Find source files and decide which language each one is written in."""

import os
import subprocess
from dataclasses import dataclass, field
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

# Tool and dependency directories. No project keeps its own source under these names.
ALWAYS_SKIP_DIRS = {
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
    ".metrics",
    "testdata",
    "__pycache__",
    ".clj-kondo",
}

# Names that build tools write to, and that a source package can also have.
OUTPUT_DIRS = {"target", "dist", "build", "out", "coverage"}

SKIP_DIRS = ALWAYS_SKIP_DIRS | OUTPUT_DIRS

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


def ignored_directories(root: Path) -> frozenset[Path] | None:
    """Directories under `root` that git ignores whole, or None outside a git checkout.

    A directory that matches an ignore pattern and still holds tracked files is
    not listed: git ignores only the untracked files in it.
    """

    command = ["git", "-C", str(root), "ls-files", "--others", "--ignored",
               "--exclude-standard", "--directory", "-z"]
    try:
        listed = subprocess.run(command, capture_output=True, text=True, errors="replace", check=False)
    except OSError:
        return None
    if listed.returncode != 0:
        return None
    return frozenset(root / item.rstrip("/") for item in listed.stdout.split("\0") if item.endswith("/"))


@dataclass
class SkipRule:
    """Which directories a walk of one project leaves out.

    `ALWAYS_SKIP_DIRS` are left out at any depth, and so is every directory git
    ignores whole, whatever its name. `OUTPUT_DIRS` are also left out directly
    under the project root, or below an ignored directory named as a path.
    Anywhere else such a name is a source package. Outside a git checkout
    nothing tells the two apart, and the name is left out at any depth.
    """

    root: Path
    ignored: frozenset[Path] | None = None
    # Left out by name alone, yet holding source files.
    unconfirmed: set[Path] = field(default_factory=set)

    @classmethod
    def for_project(cls, root: Path) -> "SkipRule":
        root = root.resolve()
        return cls(root, ignored_directories(root))

    def confirmed_output(self, path: Path) -> bool:
        if self.ignored is None:
            return False
        return any(candidate in self.ignored for candidate in (path, *path.parents))

    def git_ignores(self, path: Path) -> bool:
        return self.ignored is not None and path in self.ignored

    def skips(self, directory: Path, name: str) -> bool:
        path = directory / name
        if name in ALWAYS_SKIP_DIRS or self.git_ignores(path):
            return True
        return name in OUTPUT_DIRS and self._skips_output(directory, path)

    def _skips_output(self, directory: Path, path: Path) -> bool:
        return self.ignored is None or directory == self.root or self.confirmed_output(path)

    def note_skipped(self, path: Path) -> None:
        if path.name in OUTPUT_DIRS and not self.confirmed_output(path) and _holds_source(path):
            self.unconfirmed.add(path)


def _sources_in(directory: str, names: list[str]) -> list[Path]:
    paths = (Path(directory) / name for name in names)
    return [path for path in paths if language_of(path) is not None and not is_test_file(path)]


def _holds_source(directory: Path) -> bool:
    for dirpath, dirnames, filenames in os.walk(directory):
        dirnames[:] = [name for name in dirnames if name not in ALWAYS_SKIP_DIRS | TEST_DIRS]
        if _sources_in(dirpath, filenames):
            return True
    return False


def _kept(rule: SkipRule, directory: Path, names: list[str]) -> list[str]:
    kept = []
    for name in names:
        if name in TEST_DIRS:
            continue
        if rule.skips(directory, name):
            rule.note_skipped(directory / name)
        else:
            kept.append(name)
    return kept


def _walk(root: Path, rule: SkipRule) -> list[Path]:
    if not root.exists():
        return []
    if root.is_file():
        return [root]
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = _kept(rule, Path(dirpath), dirnames)
        found.extend(_sources_in(dirpath, filenames))
    return found


def iter_source_files(roots: list[Path], rule: SkipRule | None = None) -> list[Path]:
    """Source files under `roots`. Without a rule, each root is its own project."""

    files: set[Path] = set()
    for root in roots:
        root = root.resolve()
        for path in _walk(root, rule or SkipRule.for_project(root)):
            files.add(path.resolve())
    return sorted(files, key=lambda path: path.as_posix())
