import json
import subprocess

from crapper.cli import run


def _write(root, relative, text):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_snapshot_entries_with_one_namespace_and_name_differ_by_file(tmp_path):
    _write(tmp_path, "store/open_linux.go", "//go:build linux\n\npackage store\n\nfunc Open() int { return 1 }\n")
    _write(tmp_path, "store/open_darwin.go", "//go:build darwin\n\npackage store\n\n\nfunc Open() int { return 2 }\n")
    assert run(["--root", str(tmp_path), "--no-coverage"]) == 0
    snapshot = tmp_path / ".metrics" / "crap.edn"
    program = (
        '(->> (:entries (clojure.edn/read-string (slurp (first *command-line-args*))))'
        ' (map (juxt :namespace :name :file :line)) json/generate-string println)'
    )
    read = subprocess.run(["bb", "-e", program, str(snapshot)], capture_output=True, text=True, check=True)
    assert sorted(json.loads(read.stdout)) == [
        ["store", "Open", "store/open_darwin.go", 6],
        ["store", "Open", "store/open_linux.go", 5],
    ]
