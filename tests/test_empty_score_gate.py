from types import SimpleNamespace
from crapper.cli import run, Options, _threshold_status


def test_threshold_error_does_not_round_away_the_violation(capsys):
    assert _threshold_status(Options(action='analyze',threshold=5.0),[SimpleNamespace(crap=5.0488)]) == 2
    assert '5.0488 > 5.0' in capsys.readouterr().err


def test_measured_file_without_functions_cannot_pass_threshold(tmp_path, coverage_receipt, capsys):
    (tmp_path/'app.ts').write_text('export const value = 1;')
    report=tmp_path/'coverage/lcov.info'
    report.parent.mkdir()
    report.write_text('SF:app.ts\nDA:1,1\nend_of_record\n')
    coverage_receipt(tmp_path)
    assert run(['--root',str(tmp_path),'--threshold','5']) == 1
    assert 'no scorable entries' in capsys.readouterr().err
