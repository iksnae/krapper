import subprocess

import pytest

from crapper.cli import run
from crapper.discover import SkipRule, ignored_directories, iter_source_files
from crapper.integrity import inputs

GO = "package p\n\nfunc F(a bool) int {\n\tif a {\n\t\treturn 1\n\t}\n\treturn 2\n}\n"


def _write(root, relative, text=GO):
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
    return root


def _relative(root, files):
    return [path.relative_to(root).as_posix() for path in files]


def test_a_tracked_package_named_coverage_is_scored_and_root_output_stays_skipped(checkout):
    _write(checkout, "pkg/coverage/f.go")
    _write(checkout, "pkg/ok/g.go")
    _write(checkout, "coverage/lcov.info", "SF:pkg/ok/g.go\nDA:3,1\nend_of_record\n")
    _write(checkout, "coverage/report.js", "function shown() { return 1 }\n")
    assert _relative(checkout, iter_source_files([checkout])) == ["pkg/coverage/f.go", "pkg/ok/g.go"]


@pytest.mark.parametrize("name", ["build", "coverage", "dist", "out", "target"])
def test_a_nested_output_name_is_source_unless_git_ignores_it(checkout, name):
    _write(checkout, f"internal/{name}/f.go")
    _write(checkout, f"packages/web/{name}/bundle.js", "function built() { return 1 }\n")
    _write(checkout, ".gitignore", f"packages/*/{name}/\n")
    assert _relative(checkout, iter_source_files([checkout])) == [f"internal/{name}/f.go"]


def test_output_below_an_ignored_directory_is_output(checkout):
    _write(checkout, "generated/pkg/build/f.go")
    _write(checkout, ".gitignore", "generated/\n")
    rule = SkipRule.for_project(checkout)
    assert rule.skips(checkout / "generated" / "pkg", "build") is True
    assert rule.confirmed_output(checkout / "generated" / "pkg" / "build") is True


def test_an_ignore_pattern_does_not_hide_tracked_source(checkout):
    _write(checkout, "internal/build/f.go")
    _write(checkout, ".gitignore", "build/\n")
    _git(checkout, "add", "--force", "internal/build/f.go")
    assert _relative(checkout, iter_source_files([checkout])) == ["internal/build/f.go"]


def test_tool_and_dependency_directories_are_skipped_at_any_depth(checkout):
    _write(checkout, "pkg/ok/g.go")
    for skipped in ("pkg/vendor/dep/d.go", "pkg/testdata/t.go", "web/node_modules/m/index.js", "pkg/.venv/lib/x.py"):
        _write(checkout, skipped)
    assert _relative(checkout, iter_source_files([checkout])) == ["pkg/ok/g.go"]


def test_outside_git_an_output_name_is_skipped_at_any_depth(tmp_path):
    root = tmp_path.resolve()
    _write(root, "pkg/coverage/f.go")
    _write(root, "pkg/ok/g.go")
    assert ignored_directories(root) is None
    rule = SkipRule.for_project(root)
    assert _relative(root, iter_source_files([root], rule)) == ["pkg/ok/g.go"]
    assert rule.unconfirmed == {root / "pkg" / "coverage"}


def test_a_missing_git_binary_reads_as_outside_git(tmp_path, monkeypatch):
    def absent(*_args, **_kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr("crapper.discover.subprocess.run", absent)
    assert ignored_directories(tmp_path) is None


def test_naming_a_skipped_directory_scores_it(tmp_path):
    root = tmp_path.resolve()
    _write(root, "pkg/coverage/f.go")
    rule = SkipRule.for_project(root)
    assert _relative(root, iter_source_files([root / "pkg" / "coverage"], rule)) == ["pkg/coverage/f.go"]
    assert rule.unconfirmed == set()


def test_only_unconfirmed_output_that_holds_source_is_reported(checkout):
    _write(checkout, "pkg/ok/g.go")
    _write(checkout, "build/gen.go")
    _write(checkout, "dist/bundle.js", "function built() { return 1 }\n")
    _write(checkout, "out/notes.txt", "no source\n")
    _write(checkout, "coverage/tests/helper.go")
    _write(checkout, "coverage/node_modules/m/index.js", "function dep() { return 1 }\n")
    _write(checkout, ".gitignore", "dist/\n")
    rule = SkipRule.for_project(checkout)
    assert _relative(checkout, iter_source_files([checkout], rule)) == ["pkg/ok/g.go"]
    assert rule.unconfirmed == {checkout / "build"}


def test_the_cli_scores_the_nested_package_and_warns_about_unignored_root_output(checkout, capsys):
    _write(checkout, "pkg/coverage/f.go")
    _write(checkout, "build/gen.go")
    assert run(["--root", str(checkout), "--no-coverage"]) == 0
    captured = capsys.readouterr()
    assert "F " in captured.out
    assert "WARNING: source files skipped by directory name and not scored: build." in captured.err


def test_the_cli_is_quiet_when_nothing_doubtful_was_skipped(checkout, capsys):
    _write(checkout, "pkg/coverage/f.go")
    _write(checkout, "build/gen.go")
    _write(checkout, ".gitignore", "/build/\n")
    assert run(["--root", str(checkout), "--no-coverage"]) == 0
    assert "WARNING" not in capsys.readouterr().err


def test_receipt_inputs_bind_a_nested_package_named_coverage(checkout):
    _write(checkout, "pkg/coverage/f.go")
    _write(checkout, "coverage/lcov.info", "SF:pkg/coverage/f.go\nDA:3,1\nend_of_record\n")
    _write(checkout, "packages/web/dist/bundle.js", "function built() { return 1 }\n")
    _write(checkout, ".gitignore", "dist/\n")
    before = inputs(checkout)
    assert sorted(before) == [".gitignore", "pkg/coverage/f.go"]
    _write(checkout, "pkg/coverage/f.go", GO + "\nfunc G() {}\n")
    assert inputs(checkout)["pkg/coverage/f.go"] != before["pkg/coverage/f.go"]


def test_help_documents_the_rule(capsys):
    assert run(["--help"]) == 0
    out = capsys.readouterr().out
    assert "build, coverage, dist, out, target are skipped as build output" in out
    assert "only when git ignores them or they sit directly under the project root" in out
    assert "every directory git ignores is skipped, whatever its name" in out
