from crapper.cli import run


def test_measured_file_without_functions_cannot_pass_threshold(tmp_path, coverage_receipt, capsys):
    (tmp_path/'app.ts').write_text('export const value = 1;')
    report=tmp_path/'coverage/lcov.info'
    report.parent.mkdir()
    report.write_text('SF:app.ts\nDA:1,1\nend_of_record\n')
    coverage_receipt(tmp_path)
    assert run(['--root',str(tmp_path),'--threshold','5']) == 1
    assert 'no scorable entries' in capsys.readouterr().err
