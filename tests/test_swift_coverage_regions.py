import json
import pytest
from crapper.languages.swift_coverage import _line_counts, load_swift_coverage


@pytest.mark.parametrize('segments,expected', [
    ([], {}),
    ([[1,1,3,True,True,False],[4,1,0,False,False,False]], {1:3,2:3,3:3,4:3}),
    ([[1,1,0,True,True,False],[2,1,0,False,True,False]], {1:0}),
    ([[1,1,0,False,False,False],[3,1,2,True,True,False]], {3:2}),
    ([[1,1,1,True,True,False],[1,4,7,True,True,False]], {1:7}),
    ([[1,1,4,True,True,True]], {1:0}),
])
def test_line_regions_include_carry_and_exclude_skipped_lines(segments, expected):
    assert _line_counts(segments) == expected


@pytest.mark.parametrize('contents', ['not JSON', '[]', '{}', '{"type":"llvm.coverage.json.export","data":[{"files":[{}]}]}'])
def test_malformed_swift_exports_do_not_publish_partial_counts(tmp_path, capsys, contents):
    source=tmp_path/'Sources/Demo/App.swift'
    source.parent.mkdir(parents=True)
    source.write_text('func run() {}')
    folder=tmp_path/'target/coverage/swift'
    folder.mkdir(parents=True)
    (folder/'coverage.json').write_text(contents)
    assert load_swift_coverage(tmp_path) == {}
    assert 'skipped' in capsys.readouterr().err


def test_export_merges_only_scored_source_files(tmp_path):
    source=tmp_path/'Sources/Demo/App.swift'
    source.parent.mkdir(parents=True)
    source.write_text('func run() {}')
    folder=tmp_path/'target/coverage/swift'
    folder.mkdir(parents=True)
    files=[{'filename':str(source), 'segments':[[1,1,0,True,True,False]]},
           {'filename':str(tmp_path/'Tests/Other.swift'), 'segments':[[1,1,1,True,True,False]]}]
    export={'type':'llvm.coverage.json.export','data':[{'files':files}]}
    (folder/'first.json').write_text(json.dumps(export))
    files[0]['segments'][0][2]=1
    (folder/'second.json').write_text(json.dumps(export))
    records=load_swift_coverage(tmp_path)
    assert list(records)==[str(source)]
    assert records[str(source)] == {1:(1,1)}
