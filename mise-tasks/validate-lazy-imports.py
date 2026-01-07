#!/usr/bin/env -S uv run -s

# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

# sourcery skip: no-complex-if-expressions
# ///script
# python-version: ">=3.12"
# dependencies: ["rich", "botocore", "black"]
# ////script
"""Validate and manage lazy imports in the codebase.

This script handles:
1. lazy_import() function call validation
2. Package-level lazy imports (__init__.py) validation and reconciliation
3. Module-level __all__ management
"""

from __future__ import annotations

import ast
import importlib
import importlib.util
import json
import re
import subprocess
import sys
import warnings

from pathlib import Path
from typing import Literal, NamedTuple


# Suppress Pydantic and OpenTelemetry warnings before imports
warnings.filterwarnings(
    "ignore",
    message=r"The '(exclude|repr|frozen)' attribute.*was provided to the `Field()` function",
    category=UserWarning,
    module=r"pydantic\._internal\._generate_schema",
)
warnings.filterwarnings(
    "ignore",
    message=r"You should use `.*` instead. Deprecated since version",
    category=DeprecationWarning,
)

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.rule import Rule
from rich.table import Table


# We assume codeweaver is in the path or we are running from root
try:
    from codeweaver.core import format_file_link, is_tty
except ImportError:
    # Fallback for environments where codeweaver is not installed
    def format_file_link(path: Path, line: int) -> str:
        return f"{path}:{line}"

    def is_tty() -> bool:
        return sys.stdout.isatty()


console = Console(markup=True, emoji=True)

# Pattern for lazy_import() function calls
LAZY_IMPORT_PATTERN = re.compile(
    r'lazy_import([\s\n]*"(?P<module>[A-Za-z0-9_.]+)"\s*,?[\s\n]*"(?P<object>[A-Za-z0-9_.]+)"\s*?[\s\n]*?)'
)

# All mise tasks operate relative to the src/codeweaver directory
SRC_DIR = Path("src/codeweaver")
EXPORTS_CONFIG = Path(".codeweaver/exports_config.json")

NO_LAZY_PACKAGES = [
    "codeweaver.cli.commands",
    "codeweaver.agent_api.find_code",
    "codeweaver.providers.data",
    "codeweaver.data",
    "codeweaver.server.middleware",
]

# Modules to check for package-level lazy imports
PACKAGE_MODULES = list(SRC_DIR.rglob("**/__init__.py"))

IS_EXCEPTION = (
    "codeweaver.__version__",
    "codeweaver.server.mcp.user_agent",
    "codeweaver.core.utils.create_lazy_getattr",
    "codeweaver.core.utils.LazyImport",
    "codeweaver.core.utils.lazy_import",
    "codeweaver.server.mcp.middleware.default_middleware_for_transport",
    "codeweaver.server.mcp.middleware.McpMiddleware",
    "codeweaver.providers.agent.AgentProfile",
    "codeweaver.providers.agent.AgentProfileSpec",
    "codeweaver.providers.reranking.providers.sentence_transformers",
    "codeweaver.providers.embedding.providers.sentence_transformers",
    "codeweaver.providers.reranking.KnownRerankModelName",
    "codeweaver.providers.reranking.capabilities.dependency_map",
    "codeweaver.providers.reranking.capabilities.load_default_capabilities",
    "codeweaver.providers.reranking.get_rerank_model_provider",
    "codeweaver.providers.vector_stores.get_vector_store_provider",
    "codeweaver_tokenizers.get_tokenizer",
    "codeweaver.providers.embedding.capabilities.load_default_capabilities",
    "codeweaver.providers.embedding.capabilities.load_sparse_capabilities",
)

# ============================================================================
# CORE UTILITIES
# ============================================================================


class ExportInfo(NamedTuple):
    name: str
    type: str  # "function", "class", "variable"
    is_public: bool


def export_sort_key(name: str) -> tuple[int, str]:
    """Sort key for exports: SCREAMING_SNAKE, then CamelCase, then snake_case."""
    # Group 0: SCREAMING_SNAKE (all uppercase and underscores)
    # Group 1: CamelCase (starts with uppercase)
    # Group 2: snake_case (starts with lowercase)
    if name.isupper():
        group = 0
    elif name[0].isupper():
        group = 1
    else:
        group = 2
    return (group, name.lower())


def get_module_path(file_path: Path) -> str:
    """Convert file path to module path."""
    try:
        # Handle src/codeweaver prefix
        if str(file_path).startswith("src/"):
            rel_path = file_path.relative_to(Path("src"))
        else:
            rel_path = file_path.relative_to(SRC_DIR.parent)

        module_path = str(rel_path.with_suffix("")).replace("/", ".")
        module_path = module_path.removesuffix(".__init__")
        return module_path
    except ValueError:
        return str(file_path)


def check_import_exists(module_path: str, name: str | None = None, seen_mods: set[str] | None = None) -> bool:
    """Check if a module or attribute exists without executing code."""
    if seen_mods is None:
        seen_mods = set()
    
    if module_path in seen_mods:
        return False
    seen_mods.add(module_path)

    try:
        # Handle cases where the module might be named with a leading underscore
        possible_paths = [module_path]
        if "." in module_path:
            parts = module_path.split(".")
            if not parts[-1].startswith("_"):
                parts[-1] = "_" + parts[-1]
                possible_paths.append(".".join(parts))

        spec = None
        for p in possible_paths:
            spec = importlib.util.find_spec(p)
            if spec:
                module_path = p
                break

        if spec is None:
            return False
        if name is None:
            return True

        # Check submodules
        try:
            if importlib.util.find_spec(f"{module_path}.{name}"):
                return True
        except Exception:
            pass

        # Check AST
        if spec.origin:
            origin_path = Path(spec.origin)
            if origin_path.suffix == ".py":
                try:
                    tree = ast.parse(origin_path.read_text(encoding="utf-8"))
                    
                    all_names, dynamic_imports, tc_names = get_lazy_import_data(tree)
                    
                    # If it's in dynamic_imports or tc_names, we need to check if the target exists
                    # This allows traversing re-exports
                    if name in dynamic_imports:
                        _, submodule = dynamic_imports[name]
                        return check_import_exists(f"{module_path}.{submodule}", name, seen_mods)
                    
                    if name in tc_names:
                        # Find which module it's imported from in the TYPE_CHECKING block
                        for node in tree.body:
                            if isinstance(node, ast.If) and isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING":
                                for tc_node in node.body:
                                    if isinstance(tc_node, ast.ImportFrom):
                                        for alias in tc_node.names:
                                            if alias.name == name:
                                                # Resolve relative import if needed
                                                target_mod = tc_node.module
                                                if tc_node.level > 0:
                                                    parts = module_path.split('.')
                                                    target_mod = '.'.join(parts[: -tc_node.level]) + (f".{tc_node.module}" if tc_node.module else "")
                                                return check_import_exists(target_mod, name, seen_mods)
                        return True # Fallback if we can't find the source but it is in TC

                    # Check direct definitions
                    for node in tree.body:
                        if isinstance(node, ast.FunctionDef | ast.ClassDef | ast.AsyncFunctionDef):
                            if node.name == name:
                                return True
                        elif isinstance(node, ast.Assign):
                            for target in node.targets:
                                if isinstance(target, ast.Name) and target.id == name:
                                    return True
                        elif isinstance(node, ast.AnnAssign):
                            if isinstance(node.target, ast.Name) and node.target.id == name:
                                return True
                        elif hasattr(ast, "TypeAlias") and isinstance(node, ast.TypeAlias):
                            if isinstance(node.name, ast.Name) and node.name.id == name:
                                return True
                        elif isinstance(node, ast.ImportFrom):
                            for alias in node.names:
                                if alias.asname == name or (not alias.asname and alias.name == name):
                                    return True
                        elif isinstance(node, ast.Import):
                            for alias in node.names:
                                if alias.asname == name or (not alias.asname and alias.name.split('.')[-1] == name):
                                    return True
                except Exception:
                    pass

        return False
    except Exception:
        return False


def load_config() -> dict:
    """Load exclusions configuration."""
    if EXPORTS_CONFIG.exists():
        try:
            return json.loads(EXPORTS_CONFIG.read_text())
        except Exception:
            return {"exclusions": {}, "module_exclusions": {}}
    return {"exclusions": {}, "module_exclusions": {}}


def save_config(config: dict):
    """Save exclusions configuration."""
    if "exclusions" not in config:
        config["exclusions"] = {}
    if "module_exclusions" not in config:
        config["module_exclusions"] = {}
    if not EXPORTS_CONFIG.parent.exists():
        EXPORTS_CONFIG.parent.mkdir(parents=True)
    EXPORTS_CONFIG.write_text(json.dumps(config, indent=2))


def format_code(code: str) -> str:
    """Format code using black."""
    try:
        result = subprocess.run(
            ["black", "-q", "-"], input=code, capture_output=True, text=True, check=True
        )
        return result.stdout
    except Exception as e:
        console.print(f"[yellow]Warning: Could not format code with black: {e}[/yellow]")
        return code


def get_current_all(tree: ast.Module) -> list[str] | None:
    """Find current __all__ definition in the AST."""
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Name)
                    and target.id == "__all__"
                    and isinstance(node.value, ast.Tuple | ast.List)
                ):
                    return [elt.value for elt in node.value.elts if isinstance(elt, ast.Constant)]
    return None


def get_public_members(file_path: Path) -> tuple[list[ExportInfo], list[str] | None]:
    """Find public members in a python file using AST."""
    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except Exception as e:
        console.print(f"[red]Error parsing {file_path}: {e}[/red]")
        return [], None

    current_all = get_current_all(tree)
    members = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            if not node.name.startswith("_"):
                members.append(ExportInfo(node.name, "function", True))
        elif isinstance(node, ast.ClassDef):
            if not node.name.startswith("_"):
                members.append(ExportInfo(node.name, "class", True))
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    if target.id == "__all__":
                        continue
                    if not target.id.startswith("_") and (
                        target.id.isupper() or (current_all and target.id in current_all)
                    ):
                        members.append(ExportInfo(target.id, "variable", True))
                elif isinstance(target, ast.Tuple | ast.List):
                    for elt in target.elts:
                        if (
                            isinstance(elt, ast.Name)
                            and not elt.id.startswith("_")
                            and elt.id.isupper()
                        ):
                            members.append(ExportInfo(elt.id, "variable", True))
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name):
                if not node.target.id.startswith("_") and node.target.id.isupper():
                    members.append(ExportInfo(node.target.id, "variable", True))

    return sorted(members, key=lambda x: x.name), current_all


# ============================================================================
# SECTION 1: lazy_import() Function Call Validation
# ============================================================================


class FunctionCallError(NamedTuple):
    file_ref: str
    module: str
    obj: str
    status: str


def validate_import(module: str, obj: str) -> str | None:
    try:
        imported_module = importlib.import_module(module)
        return "MISSING OBJECT" if obj and not hasattr(imported_module, obj) else None
    except ImportError:
        return "IMPORT ERROR"
    except Exception as e:
        return f"ERROR: {e!s}"


def validate_function_calls(paths: list[Path] | None = None) -> list[FunctionCallError]:
    errors = []
    if not paths:
        search_paths = list(SRC_DIR.rglob("*.py"))
    else:
        search_paths = []
        for p in paths:
            if p.is_dir():
                search_paths.extend(p.rglob("*.py"))
            elif p.suffix == ".py":
                search_paths.append(p)

    for py_file in search_paths:
        try:
            content = py_file.read_text(encoding="utf-8")
        except Exception:
            continue
        for match in LAZY_IMPORT_PATTERN.finditer(content):
            module = match.group("module").strip('" \n\t')
            obj = match.group("object").strip(', " \n\t') if match.group("object") else None
            # Use our non-executing check first
            if not check_import_exists(module, obj):
                line_num = content.count("\n", 0, match.span()[0]) + 1
                errors.append(
                    FunctionCallError(
                        format_file_link(py_file, line_num), module, obj or "", "MISSING"
                    )
                )
    return errors


# ============================================================================
# SECTION 2: Package-Level Lazy Imports Validation (AST-based)
# ============================================================================


class PackageError(NamedTuple):
    module_name: str
    category: Literal["ERROR", "WARNING", "INFO"]
    message: str


def get_lazy_import_data(
    tree: ast.Module,
) -> tuple[list[str], dict[str, tuple[str, str]], list[str]]:
    """Extract __all__, _dynamic_imports, and TYPE_CHECKING names from AST."""
    all_names = []
    dynamic_imports = {}
    tc_names = []

    for node in tree.body:
        # __all__
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    if isinstance(node.value, ast.Tuple | ast.List):
                        all_names = [
                            elt.value for elt in node.value.elts if isinstance(elt, ast.Constant)
                        ]

        # _dynamic_imports
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "_dynamic_imports":
                    # Handle MappingProxyType({...}) or just {...}
                    dict_node = node.value
                    if isinstance(dict_node, ast.Call) and dict_node.args:
                        dict_node = dict_node.args[0]

                    if isinstance(dict_node, ast.Dict):
                        for k, v in zip(dict_node.keys, dict_node.values):
                            if (
                                isinstance(k, ast.Constant)
                                and isinstance(v, ast.Tuple)
                                and len(v.elts) == 2
                            ):
                                name = k.value
                                # parent is usually __spec__.parent
                                submodule = (
                                    v.elts[1].value if isinstance(v.elts[1], ast.Constant) else "?"
                                )
                                dynamic_imports[name] = ("?", submodule)

        # TYPE_CHECKING block
        if (
            isinstance(node, ast.If)
            and isinstance(node.test, ast.Name)
            and node.test.id == "TYPE_CHECKING"
        ):
            for tc_node in node.body:
                for alias in tc_node.names:
                    if isinstance(tc_node, ast.ImportFrom):
                        tc_names.append(alias.name)
                    elif isinstance(tc_node, ast.Import):
                        tc_names.append(alias.name.split(".")[-1])

    return all_names, dynamic_imports, tc_names


def validate_package_level_imports() -> tuple[
    list[PackageError], list[PackageError], list[PackageError]
]:
    errors, warnings, info = [], [], []
    for pkg_init in PACKAGE_MODULES:
        mod_name = get_module_path(pkg_init)
        if mod_name in NO_LAZY_PACKAGES:
            continue

        try:
            tree = ast.parse(pkg_init.read_text(encoding="utf-8"))
        except Exception as e:
            errors.append(PackageError(mod_name, "ERROR", f"Cannot parse - {e}"))
            continue

        all_names, dynamic_imports, tc_names = get_lazy_import_data(tree)

        if not all_names:
            warnings.append(PackageError(mod_name, "WARNING", "No __all__ defined"))

        if not dynamic_imports:
            info.append(PackageError(mod_name, "INFO", "No _dynamic_imports"))
            continue

        # Check consistency
        for name in all_names:
            if name not in dynamic_imports and name not in tc_names:
                # Might be locally defined
                pass

        for name in dynamic_imports:
            if name not in all_names:
                warnings.append(
                    PackageError(
                        mod_name, "WARNING", f"'{name}' in _dynamic_imports but not in __all__"
                    )
                )
            if name not in tc_names:
                warnings.append(
                    PackageError(
                        mod_name,
                        "WARNING",
                        f"'{name}' in _dynamic_imports but not in TYPE_CHECKING block",
                    )
                )

        # Validate import paths (simplified)
        for name, (_, submodule) in dynamic_imports.items():
            if submodule == "?":
                continue
            # Try to resolve relative to package
            full_mod = f"{mod_name}.{submodule}"
            if not check_import_exists(full_mod, name):
                errors.append(
                    PackageError(mod_name, "ERROR", f"Broken lazy import: {name} from {submodule}")
                )

    return errors, warnings, info


# ============================================================================
# SECTION 4: GLOBAL IMPORT SCANNER
# ============================================================================


class ImportErrorDetail(NamedTuple):
    file_path: Path
    line: int
    module: str
    name: str | None
    error: str


def scan_all_imports() -> list[ImportErrorDetail]:
    """Scan all python files for broken imports."""
    errors = []
    py_files = list(SRC_DIR.rglob("*.py"))

    with console.status("[bold blue]Scanning all imports..."):
        for py_file in py_files:
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            if alias.name.startswith("codeweaver"):
                                if not check_import_exists(alias.name):
                                    errors.append(
                                        ImportErrorDetail(
                                            py_file,
                                            node.lineno,
                                            alias.name,
                                            None,
                                            "Module not found",
                                        )
                                    )
                    elif isinstance(node, ast.ImportFrom):
                        if node.module and (node.module.startswith("codeweaver") or node.level > 0):
                            module_path = node.module or ""
                            if node.level > 0:
                                # Resolve relative import
                                parts = get_module_path(py_file).split(".")
                                module_path = ".".join(parts[: -node.level]) + (
                                    f".{node.module}" if node.module else ""
                                )

                            for alias in node.names:
                                if alias.name == "*":
                                    continue
                                if not check_import_exists(module_path, alias.name):
                                    errors.append(
                                        ImportErrorDetail(
                                            py_file,
                                            node.lineno,
                                            module_path,
                                            alias.name,
                                            "Import not found",
                                        )
                                    )
            except Exception:
                continue
    return errors


# ============================================================================
# SECTION 3: MANAGEMENT TUI
# ============================================================================


def generate_init_content(package_dir: Path, sub_exports: dict[str, list[str]]) -> str:
    module_name = get_module_path(package_dir)
    
    # Flatten exports into a list of (name, full_module) for easier sorting
    flat_exports = []
    for mod, exports in sub_exports.items():
        for exp in exports:
            flat_exports.append((exp, mod))
    
    # Sort exports by name using our custom key
    flat_exports.sort(key=lambda x: export_sort_key(x[0]))

    # TYPE_CHECKING block - Group by module but sort names within and modules by their first export
    modules_to_exports: dict[str, list[str]] = {}
    for exp, mod in flat_exports:
        if mod not in modules_to_exports:
            modules_to_exports[mod] = []
        modules_to_exports[mod].append(exp)
    
    # Sort modules based on the custom sort key of their first export
    sorted_mods = sorted(
        modules_to_exports.keys(), 
        key=lambda m: export_sort_key(modules_to_exports[m][0])
    )

    tc_lines = ["if TYPE_CHECKING:"]
    for mod in sorted_mods:
        exports = sorted(modules_to_exports[mod], key=export_sort_key)
        if exports:
            tc_lines.append(f"    from {mod} import (")
            for exp in exports:
                tc_lines.append(f"        {exp},")
            tc_lines.append("    )")

    # _dynamic_imports mapping - Sorted by the name of the import
    di_lines = ["_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({"]
    for exp, mod in flat_exports:
        rel_mod = mod.removeprefix(module_name + ".")
        di_lines.append(f'    "{exp}": (__spec__.parent, "{rel_mod}"),')
    di_lines.append("})")

    # __all__ tuple - Sorted by name
    all_lines = ["__all__ = ("]
    for exp, _ in flat_exports:
        all_lines.append(f'    "{exp}",')
    all_lines.append(")")

    docstring = f'"""Package-level lazy imports for {module_name}."""'
    content = f"""# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
{docstring}

from types import MappingProxyType
from typing import TYPE_CHECKING

from codeweaver.core.utils.lazy_import import create_lazy_getattr

{chr(10).join(tc_lines)}

{chr(10).join(di_lines)}

__getattr__ = create_lazy_getattr(_dynamic_imports, globals(), __name__)

{chr(10).join(all_lines)}

def __dir__() -> list[str]:
    return list(__all__)
"""
    return format_code(content)


def get_package_exports(package_dir: Path) -> dict[str, list[str]]:
    config = load_config()
    exclusions = config.get("exclusions", {})
    sub_exports = {}
    for item in package_dir.iterdir():
        mod_path = get_module_path(item)
        if item.is_file() and item.suffix == ".py" and item.name != "__init__.py":
            members, _ = get_public_members(item)
            effective = [m.name for m in members if m.name not in exclusions.get(mod_path, [])]
            if effective:
                sub_exports[mod_path] = effective
        elif item.is_dir() and (item / "__init__.py").exists():
            _, current_all = get_public_members(item / "__init__.py")
            if current_all:
                effective = [e for e in current_all if e not in exclusions.get(mod_path, [])]
                if effective:
                    sub_exports[mod_path] = effective
    return sub_exports


def get_module_health(file_path: Path, full_mod_name: str) -> tuple[bool, bool]:
    """Check module health: (has_broken_imports, has_missing_exports)."""
    # Broken imports
    errors = get_broken_imports(file_path, full_mod_name)
    broken = len(errors) > 0

    # Missing exports
    missing = False
    config = load_config()
    mod_excl = config.get("module_exclusions", {}).get(full_mod_name, [])
    mems, current_all = get_public_members(file_path)
    current_all = current_all or []
    if any(m.name for m in mems if m.name not in current_all and m.name not in mod_excl):
        missing = True

    return broken, missing


def get_broken_imports(file_path: Path, full_mod_name: str) -> list[ImportErrorDetail]:
    """Get specific broken imports for a module."""
    errors = []
    try:
        tree = ast.parse(file_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("codeweaver") and not check_import_exists(alias.name):
                        errors.append(
                            ImportErrorDetail(file_path, node.lineno, alias.name, None, "Module not found")
                        )
            elif isinstance(node, ast.ImportFrom):
                if node.module and (node.module.startswith("codeweaver") or node.level > 0):
                    module_path = node.module or ""
                    if node.level > 0:
                        parts = full_mod_name.split(".")
                        module_path = ".".join(parts[: -node.level]) + (
                            f".{node.module}" if node.module else ""
                        )
                    for alias in node.names:
                        if alias.name != "*" and not check_import_exists(module_path, alias.name):
                            errors.append(
                                ImportErrorDetail(
                                    file_path, node.lineno, module_path, alias.name, "Import not found"
                                )
                            )
    except Exception:
        pass
    return errors


def manage_tui():
    if not is_tty():
        console.print(
            "[bold red]Error: Management TUI requires an interactive terminal (TTY).[/bold red]"
        )
        return

    try:
        while True:
            packages = sorted([p.parent for p in SRC_DIR.rglob("__init__.py")])
            
            # Pre-calculate package health
            pkg_health = {}
            with console.status("[bold blue]Auditing packages..."):
                for pkg in packages:
                    mod_path = get_module_path(pkg)
                    # Check __init__.py consistency
                    try:
                        tree = ast.parse((pkg / "__init__.py").read_text(encoding="utf-8"))
                        all_names, dynamic_imports, tc_names = get_lazy_import_data(tree)
                        has_init_issue = not all_names or any(n not in all_names for n in dynamic_imports)
                    except Exception:
                        has_init_issue = True
                    
                    # Check if any children have issues
                    has_child_issue = False
                    for item in pkg.iterdir():
                        if item.is_file() and item.suffix == ".py" and item.name != "__init__.py":
                            b, m = get_module_health(item, get_module_path(item))
                            if b or m:
                                has_child_issue = True; break
                    
                    pkg_health[mod_path] = (has_init_issue, has_child_issue)

            table = Table(title="\nCodeWeaver Packages", expand=True)
            table.add_column("ID", style="dim", width=4)
            table.add_column("Package", style="cyan")
            table.add_column("Status", width=12)
            
            for i, pkg in enumerate(packages):
                name = get_module_path(pkg)
                init_err, child_err = pkg_health[name]
                
                style = "bold magenta" if init_err else "white"
                status = ""
                if init_err: status += "[bold red]INIT[/bold red] "
                if child_err: status += "[yellow]SUB[/yellow]"
                if not status: status = "[green]OK[/green]"
                
                table.add_row(str(i), f"[{style}]{name}[/{style}]", status)
            console.print(table)

            choice = Prompt.ask("\nSelect ID to manage (or [bold red]q[/bold red] to quit)")
            if choice.lower() == "q":
                break
            try:
                selected_pkg = packages[int(choice)]
            except (ValueError, IndexError):
                continue

            while True:
                sub_exports = get_package_exports(selected_pkg)
                console.print(
                    Panel(
                        f"Managing [bold cyan]{get_module_path(selected_pkg)}[/bold cyan]",
                        style="blue",
                    )
                )
                
                table = Table(box=None, expand=True)
                table.add_column("Module", style="cyan", width=40)
                table.add_column("Status", width=10)
                table.add_column("Exports", style="green")
                
                for mod, exports in sub_exports.items():
                    # Check health for coloring
                    f_path = selected_pkg / (mod.split(".")[-1] + ".py")
                    if not f_path.exists(): f_path = selected_pkg / mod.split(".")[-1] / "__init__.py"
                    
                    broken, missing = get_module_health(f_path, mod)
                    
                    status = ""
                    if broken: status += "[bold red]![/bold red]"
                    if missing: status += "[yellow]? [/yellow]"
                    if not status: status = "[green]✓[/green]"
                    
                    mod_display = f"[bold yellow]{mod}[/bold yellow]" if (broken or missing) else mod
                    table.add_row(mod_display, status, ", ".join(exports))
                console.print(table)

                # Create a mapping of short names to full module paths for easy input
                short_to_full = {m.split(".")[-1]: m for m in sub_exports.keys()}

                console.print("\n[bold]Actions:[/bold]")
                console.print(
                    " [[bold cyan]g[/bold cyan]]enerate init  "
                    "[[bold cyan]e[/bold cyan]]xclude items  "
                    "[[bold cyan]m[/bold cyan]]odule all  "
                    "[[bold cyan]f[/bold cyan]]ix imports  "
                    "[[bold cyan]r[/bold cyan]]econcile  "
                    "[[bold cyan]b[/bold cyan]]ack"
                )
                action = Prompt.ask(
                    "\nChoice",
                    choices=["g", "e", "m", "f", "r", "b"],
                    show_choices=False,
                )
                if action == "b":
                    break
                if action == "g":
                    content = generate_init_content(selected_pkg, sub_exports)
                    console.print(Panel(content, title="Proposed __init__.py"))
                    if Confirm.ask("Write?"):
                        (selected_pkg / "__init__.py").write_text(content, encoding="utf-8")
                elif action == "e":
                    mod_choice = Prompt.ask("Module", choices=list(short_to_full.keys()))
                    full_mod = short_to_full[mod_choice]

                    # Resolve actual file path
                    f_path = selected_pkg / (mod_choice + ".py")
                    if not f_path.exists():
                        f_path = selected_pkg / mod_choice / "__init__.py"

                    members, _ = get_public_members(f_path)
                    member_names = [m.name for m in members]
                    console.print(f"Available members: {', '.join(member_names)}")
                    to_ex = Prompt.ask("Exclusions (comma-separated)")
                    config = load_config()
                    if to_ex:
                        config["exclusions"][full_mod] = [x.strip() for x in to_ex.split(",")]
                    else:
                        config["exclusions"].pop(full_mod, None)
                    save_config(config)
                elif action == "m":
                    mod_choice = Prompt.ask("Module", choices=list(short_to_full.keys()))
                    full_mod = short_to_full[mod_choice]

                    f_path = selected_pkg / (mod_choice + ".py")
                    if not f_path.exists():
                        f_path = selected_pkg / mod_choice / "__init__.py"

                    config = load_config()
                    mod_excl = config.get("module_exclusions", {}).get(full_mod, [])

                    mems, current_all = get_public_members(f_path)
                    current_all = current_all or []
                    member_names = [m.name for m in mems]

                    missing = [
                        m for m in member_names if m not in current_all and m not in mod_excl
                    ]

                    console.print(f"\n[bold]Audit for {mod_choice}:[/bold]")
                    console.print(f"  Current __all__: {', '.join(current_all) or '[dim]None[/dim]'}")
                    console.print(f"  Discovered Public: {', '.join(member_names)}")

                    if not missing:
                        console.print("[green]✓ No missing items found in __all__.[/green]")
                    else:
                        console.print(
                            f"[yellow]! Found {len(missing)} items missing from __all__:[/yellow]"
                        )
                        for name in missing:
                            item_choice = Prompt.ask(
                                f"  Item [bold cyan]{name}[/bold cyan]: [a]dd to __all__, [e]xclude from __all__, [s]kip",
                                choices=["a", "e", "s"],
                                default="s",
                            )
                            if item_choice == "a":
                                current_all.append(name)
                                current_all.sort()
                                console.print(f"    [green]+ Added {name} to __all__[/green]")
                            elif item_choice == "e":
                                if "module_exclusions" not in config:
                                    config["module_exclusions"] = {}
                                if full_mod not in config["module_exclusions"]:
                                    config["module_exclusions"][full_mod] = []
                                config["module_exclusions"][full_mod].append(name)
                                config["module_exclusions"][full_mod].sort()
                                save_config(config)
                                console.print(f"    [red]∅ Permanently excluded {name}[/red]")

                    if Confirm.ask(f"Update __all__ in {mod_choice} now?"):
                        source = f_path.read_text()
                        sorted_all = sorted(current_all, key=export_sort_key)
                        new_all = (
                            f"__all__ = ({', '.join(f'{chr(34)}{n}{chr(34)}' for n in sorted_all)})"
                        )
                        if "__all__ =" in source:
                            source = re.sub(
                                r"__all__\s*=\s*\([^)]*\)", new_all, source, flags=re.DOTALL
                            )
                        else:
                            source += f"\n\n{new_all}\n"
                        f_path.write_text(format_code(source))
                        console.print(f"[green]Updated {f_path}[/green]")

                elif action == "f":
                    mod_choice = Prompt.ask("Module", choices=list(short_to_full.keys()))
                    full_mod = short_to_full[mod_choice]
                    f_path = selected_pkg / (mod_choice + ".py")
                    if not f_path.exists():
                        f_path = selected_pkg / mod_choice / "__init__.py"

                    errors = get_broken_imports(f_path, full_mod)
                    if not errors:
                        console.print("[green]No broken imports found![/green]")
                        continue

                    lines = f_path.read_text(encoding="utf-8").splitlines()
                    changes_made = False

                    for err in sorted(errors, key=lambda x: x.line, reverse=True):
                        full_name = f"{err.module}.{err.name}" if err.name else err.module
                        console.print(f"\n[bold red]Broken Import:[/bold red] {full_name} at line {err.line}")
                        console.print(f"[dim]{lines[err.line-1].strip()}[/dim]")
                        
                        fix_type = Prompt.ask(
                            "Fix",
                            choices=["r", "s", "m", "k"],
                            default="k"
                        )
                        # r: remove, s: substring, m: manual, k: keep

                        if fix_type == "k":
                            continue
                        
                        changes_made = True
                        if fix_type == "r":
                            # Remove the line (simplest approach for now)
                            lines.pop(err.line - 1)
                            console.print(f"  [red]- Removed line {err.line}[/red]")
                        elif fix_type == "s":
                            old = Prompt.ask("Old substring")
                            new = Prompt.ask("New substring")
                            lines[err.line - 1] = lines[err.line - 1].replace(old, new)
                            console.print(f"  [yellow]~ Replaced {old} with {new}[/yellow]")
                        elif fix_type == "m":
                            new_val = Prompt.ask("Enter replacement for this part of the import")
                            target = err.name if err.name else err.module
                            lines[err.line - 1] = lines[err.line - 1].replace(target, new_val)
                            console.print(f"  [green]+ Updated import to reference {new_val}[/green]")

                    if changes_made:
                        if Confirm.ask("Save changes and format?"):
                            f_path.write_text(format_code("\n".join(lines) + "\n"), encoding="utf-8")
                            console.print("[green]File updated and formatted.[/green]")

                elif action == "r":
                    # Find public things in submodules that ARE NOT in current sub_exports
                    # and are not already in the exclusions list.
                    config = load_config()
                    exclusions = config.get("exclusions", {})

                    missing_found = False
                    for item in sorted(selected_pkg.iterdir()):
                        if item.is_file() and item.suffix == ".py" and item.name != "__init__.py":
                            mod_path = get_module_path(item)
                            members, _ = get_public_members(item)
                            member_names = [m.name for m in members]
                            current_exports = sub_exports.get(mod_path, [])
                            current_exclusions = exclusions.get(mod_path, [])

                            missing = [
                                m
                                for m in member_names
                                if m not in current_exports and m not in current_exclusions
                            ]

                            if not missing:
                                continue

                            missing_found = True
                            console.print(
                                f"\n[bold yellow]Found {len(missing)} missing items in {mod_path}:[/bold yellow]"
                            )

                            for name in missing:
                                item_choice = Prompt.ask(
                                    f"  Item [bold cyan]{name}[/bold cyan]: [a]dd to exports, [e]xclude permanently, [s]kip",
                                    choices=["a", "e", "s"],
                                    default="s",
                                )

                                if item_choice == "a":
                                    if mod_path not in sub_exports:
                                        sub_exports[mod_path] = []
                                    if name not in sub_exports[mod_path]:
                                        sub_exports[mod_path].append(name)
                                        sub_exports[mod_path].sort()
                                    console.print(
                                        f"    [green]+ Added {name} to current session exports[/green]"
                                    )

                                elif item_choice == "e":
                                    if mod_path not in exclusions:
                                        exclusions[mod_path] = []
                                    if name not in exclusions[mod_path]:
                                        exclusions[mod_path].append(name)
                                        exclusions[mod_path].sort()
                                    console.print(f"    [red]∅ Permanently excluded {name}[/red]")
                                    config["exclusions"] = exclusions
                                    save_config(config)

                    if not missing_found:
                        console.print(
                            "[green]No new missing exports found (checked against current exports and JSON memory).[/green]"
                        )
                    else:
                        console.print("\n[bold green]Reconciliation pass complete.[/bold green]")
                        if Confirm.ask("Regenerate __init__.py with these changes?"):
                            content = generate_init_content(selected_pkg, sub_exports)
                            console.print(Panel(content, title="Proposed __init__.py"))
                            if Confirm.ask("Write?"):
                                (selected_pkg / "__init__.py").write_text(content, encoding="utf-8")
                                console.print("[green]Updated __init__.py successfully![/green]")
    except (EOFError, KeyboardInterrupt):
        console.print("\n[yellow]Management session interrupted. Exiting gracefully...[/yellow]")


# ============================================================================
# MAIN
# ============================================================================


def main():
    if "--manage" in sys.argv:
        manage_tui()
        return 0

    console.print(Rule("[bold cyan]CodeWeaver Import Validator & Manager[/bold cyan]"))

    # Global Import Scan
    console.print("\n[bold blue]Section 0: Global Import Scan[/bold blue]")
    import_errors = scan_all_imports()
    if import_errors:
        for e in import_errors:
            name_part = f".{e.name}" if e.name else ""
            console.print(
                f"[red]BROKEN[/red] {format_file_link(e.file_path, e.line)}: {e.module}{name_part}"
            )
    else:
        console.print("[green]✓ No broken internal imports found.[/green]")

    console.print("\n[bold blue]Section 1: lazy_import() Function Calls[/bold blue]")
    f_errors = validate_function_calls()
    if f_errors:
        for e in f_errors:
            console.print(f"[red]ERROR[/red] {e.file_ref}: {e.status} ({e.module}.{e.obj})")

    p_errors, p_warnings, p_info = validate_package_level_imports()
    for e in p_errors:
        console.print(f"[red]ERROR[/red] {e.module_name}: {e.message}")
    for w in p_warnings:
        console.print(f"[yellow]WARN[/yellow] {w.module_name}: {w.message}")

    if f_errors or p_errors:
        return 1
    console.print("[bold green]✅ Validations passed![/bold green]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
