from crapper.cli import parse_args


def test_empty_root_is_not_silently_current_directory():
    assert parse_args(['--root', '']).exit_code == 1


def test_options_can_be_interspersed_with_paths():
    options = parse_args(['src', '--source-root', 'lib', 'app', '--source-root', 'tools', '--no-coverage'])
    assert options.positionals == ['src', 'app']
    assert options.source_roots == ['lib', 'tools']
    assert options.no_coverage


def test_abbreviations_are_not_new_flags():
    assert parse_args(['--thres', '5']).exit_code == 1


def test_empty_negative_and_nonfinite_thresholds_are_rejected():
    for value in ['', '-1', 'nan', 'inf']:
        assert parse_args(['--threshold', value]).exit_code == 1
