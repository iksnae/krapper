"""Keep a mutant from launching coverage against the project under test.

`run()` falls through into `run_coverage` when a mutant skips the help return.
That would delete `target/coverage` and recurse into this suite.
"""

import pytest
import time
from crapper.integrity import inputs, report_paths, seal


@pytest.fixture
def coverage_receipt():
    def record(root):
        before = inputs(root)
        start = time.time_ns()
        for path in report_paths(root):
            path.write_bytes(path.read_bytes())
        seal(root, before, start, 'fixture test run')
    return record


@pytest.fixture(autouse=True)
def do_not_launch_project_coverage(monkeypatch):
    monkeypatch.setattr("crapper.cli.run_coverage", lambda *_args, **_kwargs: None)
