"""A Swift package below --root must not block strict coverage of the other languages."""
import json
import shlex
import sys

from conftest import mark_reports_fresh
from crapper.cli import run
from crapper.integrity import begin_coverage, inputs, seal, unverified_swift_packages, verify
from crapper.runners import run_coverage

GO = "package demo\n\nfunc Place(x int) int {\n\tif x > 0 {\n\t\treturn x\n\t}\n\treturn 0\n}\n"
SWIFT = "func greet(_ loud: Bool) -> String {\n    if loud {\n        return \"HI\"\n    }\n    return \"hi\"\n}\n"
GO_PROFILE = "mode: set\\nexample.com/demo/board.go:3.23,4.11 1 1\\nexample.com/demo/board.go:4.11,6.3 1 1\\nexample.com/demo/board.go:7.2,7.10 1 1\\n"


def _write(root, relative, text):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _go_repo_with_nested_swift(root):
    _write(root, "go.mod", "module example.com/demo\n\ngo 1.22\n")
    _write(root, "board.go", GO)
    _write(root, "mobile/ios/Package.swift", "// swift-tools-version:5.9\n")
    _write(root, "mobile/ios/Sources/App/Greeter.swift", SWIFT)


def _command(script):
    return shlex.join([sys.executable, "-c", script])


def _rows(text):
    return {line.split()[0]: line.split() for line in text.splitlines() if line.startswith(("Place", "greet"))}


def test_strict_go_coverage_runs_and_reports_the_nested_swift_functions_as_unavailable(tmp_path, monkeypatch, capsys):
    _go_repo_with_nested_swift(tmp_path)
    monkeypatch.setattr("crapper.cli.run_coverage", run_coverage)
    script = f"from pathlib import Path; Path('coverage.out').write_text('{GO_PROFILE}')"
    assert run(["--root", str(tmp_path), "--coverage-command", _command(script)]) == 0
    captured = capsys.readouterr()
    rows = _rows(captured.out)
    assert rows["Place"][-2:] == ["100.0%", "2.0"]
    assert rows["greet"][-2:] == ["N/A", "N/A"]
    assert "Swift package mobile/ios is not at --root; its coverage is not verified and its functions are N/A." in captured.err
    assert run(["--root", str(tmp_path)]) == 0
    assert run(["--root", str(tmp_path), "--threshold", "30"]) == 1
    assert run(["--root", str(tmp_path), "--threshold", "30", "board.go"]) == 0


def test_lcov_naming_the_nested_swift_file_does_not_score_it(tmp_path, monkeypatch, capsys):
    _go_repo_with_nested_swift(tmp_path)
    monkeypatch.setattr("crapper.cli.run_coverage", run_coverage)
    lcov = "SF:mobile/ios/Sources/App/Greeter.swift\\nDA:1,1\\nDA:2,1\\nDA:3,1\\nDA:5,1\\nend_of_record\\n"
    script = (
        "from pathlib import Path; "
        f"Path('coverage.out').write_text('{GO_PROFILE}'); "
        f"p=Path('coverage/lcov.info'); p.parent.mkdir(exist_ok=True); p.write_text('{lcov}')"
    )
    assert run(["--root", str(tmp_path), "--coverage-command", _command(script)]) == 0
    rows = _rows(capsys.readouterr().out)
    assert rows["greet"][-2:] == ["N/A", "N/A"]
    assert rows["Place"][-2:] == ["100.0%", "2.0"]


def test_exploratory_coverage_still_reads_what_the_report_says(tmp_path, capsys):
    _go_repo_with_nested_swift(tmp_path)
    _write(tmp_path, "coverage/lcov.info", "SF:mobile/ios/Sources/App/Greeter.swift\nDA:1,1\nDA:2,1\nDA:3,1\nDA:5,1\nend_of_record\n")
    assert run(["--root", str(tmp_path), "--allow-unverified-coverage"]) == 0
    assert _rows(capsys.readouterr().out)["greet"][-2] == "100.0%"


def test_a_root_package_is_verified_as_before_and_a_nested_one_is_left_unverified(tmp_path):
    _write(tmp_path, "Package.swift", "// root")
    _write(tmp_path, "Examples/Demo/Package.swift", "// nested")
    folder = tmp_path / "target/coverage/swift"
    folder.mkdir(parents=True)
    description = tmp_path / "target/coverage/swift-package.json"
    export = {"type": "llvm.coverage.json.export", "data": [{"files": [
        {"filename": str(tmp_path / "Tests/DemoTests/Test.swift"), "segments": [[1, 1, 1, True, True, False]]}]}]}
    before = inputs(tmp_path)
    started = begin_coverage(tmp_path)
    description.write_text(json.dumps({"targets": [{"name": "DemoTests", "type": "test", "path": "Tests/DemoTests"}]}))
    (folder / "coverage.json").write_text(json.dumps(export))
    mark_reports_fresh(tmp_path, started)
    seal(tmp_path, before, started, "swift test")
    verify(tmp_path)
    assert unverified_swift_packages(tmp_path) == ["Examples/Demo"]


def test_a_root_package_alone_has_no_unverified_packages(tmp_path):
    _write(tmp_path, "Package.swift", "// root")
    assert unverified_swift_packages(tmp_path) == []
