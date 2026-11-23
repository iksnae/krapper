import pytest
from crapper.languages.swift import _skipped, _string_end
from crapper.languages.golang import package_namespace
from crapper.languages.java import functions_in_source as java_functions
from crapper.languages.typescript import functions_in_source, _template_text, _path_from_route


@pytest.mark.parametrize('text,start,hashes,end', [
    ('"hello"',0,0,7),
    ('"a\\"b"',0,0,6),
    ('"a\nrest',0,0,2),
    ('"unterminated',0,0,13),
    ('"""a\nb"""',0,0,9),
    ('#"raw\\"#',1,1,8),
])
def test_swift_literal_boundaries(text,start,hashes,end):
    assert _string_end(text,start,hashes) == end


@pytest.mark.parametrize('text,end', [('ordinary',None), ('###',None), ('// eof',6), ('// a\nnext',4), ('/* eof',6), ('/* ok */ tail',8), ('#"raw"#',7)])
def test_swift_skips_only_comment_or_literal(text,end):
    assert _skipped(text,0) == end


def test_java_abstract_methods_and_unowned_declarations_are_not_entries():
    assert java_functions('interface Box { int open(); }','Box.java') == []
    assert java_functions('int orphan() { return 1; }','Orphan.java') == []


def test_go_missing_module_declaration_uses_package_clause(tmp_path):
    (tmp_path/'go.mod').write_text('// no module declaration\ngo 1.25\n')
    assert package_namespace(str(tmp_path/'app.go'),'demo') == 'demo'


@pytest.mark.parametrize('text,expected',[('',None),('`',None),('plain',None),('`x',None),('x`',None),('`ok`','ok'),('``','')])
def test_template_delimiters_are_validated(text,expected):
    assert _template_text(text)==expected


def test_missing_route_callee_has_no_path():
    assert _path_from_route(b'',None) is None


def test_typescript_parenthesized_route_callbacks_stay_separate():
    source='function mount(app) { app.get("/x", ((req) => { if (req.ok) return 1; return 0; })); }'
    functions=functions_in_source(source,'src/app.ts')
    assert [(f.name,f.complexity) for f in functions] == [('mount',1),('GET /x',2)]
