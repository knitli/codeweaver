# sourcery skip: avoid-builtin-shadow, lambdas-should-be-short, no-complex-if-expressions
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""ThingRegistry manages the registration and retrieval of grammar Things and Categories for programming languages."""

import logging

from collections import defaultdict
from collections.abc import Generator, Iterable
from itertools import chain
from types import MappingProxyType
from typing import TYPE_CHECKING, cast

from codeweaver._utils import lazy_importer
from codeweaver.language import SemanticSearchLanguage
from codeweaver.semantic._types import CategoryName, Role, ThingName, ThingOrCategoryNameType


grammar_module = lazy_importer("codeweaver.semantic.grammar_things")

if TYPE_CHECKING:
    from codeweaver.semantic.grammar_things import (
        Category,
        CompositeThing,
        Connection,
        DirectConnection,
        PositionalConnections,
        ThingOrCategoryType,
        Token,
    )
else:
    Category = grammar_module.Category
    CompositeThing = grammar_module.CompositeThing
    Connection = grammar_module.Connection
    DirectConnection = grammar_module.DirectConnection
    PositionalConnections = grammar_module.PositionalConnections
    Token = grammar_module.Token
    ThingOrCategoryType = grammar_module.ThingOrCategoryType


logger = logging.getLogger(__name__)

type _TokenDict = dict[ThingName, Token]
type _CompositeThingDict = dict[ThingName, CompositeThing]
type _CategoryDict = dict[CategoryName, Category]


class ThingRegistry:
    """Registry for managing Things and Categories for programming languages.

    Responsibilities:
        - A simple store for constructed Things and Categories
        - Along with ThingGenerator, provides lazy access to Things by name

    """

    _tokens: dict[SemanticSearchLanguage, _TokenDict]
    _composite_things: dict[SemanticSearchLanguage, _CompositeThingDict]
    _categories: dict[SemanticSearchLanguage, _CategoryDict]

    _contents: tuple[
        dict[SemanticSearchLanguage, _TokenDict],
        dict[SemanticSearchLanguage, _CompositeThingDict],
        dict[SemanticSearchLanguage, _CategoryDict],
    ]

    _direct_connections: dict[SemanticSearchLanguage, dict[ThingName, list[DirectConnection]]]
    """Direct connections by source Thing name."""
    _positional_connections: dict[SemanticSearchLanguage, dict[ThingName, PositionalConnections]]
    """Positional connections by source Thing name."""

    _connections: tuple[
        dict[SemanticSearchLanguage, dict[ThingName, list[DirectConnection]]],
        dict[SemanticSearchLanguage, dict[ThingName, PositionalConnections]],
    ]

    def __init__(self) -> None:
        """Initialize the ThingRegistry."""
        (
            self._tokens,
            self._categories,
            self._composite_things,
            self._direct_connections,
            self._positional_connections,
        ) = {}, {}, {}, {}, {}
        for lang in SemanticSearchLanguage:
            # pylance complains because the defaultdict isn't the TypedDict
            self._tokens[lang] = defaultdict(dict)  # type: ignore
            self._composite_things[lang] = defaultdict(dict)  # type: ignore
            self._categories[lang] = defaultdict(dict)  # type: ignore
            self._direct_connections[lang] = defaultdict(dict)  # type: ignore
            self._positional_connections[lang] = defaultdict(dict)  # type: ignore

        self._contents = self._tokens, self._composite_things, self._categories
        self._connections = self._direct_connections, self._positional_connections

    def __contains__(
        self,
        obj: ThingOrCategoryType
        | ThingOrCategoryNameType
        | PositionalConnections
        | DirectConnection
        | Role,
    ) -> bool:
        """Check if a thing, category, or connection is registered -- by instance or name."""
        if isinstance(obj, Category | Token | CompositeThing):
            return self.is_registered(obj)
        if isinstance(obj, DirectConnection | PositionalConnections):
            if isinstance(obj, DirectConnection):
                return obj.source_thing in self._direct_connections.get(obj.language, {})
            return obj.source_thing in self._positional_connections.get(obj.language, {})
        scan = [thing for thing in self.everything if not isinstance(thing, PositionalConnections)]
        names: list[ThingOrCategoryNameType | Role] = [
            cast(ThingOrCategoryType, thing).name
            if hasattr(thing, "name")
            else cast(DirectConnection, thing).role
            for thing in scan
        ]
        return obj in names

    def is_registered(self, thing: ThingOrCategoryType) -> bool:
        """Check if a Thing or Category is already registered."""
        if isinstance(thing, Category):
            return thing.name in self._categories.get(thing.language, {})
        if isinstance(thing, Token):
            return thing.name in self._tokens.get(thing.language, {})
        return thing.name in self._composite_things.get(thing.language, {})

    def _language_content(
        self, language: SemanticSearchLanguage
    ) -> MappingProxyType[ThingOrCategoryNameType, ThingOrCategoryType]:
        """Provides a combined read-only view of all Things for a specific language."""
        return MappingProxyType(
            self._tokens[language] | self._composite_things[language] | self._categories[language]
        )

    def _register_category(self, category: Category) -> None:
        """Register a Category."""
        self._categories[category.language][category.name] = category
        if category.language == SemanticSearchLanguage.JAVASCRIPT:
            self._categories[SemanticSearchLanguage.JSX][category.name] = Category.model_construct(
                category.model_fields_set,
                **(
                    category.model_dump(mode="python", exclude={"language", "member_things"})
                    | {"language": SemanticSearchLanguage.JSX}
                ),
            )
        logger.debug("Registered %s", category)

    def _register_token(self, token: Token) -> None:
        """Register a Token."""
        self._tokens[token.language][token.name] = token
        if token.language == SemanticSearchLanguage.JAVASCRIPT:
            self._tokens[SemanticSearchLanguage.JSX][token.name] = Token.model_construct(
                token.model_fields_set,
                **(
                    token.model_dump(mode="python", exclude={"language", "categories"})
                    | {"language": SemanticSearchLanguage.JSX}
                ),
            )
        logger.debug("Registered %s", token)

    def register_thing(self, thing: ThingOrCategoryType) -> None:
        """Register a Thing in the appropriate category."""
        if isinstance(thing, Category):
            self._register_category(thing)
            return
        if isinstance(thing, Token):
            self._register_token(thing)
            return
        self._composite_things[thing.language][thing.name] = thing
        if thing.language == SemanticSearchLanguage.JAVASCRIPT:
            self._composite_things[SemanticSearchLanguage.JSX][thing.name] = (
                CompositeThing.model_construct(  # type: ignore
                    thing.model_fields_set,
                    **(
                        thing.model_dump(
                            mode="python",
                            exclude={
                                "language",
                                "direct_connections",
                                "positional_connections",
                                "categories",
                            },
                        )
                        | {"language": SemanticSearchLanguage.JSX}
                    ),
                )
            )
        logger.debug("Registered %s", thing)

    def _register_positional_connection(self, connection: PositionalConnections) -> None:
        """Register a PositionalConnections."""
        if connection.source_thing in self._positional_connections[connection.language]:
            return
        self._positional_connections[connection.language][connection.source_thing] = connection
        logger.debug("Registered %s", connection)
        if connection.language == SemanticSearchLanguage.JAVASCRIPT:
            js_connection = PositionalConnections.model_construct(
                connection.model_fields_set,
                **(
                    connection.model_dump(
                        mode="python",
                        exclude={
                            "language",
                            "constraints",
                            "target_things",
                            "connection_count",
                            "connection_class",
                        },
                    )
                    | {"language": SemanticSearchLanguage.JSX}
                ),
            )
            if (
                connection.source_thing
                not in self._positional_connections[SemanticSearchLanguage.JSX]
            ):
                self._positional_connections[SemanticSearchLanguage.JSX][
                    js_connection.source_thing
                ] = js_connection
                logger.debug("Registered %s", js_connection)

    def register_connection(self, connection: DirectConnection | PositionalConnections) -> None:
        """Register a Connection in the appropriate category."""
        if isinstance(connection, PositionalConnections):
            self._register_positional_connection(connection)
            return
        assert isinstance(connection, DirectConnection)  # noqa: S101
        if connection.source_thing not in self._direct_connections[connection.language]:
            self._direct_connections[connection.language][connection.source_thing] = []
        self._direct_connections[connection.language][connection.source_thing].append(connection)  # type: ignore
        logger.debug("Registered %s", connection)
        if connection.language == SemanticSearchLanguage.JAVASCRIPT:
            js_connection = DirectConnection.model_construct(
                connection.model_fields_set,
                **(
                    connection.model_dump(
                        mode="python",
                        exclude={
                            "language",
                            "constraints",
                            "target_things",
                            "connection_count",
                            "connection_class",
                        },
                    )
                    | {"language": SemanticSearchLanguage.JSX}
                ),
            )
            if (
                not self._direct_connections[SemanticSearchLanguage.JSX]
                or js_connection.source_thing
                not in self._direct_connections[SemanticSearchLanguage.JSX]
            ):
                self._direct_connections[SemanticSearchLanguage.JSX][
                    js_connection.source_thing
                ] = []
            self._direct_connections[SemanticSearchLanguage.JSX][js_connection.source_thing].append(
                js_connection
            )  # type: ignore
            logger.debug("Registered %s", js_connection)

    def register_connections(
        self, connections: Iterable[DirectConnection] | PositionalConnections | None
    ) -> None:
        """Register multiple Connections."""
        if connections is None:
            return
        if isinstance(connections, Connection):
            self.register_connection(connections)
            return
        for connection in connections:
            self.register_connection(connection)

    def get_thing_by_name(
        self, name: ThingOrCategoryNameType, *, language: SemanticSearchLanguage | None = None
    ) -> ThingOrCategoryType | None:
        """Get a Thing by its name across all languages."""
        if language and name in (content := self._language_content(language)):
            return content[name]
        if not language:
            for content in self._contents:
                for language in content:
                    if name in content[language]:
                        return content[language][name]  # type: ignore
        return None

    def get_category_by_name(
        self, name: CategoryName, *, language: SemanticSearchLanguage | None = None
    ) -> Category | None:
        """Get a Category by its name across all languages."""
        if language and name in (content := self._categories[language]):
            return content[name]
        if not language:
            for content in self._categories:
                for language, cats in self._categories.items():
                    if name in cats:
                        return content[language][name]  # type: ignore
        return None

    def _get_direct_connections_by_source(
        self, source: ThingName, *, language: SemanticSearchLanguage | None = None
    ) -> Generator[DirectConnection]:
        """Get DirectConnections by their source Thing name across all languages."""
        if language:
            yield from self.direct_connections[language].get(source, [])
        yield from (
            next(
                (
                    conns
                    for content in self._direct_connections.values()
                    for con_name, conns in content.items()
                    if con_name == source
                ),
                [],  # type: ignore
            )
        )

    def _get_positional_connections_by_source(
        self, source: ThingName, *, language: SemanticSearchLanguage | None = None
    ) -> PositionalConnections | None:
        """Get PositionalConnectionss by their source Thing name across all languages."""
        if language:
            return self.positional_connections[language].get(source)
        return next(
            (
                conn
                for content in self._positional_connections.values()
                for con_name, conn in content.items()
                if con_name == source
            ),
            None,
        )

    def get_positional_connections_by_source(
        self, source: ThingName, *, language: SemanticSearchLanguage | None = None
    ) -> PositionalConnections | None:
        """Get PositionalConnectionss by their source Thing name across all languages."""
        return self._get_positional_connections_by_source(source, language=language)

    def get_direct_connections_by_source(
        self, source: ThingName, *, language: SemanticSearchLanguage | None = None
    ) -> Generator[DirectConnection]:
        """Get DirectConnections by their source Thing name across all languages."""
        yield from self._get_direct_connections_by_source(source, language=language)

    def register_things(self, things: Iterable[ThingOrCategoryType]) -> None:
        """Register multiple Things."""
        for thing in things:
            self.register_thing(thing)

    @property
    def tokens(self) -> MappingProxyType[SemanticSearchLanguage, _TokenDict]:
        """Get all registered Tokens."""
        return MappingProxyType(self._tokens)

    @property
    def composite_things(self) -> MappingProxyType[SemanticSearchLanguage, _CompositeThingDict]:
        """Get all registered CompositeThings."""
        return MappingProxyType(self._composite_things)

    @property
    def categories(self) -> MappingProxyType[SemanticSearchLanguage, _CategoryDict]:
        """Get all registered Categories."""
        return MappingProxyType(self._categories)

    @property
    def connections(
        self,
    ) -> tuple[
        MappingProxyType[SemanticSearchLanguage, dict[ThingName, list[DirectConnection]]],
        MappingProxyType[SemanticSearchLanguage, dict[ThingName, PositionalConnections]],
    ]:
        """Get all registered Connections."""
        return (
            MappingProxyType(self._direct_connections),
            MappingProxyType(self._positional_connections),
        )

    @property
    def all_cats_and_things(
        self,
    ) -> MappingProxyType[
        SemanticSearchLanguage, MappingProxyType[ThingOrCategoryNameType, ThingOrCategoryType]
    ]:
        """Get all registered Things and Categories combined."""
        return MappingProxyType({
            lang: self._language_content(lang)
            for lang in SemanticSearchLanguage
            if self.has_language(lang)
        })

    @property
    def everything(
        self,
    ) -> list[CompositeThing | Token | Category | PositionalConnections | DirectConnection]:
        """Get all registered Things, Categories, and Connections as a flat list."""
        direct = [
            v
            for val in self._direct_connections.values()
            for v in chain.from_iterable(val.values())
        ]
        positional = [v for val in self._positional_connections.values() for v in val.values()]
        categories = [v for val in self._categories.values() for v in val.values()]
        tokens = [v for val in self._tokens.values() for v in val.values()]
        composite = [v for val in self._composite_things.values() for v in val.values()]
        return direct + positional + categories + tokens + composite

    @property
    def direct_connections(
        self,
    ) -> MappingProxyType[SemanticSearchLanguage, dict[ThingName, list[DirectConnection]]]:
        """Get all registered DirectConnections."""
        return MappingProxyType(self._direct_connections)

    @property
    def positional_connections(
        self,
    ) -> MappingProxyType[SemanticSearchLanguage, dict[ThingName, PositionalConnections]]:
        """Get all registered PositionalConnections."""
        return MappingProxyType(self._positional_connections)

    def has_language(self, language: SemanticSearchLanguage) -> bool:
        """Check if the registry has any Things or Categories for the specified language."""
        return bool(
            self._tokens.get(language)
            or self._composite_things.get(language)
            or self._categories.get(language)
        )


_registry: ThingRegistry | None = None


def get_registry() -> ThingRegistry:
    """Get the ThingRegistry instance."""
    global _registry
    if _registry is None:
        _registry = ThingRegistry()
        # we need to make sure NodeTypeParser isn't the caller, because that would cause infinite recursion
        # And it will call this function to get the registry to populate it
        import inspect

        caller = inspect.stack()[1]
        if "NodeTypeParser" in caller.filename or "node_type_parser" in caller.filename:
            return _registry
        if not any(_registry.has_language(lang) for lang in SemanticSearchLanguage):
            from codeweaver.semantic.node_type_parser import NodeTypeParser

            parser = NodeTypeParser()
            _ = parser.parse_all_nodes()
    return _registry


__all__ = ("ThingRegistry", "get_registry")
