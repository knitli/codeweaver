# sourcery skip: lambdas-should-be-short, no-complex-if-expressions
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Constants and patterns used in semantic analysis."""

from __future__ import annotations

import logging
import re

from functools import lru_cache
from types import MappingProxyType
from typing import TYPE_CHECKING, TypedDict

from codeweaver.core.language import SemanticSearchLanguage


logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from codeweaver.semantic.classifications import SemanticClass


NAMED_NODE_COUNTS = MappingProxyType({
    231: SemanticSearchLanguage.C_PLUS_PLUS,
    221: SemanticSearchLanguage.C_SHARP,
    192: SemanticSearchLanguage.TYPESCRIPT,
    188: SemanticSearchLanguage.HASKELL,
    183: SemanticSearchLanguage.SWIFT,
    170: SemanticSearchLanguage.RUST,
    162: SemanticSearchLanguage.PHP,
    152: SemanticSearchLanguage.JAVA,
    150: SemanticSearchLanguage.RUBY,
    149: SemanticSearchLanguage.SCALA,
    133: SemanticSearchLanguage.C_LANG,
    130: SemanticSearchLanguage.PYTHON,
    125: SemanticSearchLanguage.SOLIDITY,
    121: SemanticSearchLanguage.KOTLIN,
    120: SemanticSearchLanguage.JAVASCRIPT,
    113: SemanticSearchLanguage.GO,
    65: SemanticSearchLanguage.CSS,
    63: SemanticSearchLanguage.BASH,
    51: SemanticSearchLanguage.LUA,
    46: SemanticSearchLanguage.ELIXIR,
    43: SemanticSearchLanguage.NIX,
    20: SemanticSearchLanguage.HTML,
    14: SemanticSearchLanguage.JSON,
    6: SemanticSearchLanguage.YAML,
})
"""Count of top-level named nodes in each language's grammar. It took me awhile to come to this approach, but it's fast, reliable, and way less complicated than anything else I tried. (used to identify language based on tree structure)"""

LANGUAGE_SPECIFIC_TOKEN_EXCEPTIONS = MappingProxyType({
    SemanticSearchLanguage.BASH: {
        "A": "operator",
        "E": "operator",
        "K": "operator",
        "L": "operator",
        "P": "operator",
        "Q": "operator",
        "U": "operator",
        "a": "operator",
        "u": "keyword",  # Shell option
        "k": "keyword",  # Shell option
        "ansi_c_string": "literal",
    },
    SemanticSearchLanguage.C_LANG: {
        'L"': "keyword",
        'U"': "keyword",
        'u"': "keyword",
        'u8"': "keyword",
        "L'": "keyword",
        "U'": "keyword",
        "u'": "keyword",
        "u8'": "keyword",
        "LR'": "keyword",
        "UR'": "keyword",
        "uR'": "keyword",
        "u8R'": "keyword",
        'LR"': "keyword",
        'UR"': "keyword",
        'R"': "keyword",
        'uR"': "keyword",
        'u8R"': "keyword",
        "raw_string_delimiter": "keyword",
        "system_lib_string": "literal",
    },
    SemanticSearchLanguage.C_PLUS_PLUS: {
        'L"': "keyword",
        'U"': "keyword",
        'u"': "keyword",
        'u8"': "keyword",
        "L'": "keyword",
        "U'": "keyword",
        "u'": "keyword",
        "u8'": "keyword",
        "LR'": "keyword",
        "UR'": "keyword",
        "uR'": "keyword",
        "u8R'": "keyword",
        'LR"': "keyword",
        'UR"': "keyword",
        'R"': "keyword",
        'uR"': "keyword",
        'u8R"': "keyword",
        "literal_suffix": "keyword",
        "raw_string_delimiter": "keyword",
        "system_lib_string": "literal",
    },
    SemanticSearchLanguage.C_SHARP: {
        "string_literal_encoding": "keyword",
        "raw_string_start": "keyword",
        "raw_string_end": "keyword",
        "interpolation_brace": "punctuation",  # { } in $"{value}"
        "interpolation_format_clause": "literal",
        "interpolation_quote": "punctuation",  # quotes in interpolation
        "verbatim_string_literal": "literal",
    },
    SemanticSearchLanguage.CSS: {
        "function_name": "identifier",
        "keyword_separator": "punctuation",
        "namespace_name": "identifier",
        "nesting_selector": "operator",  # & in SCSS/modern CSS
        "property_name": "identifier",
        "selector": "identifier",
        "plain_value": "literal",
        "tag_name": "identifier",
        "unit": "literal",
        "universal_selector": "operator",  # * selector
    },
    SemanticSearchLanguage.GO: {"blank_identifier": "keyword"},
    SemanticSearchLanguage.HTML: {
        "attribute_name": "identifier",
        "tag_name": "identifier",  # div, span, etc.
    },
    SemanticSearchLanguage.TYPESCRIPT: {"unique symbol": "identifier"},
    SemanticSearchLanguage.JSX: {
        "unique symbol": "identifier",
        "...": "operator",
        "static get": "keyword",  # method modifier syntax
        "optional_chain": "operator",
        "regex_flags": "literal",
        "regex_pattern": "literal",
        "jsx_text": "literal",
    },
    SemanticSearchLanguage.JAVASCRIPT: {
        "...": "operator",
        "static get": "keyword",  # method modifier syntax
        "optional_chain": "operator",
        "regex_flags": "literal",
        "regex_pattern": "literal",
    },
    SemanticSearchLanguage.RUBY: {
        "instance_variable": "identifier",
        "simple_symbol": "identifier",
        "defined?": "keyword",
        r"%w": "keyword",
        r"%i": "keyword",
        "i": "keyword",  # String suffix for immutable
        "r": "keyword",  # Regex prefix
        "ri": "keyword",  # Combined
    },
    SemanticSearchLanguage.RUST: {
        "macro_rule!": "keyword",
        "inner_doc_comment_marker": "literal",
        "outer_doc_comment_marker": "literal",
    },
    SemanticSearchLanguage.SOLIDITY: {
        "evmasm": "keyword",
        "int": "keyword",
        # Add Solidity bytes types
        **{f"bytes{i}": "keyword" for i in range(1, 33)},
        **{f"int{bits}": "keyword" for bits in range(8, 257, 8)},
        **{f"uint{bits}": "keyword" for bits in range(8, 257, 8)},
    },
    SemanticSearchLanguage.PHP: {
        "php_tag": "keyword",
        "php_end_tag": "keyword",
        "yield_from": "keyword",
        "@": "keyword",
        "name": "identifier",  # PHP name token
        "list": "keyword",
    },
    SemanticSearchLanguage.JAVA: {"non-sealed": "keyword"},
    SemanticSearchLanguage.KOTLIN: {
        "as?": "keyword",
        "return@": "keyword",
        "super@": "keyword",
        "this@": "keyword",
    },
    SemanticSearchLanguage.SWIFT: {
        r"unowned\(safe\)": "keyword",
        r"unowned\(unsafe\)": "keyword",
        "u": "keyword",  # Swift string prefix
        "raw_str_continuing_indicator": "keyword",
        "raw_str_end_part": "keyword",
        "raw_str_interpolation_start": "keyword",
        "raw_str_part": "keyword",
        "str_escaped_char": "keyword",
        "line_str_text": "literal",
        "multi_line_str_text": "literal",
    },
    SemanticSearchLanguage.PYTHON: {
        "__future__": "keyword",
        "exec": "keyword",
        "keyword_separator": "keyword",
        "line_continuation": "keyword",
        "nonlocal": "keyword",
        "pass": "keyword",
        "positional_separator": "keyword",
        "type_conversion": "keyword",
        "wildcard_import": "keyword",
        "import_prefix": "keyword",
        "escape_interpolation": "keyword",
    },
    SemanticSearchLanguage.HASKELL: {
        "d": "keyword",
        "e": "keyword",
        "i": "keyword",
        "t": "keyword",
        "unboxed_unit": "keyword",
    },
    SemanticSearchLanguage.NIX: {
        "dollar_escape": "literal",
        "ellipsis": "operator",
        "float_expression": "literal",
        "integer_expression": "literal",
        "spath_expression": "literal",
        "uri_expression": "literal",
    },
})
"""Exceptions to the general rules for token classification. These are language-specific tokens that would otherwise be misclassified by the regex patterns below and other classification logic."""


class TokenPatternCacheDict(TypedDict):
    """TypedDict for token pattern cache."""

    operator: re.Pattern[str] | None
    literal: re.Pattern[str] | None
    identifier: re.Pattern[str] | None
    annotation: re.Pattern[str] | None
    keyword: re.Pattern[str] | None
    not_symbol: re.Pattern[str] | None


_token_pattern_cache: TokenPatternCacheDict = {}.fromkeys(  # ty: ignore[invalid-assignment]
    ("operator", "literal", "identifier", "annotation", "keyword", "not_symbol"), None
)

# spellchecker:off
IS_OPERATOR = r"""^
        (?:(
            (
                [\+\-\*/%&?|\^~!=<>]+
            )
            |
            \.\.\.|not\sin|in|-(a|o)|!?i(n|s)|as(!|\?)|is|gt|(bit)?(and|xor|or)|not|lt|le|ge|eq|not_eq|s?div|x?or_eq
            |
            \w+_operator
        ))
        $"""
"""Not perfect but should get us >95% with a couple false positives."""


def _get_operator_pattern() -> re.Pattern[str]:
    """Compile and return the operator regex pattern."""
    return re.compile(IS_OPERATOR, re.VERBOSE | re.IGNORECASE)


NOT_SYMBOL = r"""^
                        (?:
                            (
                                [a-z_][a-z0-9_]*
                                |
                                [#@_][a-z0-9_]+
                            )
                        )
                    $"""
"""Rough approximation of what is NOT a symbol (identifier, keyword, etc). Accounts for @ in C# and # in preprocessor directives."""


def _get_not_symbol_pattern() -> re.Pattern[str]:
    """Compile and return the not-symbol regex pattern."""
    return re.compile(NOT_SYMBOL, re.VERBOSE | re.IGNORECASE)


IS_LITERAL = r"""^
    (?:(
        # Boolean literals
        [Tt]rue|[Ff]alse
        |
        # Null/nil/none literals
        [nN](ull(ptr)?|il|one(Type)?)
        |
        # Numeric and general literals
        (\(\))?|const(expr)?|0x[0-9a-f]+|\d+(\.\d+)?|\\x00|1|.*literal.*
        |
        # Type names (when used as literals)
        array|object|string|char(acter)?|float(ing)?|double|bool(ean)?|int(eger)?|long|short|byte(s)?|regexp?|rune|decimal|bigint|symbol|wildcard|uint(eger)?|void
        |
        primitive_type|predefined_type|floating_point_type|boolean_type|integral_type|void_type|bottom_type|never_type|unit_type|this_type
        |
        # String content and fragments
        (ansi_c_)?string_(content|fragment|start|end)|raw_(string|text)(_content)?|escape_sequence
        |
        heredoc_(content|beginning)|multiline_string_fragment|nowdoc_string|quoted_content|text_fragment
        |
        # Numeric tokens and expressions
        (yul_)?(decimal|hex|octal)_number|color_value|number(_unit)?
        |
        (float|integer|unit)_expression
        |
        # Fragments and paths
        path_fragment|string_literal_encoding
        |
        # HTML/CSS content
        (html_character_reference|entity|raw_text|text|jsx_text)
        |
        # Undefined special value
        undefined
    ))
    $"""
"""Literal tokens in supported languages."""


def _get_literal_pattern() -> re.Pattern[str]:
    """Compile and return the literal regex pattern."""
    return re.compile(IS_LITERAL, re.VERBOSE | re.IGNORECASE)


IS_IDENTIFIER = r"""^
    (?:(
        \w*identifier\w*
        |
        attribute(_name|value)
        |
        (speci(fic|al)_)?variable(_name)?
        |
        field(_name)?|function(_name)?|method(_name)?|property(_name)?|class(_name)?
        |
        interface(_name)?|module(_name)?|namespace(_name)?|type(_name)?
        |
        constant(_name)?|enum(_name)?|struct(_name)?|trait(_name)?|union(_name)?
        |
        parameter(_name)?|argument(_name)?|label(_name)?|macro(_name)?|symbol(_name)?
        |
        name|value
    ))
    $"""
"""Identifier patterns covering variables, functions, classes, modules, properties, and similar constructs."""


def _get_identifier_pattern() -> re.Pattern[str]:
    """Compile and return the identifier regex pattern."""
    return re.compile(IS_IDENTIFIER, re.VERBOSE | re.IGNORECASE)


IS_ANNOTATION = r"""^
    (?:(
        # C/C++/C#/CSS preprocessor directives
        \#(ifdef|ifndef|include|elifndef|elifdef|elseif|error|line|nullable|defined?|el(if((in)?def)?|se)?|end(if|region)|region|if|pragma|undef|warning)?
        |
        # CSS/Swift at-rules and decorators
        @(autoclosure|charset|import|interface|media|namespace|scope|supports|escaping|keyframes)?
        |
        # Compiler attributes and calling conventions
        (__)?
            (alignof|attribute|asm|based|cdecl|clrcall|declspec|except|extension|fastcall|finally|forceinline|inline|leave|makeref|reftype|refvalue|restrict|stdcall|thiscall|thread|try|unaligned|vectorcall|volatile)
        (__)?
        |
        # Underscore-prefixed attributes
        _(Alignas|Alignof|Atomic|Generic|Nonnull|Noreturn|alignof|expression|modify|unaligned)
        |
        # Calling conventions
        (Cdecl|Fastcall|Stdcall|Thiscall|staticcall|Vectorcall)
        |
        # Swift compiler directives and attributes
        (canImport|dsohandle|externalMacro|fileID|filePath|targetEnvironment|unavailable|arch|available|column|compiler|diagnostic|line|os)
        |
        # Haskell pragmas
        (cpp|haddock|pragma)
        |
        # Kotlin annotations
        (annotation|field|param|receiver|use_site_target)
        |
        # PHP pragmas
        (strict_types|ticks)
        |
        # Rust macro metadata
        (fragment_specifier|metavariable|shebang)
        |
        # Elixir sigil modifiers
        sigil_modifiers
        |
        # C# attributes and preprocessor
        (attribute_target_specifier|annotations|checksum|enable|restore|shebang_directive|warning|warnings)
        |
        # CSS at-rules
        at_keyword
        |
        # HTML document metadata
        doctype
        |
        # JavaScript/TypeScript meta
        meta_property
        |
        # C/C++ alignment and preprocessor
        (alignas|defined)
        |
        # Explicit preprocessor patterns
        preproc_(arg|directive|nullable)
    ))
    $"""
"""Annotation patterns covering compiler directives, attributes, pragmas, and similar constructs."""


def _get_annotation_pattern() -> re.Pattern[str]:
    """Compile and return the annotation regex pattern."""
    return re.compile(IS_ANNOTATION, re.VERBOSE | re.IGNORECASE)


IS_KEYWORD = r"""^(?:
    (?:(
    # Preprocessor directives (C/C++/C#/CSS)
    \#
        (ifdef|ifndef|include|elifndef|elifdef|elseif|error|line|nullable|defined?|el(if((in)?def)?|se)?|end(if|region)|region|if|pragma|undef|warning)?
        |
    # CSS/Swift at-rules and attributes
    @
        (autoclosure|charset|import|interface|media|namespace|scope|supports|escaping|keyframes)?
        |
        # Underscore keywords and special constructs
        _
        |
    # Compiler attributes and calling conventions (C/C++/C#)
    (__)?
        (alignof|attribute|asm|based|cdecl|clrcall|declspec|except|extension|fastcall|finally|forceinline|inline|leave|makeref|reftype|refvalue|restrict|stdcall|thiscall|thread|try|unaligned|vectorcall|volatile)
        (__)?
        |
    _
        (Alignas|Alignof|Atomic|Generic|Nonnull|Noreturn|alignof|expression|modify|unaligned)
        |
    # Calling conventions (C#/Windows)
    Cdecl|Fastcall|Stdcall|Thiscall|staticcall|Vectorcall
        |
    # Swift-specific
    Protocol|Type|associatedtype|bang|borrowing|canImport|consuming|convenience|deinit|didSet|distributed|dsohandle|externalMacro|fileID|filePath|indirect|init|mutating|nonisolated|nonmutating|ownership_modifier|postfix|precedencegroup|prefix|some|subscript|swift|targetEnvironment|throw_keyword|willSet|arch|available|column|compiler|diagnostic|line|os
        |
    # Solidity-specific
    anonymous|any_source_type|basefee|blobbasefee|blobfee|blobhash|call(code|data(copy|load|size)?|value)?|caller|chainid|coinbase|contract|create2?|delegatecall|emit|enum_value|error|ether|event|extcode(copy|hash|size)|fallback|finney|gas(limit|price)?|gwei|immutable|indexed|invalid|iszero|keccak256|layout|library|log[0-9]|mapping|mcopy|memory|modifier|m(load|size|store8?)|mul(mod)?|number_unit|origin|pop|pragma_value|prevrandao|receive|returndata(copy|size)|returns?|revert|s(ar|elfbalance|elfdestruct|gt|hl|hr|ignextend|load|lt|mod|olidity(_version)?|t(imestamp|load|store)|ufixed|unicode|visibility|wei|yul_(boolean|break|continue|decimal_number|evm_builtin|hex_number|leave)|days|hours|minutes|seconds|weeks|years
        |
    # Haskell-specific
    abstract_family|all_names|anyclass|calling_convention|cases|cpp|d|data|deriving(_strategy)?|e|empty_list|family|foreign|forall|group|haddock|implicit_variable|import_package|infix[lr]?|instance|label|layout|mdo|module_id|name|newtype|nominal|pattern|phantom|prefix_(list|tuple|unboxed_(sum|tuple))|qualified|quasiquote_body|rec|representational|role|safety|star|stock|t|type_role|unit|variable
        |
    # Kotlin-specific
    actual|annotation|companion|crossinline|data|delegate|expect|field|final|infix|init|inner|internal|lateinit|noinline|operator|out|param|receiver|reified|reification_modifier|sealed|suspend|tailrec|use_site_target|val|value|vararg
        |
    # Scala-specific
    derives|end|erroneous_end_tag_name|extension|final|given|implicit|inline_modifier|into_modifier|macro|namespace_wildcard|opaque(_modifier)?|open(_modifier)?|tracked(_modifier)?|transparent_modifier|using_directive_(key|value)
        |
    # Ruby-specific
    BEGIN|END|alias|class_variable|ensure|forward_(argument|parameter)|global_variable|hash_(key_symbol|splat_nil)|heredoc_beginning|next|redo|rescue|retry|undef|uninterpreted
        |
    # PHP-specific
    bottom_type|cast_type|enddeclare|endfor|endforeach|endif|endswitch|endwhile|final(_modifier)?|include_once|operation|parent|php_(end_)?tag|readonly_modifier|relative_scope|require_once|strict_types|ticks|var_modifier|variadic_placeholder
        |
    # Rust-specific
    block|crate|dyn|expr(_20[1-2][0-9])?|fragment_specifier|ident|item|not|metavariable|mutable_specifier|never_type|pat(_param)?|path|pub|raw|remaining_field_pattern|shebang|stmt|tt|ty|unit_(expression|type)|vis
        |
    # Go-specific
    dot|fallthrough_statement|go|iota|label_name|range
        |
    # Elixir-specific
    after|alias|atom|end|rescue|sigil_modifiers|when
        |
    # Bash-specific
    file_descriptor|k|special_variable_name|u|variable_name|word
        |
    # C#-specific
    accessibility_modifier|alias|annotations|attribute_target_specifier|checked|checksum|constructor_constraint|delegate|descending|discard|empty_statement|enable|equals|field|fixed|group|implicit(_parameter|_type)?|internal|join|managed|modifier|notnull|on|orderby|param|params|partial|record|remove|required|restore|scoped|shebang_directive|sizeof|typevar|unmanaged|warning|warnings|when
        |
    # Nix-specific
    rec|recursion
        |
    # Lua-specific
    end|vararg_expression
        |
    # CSS-specific
    at_keyword|feature_name|important_value|keyword_query
        |
    # HTML-specific
    attribute_value|doctype
        |
    # JavaScript/TypeScript-specific
    accessibility_modifier|asserts|debugger_statement|existential_type|infer|meta_property|never|override_modifier|satisfies|target|this(_type)?|unknown
        |
    # Java-specific
    asterisk|exports|final|permits|provides|record|requires_modifier|strictfp|underscore_pattern|uses|when
        |
    # Modifiers (cross-language patterns)
    \w*_modifier|access_specifier|function_modifier|inheritance_modifier|member_modifier|parameter_modifier|platform_modifier|property(_behavior)?_modifier|state_(location|mutability)|storage_class_specifier|usage_modifier|variance_modifier|visibility_modifier
        |
    # Statement patterns
    break|continue|debugger|empty|fallthrough|pass|seh_leave)(_statement)?
        |
    # Method/function clauses
    (default|delete|pure_virtual)(_method)?_clause|gnu_asm_qualifier
        |
    # C/C++ storage and qualifiers
    alignas|and_eq|auto|defined|register|thread_local|variadic_parameter
        |
    # Preprocessor patterns
    preproc_(arg|directive|nullable)
        |
    # Declaration patterns
    (global|private)_module_fragment_declaration
        |
    # Common cross-language keywords (expanded for readability)
    # A-C keywords
    abstract|accessor|actor|add|addmod|address|alignof|all|any|ascending
        |
    assembly|assert|async|as|at|await
        |
    balance|base|begin|blockhash|bool|boolean|break|break_statement
        |
    by|bytes|bytes[1-3][0-9]?
        |
    case|catch|catch_keyword
        |
    chan|char|character
        |
    class|clone
        |
    co_await|co_return|co_yield|compl|concept|consteval
        |
    const|constant|constinit|constructor|continue
        |
    # D keywords
    debug|debugger|declare|def|default|default_keyword|defer|delete|decltype
        |
    difficulty|disable|do|done|dyn|dynamic
        |
    # E keywords
    each|echo|elif|ellipsis|else|else\sif|else if
        |
    enable|enabled|endswitch|endfor|endforeach|enddeclare|endif|endwhile
        |
    enum|esac|encoding|expect|extends
        |
    except|expect|export|explicit|exit|extern(al)?|extglob_pattern
        |
    # F keywords
    fallthrough
        |
    file|file_description|fileprivate|final|finally|finish|fixed|friend|fully_open_range
        |
    float|fn|func|function
        |
    for(ever|each|modifier)?
        |
    from
        |
    # G-L keywords
    gen|get|getter|global|goto|guard
        |
    hash_bang_line|heredoc(_end|_start)?|hex|hiding|hidden
        |
    id_name|if|impl|implements|import|important
        |
    in|include|inherits?|inlines?|inout|input|internal_ref
        |
    instance(of)?|instead|integer|interface|into
        |
    key|keyof|keyPath|keyframes?|keyframe_name|keyword
        |
    lambda|lambda_default_capture|lambda_specifier
        |
    lazy|let|lifetime|lock|log[1-9]|long
        |
    local|loop
        |
    # M-P keywords
    map|match|meta|method|mod(ule)?|move|mutable
        |
    namespace|native|new|noexcept|noreturn
        |
    of|offsetof|only|open|opens|operator|option|optional|or_eq|override
        |
    package|payable|pragma|private|print|property|protected|protocol|public|pure
        |
    # R keywords
    raise|readonly|ref|ref_qualifier
        |
    repeat|replace|require|requires|restrict|return
        |
    readonly_modifier|reference_modifier
        |
    # S keywords
    sealed|seconds|select|self|self_expression|set|setter|setparam
        |
    Se|Sealed|Seconds|Select|Self|Set|Setter|Setparam
        |
    shebang|shebang_line|short|sigil_name|signed|sized|stackalloc
        |
    start|static|static_assert|static_modifier|statement_label
        |
    string|struct|super|super_expression|switch|synchronized
        |
    # T keywords
    template|then|this|throw|throws|to
        |
    transient|transitive|transparent|trait|try
        |
    type|typeOf|typeof|typealias|typedef|typename|typeset
        |
    # U keywords
    unchecked|unless|union|unmanaged|unowned|unsafe|unset|unsigned|until|unsetenv
        |
    use|used|using
        |
    # V keywords
    var|via|view|virtual|virtual_specifier|void|volatile
        |
    # W-Y keywords
    weak|where|where_keyword|wildcard_import|wildcard_pattern|with|while
        |
    yield|yield\sfrom
    )))
    $"""
"""Comprehensive keyword pattern covering all supported languages. (7300 characters!)"""
# spellchecker:on


def _get_keyword_pattern() -> re.Pattern[str]:
    """Compile and return the keyword regex pattern."""
    return re.compile(IS_KEYWORD, re.VERBOSE)


def get_token_patterns_sync() -> TokenPatternCacheDict:
    """Get token patterns with lazy initialization.

    Patterns are compiled synchronously on first call and cached thereafter.
    This is typically called during module initialization before async operations begin.

    The compilation is a one-time operation (~10-50ms) that happens on first access.
    All subsequent calls return the cached patterns immediately.

    Returns:
        TokenPatternCacheDict: Compiled regex patterns for token classification
    """
    global _token_pattern_cache

    # Fast path: return cached patterns
    if _token_pattern_cache.get("operator") is not None:
        return _token_pattern_cache

    # Slow path: compile patterns synchronously (one-time only)
    operator_pat = _get_operator_pattern()
    literal_pat = _get_literal_pattern()
    identifier_pat = _get_identifier_pattern()
    annotation_pat = _get_annotation_pattern()
    keyword_pat = _get_keyword_pattern()
    not_symbol_pat = _get_not_symbol_pattern()

    _token_pattern_cache = TokenPatternCacheDict(
        operator=operator_pat,
        literal=literal_pat,
        identifier=identifier_pat,
        annotation=annotation_pat,
        keyword=keyword_pat,
        not_symbol=not_symbol_pat,
    )
    return _token_pattern_cache


TypeScriptLangs = frozenset({SemanticSearchLanguage.TYPESCRIPT, SemanticSearchLanguage.TSX})
JavaScriptLangs = frozenset({SemanticSearchLanguage.JAVASCRIPT, SemanticSearchLanguage.JSX})
JavaScriptFamily = TypeScriptLangs | JavaScriptLangs

# ========== OPTIMIZED COMPOSITE CHECK PATTERNS ==========
# Grouped by language and classification for ~10-15x faster classification
# Original: 145 individual checks | Optimized: 26 language groups + 10 generic patterns + 2 predicates
# Patterns stored as raw strings and compiled lazily on first use for faster imports

# Language-specific pattern groups (raw strings)
# Structure: {Language: tuple[(SemanticClass, pattern_string), ...]}
_LANG_SPECIFIC_PATTERNS_RAW: dict[SemanticSearchLanguage, tuple[tuple[str, str], ...]] = {
    SemanticSearchLanguage.BASH: (
        ("SYNTAX_KEYWORD", r"^(?:(?:(command_name|do_group|case_item|herestring_redirect)))$"),
        ("SYNTAX_PUNCTUATION", r"^(?:(?:(file_redirect|subscript)))$"),
    ),
    SemanticSearchLanguage.C_LANG: (
        (
            "BOUNDARY_MODULE",
            r"^(?:(?:(imports?(?:_(?:(directive|list|name|specifier))?)|linkage_specification)|(?:module_export)))$",
        ),
        (
            "DEFINITION_DATA",
            r"^(?:(?:(init_declarator|initializer_pair|subscript_range_designator|preproc_params))|(?:.+_designator))$",
        ),
        ("DEFINITION_TYPE", r"^(?:(?:(enumerator|bitfield_clause)))$"),
        # spellchecker:off
        ("FLOW_BRANCHING", r"^(?:(?:(switch(_case|_default)|seh_(except|finally)_clause)))$"),
        ("BOUNDARY_ERROR", r"^(?:(?:seh_except_clause))$"),
        ("BOUNDARY_RESOURCE", r"^(?:(?:seh_finally_clause))$"),
        # spellchecker:on
        ("OPERATION_OPERATOR", r"^(?:(?:comma_expression))$"),
        (
            "SYNTAX_ANNOTATION",
            r"^(?:(?:gnu_asm_(?:(clobber_list|goto_list|input_operand(_list)?|output_operand(_list)?)))|(?:(preproc_(?:(call|def|function_def|include|else|if))))|(?:attribute))$",
        ),
    ),
    SemanticSearchLanguage.C_PLUS_PLUS: (
        (
            "BOUNDARY_MODULE",
            r"^(?:(?:(imports?(?:_(?:(directive|list|name|specifier))?)|linkage_specification)|(?:module_export)))$",
        ),
        (
            "DEFINITION_DATA",
            r"^(?:(?:(lambda_capture_initializer|preproc_params))|(?:(init_declarator|initializer_pair|subscript_range_designator))|(?:.+_designator))$",
        ),
        (
            "DEFINITION_TYPE",
            r"^(?:(?:(alias_declaration|concept_definition|new_declarator|pointer_type_declarator|namespace_alias_definition|lambda_declarator|friend_declaration|simple_requirement|init_statement|module_(name|partition)|trailing_return_type|explicit_object_parameter_declaration|base_class_clause|bitfield_clause|dependent_name|compound_requirement|requirement_seq|variadic_declarator))|(?:optional_type_parameter_declaration)|(?:enumerator))$",
        ),
        # spellchecker:off
        (
            "FLOW_BRANCHING",
            r"^(?:(?:(switch(_case|_default)|seh_(except|finally)_clause))|(?:catch_(?:(clause|declaration)))|(?:condition_clause))$",
        ),
        ("BOUNDARY_ERROR", r"^(?:(?:seh_except_clause))$"),
        ("BOUNDARY_RESOURCE", r"^(?:(?:seh_finally_clause))$"),
        # spellchecker:on
        ("OPERATION_OPERATOR", r"^(?:(?:comma_expression))$"),
        (
            "SYNTAX_ANNOTATION",
            r"^(?:(?:gnu_asm_(clobber_list|goto_list|input_operand(?:_list)?|output_operand(?:_list)?))|(?:(consteval_block|static_assert)_declaration)|(?:preproc_(call|def|function_def|include|if))|(?:(attribute|preproc_else)))$",
        ),
    ),
    SemanticSearchLanguage.C_SHARP: (
        ("BOUNDARY_MODULE", r"^(?:(?:file_scoped_namespace_declaration))$"),
        ("DEFINITION_TYPE", r"^(?:(?:type_parameter_constraints_clause))$"),
        ("FLOW_BRANCHING", r"^(?:(?:catch_(?:(clause|declaration))))$"),
        ("OPERATION_OPERATOR", r"^(?:(?:(unary|declaration)_expression))$"),
        (
            "SYNTAX_ANNOTATION",
            r"^(?:(?:preproc_(?:(region|endregion|define|else|if)))|(?:[Aa]ttribute))$",
        ),
        ("SYNTAX_IDENTIFIER", r"^(?:(?:member_binding_expression|tuple_element))$"),
        (
            "SYNTAX_KEYWORD",
            r"^(?:(?:primary_constructor_base_type|parenthesized_variable_designation|arrow_expression_clause|subpattern|positional_pattern_clause|property_pattern_clause|interpolation_alignment_clause|argument|global_attribute|join_into_clause))$",
        ),
        ("DEFINITION_DATA", r"^(?:(?:parameter))$"),
    ),
    SemanticSearchLanguage.CSS: (
        ("SYNTAX_IDENTIFIER", r"^(?:(?:.+_selector))$"),
        ("SYNTAX_KEYWORD", r"^(?:(?:at_rule|class_name|rule_set|selectors))$"),
        ("SYNTAX_LITERAL", r"^(?:(?:.+_(query|statement|value)))$"),
    ),
    SemanticSearchLanguage.ELIXIR: (
        ("OPERATION_INVOCATION", r"^(?:call)$"),
        ("OPERATION_OPERATOR", r"^(?:(?:(access_call|unary_operator)))$"),
        ("SYNTAX_IDENTIFIER", r"^(?:(?:pair(?:_pattern)?))$"),
        (
            "SYNTAX_LITERAL",
            r"^(?:(?:(bitstring|body|charlist|keywords|map_content|sigil|source|quoted_(?:(atom|keyword)))))$",
        ),
    ),
    SemanticSearchLanguage.GO: (
        (
            "BOUNDARY_MODULE",
            r"^(?:(?:(imports?(_(directive|list|name|specifier))?|linkage_specification)))$",
        ),
        ("DEFINITION_TYPE", r"^(?:(?:(implicit_length_array_type|method_elem|keyed_element)))$"),
        ("FLOW_BRANCHING", r"^(?:(?:communication_case|default_case|literal_(element|value)))$"),
        (
            "FLOW_ITERATION",
            r"^(?:(?:for(_clause|_in_clause|_numeric_clause)?)|(?:(range_clause|receive_statement)))$",
        ),
    ),
    SemanticSearchLanguage.HASKELL: (
        ("DEFINITION_CALLABLE", r"^(?:function)$"),
        (
            "BOUNDARY_MODULE",
            r"^(?:(?:(imports?(?:_(?:(directive|list|name|specifier))?)|(?:linkage_specification)|(?:module_export))))$",
        ),
        (
            "DEFINITION_DATA",
            r"^(?:(?:(lazy|strict)_field|(?:declarations))|(?:(binding|binding_set|binding_list|local_binds))|(?:(equations|children|fields?|header|match|prefix|qualifiers|quoted_decls)))$",
        ),
        (
            "DEFINITION_TYPE",
            r"^(?:(?:(fundep|fundeps|kind_application|field_path))|(?:(full_)?enum(?:(erators?|_case|_assignment|_entry)))|(?:instance_declarations)|(?:class_(?:(body|declarations?)))|(?:(associated_type|constructor_synonym|explicit_type|gadt_constructors?|newtype_constructor))|(?:unboxed_(?:(sum|tuple))))$",
        ),
        (
            "FLOW_BRANCHING",
            r"^(?:(?:match(_conditional_expression|_default_expression)|(patterns))|(?:(alternative|alternatives)))$",
        ),
        ("FLOW_ITERATION", r"^(?:(?:do_(block|module)))$"),
        ("OPERATION_INVOCATION", r"^(?:(?:(construct_signature|data_constructors?|apply)))$"),
        ("OPERATION_OPERATOR", r"^(?:(?:quasiquote|splice))$"),
        (
            "SYNTAX_KEYWORD",
            r"^(?:(?:(annotated|constructor_synonyms|equation|quoter|field_(name|update)|function_head_parens|haskell|inferred|infix_id|special|quantified_variables|type_(params?|patterns?)|guards?)))$",
        ),
        ("SYNTAX_IDENTIFIER", r"^(?:(?:prefix_id))$"),
        ("SYNTAX_LITERAL", r"^(?:(?:(constructor_synonyms?|literal)))$"),
        ("SYNTAX_PUNCTUATION", r"^(?:parens)$"),
    ),
    SemanticSearchLanguage.JAVA: (
        ("BOUNDARY_ERROR", r"^(?:(?:catch_type))$"),
        ("BOUNDARY_RESOURCE", r"^(?:(?:resource_specification))$"),
        ("DEFINITION_DATA", r"^(?:(?:(inferred_parameters|receiver_parameter)))$"),
        ("DEFINITION_TYPE", r"^(?:(?:(dimensions(_expr)?|enum_body_declarations|superclass)))$"),
        ("FLOW_BRANCHING", r"^(?:(?:record_pattern_component|guard))$"),
        ("SYNTAX_KEYWORD", r"^(?:(?:modifiers|wildcard))$"),
        ("SYNTAX_ANNOTATION", r"^(?:(?:marker_annotation|element_value_pair|attribute))$"),
        ("SYNTAX_LITERAL", r"^(?:(?:string_interpolation))$"),
    ),
    SemanticSearchLanguage.HTML: (
        ("SYNTAX_ANNOTATION", r"^(?:(?:(attribute|quoted_attribute_value)))$"),
        (
            "SYNTAX_PUNCTUATION",
            r"^(?:(?:(element|script_element|style_element))|(?:erroneous_end_tag)|(?:(start|end|self_closing)_tag))$",
        ),
    ),
    SemanticSearchLanguage.TYPESCRIPT: (
        (
            "BOUNDARY_MODULE",
            r"^(?:(?:(imports?(_(directive|list|name|specifier))?|linkage_specification)))$",
        ),
        ("DEFINITION_DATA", r"^(?:(?:class_static_block))$"),
        (
            "DEFINITION_TYPE",
            r"^(?:(?:(full_)?enum(erators?|_case|_assignment|_entry))|(?:class_(body|declarations?)))$",
        ),
        (
            "OPERATION_INVOCATION",
            r"^(?:(?:call_signature)|(?:(construct_signature|data_constructors?)))$",
        ),
        # spellchecker:off
        (
            "FLOW_BRANCHING",
            r"^(?:(?:finally_clause)|(?:(switch(_case|_default)|seh_(except|finally)_clause))|(?:catch_(clause|declaration)))$",
        ),
        # spellchecker:on
        (
            "SYNTAX_IDENTIFIER",
            r"^(?:(?:assignment_pattern)|(?:(variable(_declarator|_declaration|_list))|value_binding_pattern)|(?:(nested_identifier|field_definition|object_assignment_pattern))|(?:(jsx_(attribute|expression|namespace_name)|namespace_(import|export)|named_imports|import_require_clause|constraint|default_type|rest_type|class_heritage|computed_property_name|sequence_expression))|(?:pair(_pattern)?))$",
        ),
        ("SYNTAX_ANNOTATION", r"^(?:(?:((asserts|type_predicate)_annotation)))$"),
        ("SYNTAX_LITERAL", r"^(?:(?:jsx_(closing|opening)_element))$"),
    ),
    SemanticSearchLanguage.JSX: (
        (
            "BOUNDARY_MODULE",
            r"^(?:(?:(imports?(_(directive|list|name|specifier))?|linkage_specification)))$",
        ),
        ("DEFINITION_DATA", r"^(?:(?:class_static_block))$"),
        (
            "DEFINITION_TYPE",
            r"^(?:(?:(full_)?enum(erators?|_case|_assignment|_entry))|(?:class_(body|declarations?)))$",
        ),
        (
            "OPERATION_INVOCATION",
            r"^(?:(?:call_signature)|(?:(construct_signature|data_constructors?)))$",
        ),
        # spellchecker:off
        (
            "FLOW_BRANCHING",
            r"^(?:(?:finally_clause)|(?:(switch(_case|_default)|seh_(except|finally)_clause))|(?:catch_(clause|declaration)))$",
        ),
        # spellchecker:on
        (
            "SYNTAX_IDENTIFIER",
            r"^(?:(?:assignment_pattern)|(?:(variable(_declarator|_declaration|_list))|value_binding_pattern)|(?:(nested_identifier|field_definition|object_assignment_pattern))|(?:(jsx_(attribute|expression|namespace_name)|namespace_(import|export)|named_imports|import_require_clause|constraint|default_type|rest_type|class_heritage|computed_property_name|sequence_expression))|(?:pair(_pattern)?))$",
        ),
        ("SYNTAX_ANNOTATION", r"^(?:(?:((asserts|type_predicate)_annotation)))$"),
        ("SYNTAX_LITERAL", r"^(?:(?:jsx_(closing|opening)_element))$"),
    ),
    SemanticSearchLanguage.JAVASCRIPT: (
        (
            "BOUNDARY_MODULE",
            r"^(?:(?:(imports?(_(directive|list|name|specifier))?|linkage_specification)))$",
        ),
        ("DEFINITION_DATA", r"^(?:(?:class_static_block))$"),
        (
            "DEFINITION_TYPE",
            r"^(?:(?:(full_)?enum(erators?|_case|_assignment|_entry))|(?:class_(body|declarations?)))$",
        ),
        (
            "OPERATION_INVOCATION",
            r"^(?:(?:call_signature)|(?:(construct_signature|data_constructors?)))$",
        ),
        # spellchecker:off
        (
            "FLOW_BRANCHING",
            r"^(?:(?:finally_clause)|(?:(switch(?:(_case|_default))|seh_(?:(except|finally))_clause))|(?:catch_(?:(clause|declaration))))$",
        ),
        # spellchecker:on
        (
            "SYNTAX_IDENTIFIER",
            r"^(?:(assignment_pattern|variable(?:(_declarator|_declaration|_list))|value_binding_pattern|nested_identifier|field_definition|object_assignment_pattern|jsx_(?:(attribute|expression|namespace_name))|namespace_(?:(import|export))|named_imports|import_require_clause|constraint|default_type|rest_type|class_heritage|computed_property_name|sequence_expression)|pair(?:_pattern)?)$",
        ),
        ("SYNTAX_LITERAL", r"^(?:(?:jsx_(?:(closing|opening))_element))$"),
    ),
    SemanticSearchLanguage.JSON: (("SYNTAX_IDENTIFIER", r"^(?:(?:pair))$"),),
    SemanticSearchLanguage.JSX: (
        (
            "BOUNDARY_MODULE",
            r"^(?:(?:(imports?(?:_(?:(directive|list|name|specifier))?)|linkage_specification)|(?:module_export)))$",
        ),
        ("DEFINITION_DATA", r"^(?:(?:class_static_block))$"),
        (
            "DEFINITION_TYPE",
            r"^(?:(?:(full_)?enum(erators?|_case|_assignment|_entry))|class_(?:(body|declarations?)))$",
        ),
        ("OPERATION_INVOCATION", r"^(?:(?:constructor_(?:(delegation_call|invocation))))$"),
        (
            "EXPRESSION_ANONYMOUS",
            r"^(?:(?:annotated_lambda|anonymous_class|anonymous_function_use_clause))$",
        ),
        ("SYNTAX_ANNOTATION", r"^(?:(?:file_annotation|attribute))$"),
        ("SYNTAX_KEYWORD", r"^(?:(?:modifiers))$"),
    ),
    SemanticSearchLanguage.LUA: (
        ("DEFINITION_DATA", r"^(?:(?:attribute))$"),
        ("FLOW_BRANCHING", r"^(?:(?:(if_)?guards?)|(?:else_(?:(clause|statement))))$"),
        (
            "FLOW_ITERATION",
            r"^(?:(?:for_generic_clause)|(?:for(?:(?:_clause|_in_clause|_numeric_clause)?)))$",
        ),
        ("OPERATION_INVOCATION", r"^(?:method_index_expression)$"),
        (
            "SYNTAX_IDENTIFIER",
            r"^(?:(?:variable(?:(_declarator|_declaration|_list))|value_binding_pattern))$",
        ),
    ),
    SemanticSearchLanguage.NIX: (
        ("DEFINITION_DATA", r"^(?:(?:(binding|binding_set|binding_list|local_binds)))$"),
        (
            "SYNTAX_IDENTIFIER",
            r"^(?:(?:(attrpath|formal|formals|inherit_from|inherited_attrs|interpolation|source_code)))$",
        ),
    ),
    SemanticSearchLanguage.PHP: (
        ("BOUNDARY_MODULE", r"^(?:(?:use_as_clause))$"),
        ("DEFINITION_DATA", r"^(?:(?:property_element|static_variable_declaration|attribute))$"),
        ("DEFINITION_TYPE", r"^(?:(?:(simple_)?enum_case))$"),
        (
            "EXPRESSION_ANONYMOUS",
            r"^(?:(?:annotated_lambda|anonymous_class|anonymous_function_use_clause))$",
        ),
        (
            "FLOW_BRANCHING",
            r"^(?:(?:(finally_clause|default_statement))|(?:match(?:(conditional_expression|default_expression)))|(?:else_(?:(clause|statement)))|case_(?:(clause|statement)))$",
        ),
        ("SYNTAX_ANNOTATION", r"^(?:(?:attribute_group))$"),
        (
            "SYNTAX_IDENTIFIER",
            r"^(?:(?:variable(?:(_declarator|_declaration|_list))|value_binding_pattern))$",
        ),
        (
            "SYNTAX_KEYWORD",
            r"^(?:(?:(anonymous_class|use_instead_of_clause|property_(hook|promotion_parameter)|class_interface_clause|const_element|by_ref|declare_directive|list_literal)))$",
        ),
    ),
    SemanticSearchLanguage.PYTHON: (
        ("BOUNDARY_RESOURCE", r"^(?:(?:with_item))$"),
        (
            "FLOW_BRANCHING",
            r"^(?:(?:(if|unless)_guard)|(?:(block|in_clause|rescue))|(?:case_clause))$",
        ),
        ("DEFINITION_CALLABLE", r"^(?:decorator)$"),
        ("DEFINITION_TYPE", r"^(?:(union_type))$"),
        ("FLOW_ITERATION", r"^(?:for_in_clause)$"),
        ("OPERATION_OPERATOR", r"^(?:(?:dictionary_splat))$"),
        (
            "SYNTAX_IDENTIFIER",
            r"^(?:(?:(exception_variable|exceptions|destructured_(left_assignment|parameter)|rest_assignment|method_parameters|block_parameters|body_statement|bare_(string|symbol)|dotted_name))|(?:pair(_pattern)?))$",
        ),
        (
            "SYNTAX_KEYWORD",
            r"^(?:(?:constrained_type|member_type|parenthesized_list_splat|chevron|if_clause|slice|relative_import|except_clause))$",
        ),
        ("SYNTAX_ANNOTATION", r"^(?:(?:attribute))$"),
        ("SYNTAX_LITERAL", r"^(?:(?:format_expression))$"),
    ),
    SemanticSearchLanguage.RUBY: (
        ("DEFINITION_TYPE", r"^(?:(?:superclass))$"),
        ("FLOW_BRANCHING", r"^(?:(?:(if|unless)_guard)|(?:(block|in_clause|rescue)))$"),
        ("FLOW_ITERATION", r"^(?:(?:do_(block|module)))$"),
        (
            "SYNTAX_IDENTIFIER",
            r"^(?:(?:(exception_variable|exceptions|destructured_(?:(left_assignment|parameter))|rest_assignment|method_parameters|block_parameters|body_statement|bare_(?:(string|symbol)))|pair(?:_pattern)?))$",
        ),
    ),
    SemanticSearchLanguage.RUST: (
        ("BOUNDARY_MODULE", r"^(?:(?:(macro_rule|scoped_use_list|use_as_clause)))$"),
        ("DEFINITION_DATA", r"^(?:(?:closure_parameters|attribute))$"),
        (
            "DEFINITION_TYPE",
            r"^(?:(?:lifetime_parameter|bracketed_type)|(?:(use_(?:(wildcard|bounds))|trait_bounds|self_parameter|token_(?:(tree|repetition))|for_lifetimes|match_arm|let_chain))|(?:(higher_ranked_trait_bound|generic_type_with_turbofish|where_predicate)))$",
        ),
        ("FLOW_BRANCHING", r"^(?:(?:let_condition|guard))$"),
    ),
    SemanticSearchLanguage.SCALA: (
        ("FLOW_BRANCHING", r"^(?:(?:case_clause|guard))$"),
        (
            "DEFINITION_TYPE",
            r"^(?:(?:(lazy|repeated)_parameter_type|(enum_case_definitions))|(?:(contravariant|covariant)_type_parameter)|(?:(simple_)?enum_case)|(?:(full_)?enum(erators?|_case|_assignment|_entry))|(?:(compound_type|applied_constructor_type|named_tuple_type|structural_type|match_type|singleton_type|type_case_clause|self_type|stable_type_identifier|identifiers|bindings|refinement|namespace_selectors|given_conditional|annotated_lambda|indented_cases|literal_type|parameter_types|access_(modifier|qualifier))|(?:(name_and_type|view_bound))|(?:(context|lower|upper)_bound))|tuple_type|annotated_type)$",
        ),
        ("SYNTAX_ANNOTATION", r"^(?:(?:annotation))$"),
        ("SYNTAX_IDENTIFIER", r"^(?:(?:(arrow|as))_renamed_identifier|package_identifier)$"),
        (
            "SYNTAX_KEYWORD",
            r"^(?:(?:computed_(?:(getter|setter|modify|property))|call_suffix|capture_list_item|key_path_(?:(expression|string_expression))|constructor_(?:(expression|suffix))|typealias_declaration|precedence_group_(?:(declaration|attribute|attributes))|playground_literal|raw_str_interpolation|interpolated_expression|deinit_declaration|directly_assignable_expression|guard_statement|repeat_while_statement|availability_condition|directive|control_transfer_statement|statements|associatedtype_declaration|external_macro_definition|macro_declaration|macro_invocation|enum_type_parameters|equality_constraint|subscript_declaration|tuple_type_item|value_(argument_label|pack_expansion|parameter_pack)|type_pack_expansion|type_parameter_pack|opaque_type|protocol_composition_type|metatype|modifiers))$",
        ),
        (
            "SYNTAX_LITERAL",
            r"^(?:(?:constructor_suffix)|(?:array|dictionary)_literal)|(?:(line|multi_line)_string_literal)|(?:(tuple|array_literal|dictionary_literal|nil_coalescing|open_(?:(end|start))_range|range)_expression)$",
        ),
    ),
    SemanticSearchLanguage.SOLIDITY: (
        (
            "BOUNDARY_MODULE",
            r"^(?:(?:(imports?(?:_(?:(directive|list|name|specifier))?)|linkage_specification)))$",
        ),
        (
            "DEFINITION_DATA",
            r"^(?:(?:(call_struct_argument|parameter|variable_declaration_statement|variable_declaration_tuple))|(?:(struct_field_assignment|struct_member|constructor_definition)))$",
        ),
        (
            "DEFINITION_TYPE",
            r"^(?:(?:(full_)?enum(erators?|_case|_assignment|_entry))|(?:class_(body|declarations?)))$",
        ),
        (
            "OPERATION_OPERATOR",
            r"^(?:(?:update_expression|payable_conversion_expression)|(?:member_expression)|(?:(array|slice)_access)|(?:(unary|declaration)_expression))$",
        ),
        (
            "SYNTAX_ANNOTATION",
            r"^(?:(?:solidity_pragma_token)|(?:(pragma_directive|assembly_statement|revert_(?:(statement|arguments))|emit_statement)))$",
        ),
        (
            "SYNTAX_IDENTIFIER",
            r"^(?:(?:variable(?:(_declarator|_declaration|_list)))|value_binding_pattern)$",
        ),
        (
            "SYNTAX_KEYWORD",
            r"^(?:(?:(error_declaration|event_definition|constructor_definition|fallback_receive_definition|meta_type_expression|constructor_conversion_expression|inline_array_expression|user_defined_type(?:_definition)?|using_alias|return_type_definition|assembly_flags|any_pragma_token|type_name|expression|statement|block_statement))|(?:yul_.+))$",
        ),
        ("SYNTAX_LITERAL", r"^(?:(boolean_literal|number_literal))$"),
    ),
    SemanticSearchLanguage.SWIFT: (
        ("DEFINITION_DATA", r"^(?:(?:lambda_function_type_parameters|attribute))$"),
        (
            "DEFINITION_TYPE",
            r"^(?:(?:protocol_(body|function_declaration|property_declaration|property_requirements)|lambda_function_type|user_type|tuple_type))$",
        ),
        ("FLOW_BRANCHING", r"^(?:(?:if_statement))$"),
        ("OPERATION_INVOCATION", r"^(?:(?:constructor_expression))$"),
        (
            "OPERATION_OPERATOR",
            r"^(?:(?:bitwise_operation)|(?:(additive|multiplicative|bitwise_operation|comparison|equality|conjunction|disjunction)_expression)|(?:(unary|declaration)_expression))$",
        ),
        ("SYNTAX_ANNOTATION", r"^(?:(?:navigation_suffix|suppressed_constraint))$"),
        (
            "SYNTAX_IDENTIFIER",
            r"^(?:(?:variable(?:(_declarator|_declaration|_list)))|value_binding_pattern|identifier)$",
        ),
        (
            "SYNTAX_KEYWORD",
            r"^(?:(?:computed_(?:(getter|setter|modify|property))|call_suffix|capture_list_item|key_path_(?:(expression|string_expression))|constructor_(?:(expression|suffix))|typealias_declaration|precedence_group_(?:(declaration|attribute|attributes))|playground_literal|raw_str_interpolation|interpolated_expression|deinit_declaration|directly_assignable_expression|guard_statement|repeat_while_statement|availability_condition|directive|control_transfer_statement|statements|associatedtype_declaration|external_macro_definition|macro_declaration|macro_invocation|enum_type_parameters|equality_constraint|subscript_declaration|tuple_type_item|value_(argument_label|pack_expansion|parameter_pack)|type_pack_expansion|type_parameter_pack|opaque_type|protocol_composition_type|metatype|modifiers))$",
        ),
        (
            "SYNTAX_LITERAL",
            r"^(?:(?:constructor_suffix)|(?:array|dictionary)_literal)|(?:(line|multi_line)_string_literal)|(?:(tuple|array_literal|dictionary_literal|nil_coalescing|open_(?:(end|start))_range|range)_expression)$",
        ),
    ),
    SemanticSearchLanguage.TSX: (
        (
            "BOUNDARY_MODULE",
            r"^(?:(?:(imports?(_(?:(directive|list|name|specifier)))?|linkage_specification)))$",
        ),
        ("DEFINITION_DATA", r"^(?:(?:class_static_block))$"),
        (
            "DEFINITION_TYPE",
            r"^(?:(?:(full_)?enum(erators?|_case|_assignment|_entry))|(?:class_(body|declarations?))|mapped_type_clause|(?:template_type))$",
        ),
        # spellchecker:off
        (
            "FLOW_BRANCHING",
            r"^(?:(?:finally_clause)|(?:(switch(?:(_case|_default))|seh_(?:(except|finally))_clause))|(?:catch_(?:(clause|declaration))))$",
        ),
        # spellchecker:on
        (
            "OPERATION_INVOCATION",
            r"^(?:(?:call_signature)|(?:(construct_signature|data_constructors?)))$",
        ),
        (
            "SYNTAX_IDENTIFIER",
            r"^(?:(assignment_pattern|variable(?:(_declarator|_declaration|_list))|value_binding_pattern|nested_identifier|field_definition|object_assignment_pattern|jsx_(?:(attribute|expression|namespace_name))|namespace_(?:(import|export))|named_imports|import_require_clause|constraint|default_type|rest_type|class_heritage|computed_property_name|sequence_expression)|pair(?:_pattern)?)$",
        ),
        ("SYNTAX_LITERAL", r"^(?:(?:jsx_(closing|opening)_element))$"),
        ("SYNTAX_ANNOTATION", r"^(?:(?:(asserts|type_predicate)_annotation))$"),
    ),
    SemanticSearchLanguage.TYPESCRIPT: (
        (
            "BOUNDARY_MODULE",
            r"^(?:(?:(imports?(_(?:(directive|list|name|specifier)))?|linkage_specification)))$",
        ),
        ("DEFINITION_DATA", r"^(?:(?:class_static_block))$"),
        (
            "DEFINITION_TYPE",
            r"^(?:(?:mapped_type_clause)|(?:(full_)?enum(?:(erators?|_case|_assignment|_entry)))|(?:template_type))$",
        ),
        # spellchecker:off
        (
            "FLOW_BRANCHING",
            r"^(?:(?:finally_clause)|switch(?:(_case|_default))|seh_(?:(except|finally))_clause|catch_(?:(clause|declaration)))$",
        ),
        # spellchecker:on
        (
            "OPERATION_INVOCATION",
            r"^(?:(?:call_signature)|(?:(construct_signature|data_constructors?)))$",
        ),
        (
            "SYNTAX_IDENTIFIER",
            r"^(?:(assignment_pattern|variable(?:(_declarator|_declaration|_list))|value_binding_pattern|nested_identifier|field_definition|object_assignment_pattern|jsx_(?:(attribute|expression|namespace_name))|namespace_(?:(import|export))|named_imports|import_require_clause|constraint|default_type|rest_type|class_heritage|computed_property_name|sequence_expression)|pair(?:_pattern)?)$",
        ),
        ("SYNTAX_LITERAL", r"^(?:(?:jsx_(closing|opening)_element))$"),
        ("SYNTAX_ANNOTATION", r"^(?:(?:(asserts|type_predicate)_annotation))$"),
    ),
    SemanticSearchLanguage.YAML: (("SYNTAX_LITERAL", r"^(?:(?:scalar))$"),),
}

# Generic cross-language patterns (raw strings)
# Structure: tuple[(SemanticClass, pattern_string), ...]
_GENERIC_PATTERNS_RAW: tuple[tuple[str, str], ...] = (
    (
        "BOUNDARY_MODULE",
        r"^(?:(?:(aliased_import|extern_alias_directive|import_spec))|(import|export|namespace)_(?:(clause|attribute|spec_list|use_clause|use_group)))$",
    ),
    (
        "DEFINITION_CALLABLE",
        r"^(?:(?:(method|property|function|abstract_method|index)_signature))$",
    ),
    (
        "DEFINITION_DATA",
        r"^(?:(?:(formal|class|function_value|bracketed)_parameters?)|(?:(block|error|event|return|call_struct_argument|function_pointer|hash_splat|keyword|optional|simple|splat|variadic|yul_variable_declaration)_parameter)|(?:.+_declaration)|(?:.+_initializer(_list)?))$",
    ),
    (
        "DEFINITION_TYPE",
        r"^(?:(?:type_(argument|parameter|constraint|projection|bound|test|case|elem)s?(?:_list)?)|(?:(asserts|type_predicate)_type_annotation)|(?:(extends_type_clause|derives_clause|inheritance_specifier))|(?:(array|dictionary|optional|function|generic|projected|qualified)_type)|(?:template_(?:(argument_list|parameter_list|declaration|body|substitution|template_parameter_declaration)))|(?:type_(alias|annotation|application|binder|binding|lambda|parameter(_declaration)?|predicate|spec|family_(result|injectivity)))|(?:(extends|implements|base|super|delegation)_(?:(clause|list|interfaces|class|specifiers?)))|(?:.+_constraint))$",
    ),
    (
        "FLOW_BRANCHING",
        r"^(?:(?:(switch|case)_(?:(body|block|entry|section|label|rule|expression_arm|pattern|block_statement_group)))|(?:(keyword|token_binding|view)_pattern)|(?:(catch|finally|rescue|after|else)_(?:(block|clause|formal_parameter)))|(?:(with|from|where|let|join|order_by|group|select|when|catch_filter)_clause)|(?:.+_pattern))$",
    ),
    (
        "OPERATION_OPERATOR",
        r"^(?:(?:(spread|splat|hash_splat|dictionary_splat|variadic)_(?:(element|argument|parameter|unpacking|pattern|type)))|(?:(prefix|postfix|navigation|check)_expression))$",
    ),
    (
        "OPERATION_INVOCATION",
        r"^(?:(?:(getter|setter|modify|didset|willset)_(?:(specifier|clause)))|(?:.+_invocation))$",
    ),
    ("SYNTAX_KEYWORD", r"^(?:(?:modifiers?|specifiers?))$"),
    (
        "SYNTAX_ANNOTATION",
        r"^(?:(decorator|preproc_(?:(elif|ifdef|elifdef|defined|error|line|pragma|undef|warning)))|.+_(?:(modifiers?|specifiers?|qualifiers?)))$",
    ),
    (
        "SYNTAX_LITERAL",
        r"^(?:(?:(heredoc|nowdoc)_(?:(body|redirect))))|(?:(bare|quoted)_(?:(string|symbol|atom|keyword|expression|pattern|type)))$",
    ),
    (
        "SYNTAX_PUNCTUATION",
        r"^(?:(?:(field|ordered_field)_declaration_list)|(?:(expression|statement)_(?:(list|case)))|(?:(arguments?|parameters))|(?:(program|source_file|compilation_unit|translation_unit|document|stylesheet|chunk))|(?:.+_(list|arguments?))|(?:.+_(?:(body|block|block_list))))$",
    ),
    # Function/Method Invocations - These should be OPERATION_INVOCATION, not operators or branching
    (
        "OPERATION_INVOCATION",
        r"^(?:(?:(function|method)_call)|(?:call_(?:(expression|invocation))?))$",
    ),
    # Anonymous Functions - These should be EXPRESSION_ANONYMOUS, not operators
    (
        "EXPRESSION_ANONYMOUS",
        r"^(?:(?:(anonymous_function|(?:(lambda|arrow|anonymous))(?:(_literal|_expression|block|error|event|return|call_struct_argument|function_pointer|hash_splat|keyword|optional|simple|splat|variadic|yul_variable_declaration(_parameter)?)?)?)))$",
    ),
    # String Literals - These should NEVER be operators
    (
        "SYNTAX_LITERAL",
        r"^(?:(?:(string|raw_string)(?:(_literal|_content|_expression))?)|(?:interpolation))$",
    ),
    # Data Structure Literals - Arrays, lists, tuples, maps, records
    (
        "SYNTAX_LITERAL",
        r"^(?:(?:(array|list|tuple|map|hash|dict|record)(?:(_literal|_expression))?))$",
    ),
    # Control Flow Statements - Correct classification by flow type
    ("FLOW_CONTROL", r"^(?:(?:return_statement))$"),
    ("FLOW_ITERATION", r"^(?:(?:for|while|until)_statement)$"),
    ("FLOW_ASYNC", r"^(?:(?:await_expression))$"),
    # Module Boundaries - Imports, exports, using directives
    ("BOUNDARY_MODULE", r"^(?:(?:(using_directive|exports)))$"),
    # Type vs Data Instances - Instances are data, not types
    ("DEFINITION_DATA", r"^(?:(?:(data|type)_instance)|(?:enum_entry))$"),
    # Variable Declarations - These are data definitions, not just identifiers
    ("DEFINITION_DATA", r"^(?:(?:variable_declarator))$"),
    # Data Operations - Field access, subscripting, selectors
    ("OPERATION_DATA", r"^(?:(?:(subscript|selector_expression|field_access|scope_resolution)))$"),
    # Operator Expressions - Negation, unary ops
    ("OPERATION_OPERATOR", r"^(?:(?:(negation|prefix_unary_expression)))$"),
    # Annotations - These should be SYNTAX_ANNOTATION, not punctuation
    ("SYNTAX_ANNOTATION", r"^(?:(?:annotation))$"),
    # Template/Generic Functions - These are callable definitions
    ("DEFINITION_CALLABLE", r"^(?:(?:template_function))$"),
    # Specific Identifiers - Boost confidence for correct low-confidence patterns
    (
        "SYNTAX_IDENTIFIER",
        r"^(?:(?:(qualified|scoped|generic)_(identifier|name))|(?:(attribute|namespace|package)_name)|(?:(label|entity|setter)))$",
    ),
    # Range expressions - These are data operations or literals
    ("OPERATION_DATA", r"^(?:(?:range(?:(_expression))?))$"),
    # Pattern Matching - Patterns are branching constructs
    ("FLOW_BRANCHING", r"^(?:(?:pattern))$"),
    # Data Bindings - These are data operations
    ("OPERATION_DATA", r"^(?:(?:bind(?:ing)?))$"),
    # Expression Statements - These are operations, not branching
    ("OPERATION_DATA", r"^(?:(?:expression_statement))$"),
    # Parameters are kind of in a grey area, technically probably just syntax, but important for most tasks, so we'll classify them as OPERATION_DATA
    ("OPERATION_DATA", r"^(?:(?:parameters?))$"),
    # Try Expressions and Statements
    ("FLOW_BRANCHING", r"^(?:(?:try_(?:(expression|statement))))$"),
    # Parenthesized Expressions - These are punctuation
    ("SYNTAX_PUNCTUATION", r"^(?:(?:parenthesized_expression))$"),
    # Tuple/Sequence Expressions - These are literals
    ("SYNTAX_LITERAL", r"^(?:(?:(tuple|sequence)_expression))$"),
    # Type-related patterns that need clarification
    (
        "DEFINITION_TYPE",
        r"^(?:(?:existential_type)|(?:(fixity|signature))|(?:(type|data)_family))$",
    ),
    # Quote expressions - Language-specific literals (Lisp, Scheme, etc.)
    ("SYNTAX_LITERAL", r"^(?:(?:quote_expression))$"),
    # Struct usage vs definition - need differentiator, but assume identifier for now
    ("SYNTAX_IDENTIFIER", r"^(?:(?:struct))$"),
    # Global statements - These are definitions or module boundaries
    ("DEFINITION_DATA", r"^(?:(?:global_statement))$"),
    # Calling conventions - These are annotations/modifiers
    ("SYNTAX_ANNOTATION", r"^(?:(?:calling_convention))$"),
    # Pair patterns - These are identifiers (key-value pairs)
    ("SYNTAX_IDENTIFIER", r"^(?:(?:pair))$"),
    # Block patterns - Code blocks for control flow
    ("FLOW_BRANCHING", r"^(?:(?:block))$"),
)

# Compiled pattern caches (populated lazily)
_LANG_PATTERNS_COMPILED: dict[
    SemanticSearchLanguage, tuple[tuple[SemanticClass, re.Pattern[str]], ...]
] = {}
_generic_patterns_compiled: tuple[tuple[SemanticClass, re.Pattern[str]], ...] | None = None


@lru_cache(maxsize=32)
def _get_lang_patterns(
    language: SemanticSearchLanguage,
) -> tuple[tuple[SemanticClass, re.Pattern[str]], ...]:
    """Get compiled language-specific patterns (cached per language).

    Args:
        language: The programming language

    Returns:
        Tuple of (SemanticClass, compiled_pattern) pairs
    """
    if language not in _LANG_PATTERNS_COMPILED:
        from codeweaver.semantic.classifications import SemanticClass

        raw_patterns = _LANG_SPECIFIC_PATTERNS_RAW.get(language, ())
        _LANG_PATTERNS_COMPILED[language] = tuple(
            (getattr(SemanticClass, class_name), re.compile(pattern))
            for class_name, pattern in raw_patterns
        )
    return _LANG_PATTERNS_COMPILED[language]


def _get_generic_patterns() -> tuple[tuple[SemanticClass, re.Pattern[str]], ...]:
    """Get compiled generic patterns (cached globally).

    Returns:
        Tuple of (SemanticClass, compiled_pattern) pairs
    """
    global _generic_patterns_compiled

    if _generic_patterns_compiled is None:
        from codeweaver.semantic.classifications import SemanticClass

        _generic_patterns_compiled = tuple(
            (getattr(SemanticClass, class_name), re.compile(pattern))
            for class_name, pattern in _GENERIC_PATTERNS_RAW
        )
    return _generic_patterns_compiled


@lru_cache(maxsize=1024)
def get_checks(thing_name: str, language: SemanticSearchLanguage) -> tuple[SemanticClass, ...]:
    """Get all classifications for a thing name using optimized lazy-compiled patterns.

    Uses lazy compilation strategy for fast module imports:
    1. Patterns stored as raw strings at module level
    2. Compiled on first access per language
    3. Cached for subsequent calls

    Tiered lookup strategy (language is always known):
    1. Language-specific patterns (fastest, most specific)
    2. Generic cross-language patterns (broader coverage)

    Args:
        thing_name: The name of the thing to classify
        language: The programming language (always known per user confirmation)

    Returns:
        Tuple of matching SemanticClass values
    """
    results: list[SemanticClass] = []

    # Tier 1: Language-specific patterns (if available for this language)
    results.extend(
        classification
        for classification, pattern in _get_lang_patterns(language)
        if pattern.match(thing_name)
    )
    # Tier 2: Generic cross-language patterns
    results.extend(
        classification
        for classification, pattern in _get_generic_patterns()
        if pattern.match(thing_name)
    )
    return tuple(results)


__all__ = (
    "LANGUAGE_SPECIFIC_TOKEN_EXCEPTIONS",
    "NAMED_NODE_COUNTS",
    "get_checks",
    "get_token_patterns_sync",
)
