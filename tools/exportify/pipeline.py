#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Pipeline orchestration for lazy import system.

Coordinates the full workflow:
1. File discovery - find Python files
2. AST parsing - extract exports
3. Graph building - propagate exports
4. Manifest generation - create export manifests
5. Code generation - write __init__.py files
"""

from __future__ import annotations

import hashlib
import logging
import time

from dataclasses import dataclass, field
from pathlib import Path

from tools.exportify.analysis.ast_parser import ASTParser
from tools.exportify.common.cache import JSONAnalysisCache
from tools.exportify.common.types import (
    ExportGenerationResult,
    GeneratedFile,
    GenerationMetrics,
    UpdatedFile,
)
from tools.exportify.discovery.file_discovery import FileDiscovery
from tools.exportify.export_manager.generator import CodeGenerator
from tools.exportify.export_manager.graph import PropagationGraph
from tools.exportify.export_manager.rules import RuleEngine


logger = logging.getLogger(__name__)


@dataclass
class PipelineStats:
    """Statistics from pipeline execution."""

    files_discovered: int = 0
    files_analyzed: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    exports_extracted: int = 0
    manifests_generated: int = 0
    files_written: int = 0
    errors: list[str] = field(default_factory=list)


class Pipeline:
    """Orchestrate the export generation pipeline."""

    def __init__(self, rule_engine: RuleEngine, cache: JSONAnalysisCache, output_dir: Path):
        """Initialize pipeline with required components.

        Args:
            rule_engine: Rule engine for export decisions
            cache: Analysis cache for performance
            output_dir: Root directory for output
        """
        self.rule_engine = rule_engine
        self.cache = cache
        self.output_dir = output_dir

        # Initialize components
        self.file_discovery = FileDiscovery()
        self.ast_parser = ASTParser()
        self.generator = CodeGenerator(output_dir)
        self.graph = PropagationGraph(rule_engine)

        # Statistics
        self.stats = PipelineStats()

    def run(
        self, source_root: Path, *, dry_run: bool = False, module: Path | None = None
    ) -> ExportGenerationResult:
        """Execute full pipeline.

        Args:
            source_root: Root directory to process
            dry_run: If True, don't write files
            module: If specified, only process this module

        Returns:
            ExportGenerationResult with complete results
        """
        start_time = time.time()

        # Update generator output directory to match source root
        self.generator.output_dir = source_root

        # Step 1: Discover files
        logger.info("Discovering Python files in %s", source_root)
        search_root = module or source_root
        python_files = self.file_discovery.discover_python_files(search_root)
        self.stats.files_discovered = len(python_files)
        logger.info("Found %d Python files", len(python_files))

        # Step 2: Analyze files and build graph
        logger.info("Analyzing files and building propagation graph")
        for file_path in python_files:
            self._process_file(file_path, source_root)

        # Step 3: Build manifests from graph
        logger.info("Building export manifests")
        try:
            manifests = self.graph.build_manifests()
            self.stats.manifests_generated = len(manifests)
        except ValueError as e:
            # Graph building failed (e.g., cycles detected)
            logger.exception("Manifest building failed")
            self.stats.errors.append(str(e))
            manifests = {}

        # Step 4: Generate code
        logger.info("Generating code for %d modules", len(manifests))
        generated_files = []
        updated_files = []
        skipped_files = []

        for manifest in manifests.values():
            try:
                code = self.generator.generate(manifest)

                # Determine if file exists
                target = self.generator._get_target_path(manifest.module_path)
                file_existed = target.exists()

                if not dry_run:
                    self.generator.write_file(manifest.module_path, code)
                    self.stats.files_written += 1

                # Record generation
                if file_existed:
                    updated_files.append(
                        UpdatedFile(
                            path=target,
                            old_content="",  # Would need to read for full diff
                            new_content=code.content,
                            changes=[f"Updated {len(manifest.all_exports)} exports"],
                        )
                    )
                else:
                    generated_files.append(
                        GeneratedFile(
                            path=target,
                            content=code.content,
                            exports=manifest.export_names,
                            source_modules=list({e.target_module for e in manifest.all_exports}),
                            timestamp=time.time(),
                            hash=code.hash,
                        )
                    )

            except Exception as e:
                logger.exception("Failed to generate %s", manifest.module_path)
                self.stats.errors.append(f"{manifest.module_path}: {e}")

        # Calculate metrics
        processing_time_ms = int((time.time() - start_time) * 1000)
        total_cache_attempts = self.stats.cache_hits + self.stats.cache_misses
        cache_hit_rate = (
            self.stats.cache_hits / total_cache_attempts if total_cache_attempts > 0 else 0.0
        )

        metrics = GenerationMetrics(
            files_analyzed=self.stats.files_analyzed,
            files_generated=len(generated_files),
            files_updated=len(updated_files),
            files_skipped=len(skipped_files),
            exports_created=self.stats.exports_extracted,
            processing_time_ms=processing_time_ms,
            cache_hit_rate=cache_hit_rate,
        )

        return ExportGenerationResult(
            generated_files=generated_files,
            updated_files=updated_files,
            skipped_files=skipped_files,
            metrics=metrics,
            success=len(self.stats.errors) == 0,
            errors=self.stats.errors,
        )

    def _process_file(self, file_path: Path, source_root: Path) -> None:
        """Process a single file (with caching).

        Args:
            file_path: Path to Python file
            source_root: Root directory for module path calculation
        """
        # Calculate module path from file path
        relative = file_path.relative_to(source_root)

        # Remove .py extension and convert to module path
        # e.g., src/codeweaver/core/types.py -> codeweaver.core.types
        parts = list(relative.parts)

        # If filename is __init__.py, use parent directory
        if relative.name == "__init__.py":
            parts = parts[:-1]  # Remove __init__.py
        else:
            # Remove .py and use as last part
            parts[-1] = relative.stem

        module_path = ".".join(parts) if parts else "root"

        # Calculate parent module
        parent_module = self._get_parent_module(module_path)

        # Check cache
        content = file_path.read_text()
        file_hash = hashlib.sha256(content.encode()).hexdigest()

        if cached := self.cache.get(file_path, file_hash):
            # Use cached analysis
            self.stats.cache_hits += 1
            analysis = cached
        else:
            # Parse file
            self.stats.cache_misses += 1
            self.stats.files_analyzed += 1

            analysis = self.ast_parser.parse_file(file_path, module_path)

            # Cache result
            self.cache.put(file_path, file_hash, analysis)

        # Add module to graph
        self.graph.add_module(module_path, parent_module)

        # Add exports to graph
        for symbol in analysis.symbols:
            # Evaluate rules for the symbol
            decision = self.rule_engine.evaluate(symbol, module_path)

            # Add decision to graph
            self.graph.add_export(decision)
            self.stats.exports_extracted += 1

    def _get_parent_module(self, module_path: str) -> str | None:
        """Get parent module path from a module path.

        Args:
            module_path: Full module path (e.g., "codeweaver.core.types")

        Returns:
            Parent module path (e.g., "codeweaver.core") or None if root
        """
        parts = module_path.split(".")
        return None if len(parts) <= 1 else ".".join(parts[:-1])


__all__ = ["Pipeline", "PipelineStats"]
