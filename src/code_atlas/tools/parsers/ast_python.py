import ast
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PythonModuleInfo:
    path: Path
    imports: list[str] = field(default_factory=list)
    defs: list[str] = field(default_factory=list)  # top-level function/class names


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

    return PythonModuleInfo(path=path, imports=imports, defs=defs)
