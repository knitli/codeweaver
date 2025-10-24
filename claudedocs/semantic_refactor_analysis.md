<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Semantic Package Refactoring Analysis

## Executive Summary

**Recommendation**: Implement a **Grammar-First Architecture** that leverages the inherent semantic structure in `node_types.json` while retaining the current pattern-based system as a fallback for unsupported languages.

**Key Insight**: The current system was built on heuristics before fully understanding that tree-sitter grammars encode explicit semantic relationships through:
- **Subtypes** → Abstract categories (polymorphic relationships)
- **Fields** → Named structural relationships
- **Children** → Positional constraints
- **Extra** → Unconstrained syntactic elements

## Current Architecture Assessment

### What Works Well ✅

1. **categories.py** - **STABLE, KEEP AS-IS**
   - Multi-dimensional importance scoring (`ImportanceScores`)
   - 5-tier hierarchical system (`SemanticTier`)
   - ~30 semantic node categories (`SemanticNodeCategory`)
   - Agent task profiles for context-aware scoring
   - This is solid domain modeling and shouldn't change

2. **node_type_parser.py** - **PARTIALLY UPDATED**
   - Already parsing grammar structure correctly
   - Good TypedDict definitions for different node field types
   - Recent improvements to support grammar-first approach
   - Foundation is strong

3. **Extension System** (extensions.py, mapper.py)
   - Language-specific pattern handling
   - Contextual refinement capabilities
   - Should remain as language-specific override layer

### What Needs Refactoring ⚠️

1. **classifier.py** - **HEAVY REFACTOR**
   - **Current Role**: Does all the guesswork and heavy lifting
   - **Problem**: Built on heuristics when grammar provides explicit semantics
   - **Complexity**: 320 lines, multiple classification phases, confidence scoring
   - **Recommendation**: Reduce to thin orchestration layer that:
     - Routes to grammar-based classifier first
     - Falls back to pattern-based classifier for new languages
     - Applies language extensions as refinements

2. **hierarchical.py** - **MODERATE REFACTOR**
   - **Current Role**: 4-phase pipeline (syntactic → tier → pattern → fallback)
   - **Problem**: Pattern matching when grammar tells us the answer
   - **Recommendation**: Repurpose as fallback classifier, add grammar-based fast path

3. **patterns.py, syntactic.py** - **KEEP AS FALLBACK**
   - Useful for languages without parsed grammars
   - Good for dynamic language loading in future
   - Move to secondary role behind grammar-based classification

## Grammar-Based Semantic Structure

### What node_types.json Actually Tells Us

```python
# Example from Python grammar
{
  "type": "expression",        # Abstract category name
  "named": true,
  "subtypes": [                # Concrete implementations
    {"type": "binary_expression", "named": true},
    {"type": "unary_expression", "named": true},
    {"type": "call", "named": true},
    {"type": "list", "named": true}
    # ... etc
  ]
}

# Example with fields (structural relationships)
{
  "type": "function_definition",
  "named": true,
  "fields": {
    "name": {                  # Named relationship
      "required": true,
      "types": [{"type": "identifier", "named": true}]
    },
    "parameters": {
      "required": true,
      "types": [{"type": "parameters", "named": true}]
    },
    "body": {
      "required": true,
      "types": [{"type": "block", "named": true}]
    }
  }
}
```

### Semantic Meaning We Can Extract

1. **Subtypes = Abstract Categories**
   - `_expression`, `_statement`, `_declaration`, `_type` → These are polymorphic groups
   - Maps directly to your 10ish abstract type categories
   - No guessing needed - grammar explicitly defines the hierarchy

2. **Fields = Structural Relationships**
   - Named relationships between parent and children
   - Grammar author's hints about semantic meaning
   - Can infer importance: `body` > `name` > `parameters` for functions

3. **Children vs Fields**
   - Fields: Named, semantic relationships
   - Children: Positional, structural constraints
   - Helps distinguish definitions (have fields) from expressions (have children)

4. **Extra = Syntactic Noise**
   - Comments, whitespace, decorators
   - Can appear anywhere without structural constraints
   - Usually SYNTAX_REFERENCES tier or filtered out

## Proposed Refactoring Strategy

### Phase 1: Create Grammar-Based Classifier (New Module)

**File**: `src/codeweaver/semantic/grammar_classifier.py`

```python
class GrammarBasedClassifier:
    """Classify nodes using inherent grammar structure from node_types.json"""

    def __init__(self, node_type_parser: NodeTypeParser):
        self.parser = node_type_parser
        # Pre-compute abstract type mappings from all 26 grammars
        self.abstract_categories = self._build_abstract_category_map()
        self.field_importance = self._analyze_field_semantics()

    def classify_node(
        self,
        node_type: str,
        language: SemanticSearchLanguage
    ) -> ClassificationResult | None:
        """Primary classification using grammar structure"""

        # 1. Check if it's a subtype (belongs to abstract category)
        if abstract_cat := self._classify_from_supertypes(node_type, language):
            return abstract_cat

        # 2. Analyze fields to infer semantic role
        if field_result := self._classify_from_fields(node_type, language):
            return field_result

        # 3. Check children constraints
        if children_result := self._classify_from_children(node_type, language):
            return children_result

        # 4. Handle extra nodes (syntactic elements)
        if self._is_extra_node(node_type, language):
            return ClassificationResult(
                category=SemanticNodeCategory.SYNTAX_REFERENCES,
                tier=SemanticTier.SYNTAX_REFERENCES,
                confidence=0.95,
                phase="grammar_extra"
            )

        return None  # No grammar-based classification possible
```

### Phase 2: Simplify classifier.py

**Before** (320 lines, complex orchestration):
```python
class SemanticNodeClassifier:
    def classify_node(...) -> EnhancedClassificationResult:
        # Extension check
        # Hierarchical classification (4 phases)
        # Confidence scoring
        # Alternative generation
        # Quality analysis
```

**After** (150 lines, simple routing):
```python
class SemanticNodeClassifier:
    def __init__(self):
        self.grammar_classifier = GrammarBasedClassifier(...)  # NEW
        self.pattern_fallback = PatternBasedClassifier(...)    # OLD hierarchical
        self.extensions = LanguageExtensionManager(...)

    def classify_node(...) -> EnhancedClassificationResult:
        # Phase 1: Try language extensions (highest specificity)
        if ext_result := self.extensions.classify_first(...):
            return self._enhance(ext_result)

        # Phase 2: Grammar-based classification (NEW - primary path)
        if grammar_result := self.grammar_classifier.classify_node(...):
            # Refine with extensions if available
            refined = self.extensions.refine_classification(grammar_result, ...)
            return self._enhance(refined)

        # Phase 3: Pattern-based fallback (OLD - for unknown languages)
        fallback_result = self.pattern_fallback.classify_node(...)
        return self._enhance(fallback_result)
```

### Phase 3: Repurpose hierarchical.py

**Rename to**: `pattern_classifier.py` (or keep name but clarify purpose)

**Role**: Fallback classifier for languages without grammar analysis

```python
class PatternBasedClassifier:  # Renamed from HierarchicalMapper
    """Pattern-based classification for languages without grammar support"""

    # Keep existing 4-phase pipeline
    # Mark as fallback/heuristic-based approach
    # Use when grammar_classifier returns None
```

### Phase 4: Enhance node_type_parser.py

**Add methods to extract semantic structure**:

```python
class NodeTypeParser:
    # Existing methods...

    @cached_property
    def abstract_type_map(self) -> dict[str, list[str]]:
        """Map abstract types to their concrete subtypes across all languages"""
        # Build from all grammars' subtype definitions
        # Groups: expression, statement, declaration, type, pattern, etc.

    @cached_property
    def field_semantic_roles(self) -> dict[str, dict[str, str]]:
        """Infer semantic roles from field names across languages"""
        # Common fields: name, body, parameters, type, value, etc.
        # Map to semantic categories

    def get_node_semantic_info(
        self,
        node_type: str,
        language: SemanticSearchLanguage
    ) -> NodeSemanticInfo:
        """Get all semantic information from grammar for a node"""
        return NodeSemanticInfo(
            is_abstract=self._has_subtypes(node_type, language),
            abstract_category=self._get_supertype(node_type, language),
            fields=self._get_fields(node_type, language),
            children_constraints=self._get_children(node_type, language),
            is_extra=self._is_extra(node_type, language),
        )
```

## Migration Path

### Step 1: Non-Breaking Addition
1. Create `grammar_classifier.py` (new file)
2. Add semantic extraction methods to `node_type_parser.py`
3. Build abstract category mappings from 26 grammars
4. No changes to existing code yet

### Step 2: Routing Layer Update
1. Update `classifier.py` to route grammar → pattern
2. Keep existing pattern-based code as fallback
3. Measure classification accuracy improvement
4. Compare confidence scores

### Step 3: Cleanup (If successful)
1. Rename `hierarchical.py` → `pattern_classifier.py`
2. Mark pattern-based system as fallback in docs
3. Reduce complexity in orchestration
4. Remove duplicate logic

### Step 4: Future Enhancement
1. Add dynamic grammar loading support
2. Use pattern-based system for new languages
3. Migrate to grammar-based once grammars available

## Impact Assessment

### Benefits ✅
1. **Accuracy**: Grammar truth > pattern guessing
2. **Maintainability**: Less heuristic code to maintain
3. **Performance**: Faster lookups (pre-computed maps vs pattern matching)
4. **Extensibility**: Easy to add new languages with grammars
5. **Confidence**: Higher confidence scores from grammar-based classification

### Risks ⚠️
1. **Grammar Coverage**: What if grammar doesn't define subtypes for all nodes?
   - **Mitigation**: Fall back to pattern-based system
2. **Grammar Variations**: Different grammars may structure things differently
   - **Mitigation**: Build mappings empirically from 26 existing grammars
3. **Implementation Effort**: New module + parser enhancements
   - **Mitigation**: Incremental approach, keep existing code as safety net

### Preserved Value 💎
- **categories.py**: No changes needed - perfect as-is
- **Pattern system**: Remains valuable as fallback
- **Extensions**: Language-specific overrides still work
- **No API changes**: Internal refactor only

## Success Metrics

1. **Classification Accuracy**: Grammar-based > 90% for nodes with grammar info
2. **Coverage**: Grammar-based handles >80% of common nodes in 26 languages
3. **Performance**: <10ms per classification (vs current pattern matching)
4. **Confidence**: Average confidence >0.85 (vs current ~0.70)
5. **Fallback Rate**: <20% of classifications require pattern fallback

## Recommendation Summary

**DO**:
- ✅ Create grammar-based classifier as primary path
- ✅ Keep categories.py unchanged (it's excellent)
- ✅ Retain pattern system as fallback (valuable for future)
- ✅ Simplify classifier.py orchestration
- ✅ Enhance node_type_parser.py with semantic extraction

**DON'T**:
- ❌ Throw away pattern-based work (useful for new languages)
- ❌ Change categories.py (stable, well-designed)
- ❌ Rush removal of existing code (keep as safety net)
- ❌ Over-engineer the grammar classifier (start simple)

**TIMELINE**:
- Week 1: Build grammar_classifier.py + semantic extraction
- Week 2: Integrate into classifier.py routing
- Week 3: Test, measure, refine
- Week 4: Cleanup and documentation

This approach gives you the best of both worlds: grammar-based accuracy where available, pattern-based flexibility for future expansion.
