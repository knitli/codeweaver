# sourcery skip: avoid-builtin-shadow, lambdas-should-be-short, no-complex-if-expressions
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Grammar provides the primary API for evaluating defined grammar rules for a language. We use grammars to analyze observed AST nodes and determine their semantic meaning."""

from __future__ import annotations

from collections import defaultdict
from types import MappingProxyType
from typing import TYPE_CHECKING, Annotated

from pydantic import Field, NonNegativeInt, computed_field
from pydantic.dataclasses import dataclass

from codeweaver._common import DATACLASS_CONFIG, DataclassSerializationMixin
from codeweaver._utils import lazy_importer
from codeweaver.language import SemanticSearchLanguage


if TYPE_CHECKING:
    from codeweaver.semantic._types import CategoryName, ThingName
    from codeweaver.semantic.grammar_things import (
        Category,
        CompositeThing,
        DirectConnection,
        PositionalConnections,
        ThingType,
        Token,
    )
    from codeweaver.semantic.thing_registry import ThingRegistry


@dataclass(frozen=True, config=DATACLASS_CONFIG, slots=True)
class Grammar(DataclassSerializationMixin):
    """A grammar represents the complete set of Things, Categories, and Connections for a specific programming language.

    Grammars are the primary objects for semantic analysis and code understanding (comparing observed ASTs to expected structures -- grammars are the expected structure half).
    """

    language: Annotated[
        SemanticSearchLanguage,
        Field(description="The programming language this Grammar represents."),
    ]

    _tokens: Annotated[frozenset[Token], Field(exclude=True, default_factory=frozenset)]

    _composite_things: Annotated[
        frozenset[CompositeThing], Field(exclude=True, default_factory=frozenset)
    ]
    _categories: Annotated[frozenset[Category], Field(exclude=True, default_factory=frozenset)]

    _direct_connections: Annotated[
        frozenset[DirectConnection], Field(exclude=True, default_factory=frozenset)
    ]
    _positional_connections: Annotated[
        frozenset[PositionalConnections], Field(exclude=True, default=frozenset)
    ]

    @classmethod
    def from_registry(cls, language: SemanticSearchLanguage) -> Grammar:
        """Create a Grammar for the specified language from the ThingRegistry.

        Args:
            language: The programming language for the Grammar.

        Returns:
            A Grammar instance for the specified language.
        """
        try:
            from codeweaver.semantic.thing_registry import get_registry

            registry: ThingRegistry = get_registry()

        except Exception:
            from codeweaver.semantic.node_type_parser import NodeTypeParser

            parser = NodeTypeParser()
            results = parser.parse_languages([language])
            direct: list[DirectConnection] = []
            positional: list[PositionalConnections] = []
            for result in results:
                if isinstance(result, CompositeThing):
                    direct.extend(iter(result.direct_connections))
                    if result.positional_connections:
                        positional.append(result.positional_connections)
            return cls(
                language=language,
                _tokens=frozenset(t for t in results if isinstance(t, Token)),
                _composite_things=frozenset(t for t in results if isinstance(t, CompositeThing)),
                _categories=frozenset(t for t in results if isinstance(t, Category)),
                _direct_connections=frozenset(direct),
                _positional_connections=frozenset(positional),
            )
        else:
            return cls(
                language=language,
                _tokens=frozenset(registry.tokens[language].values()),
                _composite_things=frozenset(registry.composite_things[language].values()),
                _categories=frozenset(registry.categories[language].values()),
                _direct_connections=frozenset(
                    conn for lst in registry.direct_connections[language].values() for conn in lst
                ),
                _positional_connections=frozenset(
                    registry.positional_connections[language].values()
                ),
            )

    @computed_field(repr=False)
    @property
    def tokens(self) -> frozenset[Token]:
        """Get all Tokens in this Grammar."""
        return self._tokens

    @computed_field(repr=False)
    @property
    def composite_things(self) -> frozenset[CompositeThing]:
        """Get all CompositeThings in this Grammar."""
        return self._composite_things

    @computed_field(repr=False)
    @property
    def categories(self) -> frozenset[Category]:
        """Get all Categories in this Grammar."""
        return self._categories

    @computed_field(repr=False)
    @property
    def direct_connections(self) -> frozenset[DirectConnection]:
        """Get all DirectConnections in this Grammar."""
        return self._direct_connections

    @computed_field(repr=False)
    @property
    def positional_connections(self) -> frozenset[PositionalConnections]:
        """Get all PositionalConnections in this Grammar."""
        return self._positional_connections

    @computed_field
    @property
    def things(self) -> frozenset[ThingType]:
        """Get all Things (CompositeThings and Tokens) in this Grammar."""
        return self._composite_things | self._tokens

    @property
    def direct_connections_by_source(self) -> MappingProxyType[ThingName, list[DirectConnection]]:
        """Get DirectConnections grouped by source Thing name."""
        from codeweaver.semantic.thing_registry import get_registry

        return MappingProxyType(get_registry().direct_connections[self.language])

    @property
    def positional_connections_by_source(
        self,
    ) -> MappingProxyType[ThingName, PositionalConnections]:
        """Get PositionalConnections grouped by source Thing name."""
        from codeweaver.semantic.thing_registry import get_registry

        return MappingProxyType(get_registry().positional_connections[self.language])

    @property
    def category_groups(self) -> MappingProxyType[CategoryName, frozenset[ThingType]]:
        """Get Things grouped by Category name."""
        if not self.has_categories:
            return MappingProxyType({})
        category_map: dict[CategoryName, frozenset[ThingType]] = defaultdict(frozenset)
        for category in self._categories:
            category_map[category.name] |= category.member_things

        return MappingProxyType(category_map)

    @computed_field
    @property
    def composite_count(self) -> NonNegativeInt:
        """Get the number of CompositeThings in this Grammar."""
        return len(self._composite_things)

    @computed_field
    @property
    def token_count(self) -> NonNegativeInt:
        """Get the number of Tokens in this Grammar."""
        return len(self._tokens)

    @computed_field
    @property
    def category_count(self) -> NonNegativeInt:
        """Get the number of Categories in this Grammar."""
        return len(self._categories)

    @computed_field
    @property
    def direct_connection_count(self) -> NonNegativeInt:
        """Get the number of DirectConnections in this Grammar."""
        return len(self._direct_connections)

    @computed_field
    @property
    def positional_connection_count(self) -> NonNegativeInt:
        """Get the number of PositionalConnections in this Grammar."""
        return len(self._positional_connections)

    @computed_field
    @property
    def anywhere_things(self) -> frozenset[ThingType]:
        """Get all Things (CompositeThings and Tokens) that can be anywhere in this Grammar."""
        return frozenset(thing for thing in self.things if thing.can_be_anywhere)

    @computed_field
    @property
    def has_categories(self) -> bool:
        """Check if this Grammar has any Categories."""
        return bool(self._categories)


def get_grammar(language: SemanticSearchLanguage) -> Grammar:
    """Get the Grammar for the specified programming language.

    Args:
        language (SemanticSearchLanguage): The programming language to get the Grammar for.

    Returns:
        Grammar: The Grammar for the specified programming language.
    """
    Category = lazy_importer("codeweaver.semantic.grammar_things").Category  # pyright: ignore[reportUnusedVariable] # noqa: N806,F841
    Token = lazy_importer("codeweaver.semantic.grammar_things").Token  # pyright: ignore[reportUnusedVariable] # noqa: N806,F841
    CompositeThing = lazy_importer("codeweaver.semantic.grammar_things").CompositeThing  # pyright: ignore[reportUnusedVariable] # noqa: N806,F841
    DirectConnection = lazy_importer("codeweaver.semantic.grammar_things").DirectConnection  # pyright: ignore[reportUnusedVariable] # noqa: N806,F841
    PositionalConnections = lazy_importer(  # pyright: ignore[reportUnusedVariable] # noqa: N806,F841
        "codeweaver.semantic.grammar_things"
    ).PositionalConnections
    ThingType = lazy_importer("codeweaver.semantic.grammar_things").ThingType  # pyright: ignore[reportUnusedVariable] # noqa: N806,F841
    return Grammar.from_registry(language)


__all__ = ("Grammar", "get_grammar")


if __name__ == "__main__":
    grammar = get_grammar(SemanticSearchLanguage.PYTHON)
    rich_console = lazy_importer("rich.console").Console()
    rich_console.print_json(grammar.dump_json())
