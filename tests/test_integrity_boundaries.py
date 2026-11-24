"""Failure-path checks for the source/report trust boundary."""
import json
from crapper.integrity import begin_coverage
import pytest
from conftest import mark_reports_fresh
from crapper.integrity import CoverageIntegrityError, RECEIPT, inputs, seal, verify


@pytest.mark.parametrize('case', ['no-targets', 'no-export', 'invalid-export', 'external-source', 'relative-source', 'external-target', 'empty-segments'])
def test_invalid_swift_evidence_refuses_receipt(tmp_path, case):
    (tmp_path/'Package.swift').write_text('// package fixture')
    folder = tmp_path/'target/coverage/swift'
    folder.mkdir(parents=True)
    target = {'name':'DemoTests', 'type':'test', 'path':'Tests/DemoTests'}
    targets = [] if case == 'no-targets' else [target]
    if case == 'external-target':
        target['path'] = '../other-tests'
    filename = str(tmp_path/'Tests/DemoTests/Test.swift')
    if case == 'external-source':
        filename = '/other-checkout/Tests/DemoTests/Test.swift'
    if case == 'relative-source':
        filename = 'Tests/DemoTests/Test.swift'
    segments = [] if case == 'empty-segments' else [[1,1,1,True,True,False]]
    export = {'type':'llvm.coverage.json.export', 'data':[{'files':[{'filename':filename, 'segments':segments}]}]}
    if case == 'invalid-export':
        export['type'] = 'not coverage'
    before = inputs(tmp_path)
    started = begin_coverage(tmp_path)
    (tmp_path/'target/coverage/swift-package.json').write_text(json.dumps({'targets':targets}))
    if case == 'no-export':
        (folder/'lcov.info').write_text('SF:Sources/Demo.swift\nDA:1,1\nend_of_record\n')
    else:
        (folder/'coverage.json').write_text(json.dumps(export))
    mark_reports_fresh(tmp_path,started)
    with pytest.raises(CoverageIntegrityError):
        seal(tmp_path, before, started, 'fixture coverage run')
    assert not (tmp_path/RECEIPT).exists()


@pytest.mark.parametrize('field,value', [('version', 99), ('checkout', '/other-checkout'), ('reports', {})])
def test_invalid_receipt_identity_is_rejected(tmp_path, coverage_receipt, field, value):
    (tmp_path/'app.ts').write_text('export function value() { return 1; }')
    report=tmp_path/'coverage/lcov.info'
    report.parent.mkdir()
    report.write_text('SF:app.ts\nDA:1,1\nend_of_record\n')
    coverage_receipt(tmp_path)
    receipt=json.loads((tmp_path/RECEIPT).read_text())
    receipt[field]=value
    (tmp_path/RECEIPT).write_text(json.dumps(receipt))
    with pytest.raises(CoverageIntegrityError):
        verify(tmp_path)


def test_input_inventory_excludes_reports_and_os_metadata(tmp_path):
    (tmp_path/'app.ts').write_text('source')
    (tmp_path/'.DS_Store').write_bytes(b'metadata')
    (tmp_path/'coverage.out').write_text('mode: set\n')
    assert list(inputs(tmp_path)) == ['app.ts']


def test_symlinked_input_cannot_read_outside_checkout(tmp_path):
    outside=tmp_path/'outside.txt'
    outside.write_text('private')
    root=tmp_path/'checkout'
    root.mkdir()
    (root/'linked.txt').symlink_to(outside)
    with pytest.raises(CoverageIntegrityError, match='escapes checkout'):
        inputs(root)
