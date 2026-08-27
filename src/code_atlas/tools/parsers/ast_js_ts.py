from dataclasses import dataclass, field
from pathlib import Path

from tree_sitter import Node
from tree_sitter_language_pack import get_parser

_LANGUAGE_BY_SUFFIX = {
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
}

_IDENTIFIER_TYPES = {"identifier", "type_identifier"}


@dataclass
class JsModuleInfo:
    path: Path
    imports: list[str] = field(default_factory=list)  # imported/re-exported module specifiers
    exports: list[str] = field(default_factory=list)  # exported identifier names (best-effort)


def parse(path: Path) -> JsModuleInfo | None:
    language = _LANGUAGE_BY_SUFFIX.get(path.suffix)
    if language is None:
        return None
    try:
        source = path.read_bytes()
    except OSError:
        return None

    tree = get_parser(language).parse(source)
    imports: list[str] = []
    exports: list[str] = []

    for node in tree.root_node.children:
        if node.type == "import_statement":
            spec = _string_literal(node)
            if spec:
                imports.append(spec)
        elif node.type == "export_statement":
            spec = _string_literal(node)
            if spec:
                imports.append(spec)  # re-export, e.g. `export * from "./x"`
                continue
            name = _find_identifier(node)
            if name:
                exports.append(name)

    return JsModuleInfo(path=path, imports=imports, exports=exports)


def _string_literal(node: Node) -> str | None:
    string_node = next((c for c in node.children if c.type == "string"), None)
    if string_node is None:
        return None
    return string_node.text.decode("utf-8", errors="replace").strip("\"'")


def _find_identifier(node: Node) -> str | None:
    if node.type in _IDENTIFIER_TYPES:
        return node.text.decode("utf-8", errors="replace")
    for child in node.children:
        found = _find_identifier(child)
        if found:
            return found
    return None
