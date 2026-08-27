import json
import re
import tomllib
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

_NAME_RE = re.compile(r"^[A-Za-z0-9_.\-]+")

_ParseResult = tuple[str | None, list[str], dict[str, str]]
_ParserFn = Callable[[Path], _ParseResult]
# filename -> (ecosystem, parser)
_PARSERS: dict[str, tuple[str, _ParserFn]] = {}


@dataclass
class ManifestInfo:
    ecosystem: str
    manifest_path: Path  # relative to repo root
    name: str | None
    dependencies: list[str]
    scripts: dict[str, str] = field(default_factory=dict)  # declared run commands, e.g. npm "scripts"


def find_manifests(root: Path) -> list[ManifestInfo]:
    """Scan the repo root and its immediate subdirectories for known manifests."""
    results: list[ManifestInfo] = []
    candidates = list(root.glob("*")) + list(root.glob("*/*"))
    for path in sorted(candidates):
        if not path.is_file() or path.name not in _PARSERS:
            continue
        ecosystem, parser = _PARSERS[path.name]
        try:
            name, deps, scripts = parser(path)
        except (OSError, ValueError, tomllib.TOMLDecodeError, ET.ParseError):
            continue
        results.append(
            ManifestInfo(
                ecosystem=ecosystem,
                manifest_path=path.relative_to(root),
                name=name,
                dependencies=deps,
                scripts=scripts,
            )
        )
    return results


def _strip_version(spec: str) -> str:
    match = _NAME_RE.match(spec.strip())
    return match.group(0) if match else spec.strip()


def _parse_package_json(path: Path) -> _ParseResult:
    data = json.loads(path.read_text())
    deps = list(data.get("dependencies", {})) + list(data.get("devDependencies", {}))
    return data.get("name"), deps, data.get("scripts", {})


def _parse_pyproject_toml(path: Path) -> _ParseResult:
    data = tomllib.loads(path.read_text())
    project = data.get("project", {})
    deps = [_strip_version(d) for d in project.get("dependencies", [])]
    scripts = project.get("scripts", {})
    return project.get("name"), deps, scripts


def _parse_requirements_txt(path: Path) -> _ParseResult:
    deps = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        deps.append(_strip_version(line))
    return None, deps, {}


def _parse_go_mod(path: Path) -> _ParseResult:
    text = path.read_text()
    name_match = re.search(r"^module\s+(\S+)", text, re.MULTILINE)
    deps = re.findall(r"^\s*(?:require\s+)?([\w./\-]+)\s+v[\w.\-+]+", text, re.MULTILINE)
    return (name_match.group(1) if name_match else None), deps, {}


def _parse_cargo_toml(path: Path) -> _ParseResult:
    data = tomllib.loads(path.read_text())
    package = data.get("package", {})
    deps = list(data.get("dependencies", {}))
    return package.get("name"), deps, {}


def _parse_pom_xml(path: Path) -> _ParseResult:
    root = ET.parse(path).getroot()
    ns = {"m": "http://maven.apache.org/POM/4.0.0"} if root.tag.startswith("{") else {}

    def find(tag: str, parent: ET.Element = root) -> str | None:
        el = parent.find(f"m:{tag}" if ns else tag, ns)
        return el.text if el is not None else None

    deps = []
    deps_parent = root.find("m:dependencies" if ns else "dependencies", ns)
    if deps_parent is not None:
        for dep in deps_parent.findall("m:dependency" if ns else "dependency", ns):
            artifact = find("artifactId", dep)
            if artifact:
                deps.append(artifact)
    return find("artifactId"), deps, {}


def _parse_gemfile(path: Path) -> _ParseResult:
    deps = re.findall(r"""^\s*gem\s+['"]([^'"]+)['"]""", path.read_text(), re.MULTILINE)
    return None, deps, {}


def _parse_composer_json(path: Path) -> _ParseResult:
    data = json.loads(path.read_text())
    deps = [d for d in list(data.get("require", {})) + list(data.get("require-dev", {})) if d != "php"]
    return data.get("name"), deps, data.get("scripts", {})


_PARSERS.update(
    {
        "package.json": ("npm", _parse_package_json),
        "pyproject.toml": ("python", _parse_pyproject_toml),
        "requirements.txt": ("python", _parse_requirements_txt),
        "requirements-dev.txt": ("python", _parse_requirements_txt),
        "go.mod": ("go", _parse_go_mod),
        "Cargo.toml": ("rust", _parse_cargo_toml),
        "pom.xml": ("java", _parse_pom_xml),
        "Gemfile": ("ruby", _parse_gemfile),
        "composer.json": ("php", _parse_composer_json),
    }
)
