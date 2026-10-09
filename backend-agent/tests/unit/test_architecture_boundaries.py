import ast
from pathlib import Path

PACKAGE_ROOT = Path(__file__).parents[2] / "agent_backend"


def _python_modules(package_dir: Path) -> list[Path]:
    return [path for path in package_dir.rglob("*.py") if "__pycache__" not in path.parts]


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
        elif isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
    return modules


def test_agent_runtime_has_no_analysis_specific_dependencies_or_identity() -> None:
    runtime_root = PACKAGE_ROOT / "agent_runtime"
    assert runtime_root.is_dir()

    for path in _python_modules(runtime_root):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imports = _imports(path)
        assert not any(
            module.startswith("agent_backend.capabilities.data_analysis")
            for module in imports
        ), path
        assert not any(
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and "data_analysis_agent" in node.value
            for node in ast.walk(tree)
        ), path


def test_foundation_does_not_depend_on_inner_application_packages() -> None:
    foundation_root = PACKAGE_ROOT / "foundation"

    for path in _python_modules(foundation_root):
        assert not any(
            module.startswith(
                (
                    "agent_backend.agent_runtime",
                    "agent_backend.capabilities",
                    "agent_backend.orchestration",
                )
            )
            for module in _imports(path)
        ), path
