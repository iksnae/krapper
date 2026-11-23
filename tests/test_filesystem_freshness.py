from dataclasses import replace
import os
import pytest
from crapper.integrity import CoverageIntegrityError, begin_coverage, inputs, seal, verify


def prepare(root):
    (root/'app.ts').write_text('export function run() { return 1; }')
    report=root/'coverage/lcov.info'
    report.parent.mkdir()
    return report


def test_new_report_at_same_filesystem_tick_is_fresh(tmp_path):
    report=prepare(tmp_path)
    before=inputs(tmp_path)
    run=begin_coverage(tmp_path)
    report.write_text('SF:app.ts\nDA:1,1\nend_of_record\n')
    os.utime(report,ns=(run.started_ns,run.started_ns))
    seal(tmp_path,before,run,'fixture test')
    verify(tmp_path)


def test_unchanged_report_at_same_tick_is_rejected(tmp_path):
    report=prepare(tmp_path)
    report.write_text('SF:app.ts\nDA:1,1\nend_of_record\n')
    before=inputs(tmp_path)
    run=begin_coverage(tmp_path)
    run=replace(run,started_ns=report.stat().st_mtime_ns)
    with pytest.raises(CoverageIntegrityError,match='rewrite cannot be established'):
        seal(tmp_path,before,run,'true')


def test_atomic_replacement_is_detected_even_with_same_mtime(tmp_path):
    report=prepare(tmp_path)
    report.write_text('SF:app.ts\nDA:1,1\nend_of_record\n')
    before=inputs(tmp_path)
    run=begin_coverage(tmp_path)
    run=replace(run,started_ns=report.stat().st_mtime_ns)
    fresh=report.with_suffix('.tmp')
    fresh.write_text(report.read_text())
    os.utime(fresh,ns=(run.started_ns,run.started_ns))
    fresh.replace(report)
    seal(tmp_path,before,run,'fixture test')
    verify(tmp_path)
