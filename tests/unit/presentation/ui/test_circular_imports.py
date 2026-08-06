import ast
from pathlib import Path

def test_main_window_no_toplevel_bootstrapper_import():
    """
    Prevents a regression where running main_window.py directly as __main__
    causes a circular import error with app_bootstrapper.
    """
    # Note: Adjust path resolution for test execution context
    path = Path(__file__).parent.parent.parent.parent.parent / "src" / "presentation" / "ui" / "main_window.py"
    if not path.exists():
        # Fallback for pytest running from repo root
        path = Path("Binace_Bot/src/presentation/ui/main_window.py")
        
    tree = ast.parse(path.read_text(encoding="utf-8"))
    
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module:
            assert "app_bootstrapper" not in node.module, (
                "Avoid top-level import of app_bootstrapper in main_window.py "
                "to prevent circular imports when executed as __main__."
            )
