<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Node Parser API Adaptation Specification

**Version**: 1.0
**Date**: 2025-10-11
**Status**: Draft for Review

## Executive Summary

This specification details the required changes to adapt `grammar_classifier.py` and associated helper scripts to the completely rewritten `node_type_parser.py` API. The new API replaces tree-sitter's confusing terminology with intuitive concepts: **Category** (abstract types), **Thing** (concrete nodes), **Connection** (edges), and **Role** (semantic purpose).

---

## 1. Core Terminology Changes

### 1.1 Primary Mappings

| Old Term | New Term | Type | Notes |
|----------|----------|------|-------|
| `abstract_type` | `Category` | `Category` | Abstract groupings that don't appear in parse trees |
| `node_type` / `node` | `Thing` | `CompositeThing \| Token` | Concrete parse tree elements |
| `composite` | `CompositeThing` | `CompositeThing` | Non-leaf Things with children |
| `token` | `Token` | `Token` | Leaf Things with no children |
| `field` | `DirectConnection` | `DirectConnection` | Named semantic relationships with Roles |
| `children` | `PositionalConnection` | `PositionalConnection` | Ordered relationships without Roles |
| field name | `Role` | `Role` (NewType) | Semantic purpose of a DirectConnection |

### 1.2 Type Definitions

```python
# New types from node_type_parser.py
Role = NewType("Role", LiteralStringT)
CategoryName = NewType("CategoryName", LiteralStringT)
ThingName = NewType("ThingName", LiteralStringT)

type ThingType = CompositeThing | Token
type ThingOrCategoryType = CompositeThing | Token | Category
type ThingOrCategoryNameType = ThingName | CategoryName
```

---

## 2. API Changes: `node_type_parser.py`

### 2.1 New Core Classes

#### Category
```python
class Category(BasedModel):
    """Abstract classification grouping Things with shared characteristics."""
    name: CategoryName
    language: SemanticSearchLanguage
    member_thing_names: frozenset[ThingName]

    @cached_property
    def member_things(self) -> frozenset[CompositeThing | Token]:
        """Resolve member Things from registry."""
```

#### Thing (Base Class)
```python
class Thing(BasedModel):
    """Base for concrete parse tree elements (Token or CompositeThing)."""
    name: ThingName
    language: SemanticSearchLanguage
    category_names: frozenset[CategoryName]
    is_explicit_rule: bool  # was: named
    can_be_anywhere: bool | None  # was: extra
    _kind: ClassVar[Literal[ThingKind.TOKEN, ThingKind.COMPOSITE]]

    @cached_property
    def categories(self) -> frozenset[Category]:
        """Resolve Categories from registry."""
```

#### CompositeThing
```python
class CompositeThing(Thing):
    """Non-leaf Thing with structural children."""
    is_start: bool | None  # was: root

    @computed_field
    @property
    def direct_connections(self) -> frozenset[DirectConnection]:
        """Connections with semantic Roles (was: fields)."""

    @computed_field
    @property
    def positional_connections(self) -> tuple[PositionalConnection, ...]:
        """Ordered connections without Roles (was: children)."""
```

#### Token
```python
class Token(Thing):
    """Leaf Thing with no structural children."""
    significance: TokenSignificance  # NEW: classification by importance
```

#### Connections
```python
class Connection(BasedModel):
    """Base for edges between Things."""
    source_thing: ThingName
    target_thing_names: tuple[ThingOrCategoryNameType, ...]
    allows_multiple: bool  # was: multiple
    requires_presence: bool  # was: required
    language: SemanticSearchLanguage

    @computed_field
    @property
    def constraints(self) -> ConnectionConstraint:
        """Cardinality constraints as enum."""

class DirectConnection(Connection):
    """Named semantic relationship with a Role."""
    role: Role  # NEW: semantic purpose (field name)

class PositionalConnection(Connection):
    """Ordered structural relationship without Role."""
```

### 2.2 Global Registry Access

```python
def _get_registry() -> _ThingRegistry:
    """Get the singleton ThingRegistry instance."""

class _ThingRegistry:
    """Central registry for all Things and Categories."""

    def get_thing_by_name(
        self, name: ThingOrCategoryNameType,
        *, language: SemanticSearchLanguage | None = None
    ) -> ThingOrCategoryType | None:
        """Retrieve Thing or Category by name."""

    def get_category_by_name(
        self, name: CategoryName,
        *, language: SemanticSearchLanguage | None = None
    ) -> Category | None:
        """Retrieve Category by name."""

    def get_connections_by_source(
        self, source: ThingName,
        *, language: SemanticSearchLanguage | None = None,
        direct: bool = True
    ) -> Generator[DirectConnection] | Generator[PositionalConnection]:
        """Get connections originating from a source Thing."""
```

### 2.3 Primary Entry Point

```python
def get_things(
    *, languages: Sequence[SemanticSearchLanguage] | None = None
) -> list[ThingOrCategoryType]:
    """Get all Things and Categories, optionally filtered by language.

    Uses lazy parsing and caching via NodeTypeParser.
    """
```

---

## 3. Required Changes: `grammar_classifier.py`

### 3.1 Current State Analysis

**File**: `src/codeweaver/semantic/grammar_classifier.py`

**Issues**:
- Multiple sections commented out due to API incompatibility
- Methods reference old terminology (`abstract_type`, `field_inference`)
- Result dataclass uses outdated classification method names
- No integration with new `Category`, `Thing`, `Connection` classes

### 3.2 Class and Method Renames

#### GrammarClassificationResult
```python
# BEFORE
class GrammarClassificationResult(NamedTuple):
    classification_method: Literal["abstract_type", "field_inference", "children", "extra"]
    evidence: str

# AFTER
class GrammarClassificationResult(NamedTuple):
    classification_method: Literal["category", "connection_inference", "positional", "anywhere"]
    evidence: str
```

**Rationale**: Align method names with new terminology.

#### GrammarBasedClassifier Methods

##### 3.2.1 Remove Old Abstract Type Map Builder

**Remove**:
```python
def _build_abstract_category_map(self) -> dict[str, SemanticNodeCategory]:
    """OBSOLETE: Use Category objects directly."""
```

**Replace with**:
```python
def _build_category_to_semantic_map(self) -> dict[CategoryName, SemanticNodeCategory]:
    """Map grammar Categories to SemanticNodeCategory enum values."""
    return {
        CategoryName("expression"): SemanticNodeCategory.OPERATION_COMPUTATION,
        CategoryName("primary_expression"): SemanticNodeCategory.OPERATION_COMPUTATION,
        CategoryName("statement"): SemanticNodeCategory.FLOW_BRANCHING,
        CategoryName("type"): SemanticNodeCategory.DEFINITION_TYPE,
        # ... etc
    }
```

##### 3.2.2 Rename Classification Methods

| Old Method | New Method | Purpose |
|------------|------------|---------|
| `_classify_from_abstract_type()` | `_classify_from_category()` | Classify via Category membership |
| `_classify_from_fields()` | `_classify_from_direct_connections()` | Classify via DirectConnection Roles |
| `_classify_from_children()` | `_classify_from_positional_connections()` | Classify via PositionalConnection patterns |

##### 3.2.3 New Method: `_classify_from_category()`

```python
def _classify_from_category(
    self, thing: CompositeThing | Token
) -> GrammarClassificationResult | None:
    """Classify a Thing based on its Category membership.

    Args:
        thing: The Thing to classify

    Returns:
        Classification result with high confidence (>0.9), or None
    """
    if not thing.categories:
        return None

    # For multi-category Things, use primary category
    primary_category = thing.primary_category
    if not primary_category:
        # Multi-category with no clear primary
        return None

    semantic_category = self._category_map.get(primary_category.name)
    if not semantic_category:
        return None

    tier = SemanticTier.from_category(semantic_category)

    return GrammarClassificationResult(
        category=semantic_category,
        tier=tier,
        confidence=0.90,
        classification_method="category",
        evidence=f"Member of '{primary_category.name}' Category"
    )
```

##### 3.2.4 New Method: `_classify_from_direct_connections()`

```python
def _classify_from_direct_connections(
    self, thing: CompositeThing
) -> GrammarClassificationResult | None:
    """Classify based on DirectConnection Role patterns.

    Args:
        thing: CompositeThing to analyze

    Returns:
        Classification with high confidence (>0.85), or None
    """
    if not thing.direct_connections:
        return None

    # Extract Roles
    roles = frozenset(conn.role for conn in thing.direct_connections)

    # Pattern matching on Role combinations
    if {"body", "name"}.issubset(roles):
        category = SemanticNodeCategory.DEFINITION_CALLABLE
    elif {"condition", "consequence"}.issubset(roles):
        category = SemanticNodeCategory.FLOW_BRANCHING
    elif {"left", "right", "operator"}.issubset(roles):
        category = SemanticNodeCategory.OPERATION_COMPUTATION
    else:
        return None

    tier = SemanticTier.from_category(category)
    role_names = sorted(roles)

    return GrammarClassificationResult(
        category=category,
        tier=tier,
        confidence=0.85,
        classification_method="connection_inference",
        evidence=f"DirectConnection Roles: {role_names}"
    )
```

##### 3.2.5 New Method: `_classify_from_positional_connections()`

```python
def _classify_from_positional_connections(
    self, thing: CompositeThing
) -> GrammarClassificationResult | None:
    """Classify based on PositionalConnection patterns.

    Args:
        thing: CompositeThing to analyze

    Returns:
        Classification with moderate confidence (>0.65), or None
    """
    if not thing.positional_connections:
        return None

    # Heuristic: CompositeThings with both DirectConnections and
    # PositionalConnections are likely structural definitions
    if thing.direct_connections:
        return GrammarClassificationResult(
            category=SemanticNodeCategory.FLOW_BRANCHING,
            tier=SemanticTier.CONTROL_FLOW_LOGIC,
            confidence=0.70,
            classification_method="positional",
            evidence="Has both DirectConnections and PositionalConnections"
        )

    # Just positional, likely a container/expression
    return GrammarClassificationResult(
        category=SemanticNodeCategory.SYNTAX_IDENTIFIER,
        tier=SemanticTier.SYNTAX_REFERENCES,
        confidence=0.65,
        classification_method="positional",
        evidence="Has PositionalConnections only"
    )
```

##### 3.2.6 Update Main Classification Pipeline

```python
def classify_node(
    self, node_type: str, language: SemanticSearchLanguage | str
) -> GrammarClassificationResult | None:
    """Classify a node using grammar structure.

    Args:
        node_type: The Thing name (e.g., "function_definition")
        language: The programming language

    Returns:
        Classification result with confidence, or None
    """
    if not isinstance(language, SemanticSearchLanguage):
        language = SemanticSearchLanguage.from_string(language)

    # Get Thing from registry
    registry = _get_registry()
    thing = registry.get_thing_by_name(ThingName(node_type), language=language)

    if not thing or isinstance(thing, Category):
        return None  # Not a concrete Thing

    # Classification pipeline (highest to lowest confidence)

    # Method 1: Category membership (confidence: 0.90)
    if result := self._classify_from_category(thing):
        return result

    # Method 2: DirectConnection Role inference (confidence: 0.85)
    if isinstance(thing, CompositeThing):
        if result := self._classify_from_direct_connections(thing):
            return result

    # Method 3: PositionalConnection patterns (confidence: 0.65-0.70)
    if isinstance(thing, CompositeThing):
        if result := self._classify_from_positional_connections(thing):
            return result

    # Method 4: can_be_anywhere flag (confidence: 0.95)
    if thing.can_be_anywhere:
        return GrammarClassificationResult(
            category=SemanticNodeCategory.DOCUMENTATION_STRUCTURED,
            tier=SemanticTier.BEHAVIORAL_CONTRACTS,
            confidence=0.95,
            classification_method="anywhere",
            evidence="Thing marked as can_be_anywhere (was 'extra')"
        )

    return None  # Could not classify
```

### 3.3 Initialization Changes

```python
class GrammarBasedClassifier:
    def __init__(self, parser: NodeTypeParser | None = None) -> None:
        """Initialize grammar-based classifier.

        Args:
            parser: NodeTypeParser instance. If None, uses global registry.
        """
        self.parser = parser or NodeTypeParser()

        # Trigger parsing if not already done
        if not _get_registry().has_language(SemanticSearchLanguage.PYTHON):
            get_things()  # Populate registry

        # Build Category -> SemanticNodeCategory mapping
        self._category_map = self._build_category_to_semantic_map()
```

---

## 4. Required Changes: `scripts/analyze_grammar_structure.py`

### 4.1 Import Changes

**Before**:
```python
# No direct imports from node_type_parser
```

**After**:
```python
from codeweaver.semantic.node_type_parser import (
    Category,
    CompositeThing,
    Token,
    DirectConnection,
    PositionalConnection,
    get_things,
    _get_registry,
)
```

### 4.2 Method Renames

| Old Name | New Name | Notes |
|----------|----------|-------|
| `abstract_types` | `categories` | Dict of Category names to member Thing names |
| `abstract_type_count` | `category_count` | Count of Categories |
| `nodes_with_fields` | `things_with_direct_connections` | Count of CompositeThings with DirectConnections |
| `common_field_names` | `common_role_names` | Counter of Role names |
| `field_semantic_roles` | `role_semantic_patterns` | Role usage patterns |
| `nodes_with_children` | `things_with_positional_connections` | Count of CompositeThings with PositionalConnections |
| `nodes_with_both` | `things_with_both_connection_types` | Both Direct and Positional |

### 4.3 Updated Data Collection

#### Before (JSON-based)
```python
if "subtypes" in node_info:
    stats.abstract_type_count += 1
    subtypes = [st["type"] for st in node_info.get("subtypes", [])]
    stats.abstract_types[node_type] = subtypes
```

#### After (Registry-based)
```python
def _analyze_language(self, language: SemanticSearchLanguage) -> GrammarStructureStats:
    """Analyze grammar structure using registry."""
    stats = GrammarStructureStats(language=language)

    registry = _get_registry()

    # Get all Things for this language
    if not registry.has_language(language):
        get_things(languages=[language])  # Lazy load

    # Count Categories
    for category_name, category in registry.categories[language].items():
        stats.categories[category_name] = list(category.member_thing_names)
        stats.category_count += 1

    # Count Things with connections
    for thing_name, thing in registry.composite_things[language].items():
        if thing.direct_connections:
            stats.things_with_direct_connections += 1

            # Count Role names
            for connection in thing.direct_connections:
                stats.common_role_names[connection.role] += 1

        if thing.positional_connections:
            stats.things_with_positional_connections += 1

        if thing.direct_connections and thing.positional_connections:
            stats.things_with_both_connection_types += 1

    return stats
```

### 4.4 Connection Reference Analysis

**Update Q1 analysis** (Category vs Concrete references):

```python
def _classify_connection_references(self, stats: GrammarStructureStats) -> None:
    """Classify whether connections reference Categories or concrete Things."""
    registry = _get_registry()
    category_names = set(registry.categories[stats.language].keys())

    # Analyze DirectConnections
    for thing_name, connections in registry.direct_connections[stats.language].items():
        for connection in connections:
            for target_name in connection.target_thing_names:
                if target_name in category_names:
                    stats.category_references_in_direct[target_name] += 1
                else:
                    stats.concrete_references_in_direct[target_name] += 1

    # Analyze PositionalConnections
    for thing_name, connections in registry.positional_connections[stats.language].items():
        for connection in connections:
            for target_name in connection.target_thing_names:
                if target_name in category_names:
                    stats.category_references_in_positional[target_name] += 1
                else:
                    stats.concrete_references_in_positional[target_name] += 1
```

---

## 5. Required Changes: `scripts/build_language_mappings.py`

### 5.1 Import Changes

**Before**:
```python
from codeweaver.semantic.node_type_parser import (
    LanguageNodeType,  # REMOVED
    NodeTypeInfo,      # REMOVED
    NodeTypeParser
)
```

**After**:
```python
from codeweaver.semantic.node_type_parser import (
    NodeTypeParser,
    Category,
    CompositeThing,
    Token,
    ThingOrCategoryType,
    get_things,
    _get_registry,
)
from codeweaver.language import SemanticSearchLanguage
```

### 5.2 Type Definition Updates

**Before**:
```python
type ProjectNodeTypes = Sequence[dict[SemanticSearchLanguage, Sequence[LanguageNodeType]]]
```

**After**:
```python
type ProjectNodeTypes = dict[SemanticSearchLanguage, list[ThingOrCategoryType]]
```

### 5.3 Main Function Rewrite

**Before** (Complex JSON parsing):
```python
def parse_node_types(node_types_dir: Path) -> Mapping[...]:
    parser = NodeTypeParser(node_types_dir=node_types_dir)
    return parser.flatten()  # REMOVED METHOD
```

**After** (Simple registry access):
```python
def parse_node_types(node_types_dir: Path) -> ProjectNodeTypes:
    """Parse node types using the global registry."""
    parser = NodeTypeParser()  # Uses default node_types directory

    result: ProjectNodeTypes = {}
    for language in SemanticSearchLanguage:
        things = get_things(languages=[language])
        result[language] = things

    return result
```

### 5.4 Pattern Analysis Updates

**Before** (JSON-based pattern detection):
```python
def down_to_node_types(project_root: ProjectNodeTypes) -> dict[...]:
    # Complex JSON traversal
    for entry in project_root:
        for lang_name, nodes in entry.items():
            if "named" in nodes and isinstance(nodes, dict):
                # ... complex logic ...
```

**After** (Registry-based simple iteration):
```python
def extract_thing_names(project_node_types: ProjectNodeTypes) -> dict[SemanticSearchLanguage, set[str]]:
    """Extract all Thing names grouped by language."""
    return {
        lang: {thing.name for thing in things if not isinstance(thing, Category)}
        for lang, things in project_node_types.items()
    }
```

### 5.5 Classification Confidence Analysis

**Update to use new classifier API**:

```python
def analyze_confidence(
    mapper: NodeMapper,
    all_things: ProjectNodeTypes,
    top: int = 50
) -> tuple[list[ConfidenceRow], list[ConfidenceRow], list[ConfidenceRow]]:
    """Analyze classification confidence for Things."""
    high, medium, low = [], [], []

    # Flatten all Things across languages
    for language, things in all_things.items():
        for thing in things:
            if isinstance(thing, Category):
                continue  # Skip abstract Categories

            conf = mapper.get_classification_confidence(thing.name, language)
            cat = mapper.classify_node_type(thing.name, language)

            row = (thing.name, cat, conf, 1)  # (name, category, confidence, lang_count)

            if conf >= 0.8:
                high.append(row)
            elif conf >= 0.5:
                medium.append(row)
            else:
                low.append(row)

    return high, medium, low
```

---

## 6. Testing Strategy

### 6.1 Unit Tests Required

#### Test Category Resolution
```python
def test_category_membership():
    """Test Thing -> Category resolution."""
    things = get_things(languages=[SemanticSearchLanguage.PYTHON])

    # Find a Thing that should have Categories
    func_def = next(t for t in things if t.name == "function_definition")

    assert isinstance(func_def, CompositeThing)
    assert len(func_def.categories) > 0
    assert any(cat.name == "statement" for cat in func_def.categories)
```

#### Test Connection Resolution
```python
def test_direct_connections():
    """Test DirectConnection resolution for CompositeThings."""
    things = get_things(languages=[SemanticSearchLanguage.PYTHON])

    func_def = next(t for t in things if t.name == "function_definition" and isinstance(t, CompositeThing))

    assert len(func_def.direct_connections) > 0

    # Check for expected Roles
    roles = {conn.role for conn in func_def.direct_connections}
    assert "name" in roles
    assert "body" in roles
```

#### Test Classification Pipeline
```python
def test_classifier_with_new_api():
    """Test GrammarBasedClassifier with new API."""
    classifier = GrammarBasedClassifier()

    result = classifier.classify_node("function_definition", SemanticSearchLanguage.PYTHON)

    assert result is not None
    assert result.category == SemanticNodeCategory.DEFINITION_CALLABLE
    assert result.confidence >= 0.85
    assert result.classification_method in ["category", "connection_inference"]
```

### 6.2 Integration Tests

#### End-to-End Grammar Analysis
```python
def test_analyze_grammar_structure_script():
    """Test analyze_grammar_structure.py with new API."""
    analyzer = GrammarStructureAnalyzer()
    stats = analyzer.analyze_language(SemanticSearchLanguage.PYTHON)

    assert stats.category_count > 0
    assert stats.things_with_direct_connections > 0
    assert len(stats.common_role_names) > 0
```

#### Language Mapping Generation
```python
def test_build_language_mappings_script():
    """Test build_language_mappings.py with new API."""
    node_types = parse_node_types(locate_node_types())

    assert SemanticSearchLanguage.PYTHON in node_types
    assert len(node_types[SemanticSearchLanguage.PYTHON]) > 0

    # Verify both CompositeThings and Tokens present
    things = node_types[SemanticSearchLanguage.PYTHON]
    assert any(isinstance(t, CompositeThing) for t in things)
    assert any(isinstance(t, Token) for t in things)
```

---

## 7. Migration Checklist

### Phase 1: Core API Adaptation (High Priority)
- [ ] Update `grammar_classifier.py` imports
- [ ] Rename `GrammarClassificationResult.classification_method` literals
- [ ] Implement `_build_category_to_semantic_map()`
- [ ] Implement `_classify_from_category()`
- [ ] Implement `_classify_from_direct_connections()`
- [ ] Implement `_classify_from_positional_connections()`
- [ ] Update `classify_node()` pipeline
- [ ] Uncomment and fix commented-out code blocks
- [ ] Remove obsolete `_build_abstract_category_map()`

### Phase 2: Helper Scripts (Medium Priority)
- [ ] Update `analyze_grammar_structure.py` imports
- [ ] Rename statistics fields (abstract -> category, fields -> direct_connections, etc.)
- [ ] Rewrite `_analyze_node()` to use registry
- [ ] Update connection reference analysis (Q1)
- [ ] Update multi-category analysis (Q2)
- [ ] Fix report generation with new terminology

### Phase 3: Language Mappings (Medium Priority)
- [ ] Update `build_language_mappings.py` imports
- [ ] Simplify `parse_node_types()` to use registry
- [ ] Rewrite `down_to_node_types()` → `extract_thing_names()`
- [ ] Update confidence analysis to work with `ThingOrCategoryType`
- [ ] Fix pattern detection logic

### Phase 4: Testing & Validation (High Priority)
- [ ] Write unit tests for Category resolution
- [ ] Write unit tests for Connection resolution
- [ ] Write integration test for classifier
- [ ] Write integration test for analyze script
- [ ] Write integration test for mappings script
- [ ] Run full test suite
- [ ] Validate output correctness

### Phase 5: Documentation (Low Priority)
- [ ] Update docstrings with new terminology
- [ ] Add examples using new API
- [ ] Document migration notes for future reference

---

## 8. Risk Assessment

### High Risk Areas
1. **Registry Initialization**: Scripts must ensure `get_things()` is called before accessing registry
2. **Type Narrowing**: Distinguish between `Category`, `CompositeThing`, and `Token` correctly
3. **Lazy Loading**: Handle cases where languages haven't been parsed yet
4. **Multi-Category Things**: Handle Things with multiple Category memberships (13.5% of Things)

### Mitigation Strategies
1. Always check `_get_registry().has_language(lang)` before accessing registry contents
2. Use `isinstance()` checks and type guards consistently
3. Call `get_things(languages=[...])` explicitly when needed
4. Use `thing.primary_category` for single-category assumptions, handle `None` case

---

## 9. Performance Considerations

### Caching Strategy
- **Registry is singleton**: `_get_registry()` returns same instance
- **Lazy parsing**: Languages only parsed when first accessed via `get_things()`
- **Cached properties**: `categories`, `direct_connections`, `positional_connections` use `@cached_property`

### Optimization Opportunities
1. **Batch language loading**: Call `get_things()` once with all needed languages
2. **Avoid redundant lookups**: Cache `_get_registry()` result in local variable
3. **Use frozen types**: All core types are frozen/immutable for safety

---

## 10. Backward Compatibility Notes

### Breaking Changes
- **No direct JSON access**: Scripts must use registry instead of parsing JSON directly
- **Type changes**: `LanguageNodeType`, `NodeTypeInfo` removed; use `ThingOrCategoryType`
- **Method renames**: All "abstract_type" → "category", "field" → "direct_connection", etc.

### Migration Path
1. Update imports first
2. Replace JSON-based analysis with registry queries
3. Update terminology in variable names and documentation
4. Test incrementally (one file at a time)

---

## 11. Open Questions & Design Decisions

### Q1: Should we preserve old JSON-based analysis methods?
**Decision**: No. The new registry-based approach is cleaner and more reliable.

### Q2: How to handle multi-category Things in classification?
**Decision**: Use `thing.primary_category` when single category expected. If `None`, classify as low confidence.

### Q3: Should scripts populate registry automatically or require explicit calls?
**Decision**: Explicit calls to `get_things()` preferred for clarity. Add checks for unpopulated languages.

---

## Appendix A: Example Code Transformations

### A.1 Grammar Classifier: Before & After

**Before** (Commented Out):
```python
def classify_node(self, node_type: str, language: SemanticSearchLanguage | str):
    # semantic_info = self.parser.get_node_semantic_info(node_type, language)
    # if result := self._classify_from_abstract_type(semantic_info):
    #     return result
    pass
```

**After** (Fully Functional):
```python
def classify_node(self, node_type: str, language: SemanticSearchLanguage | str):
    if not isinstance(language, SemanticSearchLanguage):
        language = SemanticSearchLanguage.from_string(language)

    registry = _get_registry()
    thing = registry.get_thing_by_name(ThingName(node_type), language=language)

    if not thing or isinstance(thing, Category):
        return None

    if result := self._classify_from_category(thing):
        return result

    if isinstance(thing, CompositeThing):
        if result := self._classify_from_direct_connections(thing):
            return result

    return None
```

### A.2 Grammar Analysis: Before & After

**Before** (JSON traversal):
```python
if "fields" in node_info:
    stats.nodes_with_fields += 1
    fields = node_info["fields"]
    for field_name, field_info in fields.items():
        stats.common_field_names[field_name] += 1
```

**After** (Registry access):
```python
for thing_name, thing in registry.composite_things[language].items():
    if thing.direct_connections:
        stats.things_with_direct_connections += 1
        for connection in thing.direct_connections:
            stats.common_role_names[connection.role] += 1
```

---

## Appendix B: Full Type Hierarchy

```
ThingOrCategoryType
├── Category (abstract groupings)
└── Thing (concrete parse tree elements)
    ├── Token (leaf nodes)
    └── CompositeThing (non-leaf nodes)
        ├── direct_connections: frozenset[DirectConnection]
        └── positional_connections: tuple[PositionalConnection, ...]

Connection (edges between Things)
├── DirectConnection (with Role)
│   └── role: Role
└── PositionalConnection (ordered, no Role)
```

---

## Appendix C: Recommended Implementation Order

1. **Start with `grammar_classifier.py`**: Core classification logic
2. **Then `analyze_grammar_structure.py`**: Uses classifier, generates reports
3. **Finally `build_language_mappings.py`**: Uses analysis results

**Rationale**: Each step depends on the previous one working correctly. Test thoroughly at each stage.

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-10-11 | Adam Poulemanos | Initial specification |

