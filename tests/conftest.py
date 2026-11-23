"""Keep a mutant from launching coverage against the project under test.

`run()` falls through into `run_coverage` when a mutant skips the help return.
That would delete `target/coverage` and recurse into this suite.
"""

import pytest
import os
from crapper.integrity import begin_coverage
from crapper.integrity import inputs, report_paths, seal


def mark_reports_fresh(root, run):
    """Fixture timestamps explicitly distinguish writes even on coarse clocks."""
    for path in report_paths(root):
        previous = run.reports.get(path.relative_to(root).as_posix(), (0,))[0]
        stamp = max(run.started_ns, previous) + 1
        os.utime(path, ns=(stamp, stamp))


@pytest.fixture
def coverage_receipt():
    def record(root):
        before = inputs(root)
        start = begin_coverage(root)
        for path in report_paths(root):
            path.write_bytes(path.read_bytes())
        mark_reports_fresh(root, start)
        seal(root, before, start, 'fixture test run')
    return record


@pytest.fixture(autouse=True)
def do_not_launch_project_coverage(monkeypatch):
    monkeypatch.setattr("crapper.cli.run_coverage", lambda *_args, **_kwargs: None)
