import shlex
import subprocess
import sys

import pytest

from crapper.cli import run
from crapper.discover import SkipRule, iter_source_files
from crapper.integrity import RECEIPT, inputs
from crapper.runners import run_coverage

JS = "export function f(a) { return a ? 1 : 2 }\n"


def _write(root, relative, text=JS):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _git(root, *args):
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


@pytest.fixture
def checkout(tmp_path):
    root = tmp_path.resolve()
    _git(root, "init")
    _write(root, "src/app.js")
    return root


def _relative(root, files):
    return [path.relative_to(root).as_posix() for path in files]


def test_an_ignored_directory_is_neither_discovered_nor_hashed(checkout):
    _write(checkout, ".gitignore", "/gen\n")
    _write(checkout, "gen/x.js")
    _write(checkout, "gen/sub/y.js")
    assert _relative(checkout, iter_source_files([checkout])) == ["src/app.js"]
    assert not [name for name in inputs(checkout) if name.startswith("gen/")]


def test_a_nested_ignored_directory_with_any_name_is_skipped(checkout):
    _write(checkout, ".gitignore", "/app/src/wasm\n")
    _write(checkout, "app/src/wasm/bindings.js")
    _write(checkout, "app/src/main.js")
    assert _relative(checkout, iter_source_files([checkout])) == ["app/src/main.js", "src/app.js"]


def test_an_unignored_directory_with_the_same_name_is_scored(checkout):
    _write(checkout, "gen/x.js")
    assert _relative(checkout, iter_source_files([checkout])) == ["gen/x.js", "src/app.js"]
    assert "gen/x.js" in inputs(checkout)


def test_an_ignored_directory_holding_a_tracked_file_is_walked(checkout):
    _write(checkout, ".gitignore", "gen/\n")
    _write(checkout, "gen/x.js")
    _git(checkout, "add", "--force", "gen/x.js")
    _write(checkout, "gen/y.js")
    assert _relative(checkout, iter_source_files([checkout])) == ["gen/x.js", "gen/y.js", "src/app.js"]


def test_outside_git_an_unlisted_name_is_still_scored(tmp_path):
    root = tmp_path.resolve()
    _write(root, ".gitignore", "/gen\n")
    _write(root, "gen/x.js")
    assert _relative(root, iter_source_files([root])) == ["gen/x.js"]


def test_naming_an_ignored_directory_scores_all_of_it(checkout):
    _write(checkout, ".gitignore", "/gen\n")
    _write(checkout, "gen/x.js")
    _write(checkout, "gen/sub/y.js")
    rule = SkipRule.for_project(checkout)
    assert _relative(checkout, iter_source_files([checkout / "gen"], rule)) == ["gen/sub/y.js", "gen/x.js"]
    assert rule.unconfirmed == set()


def test_the_coverage_command_can_generate_into_an_ignored_directory(checkout, monkeypatch, capsys):
    _write(checkout, ".gitignore", "/gen\n")
    script = (
        "from pathlib import Path\n"
        "Path('gen').mkdir(exist_ok=True)\n"
        "Path('gen/x.js').write_text('export function g() { return 1 }\\n')\n"
        "Path('coverage').mkdir(exist_ok=True)\n"
        "Path('coverage/lcov.info').write_text('SF:src/app.js\\nDA:1,1\\nend_of_record\\n')\n"
    )
    monkeypatch.chdir(checkout)
    monkeypatch.setattr("crapper.cli.run_coverage", run_coverage)
    command = shlex.join([sys.executable, "-c", script])
    assert run(["--root", str(checkout), "--coverage-command", command]) == 0
    assert (checkout / RECEIPT).is_file()
    assert (checkout / "gen" / "x.js").is_file()
    assert run(["--root", str(checkout), "--threshold", "30"]) == 0
    edn = (checkout / ".metrics" / "crap.edn").read_text()
    assert '"src/app.js"' in edn and "gen/" not in edn
