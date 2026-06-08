import ast
from pathlib import Path

READER_PACKAGE_ROOT = Path(__file__).parents[2] / "copilot_history"
PROHIBITED_IMPORT_ROOTS = {
    "boto3",
    "django",
    "fastapi",
    "flask",
    "google",
    "httpx",
    "mysql",
    "rails",
    "requests",
    "rest_framework",
}
PROHIBITED_SURFACE_TOKENS = (
    "BigQuery",
    "DetailPresenter",
    "ErrorEnvelope",
    "Frontend",
    "HTTPResponse",
    "MySQL",
    "RequestHandler",
    "ResponsePresenter",
    "SessionDetailPresenter",
    "SessionSummaryPresenter",
)
EXPECTED_PUBLIC_SURFACE = (
    "ActivityProjector",
    "ConversationProjector",
    "CurrentSessionReader",
    "EventNormalizer",
    "LegacySessionReader",
    "ReadFailureResult",
    "ReadSuccessResult",
    "RootResolver",
    "SearchTextProjector",
    "SessionCatalogReader",
    "SourceCatalog",
)


def _python_modules() -> tuple[Path, ...]:
    return tuple(sorted(READER_PACKAGE_ROOT.glob("*.py")))


def _import_roots(tree: ast.AST) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", maxsplit=1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", maxsplit=1)[0])
    return roots


# 概要・目的: reader package に presenter、HTTP、保存、frontend、Rails 削除の責務を混入させない。
# テストケース: backend/copilot_history 配下の Python module の import と
# public class/function 名を静的に確認する。
# 期待値: reader、normalized contract、projection の境界に不要な
# 外部層への依存や public surface が存在しない。
def test_reader_package_does_not_import_or_expose_out_of_scope_responsibilities() -> None:
    leaked_imports: dict[str, set[str]] = {}
    leaked_surface: dict[str, set[str]] = {}
    for module_path in _python_modules():
        tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))
        imports = _import_roots(tree) & PROHIBITED_IMPORT_ROOTS
        if imports:
            leaked_imports[module_path.name] = imports

        names = {
            node.name
            for node in tree.body
            if isinstance(node, ast.ClassDef | ast.FunctionDef)
        }
        leaked_names = {
            name
            for name in names
            if any(token.lower() in name.lower() for token in PROHIBITED_SURFACE_TOKENS)
        }
        if leaked_names:
            leaked_surface[module_path.name] = leaked_names

    assert leaked_imports == {}
    assert leaked_surface == {}


# 概要・目的: current workspace 読取が read-only local filesystem と
# safe YAML load に閉じていることを守る。
# テストケース: current_reader.py の AST から yaml API 呼び出しと書込系 pathlib 呼び出しを確認する。
# 期待値: yaml.safe_load だけを使い、
# write_text / open write mode / unlink などの write operation を持たない。
def test_current_reader_uses_safe_yaml_load_and_no_write_operations() -> None:
    module_path = READER_PACKAGE_ROOT / "current_reader.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))

    yaml_calls: set[str] = set()
    write_calls: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            owner = node.func.value
            if isinstance(owner, ast.Name) and owner.id == "yaml":
                yaml_calls.add(node.func.attr)
            if node.func.attr == "open":
                has_write_mode = any(
                    isinstance(arg, ast.Constant)
                    and isinstance(arg.value, str)
                    and any(mode in arg.value for mode in ("w", "a", "+", "x"))
                    for arg in node.args
                )
                if has_write_mode:
                    write_calls.add(node.func.attr)
            if node.func.attr in {
                "chmod",
                "mkdir",
                "replace",
                "rename",
                "rmdir",
                "symlink_to",
                "touch",
                "unlink",
                "write_bytes",
                "write_text",
            } and isinstance(node.func.value, ast.Name):
                write_calls.add(node.func.attr)

    assert yaml_calls == {"safe_load"}
    assert write_calls == set()


# 概要・目的: reader package の public surface を raw reader、
# normalized contract、projection に限定する。
# テストケース: copilot_history.__all__ を確認する。
# 期待値: 後続 spec が参照できる reader entrypoint と contract だけが明示 export される。
def test_reader_package_public_surface_is_explicit_and_limited() -> None:
    package_init = READER_PACKAGE_ROOT / "__init__.py"
    namespace: dict[str, object] = {}
    exec(package_init.read_text(encoding="utf-8"), namespace)

    assert namespace.get("__all__") == EXPECTED_PUBLIC_SURFACE
