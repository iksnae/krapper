"""Legacy runner failures are exercised with local fixtures and fake commands only."""
import json
import pytest
from crapper import runners


@pytest.mark.parametrize('marker,statuses', [(None, []), ('bb.edn',[0]), ('deps.edn',[1,0]), ('deps.edn',[1,1])])
def test_clojure_retry_and_missing_project(tmp_path, monkeypatch, capsys, marker, statuses):
    if marker:
        (tmp_path/marker).write_text('{}')
    pending=iter(statuses)
    calls=[]
    def command(argv, cwd):
        calls.append((argv,cwd))
        return next(pending)
    monkeypatch.setattr(runners,'run_shell',command)
    runners._cover_clojure(tmp_path)
    assert len(calls)==len(statuses)
    assert all(cwd==tmp_path for _,cwd in calls)
    if len(statuses)==2:
        assert calls[1][0]==['clj','-M:cov']
    if statuses==[1,1]:
        assert 'exited 1' in capsys.readouterr().err


def test_java_without_build_file_does_not_launch_tools(tmp_path, monkeypatch, capsys):
    source=tmp_path/'App.java';source.write_text('class App {}')
    monkeypatch.setattr(runners,'run_shell',lambda *args: pytest.fail('unexpected Java runner'))
    runners._cover_java(tmp_path,[source])
    assert 'No pom.xml' in capsys.readouterr().err


def test_marker_search_terminates_when_stop_is_not_an_ancestor(tmp_path):
    source=tmp_path/'code/app.go'
    source.parent.mkdir();source.write_text('package app')
    assert runners.nearest_marker(source,'krapper-test-marker-does-not-exist',tmp_path/'unrelated') is None


@pytest.mark.parametrize('status,existing_exec',[(0,False),(0,True),(1,False),(1,True)])
def test_java_runner_clears_old_exec_and_reports_failure(tmp_path,monkeypatch,capsys,status,existing_exec):
    (tmp_path/'pom.xml').write_text('<project/>')
    source=tmp_path/'App.java'; source.write_text('class App {}')
    old=tmp_path/'target/jacoco.exec'
    if existing_exec:
        old.parent.mkdir(); old.write_bytes(b'stale')
    calls=[]
    monkeypatch.setattr(runners,'run_shell',lambda argv,cwd: calls.append((argv,cwd)) or status)
    runners._cover_java(tmp_path,[source])
    assert not old.exists()
    assert calls==[(runners._MAVEN,tmp_path)]
    assert ('exited 1' in capsys.readouterr().err)==bool(status)


@pytest.mark.parametrize('version,ready',[(None,False),(None,True),('3.2.4',True)])
def test_vitest_install_readiness_and_version(tmp_path,monkeypatch,version,ready):
    (tmp_path/'package.json').write_text('{"scripts":{"test":"vitest"}}')
    if version:
        installed=tmp_path/'node_modules/vitest/package.json'
        installed.parent.mkdir(parents=True)
        installed.write_text(json.dumps({'version':version}))
    calls=[]
    def install(argv,cwd):
        calls.append(argv)
        if ready:
            (tmp_path/'node_modules/@vitest/coverage-v8').mkdir(parents=True)
        return 0
    monkeypatch.setattr(runners,'run_shell',install)
    assert runners._ensure_vitest_coverage(tmp_path)==ready
    assert calls[0][-1]==('@vitest/coverage-v8@'+version if version else '@vitest/coverage-v8')
    assert json.loads((tmp_path/'package.json').read_text())=={'scripts':{'test':'vitest'}}


def test_rust_install_success_without_binary_does_not_claim_ready(monkeypatch):
    monkeypatch.setattr(runners.shutil,'which',lambda _:None)
    calls=[]
    monkeypatch.setattr(runners,'run_shell',lambda argv,cwd: calls.append(argv) or 0)
    assert runners._rust_kind() is None
    assert calls==[['cargo','install','cargo-llvm-cov','--locked']]


@pytest.mark.parametrize('status',[0,1])
def test_rust_report_regeneration_and_failure(tmp_path,monkeypatch,capsys,status):
    (tmp_path/'Cargo.toml').write_text('[package]\nname="demo"\n')
    source=tmp_path/'lib.rs';source.write_text('fn run() {}')
    report=tmp_path/'target/coverage/rust/lcov.info';report.parent.mkdir(parents=True);report.write_text('stale')
    monkeypatch.setattr(runners,'_rust_kind',lambda:'llvm-cov')
    calls=[]
    monkeypatch.setattr(runners,'run_shell',lambda argv,cwd: calls.append((argv,cwd)) or status)
    runners._cover_rust(tmp_path,[source])
    assert not report.exists()
    assert len(calls)==1 and calls[0][1]==tmp_path
    assert ('exited 1' in capsys.readouterr().err)==bool(status)


@pytest.mark.parametrize('exists,test_status,export_status',[(False,0,0),(False,1,0),(True,1,0),(True,0,1),(True,0,0)])
def test_python_partial_test_and_export_failures(tmp_path,monkeypatch,capsys,exists,test_status,export_status):
    data=tmp_path/'.coverage'
    if exists:
        data.write_bytes(b'coverage data')
    calls=[]
    monkeypatch.setattr(runners,'run_shell',lambda argv,cwd: calls.append((argv,cwd)) or export_status)
    runners._record_python_lcov(tmp_path,test_status,data,['coverage','lcov'])
    assert len(calls)==int(exists)
    warned=bool(capsys.readouterr().err)
    assert warned==bool(test_status or export_status)
