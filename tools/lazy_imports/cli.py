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


logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from tools.lazy_imports.types import ExportGenerationResult, ValidationReport

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


@app.command
def validate(
    fix: Annotated[bool, Parameter(help="Auto-fix import issues")] = False,
    strict: Annotated[bool, Parameter(help="Fail on any issues (including warnings)")] = False,
    module: Annotated[Path | None, Parameter(help="Validate specific module")] = None,
) -> None:
    """Validate that imports match exports.

    Checks:
    - All lazy_import() calls resolve to real modules
    - __all__ declarations match _dynamic_imports
    - TYPE_CHECKING imports exist
    - No broken imports

    Examples:
        codeweaver lazy-imports validate
        codeweaver lazy-imports validate --fix
        codeweaver lazy-imports validate --strict
        codeweaver lazy-imports validate --module src/codeweaver/core
    """
    from tools.lazy_imports.common.cache import AnalysisCache
    from tools.lazy_imports.validator import ImportValidator

    _print_info("Validating lazy imports...")
    console.print()

    cache = AnalysisCache()
    validator = ImportValidator(cache=cache)

    results = validator.validate(module_path=module, strict=strict)
    _print_validation_results(results)

    if fix and (results.errors or results.warnings):
        _print_info("Attempting to fix issues...")
        from tools.lazy_imports.validator.fixer import AutoFixer

        fixer = AutoFixer(Path.cwd(), dry_run=False)
        fixed_files = fixer.fix_all(results.errors + results.warnings)
        console.print()
        _print_success(f"Fixed {len(fixed_files)} files")
        for file in fixed_files:
            console.print(f"  [green]•[/green] {file}")
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
        codeweaver lazy-imports generate
        codeweaver lazy-imports generate --dry-run
        codeweaver lazy-imports generate --module src/codeweaver/core
        codeweaver lazy-imports generate --source tools/lazy_imports --output /tmp/test
    """

    def _raise_system_exit(message: str) -> NoReturn:
        _print_error(message)
        raise SystemExit(1)

    from tools.lazy_imports.common.cache import JSONAnalysisCache
    from tools.lazy_imports.export_manager import RuleEngine
    from tools.lazy_imports.pipeline import Pipeline

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


@app.command
def analyze(
    format: Annotated[str, Parameter(help="Output format: json, table, or report")] = "table",  # noqa: A002
    source: Annotated[Path, Parameter(help="Source directory to analyze")] = Path("src"),
) -> None:
    """Analyze export patterns across the codebase.

    Generates statistics about:
    - Export counts by module
    - Propagation patterns
    - Rule usage
    - Cache effectiveness

    Examples:
        codeweaver lazy-imports analyze
        codeweaver lazy-imports analyze --format json
        codeweaver lazy-imports analyze --format report
        codeweaver lazy-imports analyze --source lazy_imports
    """
    from tools.lazy_imports.common.cache import AnalysisCache
    from tools.lazy_imports.export_manager import RuleEngine
    from tools.lazy_imports.pipeline import Pipeline

    _print_info("Analyzing export patterns...")
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

    # Initialize cache
    cache = AnalysisCache()

    # Create pipeline
    _print_info(f"Analyzing codebase in {source}...")
    pipeline = Pipeline(rule_engine=rules, cache=cache, output_dir=Path.cwd())

    # Run analysis in dry-run mode
    try:
        result = pipeline.run(
            source_root=source,
            dry_run=True,  # analyze command doesn't write files
        )

        # Display results using existing function
        _print_generation_results(result)

    except Exception as e:
        _print_error(f"Analysis failed: {e}")
        logger.exception("Analysis error details")
        raise SystemExit(1) from e


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
        codeweaver lazy-imports doctor
    """
    console.print()
    console.print(Panel("[bold]Lazy Import System Health Check[/bold]", expand=False))
    console.print()

    # Check cache
    _print_info("Checking analysis cache...")
    from tools.lazy_imports.common.cache import AnalysisCache

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
        console.print("  [dim]Recommendation: Run 'codeweaver lazy-imports migrate'[/dim]")

    console.print()

    # Overall status
    if stats.invalid_entries > stats.total_entries * 0.1:  # More than 10% invalid
        _print_warning("High invalid cache rate - consider clearing cache")
        console.print("  [dim]Run: codeweaver lazy-imports clear-cache[/dim]")
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
        codeweaver lazy-imports migrate
        codeweaver lazy-imports migrate --dry-run
        codeweaver lazy-imports migrate --no-backup
        codeweaver lazy-imports migrate --rules-output custom/path.yaml
        codeweaver lazy-imports migrate --verbose
    """
    from tools.lazy_imports.migration import migrate_to_yaml

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
        codeweaver lazy-imports status
        codeweaver lazy-imports status --verbose
    """
    console.print()
    console.print(Panel("[bold]Lazy Import System Status[/bold]", expand=False))
    console.print()

    # Cache status
    from tools.lazy_imports.common.cache import AnalysisCache

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
        codeweaver lazy-imports clear-cache
    """
    from tools.lazy_imports.common.cache import AnalysisCache

    _print_info("Clearing analysis cache...")
    console.print()

    cache = AnalysisCache()
    cache.clear()

    _print_success("Cache cleared successfully")
    console.print()


if __name__ == "__main__":
    app()

__all__ = ("app",)
