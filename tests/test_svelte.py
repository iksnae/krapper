import pytest

from crapper.analyze import analyze_files
from crapper.coverage import load_bundle
from crapper.discover import is_test_file, iter_source_files, language_of
from crapper.languages.svelte import component_script
from crapper.languages.typescript import functions_in_source

COMPONENT = """\
<script module lang="ts">
  export function clamp(value: number, max: number): number {
    return value > max ? max : value;
  }
</script>

<script lang="ts">
  let { start = 0 }: { start?: number } = $props();
  let count = $state(start);

  function step(by: number) {
    if (by > 0 && count < 10) {
      count = clamp(count + by, 10);
    } else if (by < 0) {
      count = 0;
    }
  }

  const label = (n: number) => (n > 5 ? 'high' : 'low');

  function unused(flag: boolean) {
    if (flag) {
      return 1;
    }
    return 2;
  }
</script>

{#if count > 5}
  <p data-testid="state">{label(count)}</p>
{:else}
  <p data-testid="state">{label(count)}</p>
{/if}
<button onclick={() => step(3)}>up</button>

<style>
  p { color: red; }
</style>
"""

# Written by Vitest 3.2.7 with @vitest/coverage-v8 for COMPONENT under Svelte 5:
# one test mounts it with start=1, clicks the button twice, and calls clamp(1, 5).
VITEST_LCOV = """\
TN:
SF:src/lib/Widget.svelte
DA:2,1
DA:3,3
DA:4,3
DA:7,1
DA:8,1
DA:9,1
DA:11,1
DA:12,2
DA:13,2
DA:14,2
DA:15,0
DA:16,0
DA:17,2
DA:19,1
DA:21,1
DA:22,0
DA:23,0
DA:24,0
DA:25,0
DA:26,0
DA:27,1
DA:29,1
DA:30,1
DA:32,1
DA:34,1
BRDA:2,0,0,3
BRDA:3,1,0,0
BRDA:7,2,0,1
BRDA:11,3,0,2
BRDA:14,4,0,0
BRDA:19,5,0,3
BRDA:19,6,0,1
BRDA:19,7,0,2
BRDA:30,8,0,1
BRDA:30,9,0,1
BRDA:32,10,0,1
BRDA:32,11,0,2
BRDA:29,12,0,1
BRDA:29,13,0,2
end_of_record
"""


def _write(root, relative, text):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_module_and_instance_script_functions_keep_their_component_lines():
    functions = functions_in_source(COMPONENT, "src/lib/Widget.svelte", "/proj")
    assert [(fn.namespace, fn.name, fn.complexity, fn.start_line, fn.end_line) for fn in functions] == [
        ("lib.Widget", "clamp", 2, 2, 4),
        ("lib.Widget", "step", 4, 11, 17),
        ("lib.Widget", "label", 2, 19, 19),
        ("lib.Widget", "unused", 2, 21, 26),
    ]
    assert {fn.language for fn in functions} == {"typescript"}


def test_markup_logic_is_not_an_entry():
    source = "<script>\n  let n = 0;\n</script>\n{#if n > 1}<button onclick={() => (n ? 1 : 2)}>go</button>{/if}\n"
    assert functions_in_source(source, "src/Plain.svelte") == []


def test_a_component_without_a_script_has_no_entries():
    assert functions_in_source("<p>static</p>\n<style>p { color: red }</style>\n", "src/Static.svelte") == []


def test_plain_script_is_read_as_javascript_and_legacy_module_context_counts():
    source = """\
<script context="module">
  export function load(x) { return x ?? 1; }
</script>
<script>
  export let n = 0;
  function pick(a) {
    if (a > 1 || n) { return 1; }
    return 2;
  }
</script>
"""
    masked, grammar = component_script(source)
    assert grammar == "javascript"
    assert masked.count("\n") == source.count("\n")
    functions = functions_in_source(source, "src/routes/+page.svelte")
    assert [(fn.namespace, fn.name, fn.complexity, fn.start_line) for fn in functions] == [
        ("routes.+page", "load", 2, 2),
        ("routes.+page", "pick", 3, 6),
    ]


@pytest.mark.parametrize("tag", ['<script lang="ts">', "<script lang='typescript'>", "<script lang=ts>"])
def test_a_typescript_block_selects_the_typescript_grammar(tag):
    source = f"<script>\n  const one = () => 1;\n</script>\n{tag}\n  function typed(a: number): number {{ return a; }}\n</script>\n"
    assert component_script(source)[1] == "typescript"
    assert [fn.name for fn in functions_in_source(source, "Mixed.svelte")] == ["one", "typed"]


def test_a_script_nested_in_markup_is_not_component_code():
    source = """\
<svelte:head>
  <script>
    function tracker(a) { return a ? 1 : 2; }
  </script>
</svelte:head>
<script>
  function mine() { return 1; }
</script>
"""
    assert [fn.name for fn in functions_in_source(source, "Head.svelte")] == ["mine"]


def test_byte_spans_point_into_the_component_after_multibyte_markup():
    source = "<p>héllo — ✓</p>\n<script>\n  function after() { return 1; }\n</script>\n"
    function = functions_in_source(source, "Wide.svelte")[0]
    data = source.encode("utf-8")
    assert data[function.start_byte : function.end_byte].decode("utf-8") == "function after() { return 1; }"
    assert function.start_line == 3


def test_svelte_discovery_follows_the_existing_skip_and_test_rules(tmp_path):
    assert language_of("src/lib/Widget.svelte") == "typescript"
    assert is_test_file("src/lib/Widget.test.svelte") is True
    assert is_test_file("src/lib/Widget.spec.svelte") is True
    assert is_test_file("src/lib/Widget.svelte") is False
    assert is_test_file("src/lib/Widget.svelte.test.ts") is True
    kept = _write(tmp_path, "src/lib/Widget.svelte", COMPONENT)
    for skipped in (
        "node_modules/pkg/Dep.svelte",
        "dist/Built.svelte",
        "build/Built.svelte",
        "src/__tests__/Harness.svelte",
        "tests/Fixture.svelte",
        "src/lib/Widget.test.svelte",
    ):
        _write(tmp_path, skipped, COMPONENT)
    assert iter_source_files([tmp_path]) == [kept.resolve()]


def test_vitest_lcov_gives_each_component_function_its_coverage_and_crap(tmp_path):
    component = _write(tmp_path, "src/lib/Widget.svelte", COMPONENT)
    _write(tmp_path, "coverage/lcov.info", VITEST_LCOV)
    entries = analyze_files([component], tmp_path, load_bundle(tmp_path))
    scored = {entry.name: (entry.namespace, entry.complexity, entry.coverage, entry.crap) for entry in entries}
    assert scored == {
        "step": ("lib.Widget", 4, 50.0, 6.0),
        "unused": ("lib.Widget", 2, 16.6667, 4.3148),
        "clamp": ("lib.Widget", 2, 50.0, 2.5),
        "label": ("lib.Widget", 2, 100.0, 2.0),
    }
