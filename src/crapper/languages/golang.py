"""Go functions and cyclomatic complexity, following crap4go.

Decision points are `if`, `for`, `range`, each `switch` / type-switch case,
each `select` clause, and `&&` / `||`. Coverage later uses Go's statement
profile. The namespace is the package import path; methods are namespaced by
their receiver type (`import/path.Widget`) and named `Run`, which is the join
uml-viewer makes between a class and its operations.
"""

from pathlib import Path

from crapper.languages.treesitter import (
    absolute_path as _absolute,
    binary_logic,
    child_of_type,
    complexity,
    descendants,
    end_line,
    node_text,
    parse,
    start_line,
)
from crapper.model import Function

_DECISIONS = {
    "if_statement",
    "for_statement",
    "expression_case",
    "type_case",
    "communication_case",
    "default_case",
}


def _is_decision(node) -> bool:
    return node.type in _DECISIONS or binary_logic(node)


def _skip(_node) -> bool:
    return False


def _package_clause(data: bytes, root) -> str:
    for node in descendants(root):
        if node.type == "package_identifier":
            return node_text(data, node)
    return ""


def _type_identifiers(node) -> list[str]:
    found = []
    for item in descendants(node):
        if item.type == "type_identifier":
            found.append(item)
    return found


def _receiver_type(data: bytes, method) -> str | None:
    params = child_of_type(method, "parameter_list")
    if params is None:
        return None
    idents = _type_identifiers(params)
    if not idents:
        return None
    return node_text(data, idents[0])


def _method_name(data: bytes, method) -> str | None:
    ident = child_of_type(method, "field_identifier")
    if ident is None:
        return None
    return node_text(data, ident)


def _function_name(data: bytes, fn) -> str | None:
    ident = child_of_type(fn, "identifier")
    if ident is None:
        return None
    return node_text(data, ident)


def _module_directory(path: Path) -> Path | None:
    for directory in (path.parent, *path.parent.parents):
        if (directory / "go.mod").is_file():
            return directory
    return None


def _module_declaration(directory: Path) -> str | None:
    for line in (directory / "go.mod").read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("module "):
            return stripped.split(None, 1)[1].strip()
    return None


def package_namespace(path: str, package_name: str) -> str:
    """Import path of the package, or its package clause without a module."""
    directory = _module_directory(Path(path).resolve())
    if directory is None:
        return package_name
    module = _module_declaration(directory)
    if not module:
        return package_name
    relative = Path(path).resolve().parent.relative_to(directory).as_posix()
    return module if relative == "." else f"{module}/{relative}"


def _has_function_body(node) -> bool:
    return node.type in {"function_declaration", "method_declaration"} and child_of_type(node, "block") is not None


def _function_identity(data: bytes, node, package: str):
    if node.type == "method_declaration":
        receiver = _receiver_type(data, node)
        namespace = f"{package}.{receiver}" if receiver else None
        return _method_name(data, node), namespace
    return _function_name(data, node), package


def _record_function(data: bytes, node, package: str, path: str) -> Function | None:
    if not _has_function_body(node):
        return None
    name, namespace = _function_identity(data, node, package)
    if not name or namespace is None:
        return None
    return Function(name=name, namespace=namespace,
                    complexity=complexity(node, _is_decision, _skip),
                    start_line=start_line(node), end_line=end_line(node),
                    path=path, language="go")


def functions_in_source(
    source: str, path: str, project_root: str | None = None
) -> list[Function]:
    data, tree = parse(source, "go")
    package = package_namespace(_absolute(path, project_root), _package_clause(data, tree.root_node))
    found: list[Function] = []
    for node in descendants(tree.root_node):
        recorded = _record_function(data, node, package, path)
        if recorded is not None:
            found.append(recorded)
    return found
