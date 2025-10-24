<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Flexible Extension System Specification

**Version**: 1.0
**Date**: 2025-01-28
**Authors**: Claude Code Design System

## Executive Summary

This specification defines a new configuration-driven rule engine for the CodeWeaver semantic classification extension system. The current hardcoded approach in `codeweaver.semantic.extensions` does not scale to handle 5900+ node types across 20+ languages. This design transforms the system from hardcoded Python methods to flexible, configurable rule definitions.

## Problem Statement

### Current System Limitations

The existing extension system suffers from several scalability issues:

1. **Code Explosion**: Each new language pattern requires new Python methods
   - `_compile_specialized_patterns()` would need 100+ pattern tuples
   - Language-specific getters like `_get_rust_lifetime_category()` multiply
   - `_check_language_refinement()` becomes unwieldy with 100+ refinement rules

2. **Maintenance Burden**: Adding support for new languages requires code changes
3. **Performance**: Hardcoded patterns cannot be optimized or cached effectively
4. **Discoverability**: Language-specific behavior is scattered across Python code

### Scale Requirements

- **5900 node types** (2900 unique) across 20+ programming languages
- **Extensible architecture** for adding new languages without code changes
- **High performance** classification with sub-millisecond response times
- **Maintainable configuration** that non-Python developers can contribute to

## Design Overview

### Core Architecture

The new system implements a **Configuration-Driven Rule Engine** with these key components:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Rule Engine   │───▶│  Rule Types     │───▶│  Configuration  │
│                 │    │                 │    │                 │
│ - Evaluation    │    │ - DirectMapping │    │ - YAML/JSON     │
│ - Caching       │    │ - Pattern       │    │ - Language Files│
│ - Optimization  │    │ - Refinement    │    │ - Validation    │
└─────────────────┘    │ - Contextual    │    └─────────────────┘
                       │ - Composite     │
                       └─────────────────┘
```

### Design Patterns Applied

1. **Strategy Pattern**: Different rule types implement common `ClassificationRule` interface
2. **Chain of Responsibility**: Rules evaluated in priority order until match found
3. **Factory Pattern**: Language-specific rule factories for modular loading
4. **Configuration Pattern**: Data-driven rule definitions replace hardcoded logic

## Detailed Design

### 1. Rule System Architecture

#### Core Interfaces

```python
from typing import Protocol, runtime_checkable
from pydantic.dataclasses import dataclass

from codeweaver._common import BaseEnum, DataclassSerializationMixin


@runtime_checkable
class ClassificationRule(Protocol):
    """Protocol for all classification rules."""

    def evaluate(self, context: RuleContext) -> RuleResult | None:
        """Evaluate rule against context, return result or None if no match."""
        ...

    def priority(self) -> int:
        """Return rule priority (lower number = higher priority)."""
        ...

    def applies_to(self, language: SemanticSearchLanguage, node_type: str) -> bool:
        """Check if rule is applicable to given language/node type."""
        ...

@dataclass(frozen=True)
class RuleContext(DataclassSerializationMixin):
    """Context information for rule evaluation."""
    node_type: str
    language: SemanticSearchLanguage
    parent_type: str | None = None
    sibling_types: list[str] | None = None
    file_path: str | None = None
    registry: CategoryRegistry | None = None

@dataclass(frozen=True)
class RuleResult(DataclassSerializationMixin):
    """Result of rule evaluation."""
    category: SemanticNodeCategory
    confidence: float
    source: str
    matched_pattern: str | None = None
    metadata: dict[str, Any] | None = None

class RuleType(str, BaseEnum):
    """Enumeration of supported rule types."""
    DIRECT_MAPPING = "direct_mapping"
    PATTERN = "pattern"
    REFINEMENT = "refinement"
    CONTEXTUAL = "contextual"
    COMPOSITE = "composite"
```

#### Rule Engine

```python
class ClassificationRuleEngine:
    """Main engine for rule-based classification."""

    def __init__(self, registry: CategoryRegistry):
        self.registry = registry
        self.rules: dict[SemanticSearchLanguage, list[ClassificationRule]] = {}
        self.cache: dict[tuple, RuleResult] = {}

    def add_rule(self, language: SemanticSearchLanguage, rule: ClassificationRule) -> None:
        """Add rule for specific language."""
        if language not in self.rules:
            self.rules[language] = []
        self.rules[language].append(rule)
        self._sort_rules_by_priority(language)

    def classify(self, context: RuleContext) -> RuleResult | None:
        """Classify node using configured rules."""
        cache_key = self._make_cache_key(context)
        if cache_key in self.cache:
            return self.cache[cache_key]

        result = self._evaluate_rules(context)
        if result:
            self.cache[cache_key] = result
        return result

    def _evaluate_rules(self, context: RuleContext) -> RuleResult | None:
        """Evaluate rules in priority order."""
        if context.language not in self.rules:
            return None

        for rule in self.rules[context.language]:
            if rule.applies_to(context.language, context.node_type):
                if result := rule.evaluate(context):
                    return result
        return None
```

### 2. Rule Types

#### DirectMappingRule

Replaces hardcoded registry mappings:

```python
@dataclass(frozen=True)
class DirectMappingRule(DataclassSerializationMixin):
    """Direct node_type -> category mapping."""
    language: SemanticSearchLanguage
    mappings: dict[str, SemanticNodeCategory]
    priority_value: int = 100

    def evaluate(self, context: RuleContext) -> RuleResult | None:
        if context.node_type in self.mappings:
            return RuleResult(
                category=self.mappings[context.node_type],
                confidence=0.95,
                source="direct_mapping",
                matched_pattern=f"direct:{context.node_type}"
            )
        return None

    def priority(self) -> int:
        return self.priority_value

    def applies_to(self, language: SemanticSearchLanguage, node_type: str) -> bool:
        return language == self.language and node_type in self.mappings
```

#### PatternRule

Replaces hardcoded specialized patterns:

```python
@dataclass(frozen=True)
class PatternRule(DataclassSerializationMixin):
    """Regex pattern-based classification."""
    language: SemanticSearchLanguage
    pattern: re.Pattern[str]
    category: SemanticNodeCategory
    base_confidence: float
    description: str
    priority_value: int = 200

    def evaluate(self, context: RuleContext) -> RuleResult | None:
        if match := self.pattern.search(context.node_type):
            confidence = self._calculate_confidence(match, context.node_type)
            return RuleResult(
                category=self.category,
                confidence=confidence,
                source="pattern",
                matched_pattern=f"{self.description}:{self.pattern.pattern}"
            )
        return None

    def _calculate_confidence(self, match: re.Match[str], node_type: str) -> float:
        """Calculate confidence based on match quality."""
        base = self.base_confidence
        # Exact match bonus
        if match.group(0) == node_type:
            base += 0.1
        # Case-sensitive match bonus
        if not (self.pattern.flags & re.IGNORECASE):
            base += 0.05
        return min(0.95, base)
```

#### RefinementRule

Replaces hardcoded language refinements:

```python
@dataclass(frozen=True)
class RefinementRule(DataclassSerializationMixin):
    """Refines base categories with language-specific knowledge."""
    language: SemanticSearchLanguage
    base_category: SemanticNodeCategory
    refined_category: SemanticNodeCategory
    conditions: dict[str, Any]
    confidence: float
    priority_value: int = 300

    def evaluate(self, context: RuleContext) -> RuleResult | None:
        # This would be called after base classification
        # Implementation depends on how we pass base results through
        pass
```

#### ContextualRule

Replaces hardcoded contextual logic:

```python
@dataclass(frozen=True)
class ContextualRule(DataclassSerializationMixin):
    """Context-aware classification using parent/sibling information."""
    language: SemanticSearchLanguage
    base_category: SemanticNodeCategory | None
    parent_patterns: list[str] | None
    sibling_patterns: list[str] | None
    file_path_patterns: list[str] | None
    target_category: SemanticNodeCategory
    confidence: float
    priority_value: int = 400

    def evaluate(self, context: RuleContext) -> RuleResult | None:
        if not self._context_matches(context):
            return None

        return RuleResult(
            category=self.target_category,
            confidence=self.confidence,
            source="contextual",
            matched_pattern=f"context:{self.target_category.name}"
        )

    def _context_matches(self, context: RuleContext) -> bool:
        """Check if context matches rule conditions."""
        # Check parent patterns
        if self.parent_patterns and context.parent_type:
            if not any(pattern in context.parent_type.lower()
                      for pattern in self.parent_patterns):
                return False

        # Check sibling patterns
        if self.sibling_patterns and context.sibling_types:
            sibling_text = " ".join(context.sibling_types).lower()
            if not any(pattern in sibling_text
                      for pattern in self.sibling_patterns):
                return False

        # Check file path patterns
        if self.file_path_patterns and context.file_path:
            if not any(pattern in context.file_path.lower()
                      for pattern in self.file_path_patterns):
                return False

        return True
```

### 3. Configuration Format

#### Language Extension Files

Each language has a configuration file (e.g., `extensions/rust.yaml`):

```yaml
# rust.yaml
language: rust
version: "1.0"

rules:
  # Direct mappings (highest priority)
  - type: direct_mapping
    priority: 100
    mappings:
      impl_item: "RUST_DEFINITION_TRAIT_IMPL"
      lifetime: "RUST_ANNOTATION_LIFETIME"
      generic_param: "RUST_DEFINITION_GENERIC"
      trait_item: "DEFINITION_TYPE"

  # Pattern-based rules
  - type: pattern
    priority: 200
    patterns:
      - pattern: "impl.*item"
        category: "RUST_DEFINITION_TRAIT_IMPL"
        confidence: 0.85
        description: "impl_item"
        flags: ["IGNORECASE"]

      - pattern: ".*lifetime.*"
        category: "RUST_ANNOTATION_LIFETIME"
        confidence: 0.80
        description: "lifetime"
        flags: ["IGNORECASE"]

      - pattern: "generic.*param"
        category: "RUST_DEFINITION_GENERIC"
        confidence: 0.75
        description: "generic_param"
        flags: ["IGNORECASE"]

  # Refinement rules
  - type: refinement
    priority: 300
    refinements:
      - base_category: "DEFINITION_TYPE"
        refined_category: "RUST_DEFINITION_TRAIT_IMPL"
        confidence: 0.75
        conditions:
          node_patterns: ["impl", "trait"]

  # Contextual rules
  - type: contextual
    priority: 400
    rules:
      - target_category: "RUST_DEFINITION_TRAIT_IMPL"
        confidence: 0.70
        conditions:
          file_path_patterns: [".rs"]
          parent_patterns: ["impl_block", "trait_impl"]

# Category definitions for this language
categories:
  RUST_DEFINITION_TRAIT_IMPL:
    description: "Rust trait implementations"
    tier: 1
    parent_category: "DEFINITION_TYPE"
    importance_scores:
      discovery: 0.90
      comprehension: 0.85
      modification: 0.88
      debugging: 0.70
      documentation: 0.85
    examples: ["impl blocks", "trait implementations"]

  RUST_ANNOTATION_LIFETIME:
    description: "Rust lifetime annotations"
    tier: 1
    parent_category: "ANNOTATION_METADATA"
    importance_scores:
      discovery: 0.85
      comprehension: 0.80
      modification: 0.90
      debugging: 0.75
      documentation: 0.80
    examples: ["lifetime parameters", "lifetime bounds"]
```

#### JSX/React Configuration Example

```yaml
# jsx.yaml
language: jsx
version: "1.0"

rules:
  - type: pattern
    priority: 200
    patterns:
      - pattern: "jsx.*element"
        category: "REACT_DEFINITION_COMPONENT"
        confidence: 0.90
        description: "jsx_element"
        flags: ["IGNORECASE"]

      - pattern: "use[A-Z][a-zA-Z]*"
        category: "REACT_OPERATION_HOOK"
        confidence: 0.85
        description: "react_hook"

      - pattern: ".*Component$"
        category: "REACT_DEFINITION_COMPONENT"
        confidence: 0.80
        description: "component_name"
        flags: ["IGNORECASE"]

  - type: contextual
    priority: 400
    rules:
      - target_category: "REACT_DEFINITION_COMPONENT"
        confidence: 0.85
        conditions:
          file_path_patterns: [".jsx", ".tsx", "component"]
          sibling_patterns: ["jsx", "react"]

      - target_category: "REACT_OPERATION_HOOK"
        confidence: 0.80
        conditions:
          parent_patterns: ["component", "function"]
          sibling_patterns: ["jsx", "return"]

categories:
  REACT_DEFINITION_COMPONENT:
    description: "React component definitions"
    tier: 1
    parent_category: "DEFINITION_CALLABLE"
    importance_scores:
      discovery: 0.95
      comprehension: 0.90
      modification: 0.85
      debugging: 0.75
      documentation: 0.90
    examples: ["function components", "class components"]

  REACT_OPERATION_HOOK:
    description: "React hook usage"
    tier: 4
    parent_category: "OPERATION_INVOCATION"
    importance_scores:
      discovery: 0.70
      comprehension: 0.80
      modification: 0.75
      debugging: 0.85
      documentation: 0.70
    examples: ["useState calls", "useEffect calls", "custom hooks"]
```

### 4. Configuration Loading System

```python
class ConfigurationLoader:
    """Loads and validates rule configurations."""

    def __init__(self, extension_dirs: list[Path]):
        self.extension_dirs = extension_dirs
        self.rule_factories = self._build_rule_factories()

    def load_language_extensions(self, language: SemanticSearchLanguage) -> list[ClassificationRule]:
        """Load all rules for a specific language."""
        rules = []

        for ext_dir in self.extension_dirs:
            config_file = ext_dir / f"{language.name.lower()}.yaml"
            if config_file.exists():
                config = self._load_config(config_file)
                rules.extend(self._create_rules_from_config(config, language))

        return rules

    def _create_rules_from_config(self, config: dict, language: SemanticSearchLanguage) -> list[ClassificationRule]:
        """Create rule objects from configuration."""
        rules = []

        for rule_config in config.get("rules", []):
            rule_type = RuleType(rule_config["type"])
            factory = self.rule_factories[rule_type]
            rule = factory.create(language, rule_config)
            rules.append(rule)

        return rules

class RuleFactory(Protocol):
    """Factory for creating rules from configuration."""

    def create(self, language: SemanticSearchLanguage, config: dict) -> ClassificationRule:
        """Create rule instance from configuration."""
        ...

class DirectMappingRuleFactory:
    """Factory for DirectMappingRule."""

    def create(self, language: SemanticSearchLanguage, config: dict) -> DirectMappingRule:
        mappings = {
            node_type: SemanticNodeCategory.from_string(category_name)
            for node_type, category_name in config["mappings"].items()
        }
        return DirectMappingRule(
            language=language,
            mappings=mappings,
            priority_value=config.get("priority", 100)
        )

class PatternRuleFactory:
    """Factory for PatternRule."""

    def create(self, language: SemanticSearchLanguage, config: dict) -> list[PatternRule]:
        rules = []
        for pattern_config in config["patterns"]:
            flags = 0
            for flag_name in pattern_config.get("flags", []):
                flags |= getattr(re, flag_name, 0)

            pattern = re.compile(pattern_config["pattern"], flags)
            category = SemanticNodeCategory.from_string(pattern_config["category"])

            rule = PatternRule(
                language=language,
                pattern=pattern,
                category=category,
                base_confidence=pattern_config["confidence"],
                description=pattern_config["description"],
                priority_value=config.get("priority", 200)
            )
            rules.append(rule)
        return rules
```

### 5. Migration Strategy

#### Phase 1: Infrastructure

1. **Create rule interfaces and base classes**
2. **Implement rule engine with caching**
3. **Build configuration loader with validation**
4. **Add backward compatibility layer**

#### Phase 2: Rule Migration

1. **Extract existing hardcoded patterns to configuration files**
2. **Convert specialized pattern methods to PatternRule configs**
3. **Transform refinement logic to RefinementRule configs**
4. **Replace contextual logic with ContextualRule configs**

#### Phase 3: Optimization

1. **Add rule indexing for fast lookup**
2. **Implement rule caching and memoization**
3. **Add hot-reloading for development**
4. **Performance tuning and benchmarking**

#### Backward Compatibility

**NONE!** This is an unreleased app, so the implementation needs to be clean with no duck tape. 

```python
class LegacyCompatibilityManager:
    """Provides compatibility with existing hardcoded extensions."""

    def __init__(self, rule_engine: ClassificationRuleEngine):
        self.rule_engine = rule_engine
        self.legacy_manager = LanguageExtensionManager()  # Current implementation

    def check_extensions_first(self, node_type: str, language: SemanticSearchLanguage) -> ClassificationResult | None:
        """Check new rule engine first, fallback to legacy."""
        context = RuleContext(node_type=node_type, language=language)

        # Try new rule engine
        if result := self.rule_engine.classify(context):
            return self._convert_to_classification_result(result)

        # Fallback to legacy system
        return self.legacy_manager.check_extensions_first(node_type, language)
```

## Performance Considerations

### Optimization Strategies

1. **Rule Indexing**: Build indices for fast rule lookup by language and node type
2. **Pattern Compilation**: Pre-compile regex patterns for optimal performance
3. **Result Caching**: Cache classification results with LRU eviction
4. **Lazy Loading**: Load language-specific rules only when needed
5. **Rule Prioritization**: Evaluate high-confidence rules first

### Performance Targets

- **Sub-millisecond classification**: Single node classification in <1ms
- **Batch processing**: 1000+ nodes classified per second
- **Memory efficiency**: <10MB memory overhead for rule engine
- **Startup time**: <100ms to load all language configurations

## Benefits and Trade-offs

### Benefits

1. **Scalability**: Configuration scales to thousands of rules without code changes
2. **Maintainability**: Centralized, declarative rule definitions
3. **Flexibility**: Easy to add new rule types and composition patterns
4. **Performance**: Rules can be optimized, cached, and indexed
5. **Contribution**: Non-Python developers can contribute language rules
6. **Testing**: Rules can be unit tested independently
7. **Discoverability**: All language behavior visible in configuration files

### Trade-offs

1. **Complexity**: More components than hardcoded approach
2. **Learning Curve**: Contributors need to understand configuration format
3. **Validation**: Configuration validation becomes important
4. **Debugging**: Rule conflicts may be harder to debug than code

### Migration Risk Mitigation

- **Backward compatibility layer** during transition
- **Gradual migration** of one language at a time
- **Comprehensive testing** of migrated configurations
- **Performance monitoring** to ensure no regressions

## Future Extensions

### Rule Type Extensions

1. **Machine Learning Rules**: Rules that use ML models for classification
2. **Statistical Rules**: Rules based on corpus analysis and frequency data
3. **Semantic Rules**: Rules that consider semantic similarity between node types
4. **Composite Rules**: Boolean combinations of multiple rule types

### Configuration Enhancements

1. **Rule Dependencies**: Rules that depend on other rule results
2. **Conditional Rules**: Rules with complex conditional logic
3. **Template Rules**: Parameterized rule templates for reuse
4. **Version Management**: Versioned rule configurations with migration support

### Integration Possibilities

1. **Language Server Integration**: Rules loaded from language server capabilities
2. **Community Contributions**: Shared repository of language rule configurations
3. **AI-Assisted Rule Generation**: Use AI to suggest rules based on corpus analysis
4. **Runtime Rule Modification**: Dynamic rule updates based on user feedback

## Implementation Plan

### Milestone 1: Core Infrastructure (2 weeks)
- [ ] Define rule interfaces and protocols
- [ ] Implement basic rule engine with priority evaluation
- [ ] Create configuration loader with YAML support
- [ ] Add comprehensive unit tests

### Milestone 2: Rule Types (2 weeks)
- [ ] Implement DirectMappingRule and factory
- [ ] Implement PatternRule and factory
- [ ] Implement RefinementRule and factory
- [ ] Implement ContextualRule and factory

### Milestone 3: Migration (2 weeks)
- [ ] Extract existing Rust patterns to configuration
- [ ] Extract existing JSX/React patterns to configuration
- [ ] Add backward compatibility layer
- [ ] Performance testing and optimization

### Milestone 4: Validation & Testing (1 week)
- [ ] Add configuration validation
- [ ] Comprehensive integration tests
- [ ] Performance benchmarking
- [ ] Documentation and examples

### Total Estimated Time: 7 weeks

## Conclusion

This configuration-driven rule engine transforms the CodeWeaver semantic extension system from a hardcoded, non-scalable approach to a flexible, maintainable, and performant solution. The design addresses the core problem of handling 5900+ node types across 20+ languages while providing a clear migration path and maintaining backward compatibility.

The rule-based approach provides the scalability needed for CodeWeaver's ambitious language support goals while making the system more accessible to contributors and easier to maintain and optimize.