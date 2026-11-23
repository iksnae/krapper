from pathlib import Path
import pytest
from crapper.cli import parse_args, run
from crapper.coverage import parse_lcov
from crapper.languages.typescript import _module_namespace

@pytest.mark.parametrize('value', ['nan', 'inf', 'Infinity'])
def test_finite_threshold(value):
    assert parse_args(['--threshold', value]).action == 'help'

def test_default_does_not_run_coverage(tmp_path, monkeypatch):
    (tmp_path / 'app.go').write_text('package app\nfunc Run() {}')
    monkeypatch.setattr('crapper.cli.run_coverage', lambda *a: pytest.fail('executed coverage'))
    assert run(['--root', str(tmp_path)]) == 0

def test_lcov_union():
    a = 'SF:a.ts\nDA:1,1\nDA:2,1\nBRDA:1,0,0,1\nBRDA:1,0,1,0\nend_of_record\n'
    b = 'SF:a.ts\nDA:1,0\nBRDA:1,0,0,0\nBRDA:1,0,1,1\nend_of_record\n'
    for text in [a+b,b+a]:
        record = parse_lcov(text)['a.ts']
        assert record == {1:(1,1),2:(1,1)}
        assert record.branches == {1:(2,2)}

def test_package_identity():
    assert _module_namespace('packages/a/src/index.ts', '.') != _module_namespace('packages/b/src/index.ts', '.')
