# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Lazy imports CLI commands.

Provides user interface for all lazy import operations:
- Validation and fixing of imports
- Generation of __init__.py files
- Analysis and health checks
- Migration from old system
"""

from __future__ import annotations

import logging

from pathlib import Path
from typing import TYPE_CHECKING, Annotated, NoReturn

from cyclopts import App, Parameter
from rich.console import Console
from rich.panel import Panel

from tools.exportify.common.types import MemberType, RuleAction, RuleEngine


logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from tools.exportify.types import ExportGenerationResult, ValidationReport

app = App(name="lazy-imports", help="Manage lazy imports and auto-generated __init__.py files")

console = Console()


def _print_success(message: str) -> None:
    """Print success message."""
    console.print(f"[green]✓[/green] {message}")


def _print_error(message: str) -> None:
    """Print error message."""
    console.print(f"[red]✗[/red] {message}")


def _print_warning(message: str) -> None:
    """Print warning message."""
    console.print(f"[yellow]⚠[/yellow] {message}")


def _print_info(message: str) -> None:
    """Print info message."""
    console.print(f"[cyan]ℹ[/cyan] {message}")  # noqa: RUF001


def _print_generation_results(result: ExportGenerationResult) -> None:
    """Print export generation results with colors."""
    console.print()
    console.print(Panel("[bold]Export Generation Results[/bold]", expand=False))
    console.print()

    # Summary metrics
    metrics = result.metrics
    console.print(f"  Files analyzed: [cyan]{metrics.files_analyzed}[/cyan]")
    console.print(f"  Files generated: [green]{metrics.files_generated}[/green]")
    console.print(f"  Files updated: [yellow]{metrics.files_updated}[/yellow]")
    console.print(f"  Files skipped: [dim]{metrics.files_skipped}[/dim]")
    console.print(f"  Exports created: [green]{metrics.exports_created}[/green]")
    console.print(f"  Processing time: [cyan]{metrics.processing_time_ms / 1000:.2f}s[/cyan]")
    console.print(f"  Cache hit rate: [cyan]{metrics.cache_hit_rate * 100:.1f}%[/cyan]")
    console.print()

    # Errors if any
    if result.errors:
        console.print("[red]Errors encountered:[/red]")
        for error in result.errors:
            console.print(f"  [red]•[/red] {error}")
        console.print()

    # Status
    if result.success:
        _print_success("Export generation completed successfully")
    else:
        _print_error("Export generation failed")
    console.print()


def _print_validation_results(report: ValidationReport) -> None:
    """Print validation results with colors."""
    console.print()
    console.print(Panel("[bold]Validation Results[/bold]", expand=False))
    console.print()

    # Summary
    metrics = report.metrics
    console.print(f"  Files validated: [cyan]{metrics.files_validated}[/cyan]")
    console.print(f"  Imports checked: [cyan]{metrics.imports_checked}[/cyan]")
    console.print(f"  Consistency checks: [cyan]{metrics.consistency_checks}[/cyan]")
    console.print(f"  Validation time: [cyan]{metrics.validation_time_ms / 1000:.2f}s[/cyan]")
    console.print()

    # Errors
    if report.errors:
        console.print(f"[red]Errors found: {len(report.errors)}[/red]")
        for error in report.errors:
            location = f"{error.file}:{error.line}" if error.line else str(error.file)
            console.print(f"  [red]•[/red] {location}")
            console.print(f"    {error.message}")
            if error.suggestion:
                console.print(f"    [dim]Suggestion: {error.suggestion}[/dim]")
        console.print()

    # Warnings
    if report.warnings:
        console.print(f"[yellow]Warnings found: {len(report.warnings)}[/yellow]")
        for warning in report.warnings:
            location = f"{warning.file}:{warning.line}" if warning.line else str(warning.file)
            console.print(f"  [yellow]•[/yellow] {location}")
            console.print(f"    {warning.message}")
            if warning.suggestion:
                console.print(f"    [dim]Suggestion: {warning.suggestion}[/dim]")
        console.print()

    # Status
    if report.success:
        _print_success("All validations passed")
    else:
        _print_error("Validation failed")
    console.print()


def _resolve_validation_files(module: Path | None, *, json_output: bool) -> list[Path] | None:
    """Resolve file paths to validate based on module parameter."""
    if not module:
        return None

    if module.is_file():
        return [module]
    if module.is_dir():
        return list(module.rglob("*.py"))

    if not json_output:
        _print_error(f"Module path does not exist: {module}")
    raise SystemExit(1)


def _output_validation_json(results) -> None:
    """Output validation results in JSON format."""
    import json as json_lib

    output_data = {
        "success": results.success,
        "errors": [
            {
                "file": str(error.file),
                "line": error.line,
                "message": error.message,
                "code": error.code,
                "suggestion": error.suggestion,
            }
            for error in results.errors
        ],
        "warnings": [
            {
                "file": str(warning.file),
                "line": warning.line,
                "message": warning.message,
                "suggestion": warning.suggestion,
            }
            for warning in results.warnings
        ],
        "metrics": {
            "files_validated": results.metrics.files_validated,
            "imports_checked": results.metrics.imports_checked,
            "consistency_checks": results.metrics.consistency_checks,
            "validation_time_ms": results.metrics.validation_time_ms,
        },
    }
    console.print(json_lib.dumps(output_data, indent=2))


def _output_validation_verbose(results) -> None:
    """Output validation results in verbose human-readable format."""
    console.print()
    console.print(Panel("[bold]Validation Results[/bold]", expand=False))
    console.print()

    # Show errors with full context
    if results.errors:
        console.print(f"[red]Errors found: {len(results.errors)}[/red]")
        console.print()
        for error in results.errors:
            location = f"{error.file}:{error.line}" if error.line else str(error.file)
            console.print(f"[red]ERROR[/red] {location}: [bold]{error.code}[/bold]")
            _print_error_in_validation(error)
    # Show warnings with full context
    if results.warnings:
        console.print(f"[yellow]Warnings found: {len(results.warnings)}[/yellow]")
        console.print()
        for warning in results.warnings:
            location = f"{warning.file}:{warning.line}" if warning.line else str(warning.file)
            console.print(f"[yellow]WARNING[/yellow] {location}")
            _print_error_in_validation(warning)
    # Show metrics
    metrics = results.metrics
    console.print("[bold]Metrics:[/bold]")
    console.print(f"  Files validated: [cyan]{metrics.files_validated}[/cyan]")
    console.print(f"  Imports checked: [cyan]{metrics.imports_checked}[/cyan]")
    console.print(f"  Consistency checks: [cyan]{metrics.consistency_checks}[/cyan]")
    console.print(f"  Validation time: [cyan]{metrics.validation_time_ms / 1000:.2f}s[/cyan]")
    console.print()


def _print_error_in_validation(error):
    console.print(f"  {error.message}")
    if error.suggestion:
        console.print(f"  [dim]Suggestion: {error.suggestion}[/dim]")
    console.print()


def _output_validation_concise(results) -> None:
    """Output validation results in concise human-readable format."""
    if results.errors:
        for error in results.errors:
            location = f"{error.file}:{error.line}" if error.line else str(error.file)
            console.print(f"[red][ERROR][/red] {location}: {error.code} ({error.message})")

    if results.warnings:
        for warning in results.warnings:
            location = f"{warning.file}:{warning.line}" if warning.line else str(warning.file)
            console.print(f"[yellow][WARNING][/yellow] {location}: {warning.message}")

    # Show summary
    console.print()
    console.print(f"Files validated: {results.metrics.files_validated}")
    console.print(f"Errors: {len(results.errors)}, Warnings: {len(results.warnings)}")


@app.command
def validate(
    fix: Annotated[bool, Parameter(help="Auto-fix import issues")] = False,
    strict: Annotated[bool, Parameter(help="Fail on any issues (including warnings)")] = False,
    module: Annotated[Path | None, Parameter(help="Validate specific module or file")] = None,
    json_output: Annotated[bool, Parameter(name="json", help="Output results as JSON")] = False,
    verbose: Annotated[bool, Parameter(help="Show detailed validation information")] = False,
) -> None:
    """Validate that imports match exports.

    Checks:
    - All lazy_import() calls resolve to real modules
    - __all__ declarations match _dynamic_imports
    - TYPE_CHECKING imports exist
    - No broken imports

    Examples:
        exportify validate
        exportify validate --fix
        exportify validate --strict
        exportify validate --module src/codeweaver/core
        exportify validate --json
        exportify validate --verbose
    """
    from tools.exportify.common.cache import JSONAnalysisCache
    from tools.exportify.validator.validator import LazyImportValidator

    if not json_output:
        _print_info("Validating lazy imports...")
        console.print()

    # Set up validator
    cache = JSONAnalysisCache()
    project_root = Path.cwd()
    validator = LazyImportValidator(project_root=project_root, cache=cache)

    # Determine files to validate
    file_paths = _resolve_validation_files(module, json_output)

    # Run validation
    results = validator.validate(file_paths=file_paths)

    # Output results based on format
    if json_output:
        _output_validation_json(results)
    elif verbose:
        _output_validation_verbose(results)
    else:
        _output_validation_concise(results)

    # Status message
    console.print()
    if results.success:
        _print_success("All validations passed")
    else:
        _print_error("Validation failed")
    console.print()

    # Auto-fix if requested
    if fix and (results.errors or results.warnings) and not json_output:
        _print_info("Auto-fix is not yet implemented")
        console.print()

    # Exit with error code if validation failed
    if not results.success or (strict and results.warnings):
        raise SystemExit(1)


@app.command
def generate(
    dry_run: Annotated[bool, Parameter(help="Show changes without writing files")] = False,
    module: Annotated[Path | None, Parameter(help="Generate for specific module")] = None,
    source: Annotated[Path, Parameter(help="Source root directory")] = Path("src"),
    output: Annotated[
        Path | None, Parameter(help="Output directory (default: same as source)")
    ] = None,
) -> None:
    """Generate __init__.py files from export manifests.

    Analyzes the codebase and generates __init__.py files with:
    - Proper __all__ declarations
    - lazy_import() calls for exports
    - TYPE_CHECKING imports where appropriate

    Examples:
        exportify generate
        exportify generate --dry-run
        exportify generate --module src/codeweaver/core
        exportify generate --source tools/exportify --output /tmp/test
    """

    def _raise_system_exit(message: str) -> NoReturn:
        _print_error(message)
        raise SystemExit(1)

    from tools.exportify.common.cache import JSONAnalysisCache
    from tools.exportify.export_manager import RuleEngine
    from tools.exportify.pipeline import Pipeline

    _print_info("Generating exports...")
    console.print()

    # Load rules
    _print_info("Loading export rules...")
    rules = RuleEngine()
    rules_path = Path(".codeweaver/lazy_import_rules.yaml")

    if not rules_path.exists():
        _print_warning(f"Rules file not found: {rules_path}")
        _print_info("Using default rules")
    else:
        rules.load_rules([rules_path])
        _print_success(f"Loaded rules from {rules_path}")

    console.print()

    # Set up cache and output directory
    cache = JSONAnalysisCache()
    output_dir = output or source

    # Create pipeline
    _print_info("Initializing pipeline...")
    pipeline = Pipeline(rule_engine=rules, cache=cache, output_dir=output_dir)

    # Determine source root
    source_root = source
    if not source_root.exists():
        _print_error(f"Source directory not found: {source_root}")
        raise SystemExit(1)

    console.print()

    # Show dry-run status
    if dry_run:
        _print_info("Dry run mode - no files will be written")
        console.print()

    # Execute pipeline
    _print_info(f"Processing {source_root}...")
    if module:
        _print_info(f"Filtering to module: {module}")

    console.print()

    try:
        result = pipeline.run(source_root=source_root, dry_run=dry_run, module=module)

        # Display results
        _print_generation_results(result)

        # Exit with error if generation failed
        if not result.success:
            _raise_system_exit("Export generation failed - see above for details")

    except Exception as e:
        _print_error(f"Pipeline execution failed: {e}")
        console.print()
        import traceback

        console.print("[dim]Full traceback:[/dim]")
        console.print(traceback.format_exc())
        raise SystemExit(1) from e


def _analyze_target_path(module: Path | None, source_root: Path) -> tuple[Path, Path, str]:
    """Determine and validate target path for analysis.

    Returns: (target_path, target_file, module_path)
    """
    # Parse target module or package
    if module:
        target_path = module
        if not target_path.exists():
            _print_error(f"Module not found: {target_path}")
            raise SystemExit(1)
    else:
        target_path = source_root

    # For simplicity, analyze a single module for now
    if target_path.is_dir():
        init_file = target_path / "__init__.py"
        if not init_file.exists():
            _analyze_missing_init_and_exit(target_path)
        target_file = init_file
        module_path = _path_to_module(target_path, source_root)
    else:
        target_file = target_path
        module_path = _path_to_module(target_path.parent, source_root)

    return target_path, target_file, module_path


def _analyze_missing_init_and_exit(target_path) -> NoReturn:
    _print_warning(f"No __init__.py found in {target_path}")
    _print_info("Searching for Python modules...")

    # Find all Python files in directory
    python_files = list(target_path.rglob("*.py"))
    if not python_files:
        _print_error("No Python files found")
        raise SystemExit(1)

    _print_info(f"Found {len(python_files)} Python files")
    console.print()

    # For now, just show summary
    _print_warning("Multi-module analysis not yet fully implemented")
    _print_info("Please specify a specific module with __init__.py")
    raise SystemExit(1)


def _collect_analysis_data(
    target_path: Path, module_path: str, rules: RuleEngine
) -> tuple[dict, dict]:
    """Collect symbols and decisions from target module."""
    from collections import defaultdict

    from tools.exportify.analysis.ast_parser import ASTParser

    parser = ASTParser()

    # Parse all Python files in the package
    package_dir = target_path if target_path.is_dir() else target_path.parent
    python_files = [f for f in package_dir.glob("*.py") if f.name != "__init__.py"]

    # Collect all symbols from child modules
    all_symbols: dict[str, list] = defaultdict(list)
    all_decisions: dict[str, list] = defaultdict(list)

    for py_file in python_files:
        rel_module = py_file.stem
        full_module = f"{module_path}.{rel_module}"

        analysis = parser.parse_file(py_file, full_module)
        all_symbols[rel_module] = analysis.symbols

        # Evaluate rules for each symbol
        for symbol in analysis.symbols:
            decision = rules.evaluate(symbol, full_module)
            if decision.action != RuleAction.NO_DECISION:
                all_decisions[rel_module].append(decision)

    return all_symbols, all_decisions


def _build_manifest(module_path: str, all_decisions: dict, rules: RuleEngine):
    """Build manifest from decisions."""
    from tools.exportify.export_manager import CodeGenerator
    from tools.exportify.export_manager.graph import PropagationGraph

    # Generate code to see what would be created
    CodeGenerator(output_dir=Path.cwd())

    # Build propagation graph (simplified for single module analysis)
    graph = PropagationGraph(rule_engine=rules)

    # Add modules to graph first
    graph.add_module(module_path, parent=None)
    for rel_module in all_decisions:
        full_module = f"{module_path}.{rel_module}"
        graph.add_module(full_module, parent=module_path)

    # Add export decisions
    for decisions in all_decisions.values():
        for decision in decisions:
            if decision.action == RuleAction.INCLUDE:
                graph.add_export(decision)

    manifests = graph.build_manifests()
    return manifests.get(module_path)


def _get_preserved_code(target_file: Path) -> str:
    """Extract preserved code from existing __init__.py."""
    if target_file.exists() and target_file.name == "__init__.py":
        content = target_file.read_text()
        from tools.exportify.export_manager.section_parser import SectionParser

        parser_section = SectionParser()
        parsed = parser_section.parse_content(content)
        return parsed.preserved_code
    return ""


def _print_json_output(
    module_path: str, all_symbols: dict, all_decisions: dict, target_manifest, preserved_code: str
) -> None:
    """Print analysis results in JSON format."""
    import json

    output = {
        "package": module_path,
        "status": "ready" if target_manifest else "no_exports",
        "symbols": {
            rel_module: [
                {
                    "name": s.name,
                    "type": s.member_type.value,
                    "provenance": s.provenance.value,
                    "is_private": s.is_private,
                    "location": {"line": s.location.line},
                }
                for s in symbols
            ]
            for rel_module, symbols in all_symbols.items()
        },
        "decisions": {
            rel_module: [
                {
                    "symbol": d.export_name,
                    "action": d.action.value,
                    "rule": d.reason,
                    "propagation": d.propagation.value if d.propagation else None,
                }
                for d in decisions
            ]
            for rel_module, decisions in all_decisions.items()
        },
        "would_generate": {
            "type_checking_count": len(target_manifest.all_exports) if target_manifest else 0,
            "dynamic_imports_count": len([
                e for e in target_manifest.all_exports if not e.is_type_only
            ])
            if target_manifest
            else 0,
            "all_count": len(target_manifest.all_exports) if target_manifest else 0,
        },
        "preserved_code": bool(preserved_code),
    }
    console.print(json.dumps(output, indent=2))


def _print_symbols_section(all_symbols: dict, *, verbose: bool) -> None:
    """Print detected symbols section."""
    from collections import defaultdict

    total_symbols = sum(len(symbols) for symbols in all_symbols.values())
    console.print(f"[bold]Detected Symbols ({total_symbols}):[/bold]")

    for rel_module, symbols in sorted(all_symbols.items()):
        if not symbols:
            continue

        console.print(f"  [cyan]{rel_module}.py[/cyan]:")
        by_type: dict[MemberType, list] = defaultdict(list)
        for symbol in symbols:
            by_type[symbol.member_type].append(symbol)

        for member_type in [
            MemberType.CLASS,
            MemberType.FUNCTION,
            MemberType.CONSTANT,
            MemberType.VARIABLE,
            MemberType.TYPE_ALIAS,
            MemberType.IMPORTED,
        ]:
            if member_type not in by_type:
                continue

            names = [s.name for s in by_type[member_type]]
            if not verbose:
                display_names = names[:5]
                if len(names) > 5:
                    display_names.append(f"... and {len(names) - 5} more")
                console.print(f"    {member_type.value.title()}: {', '.join(display_names)}")
            else:
                console.print(f"    {member_type.value.title()}:")
                for name in names:
                    console.print(f"      • {name}")

    console.print()


def _print_decisions_section(all_decisions: dict, *, verbose: bool) -> None:
    """Print export rules applied section."""
    total_decisions = sum(len(decisions) for decisions in all_decisions.values())
    console.print(f"[bold]Export Rules Applied ({total_decisions}):[/bold]")

    for rel_module, decisions in sorted(all_decisions.items()):
        if not decisions:
            continue

        console.print(f"  [cyan]{rel_module}.py[/cyan]:")
        for decision in decisions[: None if verbose else 10]:
            status = "✓" if decision.action == RuleAction.INCLUDE else "✗"
            color = "green" if decision.action == RuleAction.INCLUDE else "red"
            console.print(
                f"    [{color}]{status}[/{color}] {decision.export_name:<20} [{decision.reason}]"
            )

        if not verbose and len(decisions) > 10:
            console.print(f"    [dim]... and {len(decisions) - 10} more[/dim]")

    console.print()


def _print_generation_section(target_manifest) -> None:
    """Print would generate section."""
    if not target_manifest:
        return

    runtime_exports = [e for e in target_manifest.all_exports if not e.is_type_only]
    console.print("[bold]Would Generate:[/bold]")
    console.print(f"  TYPE_CHECKING: [cyan]{len(target_manifest.all_exports)}[/cyan] imports")
    console.print(f"  _dynamic_imports: [cyan]{len(runtime_exports)}[/cyan] entries")
    console.print(f"  __all__: [cyan]{len(target_manifest.all_exports)}[/cyan] exports")
    console.print()


def _print_preserved_code_section(preserved_code: str, *, verbose: bool) -> None:
    """Print preserved code section."""
    if not preserved_code:
        return

    console.print("[bold]Preserved Code:[/bold]")
    lines = preserved_code.strip().split("\n")
    console.print(f"  {len(lines)} lines of user code")

    if verbose:
        console.print()
        console.print("  [dim]Preview:[/dim]")
        for line in lines[:10]:
            console.print(f"  [dim]{line}[/dim]")
        if len(lines) > 10:
            console.print(f"  [dim]... and {len(lines) - 10} more lines[/dim]")

    console.print()


def _print_warnings_section(target_manifest) -> None:
    """Print warnings section."""
    warnings = []
    if not target_manifest or not target_manifest.all_exports:
        warnings.append("No exports detected - package may be empty or all private")

    console.print("[bold]Warnings:[/bold]")
    if warnings:
        for warning in warnings:
            _print_warning(warning)
    else:
        console.print("  None")

    console.print()


def _print_ready_status(target_manifest) -> None:
    """Print final ready status."""
    if target_manifest and target_manifest.all_exports:
        _print_success("Ready: Yes")
    else:
        _print_warning("Ready: No (no exports to generate)")


def _print_text_output(
    module_path: str,
    all_symbols: dict,
    all_decisions: dict,
    target_manifest,
    preserved_code: str,
    *,
    verbose: bool,
) -> None:
    """Print analysis results in human-readable text format."""
    console.print(f"[bold]Package:[/bold] {module_path}")
    console.print(
        f"[bold]Status:[/bold] {'[green]Ready for generation[/green]' if target_manifest else '[yellow]No exports detected[/yellow]'}"
    )
    console.print()

    _print_symbols_section(all_symbols, verbose)
    _print_decisions_section(all_decisions, verbose)
    _print_generation_section(target_manifest)
    _print_preserved_code_section(preserved_code, verbose)
    _print_warnings_section(target_manifest)
    _print_ready_status(target_manifest)


@app.command
def analyze(
    module: Annotated[Path | None, Parameter(help="Analyze specific module")] = None,
    source: Annotated[Path, Parameter(help="Source directory to analyze")] = Path("src"),
    verbose: Annotated[bool, Parameter(help="Show detailed analysis")] = False,
    format: Annotated[  # noqa: A002
        str, Parameter(help="Output format: text, json")
    ] = "text",
) -> None:
    """Analyze package structure and show what would be generated.

    Performs dry-run analysis showing:
    - Detected symbols with metadata
    - Export rules applied
    - What would be generated
    - Preserved code sections
    - Warnings and issues

    Examples:
        exportify analyze
        exportify analyze --module src/codeweaver/core/types
        exportify analyze --verbose
        exportify analyze --format json
    """
    from tools.exportify.common.cache import AnalysisCache
    from tools.exportify.export_manager import RuleEngine

    _print_info("Analyzing package structure...")
    console.print()

    # Load rules
    _print_info("Loading export rules...")
    rules = RuleEngine()
    rules_path = Path(".codeweaver/lazy_import_rules.yaml")

    if not rules_path.exists():
        _print_warning(f"Rules file not found: {rules_path}")
        _print_info("Using default rules")
    else:
        rules.load_rules([rules_path])
        _print_success(f"Loaded rules from {rules_path}")

    console.print()

    # Determine target path
    source_root = source
    if not source_root.exists():
        _print_error(f"Source directory not found: {source_root}")
        raise SystemExit(1)

    # Analyze target path
    target_path, target_file, module_path = _analyze_target_path(module, source_root)

    # Parse the module
    _print_info(f"Analyzing module: {module_path}")
    console.print()

    AnalysisCache()

    # Collect analysis data
    all_symbols, all_decisions = _collect_analysis_data(target_path, module_path, rules)

    # Build manifest
    target_manifest = _build_manifest(module_path, all_decisions, rules)

    # Get preserved code
    preserved_code = _get_preserved_code(target_file)

    # Output results
    if format == "json":
        _print_json_output(module_path, all_symbols, all_decisions, target_manifest, preserved_code)
    else:
        _print_text_output(
            module_path, all_symbols, all_decisions, target_manifest, preserved_code, verbose
        )

    console.print()


def _path_to_module(path: Path, source_root: Path) -> str:
    """Convert a file path to a module path."""
    try:
        relative = path.relative_to(source_root)
    except ValueError:
        # Not relative to source_root, use absolute
        relative = path

    parts = relative.parts
    return ".".join(parts)


@app.command
def doctor() -> None:
    """Run health checks and provide actionable advice.

    Checks:
    - Cache health and validity
    - Rule configuration
    - Export conflicts
    - Performance issues

    Provides recommendations for improvements.

    Examples:
        exportify doctor
    """
    console.print()
    console.print(Panel("[bold]Lazy Import System Health Check[/bold]", expand=False))
    console.print()

    # Check cache
    _print_info("Checking analysis cache...")
    from tools.exportify.common.cache import AnalysisCache

    cache = AnalysisCache()
    stats = cache.get_stats()

    console.print(f"  Total entries: [cyan]{stats.total_entries}[/cyan]")
    console.print(f"  Valid entries: [green]{stats.valid_entries}[/green]")
    console.print(f"  Invalid entries: [red]{stats.invalid_entries}[/red]")
    console.print(f"  Cache size: [cyan]{stats.total_size_bytes / 1024:.1f}KB[/cyan]")
    console.print(f"  Hit rate: [cyan]{stats.hit_rate * 100:.1f}%[/cyan]")
    console.print()

    # Check rules
    _print_info("Checking rule configuration...")
    rules_path = Path(".codeweaver/lazy_import_rules.yaml")

    if rules_path.exists():
        _print_success(f"Rules file found: {rules_path}")
    else:
        _print_warning(f"Rules file not found: {rules_path}")
        console.print("  [dim]Recommendation: Run 'exportify migrate'[/dim]")

    console.print()

    # Overall status
    if stats.invalid_entries > stats.total_entries * 0.1:  # More than 10% invalid
        _print_warning("High invalid cache rate - consider clearing cache")
        console.print("  [dim]Run: exportify clear-cache[/dim]")
    else:
        _print_success("System health looks good")

    console.print()


@app.command
def migrate(
    backup: Annotated[bool, Parameter(help="Create backup before migration")] = True,
    rules_output: Annotated[Path, Parameter(help="Output path for rules YAML")] = Path(
        ".codeweaver/lazy_import_rules.yaml"
    ),
    dry_run: Annotated[bool, Parameter(help="Show changes without writing files")] = False,
    verbose: Annotated[bool, Parameter(help="Show detailed migration report")] = False,
) -> None:
    """Migrate from old hardcoded system to new YAML rules.

    Converts the old validate-lazy-imports.py script to:
    - Declarative YAML rules
    - Configuration files
    - New system format

    Creates backups of old configuration for rollback.

    Examples:
        exportify migrate
        exportify migrate --dry-run
        exportify migrate --no-backup
        exportify migrate --rules-output custom/path.yaml
        exportify migrate --verbose
    """
    from tools.exportify.migration import migrate_to_yaml

    _print_info("Starting migration to new lazy import system...")
    console.print()

    old_script = Path("mise-tasks/validate-lazy-imports.py")

    # Create backup if old script exists and backup is requested
    if backup and old_script.exists():
        backup_path = old_script.with_suffix(".py.backup")
        _print_info(f"Creating backup at {backup_path}...")
        import shutil

        shutil.copy2(old_script, backup_path)
        _print_success(f"Backup created: {backup_path}")
        console.print()

    # Run migration
    _print_info("Performing migration...")
    result = migrate_to_yaml(rules_output, old_script=old_script, dry_run=dry_run)

    if not result.success:
        _print_error("Migration failed:")
        for error in result.errors:
            console.print(f"  [red]•[/red] {error}")
        console.print()
        raise SystemExit(1)

    # Show results
    console.print()
    _print_success("Migration completed successfully!")
    console.print(f"  Rules extracted: [cyan]{len(result.rules_extracted)}[/cyan]")

    include_overrides = len(result.overrides_extracted.get("include", {}))
    exclude_overrides = len(result.overrides_extracted.get("exclude", {}))
    console.print(
        f"  Overrides: [cyan]{include_overrides}[/cyan] include, "
        f"[cyan]{exclude_overrides}[/cyan] exclude"
    )
    console.print()

    if dry_run:
        _print_info("Dry run mode - no files written")
        console.print()
        console.print("[bold]Generated YAML:[/bold]")
        console.print("─" * 80)
        console.print(result.yaml_content)
        console.print("─" * 80)
    else:
        _print_success(f"Rules written to: {rules_output}")
        report_path = rules_output.with_suffix(".migration.md")
        _print_success(f"Migration report: {report_path}")

    console.print()

    if verbose and result.equivalence_report:
        console.print("[bold]Migration Report:[/bold]")
        console.print()
        console.print(result.equivalence_report)
        console.print()


@app.command
def status(verbose: Annotated[bool, Parameter(help="Show detailed information")] = False) -> None:
    """Show current export/import health status.

    Displays:
    - Cache statistics
    - Validation status
    - Rule configuration status
    - Recent activity

    Examples:
        exportify status
        exportify status --verbose
    """
    console.print()
    console.print(Panel("[bold]Lazy Import System Status[/bold]", expand=False))
    console.print()

    # Cache status
    from tools.exportify.common.cache import AnalysisCache

    cache = AnalysisCache()
    stats = cache.get_stats()

    console.print("[bold]Cache Status:[/bold]")
    console.print(f"  Entries: [cyan]{stats.valid_entries}/{stats.total_entries}[/cyan] valid")
    console.print(f"  Hit rate: [cyan]{stats.hit_rate * 100:.1f}%[/cyan]")
    console.print()

    # Configuration status
    console.print("[bold]Configuration:[/bold]")
    rules_path = Path(".codeweaver/lazy_import_rules.yaml")

    if rules_path.exists():
        console.print(f"  Rules: [green]✓[/green] {rules_path}")
    else:
        console.print("  Rules: [red]✗[/red] Not found")

    console.print()

    # System status
    console.print("[bold]System:[/bold]")
    console.print("  Status: [green]Ready[/green]")
    console.print()

    if verbose:
        console.print("[bold]Detailed Information:[/bold]")
        console.print(f"  Cache size: {stats.total_size_bytes / 1024:.1f}KB")
        console.print(f"  Invalid entries: {stats.invalid_entries}")
        console.print()


@app.command(name="clear-cache")
def clear_cache() -> None:
    """Clear the analysis cache.

    Removes all cached analysis results. The cache will be rebuilt
    on the next validation or generation run.

    Use this when:
    - Cache is corrupted
    - Schema version changed
    - Performance issues

    Examples:
        exportify clear-cache
    """
    from tools.exportify.common.cache import AnalysisCache

    _print_info("Clearing analysis cache...")
    console.print()

    cache = AnalysisCache()
    cache.clear()

    _print_success("Cache cleared successfully")
    console.print()


if __name__ == "__main__":
    app()

__all__ = ("app",)
