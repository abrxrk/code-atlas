import ast
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PythonModuleInfo:
    path: Path
    imports: list[str] = field(default_factory=list)
    defs: list[str] = field(default_factory=list)  # top-level function/class names
    main_guard_line: int | None = None  # line of a top-level `if __name__ == "__main__":`, if any


def parse(path: Path) -> PythonModuleInfo | None:
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return None

    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)

    defs = [
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    ]

    main_guard_line = next(
        (node.lineno for node in tree.body if isinstance(node, ast.If) and _is_main_guard(node.test)),
        None,
    )

    return PythonModuleInfo(path=path, imports=imports, defs=defs, main_guard_line=main_guard_line)


def _is_main_guard(test: ast.expr) -> bool:
    """Matches `__name__ == "__main__"` in either operand order."""
    if not isinstance(test, ast.Compare) or len(test.ops) != 1 or not isinstance(test.ops[0], ast.Eq):
        return False
    operands = (test.left, test.comparators[0])
    names = {n.id for n in operands if isinstance(n, ast.Name)}
    strings = {c.value for c in operands if isinstance(c, ast.Constant) and isinstance(c.value, str)}
    return "__name__" in names and "__main__" in strings
