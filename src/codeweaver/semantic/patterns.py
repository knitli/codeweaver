# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Pre-compiled regex patterns for semantic node classification."""

from __future__ import annotations

import contextlib
import re

from functools import lru_cache
from re import Pattern
from typing import ClassVar, Literal, NamedTuple, cast

import textcase

from pydantic import NonNegativeFloat

from codeweaver.semantic.categories import ImportanceRank, SemanticClass


class Matched(NamedTuple):
    """Result of a regex match with additional metadata."""

    category: SemanticClass
    confidence: NonNegativeFloat
    text: str | None
    obj: re.Match[str] | None
    pattern: str | None = None

    @classmethod
    def from_match(cls, match: re.Match[str], *, from_search: bool = False) -> Matched | None:
        """Create a Matched instance from a regex match object.

        The punctuation and operator matches are all given a higher confidence score, since they are unambiguous -- the patterns are exact matches, which is also why the returned pattern is just the matched text.

        Note: We account for finding punctuation or operators in a search context (not anchored to start/end) but that should actually never happen since those patterns are anchored. Just in case, we lower the confidence a bit.
        """
        groups = match.groupdict()
        if group_key := next(
            (k for k, v in groups.items() if v and isinstance(v, str) and k != "0"), None
        ):
            match group_key:
                case "operator":
                    return cls(
                        SemanticClass.OPERATION_OPERATOR,
                        0.75 if from_search else 0.95,
                        match[group_key],
                        match,
                        match[group_key],
                    )
                case "punctuation":
                    return cls(
                        SemanticClass.SYNTAX_PUNCTUATION,
                        0.65 if from_search else 0.9,
                        match[group_key],
                        match,
                        match[group_key],
                    )
                case _:
                    category = SemanticClass.from_string(group_key)
                    # `codeweaver.semantic.categories.ImportanceRank` is an int enum from 1 (highest tier, structural definitions) to 5 (lowest tier, syntax references).
                    # We map this to a confidence score between 0.5 and 0.9
                    # Tier 1 -> 0.5 + 0.1 * 1 = 0.6
                    # Tier 5 -> 0.5 + 0.1 * 5 = 1.0 (capped at 0.9)
                    confidence = min(category.tier * 0.1 + 0.4, 0.9)
                    if from_search:
                        confidence = confidence - 0.25
                    return cls(
                        category,
                        confidence,
                        match[group_key],
                        match,
                        Matcher.pattern_from_match(
                            match, "tier", category=category, group_key=group_key
                        ),
                    )
        return None


class Matcher:
    """Compiles and holds a complex regex pattern for semantic node classification.

    Stores the compiled pattern as a class variable to avoid recompilation. Since we keep the pattern in the class, it's lazily compiled on first use.
    """

    _pattern: ClassVar[Pattern[str]] | None = None
    _syntax_only_pattern: ClassVar[Pattern[str]] | None = None

    _operators_group: ClassVar[tuple[str, ...]] = ()
    _punctuation_group: ClassVar[tuple[str, ...]] = ()
    _tiered_group: ClassVar[tuple[str, ...]] = ()

    _group_matcher: ClassVar[Pattern[str]] = re.compile(r"\(\?P<(?P<name>\w+)>", re.IGNORECASE)

    def __init__(self) -> None:
        """Compile all necessary regex patterns once."""
        if type(self)._pattern is not None:
            return  # Already compiled
        multi_char_operators = self._compile_multi_char_operators()
        single_char_operators = self._compile_single_char_operators()
        pure_punctuation = self._compile_pure_punctuation()
        tier_patterns = self._compile_tier_patterns()
        l_parens = r"("
        r_parens = r")"
        assembled_operators = self._as_named_group(
            f"^{l_parens}{multi_char_operators}|{single_char_operators}{r_parens}$", "operator"
        )
        assembled_punctuation = self._as_named_group(
            f"^{l_parens}{pure_punctuation}{r_parens}$", "punctuation"
        )
        # not truly syntax-only, but close enough -- we only care about operators and punctuation here
        type(self)._syntax_only_pattern = re.compile(
            f"{l_parens}{assembled_operators}|{assembled_punctuation}{r_parens}", re.IGNORECASE
        )
        type(self)._pattern = re.compile(
            f"{assembled_operators}|{assembled_punctuation}|{tier_patterns}", re.IGNORECASE
        )

    # ================================================
    # *           Public Interface           *
    # ================================================

    @property
    def pattern(self) -> Pattern[str]:
        """Get the compiled regex pattern."""
        if type(self)._pattern is None:
            raise ValueError("Patterns have not been compiled.")
        return cast(Pattern[str], type(self)._pattern)

    def match(self, text: str, /, *, only_syntactic: bool = False) -> Matched | None:
        """Match the text against the compiled pattern."""
        if (
            matched := self.syntax_only_pattern.match(text)
            if only_syntactic
            else self.pattern.match(text)
        ):
            return Matched.from_match(matched)
        return None

    def search(self, text: str, /, *, only_syntactic: bool = False) -> Matched | None:
        """Search the text against the compiled pattern."""
        if (
            matched := self.syntax_only_pattern.search(text)
            if only_syntactic
            else self.pattern.search(text)
        ):
            return Matched.from_match(matched, from_search=True)
        return None

    @property
    def syntax_only_pattern(self) -> Pattern[str]:
        """Get a compiled regex pattern for syntax-only matching (operators and punctuation)."""
        if not type(self)._syntax_only_pattern:
            raise ValueError("Patterns have not been compiled.")
        return cast(Pattern[str], type(self)._syntax_only_pattern)

    @classmethod
    def pattern_from_match(
        cls,
        match: re.Match[str],
        kind: Literal["operator", "punctuation", "tier"],
        *,
        category: SemanticClass | None = None,
        group_key: str | None = None,
    ) -> str:  # sourcery skip: no-complex-if-expressions, use-getitem-for-re-match-groups
        """Get the regex pattern string for a specific match kind.

        Args:
            match: The regex match object.
            kind: The kind of pattern to retrieve ("operator", "punctuation", or "tier").
            category: Optional SemanticClass to narrow down the tier pattern.
            group_key: Optional specific group key to look for in the match.

        While compiling a large regex is more efficient for matching, you lose the ability to extract individual patterns for specific categories. This method allows you to retrieve the specific pattern string for a given kind of match.

        This may seem inefficient, but since we only use it for a small fraction of matches for added confidence, it still beats running multiple regexes on every node.
        """
        if kind in ("operator", "punctuation") and match.group(kind):
            return match.group(kind)
        if kind != "tier":
            raise ValueError(
                "Kind must be 'operator', 'punctuation', or 'tier' with a valid match."
            )
        if (
            not cls._pattern
            or not cls._operators_group
            or not cls._punctuation_group
            or not cls._tiered_group
        ):
            _ = cls()  # Ensure patterns are compiled
            assert cls._pattern  # noqa: S101
            assert cls._tiered_group  # noqa: S101
        cat = textcase.snake(str(category)) if category else ""
        key = (
            group_key
            or (cat if cat and category and any(v for v in cls._tiered_group if cat in v) else None)
            or next((k for k in match.groupdict() if k != "0" and match[k]), None)
        )
        if not key:
            raise ValueError("Cannot determine group key for tier pattern.")
        search_values = next(
            (
                v
                for v in cls._tiered_group
                if cls._group_matcher.search(v)
                and cast(re.Match[str], v).groupdict()["name"] == key
            ),
            None,
        )
        patterns = (
            search_values.replace(f"(?P<{key}>", "").rstrip(")").strip("^$").strip("()").split("|")
            if search_values
            else []
        )
        matched_text = match.group(key)
        if matched_text and patterns:
            if exact_match := next(
                (p for p in patterns if p.lower() == matched_text.lower()), None
            ):
                return exact_match
            for pattern in patterns:
                if re.match(pattern, matched_text, re.IGNORECASE):
                    return pattern
        raise ValueError("Cannot find pattern for the given match.")

    # ================================================
    # *        Private Helper Methods        *

    def _as_named_group(self, pattern: str, group_name: str) -> str:
        """Wrap a pattern in a named capturing group."""
        opening = r"(?P<"
        closing = r")"
        return f"{opening}{textcase.snake(group_name)}>{pattern}{closing}"

    def _compile_multi_char_operators(self) -> str:
        """Multi-character operators sorted by length descending."""
        multi_char_ops = {
            "is not",
            "not in",
            "== /=",
            "+ - *",
            ". . .",
            ">>>=",
            "$ $!",
            "&&&",
            "&>>",
            "+++",
            ";;&",
            "<&-",
            "<<-",
            "<<<",
            ">>>",
            "<<~",
            "<|>",
            "<~>",
            ">&-",
            "?->",
            "---",
            "->.",
            "->*",
            "!==",
            "!in",
            "!is",
            "??=",
            "?=>",
            "...",
            "..<",
            "..=",
            "&&=",
            "&^=",
            "**=",
            "//=",
            "<<=",
            "===",
            ">>=",
            "<=>",
            "==~",
            "=>>",
            "and",
            "not",
            "<$>",
            "<*>",
            "++<",
            "--<",
            "++>",
            "++=",
            "--=",
            "==>",
            "==<",
            "=<<",
            "=++",
            "=**",
            "=/=",
            "=--",
            "||=",
            "^^=",
            "++.",
            "--.",
            "!!!",
            "|||",
            "^^^",
            ":=",
            "**",
            ">=",
            "<=",
            "==",
            "!=",
            "&&",
            "||",
            "++",
            "--",
            "+=",
            "-=",
            "*=",
            "/=",
            "%=",
            "&=",
            "^=",
            "|=",
            "<<",
            ">>",
            "->",
            "=>",
            "??",
            "?.",
            "!!",
            "!~",
            "=~",
            "<>",
            "<~",
            "~>",
            "~@",
            "$=",
            "~=",
            "<*",
            "*>",
            "|~",
            "|>",
            "<|",
            "^^",
            "=+",
            "=*",
            "=-",
            "<$",
            "is",
            "in",
            "or",
            "%%",
            "$$",
            "@@",
            "..",
            "=:",
            "<:",
            ":>",
            # Bash comparison, arithmetic, unary, and logical operations
            "$*",
            "$@",
            "$?",
            "-eq",
            "-ne",
            "-lt",
            "-le",
            "-gt",
            "-ge",
            "-z",
            "-n",
            "-f",
            "-d",
            "-e",
            "-r",
            "-w",
            "-x",
            "-v",
            # These show up in the Haskell grammar. No idea what they do.
            # Not a Haskell expert, but I think you can define arbitrary operators
            "->>",
            "<-<",
            ">->",
            "∀",
            "∃",
            "∧",
            "∨",  # noqa: RUF001
            "¬",
            "⇒",
            "⇔",
            "λ",
            "⊸",
            "★",
            "⟦",
            "⟧",
        }
        alphas = {a for a in multi_char_ops if a.isalpha() or a.replace(" ", "").isalpha()}
        non_alpha_ops = multi_char_ops - alphas
        alphas = sorted(alphas, key=len, reverse=True)
        if not type(self)._operators_group:
            type(self)._operators_group = tuple(
                sorted(non_alpha_ops, key=len, reverse=True) + alphas
            )
        # Sort by length descending to match longest patterns first
        non_alpha_ops = "|".join(re.escape(a) for a in sorted(non_alpha_ops, key=len, reverse=True))
        multi_char_ops = "|".join(
            re.escape(a) for a in sorted(multi_char_ops, key=len, reverse=True)
        )

        return f"{non_alpha_ops}|{multi_char_ops}"

    def _compile_single_char_operators(self) -> str:
        """Single character operators (only if not in hybrid context)."""
        single_ops = ["+", "-", "*", "/", "%", "=", "!", "&", "^", "~", "?", "@", "|", "<", ">"]
        if all(char for char in single_ops if char not in type(self)._operators_group):
            type(self)._operators_group += tuple(single_ops)
        return "|".join(re.escape(op) for op in single_ops)

    def _compile_pure_punctuation(self) -> str:
        """Pure punctuation symbols and delimiters."""
        punctuation = {
            r'r#####"',
            r"<\*<<<",
            r'r####"',
            r"<\!--",
            r"/\*\*",
            r'r###"',
            r"r####",
            r"<!--",
            r"<%--",
            r"--%>",
            r'r##"',
            r"r###",
            r"////",
            r"\\\\",
            r"-->",
            r"<\?",
            r"\?>",
            r"\*/",
            r"/\*",
            r'r#"',
            r"r##",
            r"///",
            r'"""',
            r"'''",
            r'""',
            r"''",
            r"\\",
            r"r#",
            r"//",
            r"##",
            r"\(",
            r"\)",
            r"\[",
            r"\]",
            r"\{",
            r"\}",
            r"<%",
            r"%>",
            r"``",
            r"\.",
            r"::",
            r"\$",
            r"< >",
            r";",
            r"'",
            r'"',
            r"`",
            r"#",
        }
        if not type(self)._punctuation_group:
            type(self)._punctuation_group = tuple(sorted(punctuation, key=len, reverse=True))
        return "|".join(punctuation)

    def _compile_tier_patterns(self) -> str:
        """Tier-based patterns for semantic categories."""
        # Define patterns for each semantic category
        category_patterns = {
            # Tier 1: PRIMARY_DEFINITIONS
            SemanticClass.DEFINITION_CALLABLE: r"(function|fn|proc\w*|def(inition)?|subroutine|procedure|method|constr\w+|init\w*|factory|creator).*(def(inition)?|declaration|statement)|.*function(?!_call)|class.*constructor|.*method(?!_call)|arrow_function|def.*function|def.*callable|callable.*def|def.*method|^def_\w+",
            SemanticClass.DEFINITION_TYPE: r".*(protocol|trait|generic|variatic|covariant|struct|variant|union|enum|interface|record|abstract|signature).*|.*(type|class).*(def\w+|declaration|statement|alias)|.*_type$|.*type.*alias.*",
            SemanticClass.DEFINITION_DATA: r"(constant|config\w*|schema|enum\w*|settings?).*(def(inition)?|class|type|declaration|statement)",
            SemanticClass.DEFINITION_TEST: r"(describe|fixture|test|case|scenario|spec|it).*|test.*(def(inition)?|class|case|scenario|spec|it)",
            # Tier 2: BEHAVIORAL_CONTRACTS
            SemanticClass.BOUNDARY_MODULE: r"(import\w*|from|source|export\w*|extern|req\w*|include|use).*(def(inition)?|declaration|statement)|(library|mod\w*|package|program|namespace|resource|file|compilation.*(def(inition)?|declaration|statement|unit|import|export|extern|req\w*|use)).*",
            SemanticClass.BOUNDARY_ERROR: r"(try|catch|except|finally|throw(able)?|unwrap|suppress(ion)?|raise|rescue|panic|abort|ensure).*(def(inition)?|declaration|statement|block|expression|type|class|handler?)",
            # spellchecker:off
            SemanticClass.BOUNDARY_RESOURCE: r"(context|resource|handle.*|conn.*|db.*|socket.*|file.*|network.*|mem.*|life\w+)\w+(manager?|life\w+|alloc|dealloc|open|close|read|write|conn(ect)?|disconn(ect)?|query|op(erations?)?|transact(ions?)?|stream|buffer|cache)|(resource|handle.*|conn.*|db.*|socket.*|file.*|network.*|mem.*).*(def(inition)?|declaration|statement)",
            # spellchecker:on
            SemanticClass.DOCUMENTATION_STRUCTURED: r"(docstrings?|jsdoc|api|javadoc|r(ust)?doc|kdoc|contract|doc$|specification|spec|comments?|func(tion)?|method|class|interface|trait|protocol|abstract|signature|document.*)\w*(def(inition)?|declaration|statement|block|header|section|comments?)|.*swagger\w*|\w*openapi\w*|\w*apidoc\w*|\w*raml\w*|\w*apiary\w*|\w*postman\w*|\w*json\w*schema\w*",
            # Import/dependency patterns are handled by BOUNDARY_MODULE above
            # Tier 3: CONTROL_FLOW_LOGIC
            SemanticClass.FLOW_BRANCHING: r"(<branching>|if\s?then|then|if\s?else|else\s?if|if|else|elif|switch|case|match|condition(al)?|guard|when|and\s?then)\w+(def(inition)?|declaration|statement|block|expression)",
            SemanticClass.FLOW_ITERATION: r"(<looping>|for\s?each|for|for\s?in|iter(at(e|or|ion))?|for\s?to|for|while|par\s?each|chain|loop|for\s?each|repeat|until|do\s?while|do|gen(er(at(e|or|ion)))?).*(def(inition)?|declaration|statement|block|expression)",
            # Around here we can start being more aggressive with matching, because false positives will have less impact due to weighting
            SemanticClass.FLOW_CONTROL: r".*(return|yield|yield\s?(while|for|until|from)|break|control|stop|continue|goto|exit|abort).*",
            SemanticClass.FLOW_ASYNC: r".*(async\w+|await|defer|aexit|aenter|spawn|tasks?|coroutine|channel|select|promise|future|concurrent|parallel|multiproc\w+|workers?|thread(ing)?s?|mutex|lock|semaphore|atomic).*",
            # Tier 4: OPERATIONS_EXPRESSIONS
            SemanticClass.OPERATION_INVOCATION: r".*(call\w*|invoke\w*|apply\w*|exec\w*|run\w*|perform\w*|signal|start|emit\w*|dispatch\w*|trigger\w*|spawn\w*|send\w*|post\w*).*",
            SemanticClass.OPERATION_DATA: r".*(let|var\w*|const\w*|declare|define|properties|private|public|pub\w+|hidden|name||access\w*|assign\w*|update\w*|set\w*|get\w*|fetch\w*|put\w*|insert\w*|delete\w*|remove\w*|pop\w*|push\w*|append\w*|prepend\w*|slice\w*|index\w*|map\w*|filter\w*|reduce\w*|fold\w*|collect\w*|collect|concat\w*).*",
            SemanticClass.OPERATION_OPERATOR: r".*(binary|unary|arith(metic|matic)|comparison|integral|diff|matrix|matric\w*|array\w*|logical|bitwise|math\w*|calc\w*|compute\w*|eval\w*|sum\w*|subtract\w*|multiply\w*|divide\w*|modulo\w*|exponent\w*|increment\w*|decrement\w*|negate\w*|compare\w*|equal\w*|less\w*|greater\w*|and\w*|or\w*|not\w*|xor\w*|shift\w*|count|enumerate|pipe|expand|expansion|un(wind|pack|wrap)).*",
            SemanticClass.EXPRESSION_ANONYMOUS: r".*(lambda|closure|block|inline|immediate|self-invoking|self-executing|iife|anon|unnamed|let\s?while).*",
            # Tier 5: SYNTAX_REFERENCES
            SemanticClass.SYNTAX_IDENTIFIER: r"\w*(var\w*|let\w*|const\w*|id\w*|val\w*|name|sym.*|attr\w*|access\w*|field\w*|prop\w*|prop\w*|index\w*|idx|key\w*|key\w*|param\w*|arg\w*(?!.+list)|kwarg\w*)\w*",
            SemanticClass.SYNTAX_LITERAL: r"\w*(str|char|int|float|double|bool(ean)?|true|literal|int.+|float.+|false|null|nil|none|undef(ined)?|void|number|numeric|bigint|byte|long|array|bytes?|array\w*|list\w*|dict\w*|map\w*|set\w*|tuple\w*|obj\w*|struct\w*|enum\w*|variant\w*|date.*|time.*|size.*|\u0000|empty\w*|zero|complex|decimal)\w+",
            SemanticClass.SYNTAX_ANNOTATION: r".*(attr\w*|annotation|annotate\w*|decorator|decoration|meta\w*|tag\w*|mark\w*|note\w*|comment\w*|doc\w*|inline|override|\[attribute\]).*",
            SemanticClass.SYNTAX_PUNCTUATION: r".*(punctuation|delimiter|bracket|paren|semicolon|comma|list|arguments|argument_list|args|brace|caret|quot(e|ation)|colon|space|tab|tag|newline|carriage|indent|dedent|backtick|asterix|at|slash|hyphen).*",
        }
        named_groups = {
            cat: self._as_named_group(pat, str(cat)) for cat, pat in category_patterns.items()
        }
        if not type(self)._tiered_group:
            type(self)._tiered_group = tuple(named_groups.values())
        return "|".join(named_groups.values())


_matcher: Matcher | None = None

# Utility functions for caching (standalone to work with lru_cache)


@lru_cache(maxsize=1024)
def match_tier_patterns_cached(
    node_type: str, tier_category: str | ImportanceRank, *, only_syntactic: bool = False
) -> Matched | None:
    """Cached tier pattern matching utility."""
    with contextlib.suppress(AttributeError, ValueError):
        tier = (
            ImportanceRank.from_string(tier_category)
            if isinstance(tier_category, str)
            else (tier_category or None)
        )
        matcher = get_compiled_patterns()
        if (match := matcher.match(node_type, only_syntactic=only_syntactic)) or (
            match := matcher.search(node_type, only_syntactic=only_syntactic)
        ):
            # lower tier number means higher importance (1 is highest, 5 is lowest)
            if tier is None or match.category.tier >= tier:
                return match
            # penalize confidence with tier upgrade
            return Matched(
                match.category, match.confidence * 0.75, match.text, match.obj, match.pattern
            )
    return None


def get_compiled_patterns() -> Matcher:
    """Get the global compiled patterns instance."""
    global _matcher
    if _matcher is None:
        _matcher = Matcher()  # pyright: ignore[reportConstantRedefinition]
    return _matcher
