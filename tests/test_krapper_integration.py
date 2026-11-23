import json
from crapper.cli import run
from crapper.coverage import load_bundle
from crapper.discover import iter_source_files
from crapper.analyze import analyze_files


def test_four_languages_with_existing_coverage(tmp_path, coverage_receipt):
    sources = {
        'Sources/Demo/Choose.swift': 'func choose(_ ok: Bool) -> Int { if ok { return 1 }; return 0 }\n',
        'main.go': 'package demo\nfunc Choose(ok bool) int { if ok { return 1 }; return 0 }\n',
        'src/lib.rs': 'pub fn choose(ok: bool) -> i32 { if ok { 1 } else { 0 } }\n',
        'src/app.ts': 'export function choose(ok: boolean) { return ok ? 1 : 0; }\n',
    }
    for name, source in sources.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source)
    coverage = tmp_path / 'coverage'
    coverage.mkdir()
    coverage.joinpath('lcov.info').write_text(''.join(f'SF:{name}\nDA:1,1\nDA:2,1\nend_of_record\n' for name in sources))
    (tmp_path / 'coverage.out').write_text('mode: set\nmain.go:2.1,2.80 3 1\n')
    entries = analyze_files(iter_source_files([tmp_path]), tmp_path, load_bundle(tmp_path))
    assert {e.language for e in entries} == {'swift', 'go', 'rust', 'typescript'}
    assert all(e.complexity == 2 and e.coverage == 100 and e.crap == 2 for e in entries)
    coverage_receipt(tmp_path)
    assert run(['--root', str(tmp_path), '--threshold', '1']) == 2


def test_swiftpm_json_coverage(tmp_path):
    source = tmp_path / 'Sources/Demo/App.swift'
    source.parent.mkdir(parents=True)
    source.write_text('func run() {\n print(1)\n}\n')
    folder = tmp_path / 'target/coverage/swift'
    folder.mkdir(parents=True)
    export = {'type':'llvm.coverage.json.export', 'data':[{'files':[{'filename':str(source), 'segments':[[1,12,1,True,True,False],[3,2,0,False,False,False]]}]}]}
    folder.joinpath('demo.json').write_text(json.dumps(export))
    entries = analyze_files([source], tmp_path, load_bundle(tmp_path))
    assert len(entries) == 1
    assert entries[0].coverage == 100
    assert entries[0].namespace == 'Demo'


def test_multi_report_union(tmp_path):
    for folder, hits in [('a', 1), ('b', 0)]:
        path = tmp_path / 'coverage' / folder / 'lcov.info'
        path.parent.mkdir(parents=True)
        path.write_text(f'SF:app.ts\nDA:1,{hits}\nend_of_record\n')
    assert load_bundle(tmp_path).lcov['app.ts'][1] == (1, 1)
