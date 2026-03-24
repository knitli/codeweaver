# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Migration commands for collection transformations."""

from __future__ import annotations

from typing import Annotated

import cyclopts

from cyclopts import App
from rich.console import Console

from codeweaver.cli.ui import (
    CLIErrorHandler,
    StatusDisplay,
    get_display,
    handle_keyboard_interrupt_gracefully,
)
from codeweaver.core.di import INJECTED
from codeweaver.engine.dependencies import MigrationServiceDep


display: StatusDisplay = get_display()
console = Console()

app = App(
    "migrate",
    help="Migrate vector collections between dimensions or quantization levels.",
    console=display.console,
)


@app.command()
async def migrate(
    target_dimension: Annotated[
        int, cyclopts.Parameter(help="New target dimension (must be less than current dimension)")
    ],
    workers: Annotated[
        int,
        cyclopts.Parameter(
            name=["--workers", "-w"], help="Number of parallel workers (default: 4)"
        ),
    ] = 4,
    batch_size: Annotated[
        int,
        cyclopts.Parameter(name=["--batch-size", "-b"], help="Vectors per batch (default: 1000)"),
    ] = 1000,
    no_resume: Annotated[
        bool,
        cyclopts.Parameter(
            name=["--no-resume"], help="Start fresh instead of resuming from checkpoint"
        ),
    ] = False,
    migration_service: MigrationServiceDep = INJECTED,
) -> None:
    """Migrate collection to new dimension with parallel workers.

    Performs dimension reduction using parallel workers for efficient processing.
    Includes 4-layer data integrity validation and automatic checkpoint/resume.

    Args:
        target_dimension: New dimension (must be less than current)
        workers: Number of parallel workers (default 4)
        batch_size: Vectors per batch (default 1000)
        no_resume: Start fresh instead of resuming from checkpoint
        migration_service: Injected migration service
    """
    display.print_command_header("Migrate Collection")

    try:
        display.console.print()
        display.console.print(
            f"⏳ Starting migration to dimension [cyan]{target_dimension}[/cyan] "
            f"with [cyan]{workers}[/cyan] workers..."
        )
        display.console.print()

        # Execute migration
        result = await migration_service.migrate_dimensions_parallel(
            new_dimension=target_dimension,
            worker_count=workers,
            batch_size=batch_size,
            resume=not no_resume,
        )

        # Success output
        display.console.print()
        display.print_success("Migration completed successfully!")
        display.console.print()

        # Show statistics
        display.console.print(f"  Vectors migrated: [cyan]{result.vectors_migrated:,}[/cyan]")
        display.console.print(f"  Time elapsed: [cyan]{result.elapsed.total_seconds():.1f}s[/cyan]")
        display.console.print(f"  Workers used: [cyan]{result.worker_count}[/cyan]")
        display.console.print(f"  Speedup factor: [cyan]{result.speedup_factor:.1f}x[/cyan]")
        display.console.print()

        # Rollback info
        if result.rollback_available:
            display.console.print(
                f"  💾 Rollback available for [cyan]{result.rollback_retention_days}[/cyan] days"
            )
            display.console.print("  To rollback: [yellow]cw migrate rollback[/yellow]")
        else:
            display.console.print("  ⚠️  Rollback not available")

        display.console.print()

    except Exception as e:
        display.console.print()
        display.print_error(f"Migration failed: {e}")
        display.console.print()
        display.console.print("Suggestions:")
        display.console.print("  • Check logs for detailed error information")
        display.console.print("  • Resume migration: [yellow]cw migrate resume[/yellow]")
        display.console.print("  • Check system health: [yellow]cw doctor[/yellow]")
        display.console.print()
        raise


@app.command()
async def resume(migration_service: MigrationServiceDep = INJECTED) -> None:
    """Resume a failed migration from the last checkpoint.

    Resumes the most recent migration that was interrupted or failed.
    Uses saved checkpoint state to continue from where it left off.

    Args:
        migration_service: Injected migration service
    """
    display.print_command_header("Resume Migration")

    try:
        display.console.print()
        display.console.print("⏳ Resuming migration from last checkpoint...")
        display.console.print()

        # Note: This will require implementing a resume-specific method
        # For now, calling migrate with resume=True should work if checkpoint exists
        display.print_warning(
            "Resume feature requires migration ID - use migrate command with default resume behavior"
        )
        display.console.print()
        display.console.print(
            "The migration command automatically resumes from checkpoint by default."
        )
        display.console.print("Just run: [yellow]cw migrate <target-dimension>[/yellow]")
        display.console.print()

    except Exception as e:
        display.console.print()
        display.print_error(f"Resume failed: {e}")
        display.console.print()
        display.console.print("Suggestions:")
        display.console.print("  • Check if a checkpoint exists")
        display.console.print("  • Check logs for detailed error information")
        display.console.print("  • Start fresh: [yellow]cw migrate --no-resume[/yellow]")
        display.console.print()
        raise


@app.command()
async def rollback(migration_service: MigrationServiceDep = INJECTED) -> None:
    """Rollback the last migration.

    Reverts to the previous collection state before the last migration.
    Only available within the rollback retention period (default: 7 days).

    Args:
        migration_service: Injected migration service
    """
    display.print_command_header("Rollback Migration")

    try:
        display.console.print()
        display.console.print("⏳ Rolling back last migration...")
        display.console.print()

        # Note: This requires implementing rollback_migration method on MigrationService
        # Placeholder for now - actual implementation needed
        display.print_warning("Rollback feature not yet implemented in MigrationService")
        display.console.print()
        display.console.print("This will be implemented in the next phase of the migration system.")
        display.console.print()
        display.console.print("What rollback will do:")
        display.console.print("  • Restore previous collection configuration")
        display.console.print("  • Switch collection alias back to old collection")
        display.console.print("  • Preserve migration history for audit")
        display.console.print()

    except Exception as e:
        display.console.print()
        display.print_error(f"Rollback failed: {e}")
        display.console.print()
        display.console.print("Suggestions:")
        display.console.print("  • Check if rollback is still available")
        display.console.print("  • Check logs for detailed error information")
        display.console.print("  • Contact support if data recovery is critical")
        display.console.print()
        raise


def main() -> None:
    """Entry point for the migrate CLI command."""
    display_instance = StatusDisplay()
    error_handler = CLIErrorHandler(display_instance, verbose=True, debug=True)

    with handle_keyboard_interrupt_gracefully():
        try:
            app()
        except Exception as e:
            error_handler.handle_error(e, "Migration", exit_code=1)


if __name__ == "__main__":
    main()


__all__ = ()
