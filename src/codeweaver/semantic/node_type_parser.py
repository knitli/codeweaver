# sourcery skip: avoid-builtin-shadow, lambdas-should-be-short, no-complex-if-expressions
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Parser for tree-sitter node-types.json files with intuitive terminology.

This module provides functionality to parse tree-sitter `node-types.json` files and extract
grammar information using clear, intuitive terminology instead of tree-sitter's confusing vocabulary.

## Background

tl;dr: **This is the parser we wish we had when we started working with tree-sitter. We hope it
makes your experience with tree-sitter grammars smoother and more intuitive.**

When developing CodeWeaver and our rust-based future backend, Thread, we spent a lot of time
with tree-sitter and its quirks. While tree-sitter is a powerful tool, its vocabulary and structure,
combined with the lack of comprehensive documentation, can make it challenging to work with.
Simply put: it's not intuitive.

This is on full display in the `node-types.json` file, which describes the different node types
in a grammar. The `node-types.json` file is crucial for understanding how to interact with parse trees, but its
structure and terminology are confusing. It *conflates* several distinct concepts (meaning it treats them as if they are the same):
- It doesn't clearly differentiate between **nodes** (vertices) and **edges** (relationships)
- It uses "named" to describe both nodes and edges, meaning "has a grammar rule", not "has a name"
  (everything has a name!)
- It flattens hierarchies and structural patterns in ways that obscure their meaning

When I originally wrote the last version of this parser, my misunderstandings of these concepts led to a week of lost time and incorrect assumptions. After that, I decided to write this parser using terminology
and structure that more intuitively describes the concepts at play -- completely departing from
tree-sitter's terminology.

Knitli is fundamentally about making complex systems more intuitive and accessible, and this is
a perfect example of that philosophy in action. By using clearer terminology and structure, we're
making it easier for developers to understand and work with tree-sitter grammars. This saves time,
reduces frustration, and empowers developers to build better tools.

**For tree-sitter experts:** We provide a translation guide below to help bridge the gap between
the two terminologies. If you find this frustrating, we understand -- but we believe clarity for
newcomers is more important than tradition.

## CodeWeaver's Terminology

We clarify and separate concepts that tree-sitter conflates: nodes vs edges, abstract vs concrete,
structural roles vs semantic meaning. Here's our approach:

### Abstract Groupings

**Category** - Abstract classification that groups Things with shared characteristics.
- Categories do NOT appear in parse trees (abstract only)
- Used for polymorphic type constraints and classification (identifying what something can be used as)
- Example: `expression` is a Category containing `binary_expression`, `unary_expression`, etc.
- **Tree-sitter equivalent**: Nodes with `subtypes` field (abstract types)
- **Empirical finding**: ~110 unique Categories across 25 languages, but much smaller number when normalized (across languages) ~ 16 categories with members across many languages

**Multi-Category Membership:**
- Things can belong to multiple Categories (uncommon but important)
- **13.5%** of Things belong to 2+ Categories
- **86.5%** belong to exactly 1 Category
- Common in C/C++ (declarators serving multiple roles)
- Example: `identifier` → `[_declarator, expression]`

### Concrete Parse Tree Nodes

**Thing** - A concrete element that appears in the parse tree.
- Two kinds: **Token** (leaf) or **Composite** (non-leaf)
- What you actually see when you parse code
- **Tree-sitter equivalent**: Named or unnamed "nodes" (named does not correlate to our Composite vs Token distinction)
- Name chosen for clarity: "it's a thing in your code" (considered: Entity, Element, Construct)

**Token** - Leaf Thing with no structural children.
- Represents keywords, identifiers, literals, punctuation
- What you literally **see** in the source code
- Classified by purpose: keyword, identifier, literal, punctuation, comment
- **Tree-sitter equivalent**: Node with no `fields` or `children`

**Composite Node** - Non-leaf Thing with structural children.
- Has Direct and/or Positional connections to child Things
- Represents complex structures: functions, classes, expressions
- **Tree-sitter equivalent**: Node with `fields` and/or `children`

### Structural Relationships

**Connection** - Directed relationship from parent Thing to child Thing(s).
- Graph terminology: an "edge"
- Three classes: Direct, Positional, Loose
- **Tree-sitter equivalent**: `fields` (Direct), `children` (Positional), `extras` (Loose)

**ConnectionClass** - Classification of connection types:

1. **DIRECT** - Named semantic relationship with a **Role**
   - Has a specific semantic function (e.g., "condition", "body", "parameters")
   - Most precise type of structural relationship
   - **Tree-sitter equivalent**: Grammar "fields"
   - **Empirical finding**: 9,606 Direct connections across all languages

2. **POSITIONAL** - Ordered structural relationship without semantic naming
   - Position matters but no explicit role name
   - Example: function arguments in some languages
   - **Tree-sitter equivalent**: Grammar "children"
   - If a thing has fields, it can also have children, but not vice versa (all things with children have fields)
   - All children are named (is_explicit_rule = True)
   - **Empirical finding**: 6,029 Positional connections across all languages


*Note: Direct and Positional Connections describe **structure**, while Loose Connections
describe **permission**.*

**Role** - Named semantic function of a Direct connection.
- Only Direct connections have Roles (Positional and Loose do not)
- Describes **what purpose** a child serves, not just that it exists
- Examples: "condition", "body", "parameters", "left", "right", "operator"
- **Tree-sitter equivalent**: Field name in grammar
- **Empirical finding**: ~90 unique role names across all languages

### Connection Target References

**Polymorphic Type Constraints:**
Connections can reference either Categories (abstract) OR concrete Things, enabling flexible
type constraints:

**Category References** (polymorphic constraints):
- Connection accepts ANY member of a Category
- Example: `condition` field → `expression` (accepts any expression type)
- **Empirical finding**:
  - **7.9%** of field references are to Categories
  - **10.3%** of children references are to Categories
- Common pattern: `argument_list.children → expression` (any expression type accepted)

**Concrete Thing References** (specific constraints):
- Connection accepts only specific Thing types
- Example: `operator` field → `["+", "-", "*", "/"]` (specific operators only)
- **Empirical finding**:
  - **92.1%** of field references are to concrete Things
  - **89.7%** of children references are to concrete Things
- Common pattern: Structural components like `parameter_list`, `block`, specific tokens

**Mixed References** (both in same connection):
- Single connection can reference both Categories AND concrete Things
- Example: `body` field → `[block, expression]` (either concrete type)
- Design principle: Store references as-is, provide resolution utilities when needed

### Attributes

**Thing Attributes:**

- **can_be_anywhere** (bool)
    - Whether the Thing can appear anywhere in the parse tree (usually comments)
    - **Tree-sitter equivalent**: the `extra` attribute
    Data notes:
   - Only used in a plurality of languages (11 of 25)
   - *almost always* a **comment**. Two exceptions:
        - Python: `line_continuation` token (1/2, other is `comment`)
        - PHP: `text_interpolation` (1/2, other is `comment`)
   - **Empirical finding**: 1 or 2 things with 'can_be_anywhere' attribute per language ('comment' is one for all 11, others with 2 are other types of comment like 'html_comment' for javascript (for jsx))

- **is_explicit_rule** (bool)
  - Whether the Thing has a dedicated named production rule in the grammar
  - True: Named grammar rule (represented in grammar with semantic name)
  - False: Anonymous grammar construct or synthesized node
  - **Tree-sitter equivalent**: `named = True/False` (i.e. 'named nodes')
  - **Note**: Included for completeness; limited practical utility for semantic analysis
    in practice, most significant nodes are named, and most unnamed nodes are trivial (punctuation, formatting), but it's not a perfect correlation. Other tools and libraries tend to treat unnamed nodes
    as synonymous with "insignificant", but we don't make that assumption here.

- **kind** (ThingKind enum)
  - Classification of Thing type: TOKEN or COMPOSITE
  - TOKEN: Leaf Thing with no structural children
  - COMPOSITE: Non-leaf Thing with structural children

- **is_file** (bool, Composite only)
  - Whether this Composite is the root of the parse tree (i.e., the start symbol)

- **is_significant** (bool, Token only)
  - Whether the Token carries semantic/structural meaning vs formatting trivia
  - True: keywords, identifiers, literals, operators, comments
  - False: whitespace, line continuations, formatting tokens
  - Practically similar to `is_explicit_rule` but focuses on semantic importance
  - Used for filtering during semantic analysis vs preserving for formatting

**Connection Attributes:**

- **allows_multiple** (bool)
  - Whether the Connection permits multiple children of specified type(s)
  - Defines cardinality upper bound (0 or 1 vs 0 or many)
  - **Tree-sitter equivalent**: `multiple = True/False`
  - **Note**: Specifies CAN have multiple, not MUST have multiple

- **requires_presence** (bool)
  - Whether at least one child of specified type(s) MUST be present
  - Defines cardinality lower bound (0 or more vs 1 or more)
  - **Tree-sitter equivalent**: `required = True/False`
  - **Note**: Doesn't require a specific Connection, just ≥1 from the allowed list

**Cardinality Matrix:**

| requires_presence | allows_multiple | Meaning |
|------------------|-----------------|---------|
| False | False | 0 or 1 (optional single) |
| False | True | 0 or more (optional multiple) |
| True | False | exactly 1 (required single) |
| True | True | 1 or more (required multiple) |

## Tree-sitter Translation Guide

For developers familiar with tree-sitter terminology:

| Tree-sitter Term | CodeWeaver Term | Notes |
|-----------------|-----------------|-------|
| Abstract type (with subtypes) | Category | Doesn't appear in parse trees |
| Named/unnamed node | Thing | Concrete parse tree node |
| Node with no fields | Token | Leaf node |
| Node with fields/children | Composite Thing | Non-leaf node |
| Field | Direct Connection | Has semantic Role |
| Child | Positional Connection | Ordered, no Role |
| Field name | Role | Semantic function |
| Extra | `can_be_anywhere`  | Can be anywhere in the AST |
| `named` attribute | `is_explicit_rule` | Has named grammar rule |
| `multiple` attribute | `allows_multiple` | Upper cardinality bound |
| `required` attribute | `requires_presence` | Lower cardinality bound |
| 'root' attribute | `is_file` | The starting node of the parse tree |

## Design Rationale

**Why these names?**
- **Thing**: Simple, clear, unpretentious. "It's a thing in your code."
- **Category**: Universally understood as abstract grouping
- **Connection**: Graph theory standard; clearer than conflating fields/children/extras
- **Role**: Describes purpose, not just presence
- **ConnectionClass**: Explicit enumeration of relationship types

**Empirical validation:**
- Analysis of 25 languages, 5,000+ node types
- ~110 unique Categories, ~736 unique Things with category membership
- 7.9-10.3% of references are polymorphic (Category references)
- 13.5% of Things have multi-category membership
- Patterns consistent across language families

**Benefits:**
- **Clearer mental model**: Separate nodes, edges, and attributes explicitly
- **Easier to learn**: Intuitive names reduce cognitive load
- **Better tooling**: Explicit types enable better type checking and validation
- **Future-proof**: Accommodates real-world patterns (multi-category, polymorphic references)
"""

from __future__ import annotations

import logging
import pickle

from collections.abc import Callable, Sequence
from importlib.resources import files
from itertools import groupby
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, ClassVar, TypedDict, cast, overload

from pydantic import DirectoryPath, Field, FilePath
from pydantic_core import from_json

from codeweaver.core.language import SemanticSearchLanguage
from codeweaver.core.types.aliases import CategoryNameT, ThingName
from codeweaver.core.types.models import RootedRoot
from codeweaver.semantic.types import NodeTypeDTO


if TYPE_CHECKING:
    from codeweaver.semantic.grammar import (
        Category,
        CompositeThing,
        DirectConnection,
        PositionalConnections,
        ThingOrCategoryType,
        ThingType,
        Token,
    )


logger = logging.getLogger()


# ===========================================================================
# *  Translating Node Types Files to CodeWeaver
#
# *  CodeWeaver's internal types are in `codeweaver.semantic.grammar_things`
#  That module also has a detailed explanation of the terminology and design.
#
# - The downside of adopting your own vocabulary and structure is that you
#   have to translate between your internal representation and the external
#   format.
# - Once the JSON for each language is loaded, we need to translate it into
#   our internal representation.
#
# * node-types.json Structure:
# - An array of 'node type' objects with:
#   - Always: `type` (str), `named` (bool)
#   - Sometimes: `root` (bool), `fields` (object), `children` (object),
#     `subtypes` (array), `extra` (bool)
#
# *   Field Details:
#   - subtypes: array of objects with `type` (str) and `named` (bool)
#   - children: a 'child type' object with `multiple` (bool), `required`
#     (bool), and `types` (array of objects with `type` and `named`)
#   - fields: object mapping field names (strings) to child type objects
#     (same structure as children)
#   - extra: boolean indicating this node can appear anywhere in the tree
#
#! Mapping to CodeWeaver:
#
# * Node Classification:
#  - Categories: node types that HAVE `subtypes` (abstract groupings like
#    "expression"); the nodes listed in the subtypes array become the
#    Category's member_things
#  - Tokens: nodes with NO fields AND NO children (leaf nodes)
#  - Composites: nodes with fields OR children (non-leaf nodes)
#  - Note: Categories, Tokens, and Composites can ALL have `extra: true`
#
# * Connection Types:
#  - Direct connections: derived from `fields` (semantic relationships with
#    named Roles)
#  - Positional connections: derived from `children` (ordered relationships,
#    no semantic Role)
#  - Note: The `extra` flag doesn't create connections; it marks Things that
#    can appear as children anywhere in the tree
#
# * Field Mappings:
#  - Role: the key name in the `fields` object (e.g., "condition", "body")
#  - is_explicit_rule: maps from `named`
#  - allows_multiple: maps from `multiple` (in child type objects)
#  - requires_presence: maps from `required` (in child type objects)
#  - target_things: the `types` array in fields/children
#  - source_thing: the `type` of the containing node
#  - is_file: maps from `root`
#  - can_appear_anywhere: maps from `extra` (marks Things that can appear
#    as children of any node)
#
# * Translation Algorithm:
#  - We use a lazy registry pattern to manage Things and Categories, so they can hold references to each other while being constructed and immutable.
#  - First pass: parse the JSON into intermediate DTO structures (NamedTuples and BasedModels)
#    that mirror the JSON structure but are easier to work with in Python.
#  - Second pass: convert the DTOs into our internal Thing and Category classes,
#    using the registry to resolve references by name.
#  - For composite things, we create DirectConnections and PositionalConnections using the same registry and generator system we use for thing and category membership.
#
# * Approach: DTO classes for JSON structure, then conversion functions to keep pydantic validation
# cleanly separated from parsing logic. We'll use NamedTuple for DTOs to keep them lightweight, but allow for methods if needed (unlike TypedDict).
# ===========================================================================


def _get_types_files_in_directory(directory: DirectoryPath | None = None) -> list[Path]:
    """Get list of node types files in a directory.

    Args:
        directory: Directory to search for node types files. If None, uses package resources.

    Returns:
        List of node types file paths
    """
    if directory is None:
        # Use importlib.resources to access package data
        data_dir = files("codeweaver.data") / "node_types"
        if not data_dir.is_dir():
            return []
        return [
            Path(str(data_dir / item.name))
            for item in data_dir.iterdir()
            if item.name.endswith("node-types.json")
        ]

    return [
        path
        for path in directory.iterdir()
        if path.is_file() and path.name.endswith("node-types.json")
    ]


class NodeArray(RootedRoot[list[NodeTypeDTO]]):
    """Root object for node types file containing array of node type objects.

    Attributes:
        nodes: List of node type objects
    """

    root: Annotated[
        list[NodeTypeDTO], Field(description="List of node type objects from the node types file.")
    ]

    @classmethod
    def from_json_data(cls, data: dict[SemanticSearchLanguage, list[dict[str, Any]]]) -> NodeArray:
        """Create NodeArray from JSON data."""
        if len(data) != 1:
            raise ValueError("NodeArray JSON data must contain exactly one language entry.")
        language, nodes_data = next(iter(data.items()))
        nodes = [NodeTypeDTO.model_validate({**node, "language": language}) for node in nodes_data]
        return cls.model_validate(nodes)

    @property
    def language(self) -> SemanticSearchLanguage:
        """Get the language of the NodeArray."""
        if not self.root:
            raise ValueError("NodeArray is empty, cannot determine language.")
        return self.root[0].language

    def _telemetry_keys(self) -> None:
        """Telemetry keys for NodeArray."""
        return


class NodeTypeFileLoader:
    """Container for node types files in a directory structure.

    Attributes:
        directory: Directory containing node types files (None to use package resources)
        files: List of node types file paths
    """

    directory: Annotated[
        DirectoryPath | None,
        Field(description="""Directory containing node types files. None to use package resources."""),
    ] = None

    files: Annotated[
        list[Path],
        Field(
            description="""List of node types file paths.""",
            default_factory=list,
            init=False,
        ),
    ]

    _data: ClassVar[dict[SemanticSearchLanguage, list[dict[str, Any]]]] = {}

    _nodes: ClassVar[list[NodeArray]] = []

    def __init__(
        self, directory: DirectoryPath | None = None, files: list[Path] | None = None
    ) -> None:
        """Initialize NodeTypesFiles, auto-populating files if not provided."""
        # Optionally override directory
        self.directory = directory
        # Initialize files list deterministically
        if files is not None:
            self.files = files
        else:
            self.files = _get_types_files_in_directory(self.directory)
        # We keep actual file loading lazy to avoid unnecessary I/O during initialization

    def _load_data(self) -> dict[SemanticSearchLanguage, list[dict[str, Any]]]:
        """Load data (list of node types file paths)."""
        return {
            SemanticSearchLanguage.from_string(file.stem.replace("-node-types", "")): from_json(
                file.read_bytes()
            )
            for file in self.files
        }

    def _load_file(self, language: SemanticSearchLanguage) -> list[dict[str, Any]] | None:
        """Load a single node types file for a specific language."""
        if language == SemanticSearchLanguage.JSX:
            language = SemanticSearchLanguage.JAVASCRIPT

        # If using package resources, load directly
        if self.directory is None:
            data_dir = files("codeweaver.data") / "node_types"
            filename = f"{language.value}-node-types.json"
            resource = data_dir / filename
            return from_json(resource.read_bytes()) if resource.is_file() else None
        # Otherwise use file path
        file_path = next(
            (
                file
                for file in self.files
                if SemanticSearchLanguage.from_string(file.stem.replace("-node-types", ""))
                == language
            ),
            None,
        )
        if file_path and file_path.exists():
            return from_json(file_path.read_bytes())
        return None

    def get_all_types(self) -> dict[SemanticSearchLanguage, list[dict[str, Any]]]:
        """Get all types from a node types files.

        Returns:
            List of dictionaries containing raw data from node types files. This is in the tree-sitter node-types.json format.
        """
        if not type(self)._data:
            type(self)._data = self._load_data()
        return type(self)._data

    def get_node(self, language: SemanticSearchLanguage) -> NodeArray | None:
        """Get the NodeArray for a specific language.

        Args:
            language: The language to get the NodeArray for.

        Returns:
            The NodeArray for the specified language, or None if not found.
        """
        if data := self._load_file(language):
            self._data[language] = data
            return NodeArray.from_json_data({language: data})
        return None

    def get_all_nodes(self) -> list[NodeArray]:
        """Get all nodes from the node types files.

        Returns:
            List of dictionaries containing the language and list of NodeTypeDTOs for that language.
        """
        data = type(self)._data or self.get_all_types()
        if not type(self)._data:
            type(self)._data = data
        node_arrays = [
            NodeArray.from_json_data({language: lang_nodes})
            for language, lang_nodes in data.items()
        ]
        if not type(self)._nodes:
            type(self)._nodes = node_arrays
        return type(self)._nodes


class _ThingCacheDict(TypedDict):
    """TypedDict used to cache created Things before registration."""

    categories: list[Category]
    tokens: list[Token]
    composites: list[CompositeThing]
    connections: list[DirectConnection | PositionalConnections]


class NodeTypeParser:
    """Parses and translates node types files into CodeWeaver's internal representation."""

    _initialized: Callable[..., bool] = lambda: False

    _registration_cache: ClassVar[dict[SemanticSearchLanguage, _ThingCacheDict]] = {
        lang: _ThingCacheDict(categories=[], tokens=[], composites=[], connections=[]).copy()
        for lang in SemanticSearchLanguage
    }

    _cache_loaded: ClassVar[bool] = False

    def __init__(
        self, languages: Sequence[SemanticSearchLanguage] | None = None, use_cache: bool = True
    ) -> None:
        """Initialize NodeTypeParser with an optional NodeTypeFileLoader.

        Args:
            languages: Optional pre-loaded list of languages to parse; if None, will load all available languages.
            use_cache: Whether to try loading from the pre-built cache. Default True.
        """
        self._languages: frozenset[SemanticSearchLanguage] = frozenset(
            languages or iter(SemanticSearchLanguage)
        )

        self._loader = NodeTypeFileLoader()
        self._use_cache = use_cache

        # Try to load from cache if enabled
        if use_cache and not type(self)._cache_loaded:
            self._load_from_cache()

        self._initialized = lambda: self.cache_complete()

    # we don't start the process until explicitly called

    @property
    def registration_cache(self) -> dict[SemanticSearchLanguage, _ThingCacheDict]:
        """Get the registration cache for serialization.

        This provides public access to the internal registration cache,
        primarily for build scripts that need to serialize the cache.

        Returns:
            Dictionary mapping languages to their cached Things and Categories.
        """
        return type(self)._registration_cache

    def _load_from_cache(self) -> bool:
        """Try to load pre-processed node types from cache.

        Returns:
            True if cache was loaded successfully, False otherwise.
        """
        try:
            # Try to load cache from package resources
            cache_resource = files("codeweaver.data") / "node_types_cache.pkl"
            if not cache_resource.is_file():
                logger.debug("Node types cache not found, will parse from JSON files")
                return False

            cache_data = pickle.loads(cache_resource.read_bytes())
            type(self)._registration_cache = cache_data["registration_cache"]
            type(self)._cache_loaded = True
            logger.debug("Loaded node types from cache")
            return True

        except Exception as e:
            logger.warning("Failed to load node types cache, will parse from JSON: %s", e)
            return False

    @property
    def nodes(self) -> list[NodeArray]:
        """Get the list of NodeArray to parse."""
        if len(self._languages) == len(SemanticSearchLanguage):
            return self._loader.get_all_nodes()
        return cast(
            list[NodeArray],
            [
                self._loader.get_node(lang)
                for lang in self._languages
                if self._loader.get_node(lang)
            ],
        )

    def _flattened_nodes_for_language(
        self, language: SemanticSearchLanguage
    ) -> list[ThingOrCategoryType]:
        """Get a flattened list of all Things and Categories for a specific language."""
        return [
            *self._registration_cache[language]["categories"],
            *self._registration_cache[language]["tokens"],
            *self._registration_cache[language]["composites"],
        ]

    def parse_all_nodes(self) -> list[ThingOrCategoryType]:
        """Parse and translate all node types files into internal representation."""
        assembled_things: list[ThingOrCategoryType] = []
        for node_array in self.nodes:
            assembled_things.extend(self._parse_node_array(node_array) or [])
        self._register_everything()
        return assembled_things

    def parse_for_language(self, language: SemanticSearchLanguage) -> list[ThingOrCategoryType]:
        """Parse and translate node types files for a specific language into internal representation.

        Args:
            language: The language to parse node types for.

        Returns:
            List of parsed and translated node types for the specified language.
        """
        if language not in self._languages:
            self._languages = frozenset([language]) | self._languages
        if not type(self)._registration_cache[language]["tokens"] and (
            array := self._loader.get_node(language)
        ):
            _ = self._parse_node_array(array)
        self._register_everything()
        return self._flattened_nodes_for_language(language)

    def parse_languages(
        self, languages: Sequence[SemanticSearchLanguage] | None = None
    ) -> list[ThingOrCategoryType]:
        """Parse and translate node types files for a specific set of languages into internal representation.

        Args:
            languages: The languages to parse node types for. If None, will use internal self._languages or all languages if self._languages is empty.

        Returns:
            List of parsed and translated node types for the specified languages.
        """
        self._languages = frozenset(languages or iter(SemanticSearchLanguage)) | self._languages
        for language in languages or self._languages:
            # no tokens, no grammar
            if len(self._registration_cache[language]["tokens"]) == 0 and (
                array := self._loader.get_node(language)
            ):
                _ = self._parse_node_array(array)
        self._register_everything()
        return [
            thing
            for lang in (languages or self._languages)
            for thing in self._flattened_nodes_for_language(lang)
        ]

    def cache_complete(self) -> bool:
        """Check if the internal cache is fully populated for all specified languages."""
        return all(
            len(type(self)._registration_cache[lang]["tokens"]) > 0
            and len(type(self)._registration_cache[lang]["composites"]) > 0
            for lang in self._languages
        )

    def _register_everything(self) -> None:
        """Register all Things and Categories in the internal mapping."""
        if not type(self)._registration_cache:
            _ = self.parse_all_nodes()
        from codeweaver.semantic.registry import get_registry

        registry = get_registry()
        for language in self._languages:
            for thing in self._flattened_nodes_for_language(language):
                registry.register_thing(thing)
            for connection in type(self)._registration_cache[language]["connections"]:
                registry.register_connection(connection)

    def _create_category(self, node_dto: NodeTypeDTO) -> Category:
        """Create a Category from a NodeTypeDTO and add it to the internal mapping.

        Args:
            node_dto: NodeTypeDTO representing the category to create.
        """
        from codeweaver.semantic.grammar import Category

        return Category.from_node_dto(node_dto)

    def _create_token(self, node_dto: NodeTypeDTO) -> Token:
        """Create a Token from a NodeTypeDTO and add it to the internal mapping.

        Args:
            node_dto: NodeTypeDTO representing the token to create.
        """
        from codeweaver.semantic.grammar import Token

        return self._build_thing(node_dto, Token)

    def _get_node_categories(self, node_dto: NodeTypeDTO) -> frozenset[CategoryNameT]:
        """Get the set of Categories a node belongs to based on its name and language.

        Args:
            node_dto: NodeTypeDTO representing the node to check.

        Returns:
            Set of Categories the node belongs to.
        """
        categories = type(self)._registration_cache.get(node_dto.language, {}).get("categories", [])
        return frozenset(
            category.name for category in categories if category.includes(ThingName(node_dto.node))
        )

    def _create_composite(self, node_dto: NodeTypeDTO) -> CompositeThing:
        """Create a CompositeThing from a NodeTypeDTO and add it to the internal mapping.

        Also creates and registers any DirectConnections and PositionalConnections. Note that these connections *behave* like they belong to the CompositeThing, but they are registered globally in the registry.

        Args:
            node_dto: NodeTypeDTO representing the composite to create.
        """
        from codeweaver.semantic.grammar import (
            CompositeThing,
            DirectConnection,
            PositionalConnections,
        )

        composite_thing = self._build_thing(node_dto, CompositeThing)
        connections: list[DirectConnection | PositionalConnections] = []
        if node_dto.fields:
            connections.extend(DirectConnection.from_node_dto(node_dto=node_dto))
        if node_dto.children:
            connections.append(
                cast(PositionalConnections, PositionalConnections.from_node_dto(node_dto=node_dto))
            )
        type(self)._registration_cache[node_dto.language]["connections"].extend(connections)
        return composite_thing

    @overload
    def _build_thing(self, node_dto: NodeTypeDTO, thing: type[Token]) -> Token: ...
    @overload
    def _build_thing(
        self, node_dto: NodeTypeDTO, thing: type[CompositeThing]
    ) -> CompositeThing: ...
    def _build_thing(self, node_dto: NodeTypeDTO, thing: type[ThingType]) -> ThingType:
        """Build a Thing (Token or CompositeThing) from a NodeTypeDTO and register it."""
        category_names = self._get_node_categories(node_dto)
        return thing.from_node_dto(node_dto, category_names=category_names)  # type: ignore

    def _parse_node_array(self, node_array: NodeArray) -> list[ThingOrCategoryType]:
        """Parse and translate a single node types file into internal representation.

        Args:
            node_array: NodeArray containing the list of NodeTypeDTOs to parse.
        """
        category_nodes: list[NodeTypeDTO] = []
        token_nodes: list[NodeTypeDTO] = []
        composite_nodes: list[NodeTypeDTO] = []
        for key, group in groupby(
            sorted(node_array.root, key=lambda n: (n.is_category, n.is_token, n.is_composite)),
            key=lambda n: (n.is_category, n.is_token, n.is_composite),
        ):
            match key:
                case True, False, False:
                    category_nodes.extend(group)
                case False, True, False:
                    token_nodes.extend(group)
                case False, False, True:
                    composite_nodes.extend(group)
                case _:
                    logger.warning("Skipping unclassified node types: %s", list(group))
        if category_nodes:
            type(self)._registration_cache[node_array.language]["categories"].extend(
                self._create_category(node_dto) for node_dto in category_nodes
            )
        if token_nodes:
            type(self)._registration_cache[node_array.language]["tokens"].extend(
                self._create_token(node_dto) for node_dto in token_nodes
            )
        if composite_nodes:
            type(self)._registration_cache[node_array.language]["composites"].extend(
                self._create_composite(node_dto) for node_dto in composite_nodes
            )
        return self._flattened_nodes_for_language(node_array.language)

    def _validate(self) -> None:
        """Validate the internal state of the parser."""
        from codeweaver.semantic.grammar import CompositeThing, Token
        from codeweaver.semantic.registry import get_registry

        registry = get_registry()
        for language in self._languages:
            if len(self._registration_cache[language]["composites"]) > 0:
                for thing in self._flattened_nodes_for_language(language):
                    if thing not in registry:
                        raise ValueError(f"Thing {thing.name} not registered in registry.")
                    if (
                        isinstance(thing, CompositeThing | Token)
                        and thing.has_categories
                        and not thing.categories
                    ):
                        raise ValueError(f"Thing {thing.name} should have categories but has none.")
                    if isinstance(thing, CompositeThing) and (
                        not thing.direct_connections or not thing.positional_connections
                    ):
                        raise ValueError(
                            f"CompositeThing {thing.name} should have direct or positional connections but has none."
                        )
            logger.warning(
                "No composites found for language %s during validation.", language.as_title
            )


_parser: NodeTypeParser | None = None


def get_things(
    *, languages: Sequence[SemanticSearchLanguage] | None = None
) -> list[ThingOrCategoryType]:
    """Get all Things and Categories from the registry, optionally filtered by language.

    Args:
        languages: Optional list of languages to filter by; if None, returns all Things and Categories.

    Returns:
        List of Things and Categories matching the specified languages.
    """
    global _parser
    if _parser is None:
        _parser = NodeTypeParser(languages=languages or list(SemanticSearchLanguage))
    return _parser.parse_languages(languages=languages or list(SemanticSearchLanguage))


# Debug harness

# sourcery skip: avoid-builtin-shadow
if __name__ == "__main__":
    has_rich = False
    from importlib.util import find_spec

    if find_spec("rich"):
        from rich.console import Console

        console = Console(markup=True)
        print = console.print  # type: ignore  # noqa: A001
        has_rich = True
    parser = NodeTypeParser()
    all_things = parser.parse_all_nodes()
    print("Parsed Things and Categories:")
    for thing in sorted(
        all_things,
        key=lambda x: (
            x.language.as_title,
            x.is_composite if hasattr(x, "is_composite") else False,  # type: ignore
            x.name,
        ),
    ):
        print(
            f" - [bold dark_orange]{thing.language.as_title}[/bold dark_orange]: [cyan]{thing.name}[/cyan] [green]({thing.kind if hasattr(thing, 'kind') else 'Category'})[/green]"  # type: ignore
            if has_rich
            else f" - {thing.language.as_title}: {thing.name} ({thing.kind if True else 'Category'})"  # type: ignore
        )
    print(
        f"[magenta]Total: {len(all_things)} Things and Categories[/magenta]"
        if has_rich
        else f"Total: {len(all_things)} Things and Categories"
    )  # type: ignore


__all__ = ("NodeArray", "NodeTypeFileLoader", "NodeTypeParser", "get_things")
