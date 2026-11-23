import pytest
from crapper.cli import run
from crapper.analyze import analyze_files
from crapper.coverage import CoverageBundle
from crapper.discover import iter_source_files


def source(root, name='app.ts'):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('export function choose(ok: boolean) { return ok ? 1 : 0; }\n')
    return path


def test_missing_is_not_measured_zero(tmp_path, capsys):
    path = source(tmp_path)
    missing = analyze_files([path], tmp_path, CoverageBundle())[0]
    assert missing.coverage is None and missing.crap is None
    assert 'unavailable' in capsys.readouterr().err.lower()
    zero = analyze_files([path], tmp_path, CoverageBundle(lcov={'app.ts': {1:(0,1)}}))[0]
    assert zero.coverage == 0 and zero.crap == 6


@pytest.mark.parametrize('partial', [False, True])
def test_incomplete_threshold_fails(tmp_path, partial):
    source(tmp_path)
    if partial:
        source(tmp_path, 'covered.ts')
        report = tmp_path / 'coverage/lcov.info'
        report.parent.mkdir()
        report.write_text('SF:covered.ts\nDA:1,1\nend_of_record\n')
    assert run(['--root', str(tmp_path), '--threshold', '30']) == 1
    metrics = (tmp_path / '.metrics/crap.edn').read_text()
    assert ':coverage nil' in metrics and ':crap nil' in metrics


def test_missing_function_measurements_are_unavailable(tmp_path):
    path = source(tmp_path)
    entry = analyze_files([path], tmp_path, CoverageBundle(lcov={'app.ts': {20:(1,1)}}))[0]
    assert entry.coverage is None and entry.crap is None


def test_swift_test_directory_not_scored(tmp_path):
    source(tmp_path, 'SwiftTests/DemoTests/Test.swift')
    assert iter_source_files([tmp_path]) == []


def test_failed_command_preserves_previous_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr('crapper.cli.run_coverage', lambda *args: 7)
    source(tmp_path)
    snapshot = tmp_path / '.metrics/crap.edn'
    snapshot.parent.mkdir()
    snapshot.write_text('previous snapshot')
    assert run(['--root', str(tmp_path), '--coverage-command', 'exit 7']) == 1
    assert snapshot.read_text() == 'previous snapshot'
