"""Our self-gate must account for every explicitly written implementation function."""
import ast
from pathlib import Path
from crapper.languages.python import functions_in_source


def test_self_analysis_accounts_for_every_implementation_function():
    root=Path(__file__).resolve().parents[1]
    for path in (root/'src/crapper').rglob('*.py'):
        source=path.read_text()
        definitions={node.lineno for node in ast.walk(ast.parse(source)) if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef))}
        measured={function.start_line for function in functions_in_source(source,str(path),str(root))}
        assert measured == definitions, f'{path}: unaccounted definitions {definitions-measured}'
