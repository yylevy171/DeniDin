"""REQ-063-08 guard: the legacy AIHandler is constructed only when the backbone flag is
off, at exactly one place - denidin.py's initialize_app. Nothing else in the app, its
scripts, the player, or the sibling apps that reuse denidin-app's code (the webapp
backend, the rolling-memory backfill) may import the src.handlers.ai_handler module:
anything they need from it lives in a shared module (src/core/ai_manager.py, the
managers, src/tool_actions/) instead.
"""
import ast
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2]
APPS_ROOT = APP_ROOT.parent
LEGACY_MODULE = "src.handlers.ai_handler"

SCANNED = [
    APP_ROOT / "src",
    APP_ROOT / "player",
    APP_ROOT / "scripts",
    APP_ROOT / "denidin.py",
    APPS_ROOT / "webapp" / "backend" / "src",
    APPS_ROOT / "rolling-memory-backfill",
]


def _python_files():
    for root in SCANNED:
        if root.is_file():
            yield root
        elif root.is_dir():
            for path in root.rglob("*.py"):
                if not {"venv", ".venv", "node_modules", "tests"} & set(path.parts):
                    yield path


def _legacy_imports(path):
    """(enclosing function name or None, line) for every import of the legacy module."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = []

    def visit(node, func):
        for child in ast.iter_child_nodes(node):
            inner = child.name if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) else func
            if isinstance(child, ast.ImportFrom) and child.module and (
                    child.module == LEGACY_MODULE
                    or (child.module == "src.handlers" and any(a.name == "ai_handler" for a in child.names))):
                found.append((func, child.lineno))
            elif isinstance(child, ast.Import) and any(a.name == LEGACY_MODULE for a in child.names):
                found.append((func, child.lineno))
            visit(child, inner)

    visit(tree, None)
    return found


def test_only_initialize_app_imports_the_legacy_ai_handler():
    offenders = []
    for path in _python_files():
        if path == APP_ROOT / "src" / "handlers" / "ai_handler.py":
            continue
        for func, line in _legacy_imports(path):
            if path == APP_ROOT / "denidin.py" and func == "initialize_app":
                continue
            offenders.append(f"{path.relative_to(APPS_ROOT)}:{line}")
    assert offenders == []


def test_initialize_app_still_imports_it_for_the_flag_off_path():
    """Sanity: the scan really sees imports (the one allowed one is found)."""
    assert ("initialize_app" in {func for func, _ in _legacy_imports(APP_ROOT / "denidin.py")})
