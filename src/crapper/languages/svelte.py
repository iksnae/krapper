"""Svelte component scripts, prepared for the TypeScript and JavaScript reader.

A component's functions live in its top-level `<script>` blocks: the instance
script and the module script (`<script module>` or `context="module"`). Every
byte outside those blocks becomes a space, and newlines stay, so each function
keeps the line and byte position it has in the `.svelte` file. Coverage reports
name those lines.

Markup is not scored: `{#if}` blocks and inline handlers have no entry. A
`<script>` nested in an element such as `<svelte:head>` is page markup, not
component code.
"""

import re

from crapper.languages.treesitter import child_of_type, node_text, parse

_TYPESCRIPT_LANG = re.compile(r"""\blang\s*=\s*["']?(?:ts|typescript)\b""")
_NEWLINE = 10
_SPACE = 32


def _script_blocks(data: bytes, root) -> list[tuple[object, str]]:
    """Each top-level script body with the text of its opening tag."""

    blocks = []
    for element in root.children:
        body = child_of_type(element, "raw_text")
        if element.type == "script_element" and body is not None:
            blocks.append((body, node_text(data, child_of_type(element, "start_tag"))))
    return blocks


def _grammar(tags: list[str]) -> str:
    if any(_TYPESCRIPT_LANG.search(tag) for tag in tags):
        return "typescript"
    return "javascript"


def component_script(source: str) -> tuple[str, str]:
    """The component with only its script bodies left, and the grammar to read it with."""

    data, tree = parse(source, "svelte")
    blocks = _script_blocks(data, tree.root_node)
    masked = bytearray(_NEWLINE if byte == _NEWLINE else _SPACE for byte in data)
    for body, _tag in blocks:
        masked[body.start_byte : body.end_byte] = data[body.start_byte : body.end_byte]
    return masked.decode("utf-8"), _grammar([tag for _body, tag in blocks])
