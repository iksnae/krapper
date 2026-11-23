import shlex
import sys
from crapper.integrity import begin_coverage
import pytest
from conftest import mark_reports_fresh
from crapper.cli import run
from crapper.integrity import CoverageIntegrityError, RECEIPT, inputs, seal, verify
from crapper.runners import run_coverage


def test_real_successful_command_creates_reusable_receipt(tmp_path, monkeypatch):
    (tmp_path/'app.ts').write_text('export function value() { return 1; }')
    script="from pathlib import Path; p=Path('coverage/lcov.info'); p.parent.mkdir(exist_ok=True); p.write_text('SF:app.ts\\nDA:1,1\\nend_of_record\\n')"
    command=shlex.join([sys.executable,'-c',script])
    monkeypatch.setattr('crapper.cli.run_coverage',run_coverage)
    assert run(['--root',str(tmp_path),'--coverage-command',command])==0
    assert (tmp_path/RECEIPT).is_file()
    assert run(['--root',str(tmp_path),'--threshold','1'])==0
    assert run(['--root',str(tmp_path),'--coverage-command','exit 7'])==1
    assert not (tmp_path/RECEIPT).exists()
    assert run(['--root',str(tmp_path)])==1


def test_modified_during_analysis_is_rejected(tmp_path, coverage_receipt, monkeypatch):
    (tmp_path/'app.ts').write_text('export function value() { return 1; }')
    report=tmp_path/'coverage/lcov.info'; report.parent.mkdir()
    report.write_text('SF:app.ts\nDA:1,1\nend_of_record\n')
    coverage_receipt(tmp_path)
    from crapper.analyze import analyze_files
    def mutate(*args):
        entries=analyze_files(*args)
        (tmp_path/'app.ts').write_text('changed')
        return entries
    monkeypatch.setattr('crapper.cli.analyze_files',mutate)
    assert run(['--root',str(tmp_path)])==1
    assert not (tmp_path/'.metrics/crap.edn').exists()


def test_cross_checkout_lcov_rejected(tmp_path):
    (tmp_path/'app.ts').write_text('source')
    before=inputs(tmp_path); start=begin_coverage(tmp_path)
    report=tmp_path/'coverage/lcov.info'; report.parent.mkdir()
    report.write_text('SF:/other/checkout/app.ts\nDA:1,1\nend_of_record\n')
    mark_reports_fresh(tmp_path,start)
    with pytest.raises(CoverageIntegrityError,match='checkout'):
        seal(tmp_path,before,start,'test')


def test_generated_pytest_cache_is_not_a_coverage_input(tmp_path):
    (tmp_path/'app.ts').write_text('source')
    report=tmp_path/'coverage/lcov.info'
    report.parent.mkdir()
    report.write_text('SF:app.ts\nDA:1,1\nend_of_record\n')
    before=inputs(tmp_path)
    started=begin_coverage(tmp_path)
    cache=tmp_path/'.pytest_cache/v/cache/nodeids'
    cache.parent.mkdir(parents=True)
    cache.write_text('["test_added"]')
    report.write_text(report.read_text())
    mark_reports_fresh(tmp_path,started)
    seal(tmp_path,before,started,'pytest fixture')
    cache.write_text('["test_changed"]')
    verify(tmp_path)


def test_empty_selection_cannot_pass_gate(tmp_path):
    assert run(['--root',str(tmp_path),'--threshold','30'])==1
    assert run(['--root',str(tmp_path),'--coverage-command','true'])==1


def test_receipt_corruption_and_new_report_rejected(tmp_path, coverage_receipt):
    (tmp_path/'app.ts').write_text('source')
    report=tmp_path/'coverage/lcov.info'; report.parent.mkdir()
    report.write_text('SF:app.ts\nDA:1,1\nend_of_record\n')
    coverage_receipt(tmp_path)
    (tmp_path/'coverage/extra').mkdir()
    (tmp_path/'coverage/extra/lcov.info').write_text(report.read_text())
    with pytest.raises(CoverageIntegrityError): verify(tmp_path)
    (tmp_path/RECEIPT).write_text('[]')
    with pytest.raises(CoverageIntegrityError): verify(tmp_path)
