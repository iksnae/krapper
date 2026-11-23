import json
from crapper.integrity import begin_coverage
import pytest
from conftest import mark_reports_fresh
from crapper.integrity import CoverageIntegrityError, inputs, seal, verify
from crapper.cli import parse_args, run


def project(root):
    (root/'app.ts').write_text('export function value() { return 1; }')
    report=root/'coverage/lcov.info'
    report.parent.mkdir()
    report.write_text('SF:app.ts\nDA:1,1\nend_of_record\n')
    return report


def bind(root):
    before=inputs(root)
    start=begin_coverage(root)
    report=root/'coverage/lcov.info'
    report.write_text(report.read_text())
    mark_reports_fresh(root,start)
    seal(root,before,start,'test command')


def test_unbound_default_refuses(tmp_path):
    project(tmp_path)
    assert run(['--root',str(tmp_path)])==1
    assert not (tmp_path/'.metrics/crap.edn').exists()


def test_receipt_detects_source_report_and_inventory_changes(tmp_path):
    report=project(tmp_path)
    bind(tmp_path)
    verify(tmp_path)
    (tmp_path/'app.ts').write_text('changed')
    with pytest.raises(CoverageIntegrityError): verify(tmp_path)
    (tmp_path/'app.ts').write_text('export function value() { return 1; }')
    report.write_text(report.read_text()+'\n')
    with pytest.raises(CoverageIntegrityError): verify(tmp_path)
    bind(tmp_path)
    (tmp_path/'new.ts').write_text('new')
    with pytest.raises(CoverageIntegrityError): verify(tmp_path)


def test_stale_report_cannot_be_sealed(tmp_path):
    project(tmp_path)
    with pytest.raises(CoverageIntegrityError):
        seal(tmp_path,inputs(tmp_path),begin_coverage(tmp_path),'true')


def test_changed_inputs_during_command_cannot_be_sealed(tmp_path):
    report=project(tmp_path)
    before=inputs(tmp_path)
    start=begin_coverage(tmp_path)
    (tmp_path/'app.ts').write_text('changed')
    report.write_text(report.read_text())
    with pytest.raises(CoverageIntegrityError): seal(tmp_path,before,start,'test')


def test_override_cannot_gate(tmp_path):
    project(tmp_path)
    assert run(['--root',str(tmp_path),'--allow-unverified-coverage'])==0
    assert parse_args(['--allow-unverified-coverage','--threshold','30']).action=='help'


def test_partial_swift_export_is_rejected(tmp_path):
    (tmp_path/'Package.swift').write_text('// fixture')
    folder=tmp_path/'target/coverage/swift'
    folder.mkdir(parents=True)
    desc=tmp_path/'target/coverage/swift-package.json'
    desc.write_text(json.dumps({'targets':[{'name':name,'type':'test','path':f'Tests/{name}'} for name in ['ATests','BTests']]}))
    export=folder/'coverage.json'
    data={'type':'llvm.coverage.json.export','data':[{'files':[{'filename':str(tmp_path/'Tests/ATests/A.swift'),'segments':[[1,1,1,True,True,False]]}]}]}
    before=inputs(tmp_path); start=begin_coverage(tmp_path)
    export.write_text(json.dumps(data)); desc.write_text(desc.read_text())
    mark_reports_fresh(tmp_path,start)
    with pytest.raises(CoverageIntegrityError,match='BTests'): seal(tmp_path,before,start,'swift test')
    data['data'][0]['files'].append({'filename':str(tmp_path/'Tests/BTests/B.swift'),'segments':[[1,1,1,True,True,False]]})
    start=begin_coverage(tmp_path); export.write_text(json.dumps(data)); desc.write_text(desc.read_text())
    mark_reports_fresh(tmp_path,start)
    seal(tmp_path,before,start,'swift test'); verify(tmp_path)
