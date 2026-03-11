# sourcery skip: no-complex-if-expressions
# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Configuration change analysis service.

This service analyzes configuration changes for compatibility and impact.
ARCHITECTURE: Plain class with no DI in constructor (factory handles DI).
"""

from __future__ import annotations

import logging

from copy import deepcopy
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, Any, Literal

from codeweaver.core.types import UNSET
from codeweaver.engine.managers.checkpoint_manager import ChangeImpact


if TYPE_CHECKING:
    from codeweaver.core.config.settings_type import CodeWeaverSettingsType as Settings
    from codeweaver.engine.managers.checkpoint_manager import CheckpointManager
    from codeweaver.engine.managers.manifest_manager import FileManifestManager
    from codeweaver.providers.config.categories import EmbeddingProviderSettingsType


logger = logging.getLogger(__name__)


@dataclass
class TransformationDetails:
    """Strongly typed transformation metadata (not dict!)."""

    type: Literal["quantization", "dimension_reduction"]
    old_value: str | int
    new_value: str | int
    complexity: Literal["low", "medium", "high"]
    time_estimate: timedelta
    requires_vector_update: bool
    accuracy_impact: str


@dataclass
class ConfigChangeAnalysis:
    """Results of configuration change analysis."""

    impact: ChangeImpact
    old_config_summary: dict[str, Any]  # Summary of old config
    new_config_summary: dict[str, Any]  # Summary of new config

    # Transformation details
    transformation_type: Literal["quantization", "dimension_reduction", "mixed"] | None
    transformations: list[TransformationDetails]

    # Impact estimates
    estimated_time: timedelta
    estimated_cost: float
    accuracy_impact: str

    # User guidance
    recommendations: list[str]
    migration_strategy: (
        Literal["full_reindex", "quantize_only", "dimension_reduction", "no_action"] | None
    )


class ConfigChangeAnalyzer:
    """Analyzes configuration changes for compatibility with policy enforcement.

    Integrates with the collection policy system to enforce configuration change
    restrictions before analyzing compatibility. Policy validation happens before
    technical compatibility checks.

    ARCHITECTURE NOTE: This is a PLAIN CLASS with no DI in constructor.
    Factory function in engine/dependencies.py handles DI integration.
    """

    def __init__(
        self,
        settings: Settings,  # NO DI markers
        checkpoint_manager: CheckpointManager,  # NO DI markers
        manifest_manager: FileManifestManager,  # NO DI markers
        vector_store: Any,  # NO DI markers - VectorStoreProvider protocol
    ) -> None:
        """Initialize with dependencies (plain parameters).

        Args:
            settings: Application settings
            checkpoint_manager: Checkpoint manager for validation
            manifest_manager: Manifest manager for collection metadata
            vector_store: Vector store provider for accessing collection metadata
        """
        self.settings = settings
        self.checkpoint_manager = checkpoint_manager
        self.manifest_manager = manifest_manager
        self.vector_store = vector_store

    async def analyze_current_config(self) -> ConfigChangeAnalysis | None:
        """Analyze current config against existing collection.

        Returns:
            Analysis result, or None if no collection exists yet.
        """
        # Get current collection metadata via checkpoint
        checkpoint = await self.checkpoint_manager.load()
        if not checkpoint:
            return None

        if self.settings.provider is UNSET:
            return None
        # Get current embedding configuration
        current_embedding = (
            self.settings.provider.embedding[0] if self.settings.provider.embedding else None
        )
        if not current_embedding:
            return None

        # Extract checkpoint fingerprint for comparison
        checkpoint_fingerprint = self.checkpoint_manager._extract_fingerprint(checkpoint)

        # Estimate vector count from manifest
        manifest = await self.manifest_manager.load()
        vector_count = manifest.total_chunks if manifest else checkpoint.chunks_indexed

        return await self.analyze_config_change(
            old_fingerprint=checkpoint_fingerprint,
            new_config=current_embedding,
            vector_count=vector_count,
        )

    async def analyze_config_change(
        self,
        old_fingerprint: Any,  # CheckpointSettingsFingerprint
        new_config: EmbeddingProviderSettingsType,
        vector_count: int,
    ) -> ConfigChangeAnalysis:
        """Comprehensive config change analysis with policy enforcement and impact classification.

        Validates configuration changes against collection policy before performing
        technical compatibility analysis. Policy enforcement happens first to ensure
        changes are allowed before analyzing their technical impact.

        Args:
            old_fingerprint: Existing checkpoint fingerprint
            new_config: New embedding configuration
            vector_count: Number of vectors in collection

        Returns:
            Detailed analysis with impact classification and recommendations

        Note:
            Policy validation occurs before compatibility checks. A STRICT policy
            may block changes that would otherwise be technically compatible.
        """
        # Create fingerprint from new config
        new_fingerprint = self.checkpoint_manager._create_fingerprint(new_config)

        # Create config summaries for reporting
        old_summary = self._create_config_summary(old_fingerprint)
        new_summary = self._create_config_summary_from_settings(new_config)

        # POLICY CHECK FIRST: Validate against collection policy before compatibility checks
        policy_result = await self._validate_policy_change(
            old_fingerprint, new_config, new_fingerprint, old_summary, new_summary, vector_count
        )
        if policy_result is not None:
            return policy_result

        # 1. Check compatibility using checkpoint manager logic
        is_compatible, impact = new_fingerprint.is_compatible_with(old_fingerprint)

        # 2. If breaking change, return early
        if not is_compatible or impact == ChangeImpact.BREAKING:
            return self._build_breaking_analysis(
                old_summary, new_summary, vector_count, reason="Requires full reindex"
            )

        # 3. If no changes, return early
        if impact == ChangeImpact.NONE:
            return ConfigChangeAnalysis(
                impact=ChangeImpact.NONE,
                old_config_summary=old_summary,
                new_config_summary=new_summary,
                transformation_type=None,
                transformations=[],
                estimated_time=timedelta(0),
                estimated_cost=0.0,
                accuracy_impact="No change",
                recommendations=[],
                migration_strategy="no_action",
            )

        # 4. Detect transformations
        changes = await self._detect_transformations(
            old_fingerprint, new_config, new_fingerprint, old_summary, new_summary, vector_count
        )

        # 5. Build response based on detected transformations
        return self._build_analysis_response(old_summary, new_summary, changes, vector_count)

    def _models_compatible(self, old_meta: Any, new_config: EmbeddingProviderSettingsType) -> bool:
        """Check if models are compatible using family-aware logic."""
        from codeweaver.providers.config.categories import AsymmetricEmbeddingProviderSettings

        # 1. Symmetric vs Asymmetric
        if isinstance(new_config, AsymmetricEmbeddingProviderSettings):
            # Asymmetric requires family tracking
            if not old_meta.dense_model_family:
                return False

            # Embed model must match exactly
            if str(new_config.embed_provider.model_name) != old_meta.dense_model:
                return False

            # Family must match
            embed_caps = new_config.embed_provider.embedding_config.capabilities
            family = (
                embed_caps.model_family.family_id
                if embed_caps and embed_caps.model_family
                else None
            )
            return family == old_meta.dense_model_family

        # 2. Symmetric
        # Must match model name exactly if no family tracking
        if not old_meta.dense_model_family:
            return str(new_config.model_name) == old_meta.dense_model

        # Family-aware symmetric
        embed_caps = new_config.embedding_config.capabilities
        family = (
            embed_caps.model_family.family_id if embed_caps and embed_caps.model_family else None
        )
        return family == old_meta.dense_model_family

    async def _validate_policy_change(
        self,
        old_fingerprint: Any,
        new_config: EmbeddingProviderSettingsType,
        new_fingerprint: Any,
        old_summary: dict[str, Any],
        new_summary: dict[str, Any],
        vector_count: int,
    ) -> ConfigChangeAnalysis | None:
        """Validate configuration change against collection policy.

        Returns:
            Analysis with BREAKING impact if blocked, None if allowed.
        """
        from codeweaver.core.exceptions import ConfigurationLockError

        try:
            # 1. Get collection metadata from vector store
            collection_metadata = await self.vector_store.collection_info()
            if not collection_metadata:
                return None

            # 2. Extract proposed models
            new_dense_model = new_summary.get("embed_model")
            new_query_model = new_summary.get("query_model")
            new_sparse_model = new_summary.get("sparse_model")
            new_provider = new_summary.get("vector_store")

            # 3. Validate against policy
            collection_metadata.validate_config_change(
                new_dense_model=new_dense_model,
                new_query_model=new_query_model,
                new_sparse_model=new_sparse_model,
                new_provider=new_provider,
            )

        except ConfigurationLockError as e:
            # Policy violation - block the change
            policy = collection_metadata.policy.value if collection_metadata else "strict"
            return ConfigChangeAnalysis(
                impact=ChangeImpact.BREAKING,
                old_config_summary=old_summary,
                new_config_summary=new_summary,
                transformation_type=None,
                transformations=[],
                estimated_time=self._estimate_reindex_time(vector_count),
                estimated_cost=self._estimate_reindex_cost(vector_count),
                accuracy_impact=f"Collection policy ({policy}) blocks this change",
                recommendations=self._build_policy_recommendations(policy, e),
                migration_strategy="full_reindex",
            )
        except Exception:
            # Graceful degradation if metadata cannot be retrieved
            logger.debug("Failed to perform policy check, skipping", exc_info=True)
            return None
        else:
            return None

    async def _detect_transformations(
        self,
        old_fingerprint: Any,
        new_config: EmbeddingProviderSettingsType,
        new_fingerprint: Any,
        old_summary: dict[str, Any],
        new_summary: dict[str, Any],
        vector_count: int,
    ) -> list[TransformationDetails]:
        """Detect and analyze available transformations (quantization, dimension reduction)."""
        changes = []

        # 1. Detect Quantization (datatype change)
        old_dtype = self._get_datatype_from_fingerprint(old_fingerprint) or "float32"
        new_dtype = self._get_datatype_from_config(new_config) or "float32"

        if old_dtype != new_dtype and self._is_valid_quantization(old_dtype, new_dtype):
            changes.append(
                TransformationDetails(
                    type="quantization",
                    old_value=old_dtype,
                    new_value=new_dtype,
                    complexity="low",
                    time_estimate=timedelta(seconds=max(5, vector_count / 10000)),
                    requires_vector_update=False,  # Datatype change only
                    accuracy_impact="Minimal (<0.1% expected)",
                )
            )

        # 2. Detect Dimension Reduction (Matryoshka)
        old_dim = self._get_dimension_from_fingerprint(old_fingerprint)
        new_dim = self._get_dimension_from_config(new_config)

        if old_dim and new_dim and new_dim < old_dim:
            # Estimate impact
            model_name = new_summary.get("embed_model", "unknown")
            impact_desc = self._estimate_matryoshka_impact(model_name, old_dim, new_dim)

            changes.append(
                TransformationDetails(
                    type="dimension_reduction",
                    old_value=old_dim,
                    new_value=new_dim,
                    complexity="medium",
                    time_estimate=self._estimate_migration_time(vector_count),
                    requires_vector_update=True,
                    accuracy_impact=impact_desc,
                )
            )

        return changes

    def _build_analysis_response(
        self,
        old_summary: dict[str, Any],
        new_summary: dict[str, Any],
        changes: list[TransformationDetails],
        vector_count: int,
    ) -> ConfigChangeAnalysis:
        """Build final analysis response based on detected transformations."""
        if not changes:
            # No transformations detected but compatible? Must be query model change
            return ConfigChangeAnalysis(
                impact=ChangeImpact.COMPATIBLE,
                old_config_summary=old_summary,
                new_config_summary=new_summary,
                transformation_type=None,
                transformations=[],
                estimated_time=timedelta(0),
                estimated_cost=0.0,
                accuracy_impact="No impact on indexed data",
                recommendations=["Ready to use new query model"],
                migration_strategy="no_action",
            )

        # Check for mixed transformations
        has_quant = any(c.type == "quantization" for c in changes)
        has_dim = any(c.type == "dimension_reduction" for c in changes)

        if has_dim:
            return self._build_transformable_analysis(
                old_summary, new_summary, changes, vector_count
            )
        if has_quant:
            return self._build_quantizable_analysis(old_summary, new_summary, changes)

        # Fallback (should not happen with proper detection)
        return self._build_breaking_analysis(
            old_summary, new_summary, vector_count, reason="Unknown change"
        )

    def _estimate_matryoshka_impact(self, model_name: str, old_dim: int, new_dim: int) -> str:
        """Estimate accuracy impact using empirical data.

        Uses Voyage-3 benchmark data for accurate predictions.
        """
        from codeweaver.providers.embedding.capabilities.resolver import EmbeddingCapabilityResolver

        resolver = EmbeddingCapabilityResolver()
        caps = resolver.resolve(model_name)

        reduction_pct = (old_dim - new_dim) / old_dim * 100

        # Use empirical data for Voyage models (EVIDENCE-BASED)
        if model_name.startswith("voyage-"):
            # Based on benchmark data
            impact_map = {
                (2048, 1024): 0.04,  # 75.16% → 75.20%
                (2048, 512): 0.47,  # 75.16% → 74.69%
                (2048, 256): 2.43,  # 75.16% → 72.73%
                (1024, 512): 0.51,  # 74.87% → 74.69% (int8)
            }
            if (old_dim, new_dim) in impact_map:
                return f"~{impact_map[(old_dim, new_dim)]:.1f}% (empirical)"

        # Generic Matryoshka estimate
        if caps and hasattr(caps, "supports_matryoshka") and caps.supports_matryoshka:
            impact = reduction_pct * 0.05  # ~5% loss per 100% reduction
            return f"~{impact:.1f}% (Matryoshka-optimized, estimated)"

        # Generic truncation estimate (conservative)
        impact = reduction_pct * 0.15  # ~15% loss per 100% reduction
        return f"~{impact:.1f}% (generic truncation, estimated)"

    async def validate_config_change(self, key: str, value: Any) -> ConfigChangeAnalysis | None:
        """Validate config change before applying (proactive validation).

        Called by `cw config set` command for early warning.

        Args:
            key: Configuration key being changed (e.g., "provider.embedding.dimension")
            value: New value for the key

        Returns:
            Analysis result if change affects index validity, None otherwise
        """
        # Only validate embedding-related changes
        if not key.startswith("provider.embedding"):
            return None

        # Simulate the change
        new_settings = self._simulate_config_change(key, value)

        # Check if collection exists (via checkpoint)
        checkpoint = await self.checkpoint_manager.load()
        if not checkpoint:
            # No existing index, change is safe
            return None

        # Get checkpoint fingerprint
        checkpoint_fingerprint = self.checkpoint_manager._extract_fingerprint(checkpoint)

        # Get new embedding config after simulation
        new_embedding_config = (
            new_settings.provider.embedding[0] if new_settings.provider.embedding else None
        )
        if not new_embedding_config:
            return None

        # Analyze impact
        manifest = await self.manifest_manager.load()
        vector_count = manifest.total_chunks if manifest else checkpoint.chunks_indexed

        return await self.analyze_config_change(
            old_fingerprint=checkpoint_fingerprint,
            new_config=new_embedding_config,
            vector_count=vector_count,
        )

    def _simulate_config_change(self, key: str, value: Any) -> Any:  # Settings
        """Simulate applying a config change to current settings.

        Args:
            key: Dotted configuration key (e.g., "provider.embedding.dimension")
            value: New value to apply

        Returns:
            Settings object with the simulated change applied
        """
        # Create deep copy of settings
        new_settings = deepcopy(self.settings)

        # Apply key=value to nested settings structure
        # Parse key like "provider.embedding.dimension" and set value
        parts = key.split(".")
        target = new_settings
        for part in parts[:-1]:
            # Handle list indexing (e.g. embedding.0)
            target = target[int(part)] if part.isdigit() else getattr(target, part)  # ty:ignore[not-subscriptable]

        last_part = parts[-1]
        if hasattr(target, last_part):
            setattr(target, last_part, value)
        elif isinstance(target, dict):
            target[last_part] = value
        elif isinstance(target, list) and last_part.isdigit():
            target[int(last_part)] = value

        return new_settings

    # Helper methods for building analysis results

    def _build_breaking_analysis(
        self,
        old_summary: dict[str, Any],
        new_summary: dict[str, Any],
        vector_count: int,
        reason: str,
    ) -> ConfigChangeAnalysis:
        """Build analysis result for breaking changes."""
        return ConfigChangeAnalysis(
            impact=ChangeImpact.BREAKING,
            old_config_summary=old_summary,
            new_config_summary=new_summary,
            transformation_type=None,
            transformations=[],
            estimated_time=self._estimate_reindex_time(vector_count),
            estimated_cost=self._estimate_reindex_cost(vector_count),
            accuracy_impact=reason,
            recommendations=[
                "Revert config: cw config revert",
                "Reindex: cw index --force",
                "Migrate to new collection: cw migrate",
            ],
            migration_strategy="full_reindex",
        )

    def _build_transformable_analysis(
        self,
        old_summary: dict[str, Any],
        new_summary: dict[str, Any],
        changes: list[TransformationDetails],
        vector_count: int,
    ) -> ConfigChangeAnalysis:
        """Build analysis result for transformable changes (dimension reduction)."""
        has_quantization = any(c.type == "quantization" for c in changes)
        transformation_type: Literal["quantization", "dimension_reduction", "mixed"] = (
            "mixed" if has_quantization else "dimension_reduction"
        )

        # Calculate total time and accuracy impact
        total_time = sum((c.time_estimate for c in changes), timedelta())
        accuracy_impacts = [c.accuracy_impact for c in changes]

        return ConfigChangeAnalysis(
            impact=ChangeImpact.TRANSFORMABLE,
            old_config_summary=old_summary,
            new_config_summary=new_summary,
            transformation_type=transformation_type,
            transformations=changes,
            estimated_time=total_time,
            estimated_cost=self._estimate_migration_cost(vector_count),
            accuracy_impact="; ".join(accuracy_impacts),
            recommendations=[
                "Run dimension reduction: cw migrate --dimension-reduction",
                "Preview impact: cw migrate --dry-run",
                "Monitor accuracy after migration",
            ],
            migration_strategy="dimension_reduction",
        )

    def _build_quantizable_analysis(
        self,
        old_summary: dict[str, Any],
        new_summary: dict[str, Any],
        changes: list[TransformationDetails],
    ) -> ConfigChangeAnalysis:
        """Build analysis result for quantizable changes (datatype only)."""
        total_time = sum((c.time_estimate for c in changes), timedelta())
        accuracy_impacts = [c.accuracy_impact for c in changes]

        return ConfigChangeAnalysis(
            impact=ChangeImpact.QUANTIZABLE,
            old_config_summary=old_summary,
            new_config_summary=new_summary,
            transformation_type="quantization",
            transformations=changes,
            estimated_time=total_time,
            estimated_cost=0.0,  # Quantization is free
            accuracy_impact="; ".join(accuracy_impacts),
            recommendations=[
                "Apply quantization: cw migrate --quantize-only",
                "No reindexing needed",
            ],
            migration_strategy="quantize_only",
        )

    def _create_config_summary(self, fingerprint: Any) -> dict[str, Any]:
        """Create human-readable summary from checkpoint fingerprint."""
        return {
            "config_type": fingerprint.embedding_config_type,
            "embed_model": fingerprint.embed_model,
            "embed_model_family": fingerprint.embed_model_family,
            "query_model": fingerprint.query_model,
            "sparse_model": fingerprint.sparse_model,
            "vector_store": fingerprint.vector_store,
        }

    def _create_config_summary_from_settings(
        self, config: EmbeddingProviderSettingsType
    ) -> dict[str, Any]:
        """Create human-readable summary from embedding config."""
        from codeweaver.providers.config.categories import AsymmetricEmbeddingProviderSettings

        if isinstance(config, AsymmetricEmbeddingProviderSettings):
            embed_caps = config.embed_provider.embedding_config.capabilities
            family = (
                embed_caps.model_family.family_id
                if embed_caps and embed_caps.model_family
                else None
            )

            return {
                "config_type": "asymmetric",
                "embed_model": str(config.embed_provider.model_name),
                "embed_model_family": family,
                "query_model": str(config.query_provider.model_name),
                "sparse_model": None,  # Get from settings if available
                "vector_store": "default",  # Get from settings if available
            }
        embed_caps = config.embedding_config.capabilities
        family = (
            embed_caps.model_family.family_id if embed_caps and embed_caps.model_family else None
        )

        return {
            "config_type": "symmetric",
            "embed_model": str(config.model_name),
            "embed_model_family": family,
            "query_model": None,
            "sparse_model": None,  # Get from settings if available
            "vector_store": "default",  # Get from settings if available
        }

    def _get_datatype_from_fingerprint(self, fingerprint: Any) -> str | None:
        """Extract datatype from checkpoint fingerprint."""
        return getattr(fingerprint, "datatype", None)

    def _get_datatype_from_config(self, config: EmbeddingProviderSettingsType) -> str | None:
        """Extract datatype from embedding config."""
        from codeweaver.providers.config.categories import AsymmetricEmbeddingProviderSettings

        if isinstance(config, AsymmetricEmbeddingProviderSettings):
            return config.datatype
        return getattr(config, "datatype", None)

    def _get_dimension_from_fingerprint(self, fingerprint: Any) -> int | None:
        """Extract dimension from checkpoint fingerprint."""
        return getattr(fingerprint, "dimension", None)

    def _get_dimension_from_config(self, config: EmbeddingProviderSettingsType) -> int | None:
        """Extract dimension from embedding config."""
        from codeweaver.providers.config.categories import AsymmetricEmbeddingProviderSettings

        if isinstance(config, AsymmetricEmbeddingProviderSettings):
            return (
                config.embed_provider.embedding_config.dimension
                if config.embed_provider.embedding_config
                else None
            )
        return config.embedding_config.dimension if config.embedding_config else None

    def _is_valid_quantization(self, old_dtype: str, new_dtype: str) -> bool:
        """Check if quantization is valid (can only reduce precision)."""
        # Valid quantization: float32 → float16 → uint8
        precision_order = ["float32", "float16", "uint8", "int8"]
        try:
            old_idx = precision_order.index(old_dtype)
            new_idx = precision_order.index(new_dtype)
        except ValueError:
            return False
        else:
            return new_idx >= old_idx  # Can only reduce precision

    def _estimate_reindex_time(self, vector_count: int) -> timedelta:
        """Estimate time for full reindexing."""
        # Rough estimate: 1000 vectors per second
        seconds = max(30, vector_count / 1000)
        return timedelta(seconds=seconds)

    def _estimate_reindex_cost(self, vector_count: int) -> float:
        """Estimate cost for full reindexing."""
        # Rough estimate: $0.0001 per vector
        return vector_count * 0.0001

    def _estimate_migration_time(self, vector_count: int) -> timedelta:
        """Estimate time for dimension reduction migration."""
        # Faster than full reindex: 5000 vectors per second
        seconds = max(10, vector_count / 5000)
        return timedelta(seconds=seconds)

    def _estimate_migration_cost(self, vector_count: int) -> float:
        """Estimate cost for dimension reduction migration."""
        # Much cheaper than reindex: $0.00001 per vector
        return vector_count * 0.00001

    def _build_policy_recommendations(
        self,
        policy: str,
        error: Any,  # ConfigurationLockError
    ) -> list[str]:
        """Build policy-specific recommendations based on policy level.

        Args:
            policy: Collection policy level (strict, family_aware, flexible, unlocked)
            error: ConfigurationLockError with details

        Returns:
            List of actionable recommendations
        """
        base_recommendations = [f"Collection policy is '{policy}' - change blocked", "", "Options:"]

        # Get error suggestions if available
        if hasattr(error, "suggestions") and error.suggestions:
            base_recommendations.extend(f"  • {s}" for s in error.suggestions)
        else:
            # Provide default recommendations based on policy
            match policy:
                case "strict":
                    base_recommendations.extend([
                        "  • Use original model configuration",
                        "  • Change policy: cw config set-policy --policy family-aware",
                        "  • Reindex with new config: cw index --force",
                    ])
                case "family_aware":
                    base_recommendations.extend([
                        "  • Use model from same family as indexed model",
                        "  • Change policy to flexible: cw config set-policy --policy flexible",
                        "  • Reindex with new config: cw index --force",
                    ])
                case "flexible":
                    base_recommendations.extend([
                        "  • WARNING: Change may degrade search quality",
                        "  • Consider reverting config or reindexing",
                        "  • Unlock policy: cw config set-policy --policy unlocked (not recommended)",
                    ])
                case _:
                    base_recommendations.extend([
                        "  • Revert config: cw config revert",
                        "  • Reindex: cw index --force",
                    ])

        return base_recommendations


__all__ = ("ConfigChangeAnalysis", "ConfigChangeAnalyzer", "TransformationDetails")
