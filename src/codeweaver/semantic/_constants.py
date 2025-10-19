# sourcery skip: lambdas-should-be-short, no-complex-if-expressions
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Constants and patterns used in semantic analysis."""

import re

from collections.abc import Callable, Iterator
from types import MappingProxyType
from typing import TYPE_CHECKING, NamedTuple

from codeweaver._utils import lazy_importer
from codeweaver.language import SemanticSearchLanguage


if TYPE_CHECKING:
    from codeweaver.semantic._types import ThingName
    from codeweaver.semantic.classifications import SemanticClass
    from codeweaver.semantic.grammar_things import CompositeThing, Token
else:
    SemanticClass = lazy_importer("codeweaver.semantic.classifications").SemanticClass
    CompositeThing = lazy_importer("codeweaver.semantic.grammar_things").CompositeThing
    Token = lazy_importer("codeweaver.semantic.grammar_things").Token
    ThingName = lazy_importer("codeweaver.semantic._types").ThingName

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

# spellchecker:off
IS_OPERATOR = re.compile(
    r"""^
        (
            (
                [\+\-\*/%&?|\^~!=<>]+
            )
            |
            \.\.\.|not\sin|in|-(a|o)|!?i(n|s)|as(!|\?)|is|gt|(bit)?(and|xor|or)|not|lt|le|ge|eq|not_eq|s?div|x?or_eq
            |
            \w+_operator
        )
        $""",
    re.VERBOSE,
)
"""Not perfect but should get us >95% with a couple false positives."""

NOT_SYMBOL = re.compile(
    r"""^
                        (
                            (
                                [a-z_][a-z0-9_]*
                                |
                                [#@_][a-z0-9_]+
                            )
                        )
                    $""",
    re.VERBOSE | re.IGNORECASE,
)
"""Rough approximation of what is NOT a symbol (identifier, keyword, etc). Accounts for @ in C# and # in preprocessor directives."""

IS_LITERAL = re.compile(
    r"""^
    (
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
    )
    $""",
    re.IGNORECASE | re.VERBOSE,
)
"""Literal tokens in supported languages."""

IS_IDENTIFIER = re.compile(
    r"""^
    (
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
    )
    $""",
    re.VERBOSE,
)

IS_ANNOTATION = re.compile(
    r"""^
    (
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
    )
    $""",
    re.VERBOSE | re.IGNORECASE,
)

IS_KEYWORD = re.compile(
    r"""^
    (
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
    Protocol|Type|associatedtype|bang|borrowing|canImport|consuming|convenience|deinit|didSet|distributed|dsohandle|externalMacro|fileID|filePath|indirect|init|mutating|nonisolated|nonmutating|ownership_modifier|postfix|precedencegroup|prefix|some|subscript|swift|targetEnvironment|throw_keyword|unavailable|willSet|arch|available|column|compiler|diagnostic|line|os
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
    )
    $""",
    re.VERBOSE,
)
"""Comprehensive keyword pattern covering all supported languages. (7300 characters!)"""
# spellchecker:on


class CompositeCheck(NamedTuple):
    """A class for checking specific patterns in CompositeThing names, optionally filtered by language and/or an additional predicate."""

    name_pattern: re.Pattern[str]
    """A regex pattern to match names."""
    classification: SemanticClass
    """The semantic classification to assign if this check matches."""
    languages: frozenset[SemanticSearchLanguage] | None = None
    """Languages to which this check applies. If None, applies to all languages."""
    predicate: Callable[[CompositeThing], SemanticClass | None] | None = None
    """An optional additional predicate to apply to the CompositeThing. Only applied if the name matches the pattern. Should return a SemanticClass if the thing matches, or None if it doesn't. Can be used to discern between different things with the same name (which does happen)."""

    def classify(
        self, thing: CompositeThing | ThingName, *, language: SemanticSearchLanguage | None = None
    ) -> SemanticClass | None:
        """Check if the given thing matches this composite check. Optionally provide a language (only helpful if thing is a ThingName)."""
        if isinstance(thing, str):
            name = thing
            language = language
        else:
            name = thing.name
            language = thing.language

        if self.name_pattern.match(name) and (self.languages is None or language in self.languages):
            if self.predicate is not None and isinstance(thing, CompositeThing):
                return self.predicate(thing)
            return self.classification
        return None


TypeScriptLangs = frozenset({SemanticSearchLanguage.TYPESCRIPT, SemanticSearchLanguage.TSX})
JavaScriptLangs = frozenset({SemanticSearchLanguage.JAVASCRIPT, SemanticSearchLanguage.JSX})
JavaScriptFamily = TypeScriptLangs | JavaScriptLangs

# ========== OPTIMIZED COMPOSITE CHECK PATTERNS ==========
# Grouped by language and classification for ~10-15x faster classification
# Original: 145 individual checks | Optimized: 26 language groups + 10 generic patterns + 2 predicates

# Language-specific pattern groups
# Structure: {Language: tuple[(SemanticClass, compiled_pattern), ...]}
LANG_SPECIFIC_PATTERNS: dict[
    SemanticSearchLanguage, tuple[tuple[SemanticClass, re.Pattern[str]], ...]
] = {
    SemanticSearchLanguage.BASH: (
        (
            SemanticClass.SYNTAX_KEYWORD,
            re.compile(r"^(?:(?:(command_name|do_group|case_item|herestring_redirect)))$"),
        ),
        (SemanticClass.SYNTAX_PUNCTUATION, re.compile(r"^(?:(?:(file_redirect|subscript)))$")),
    ),
    SemanticSearchLanguage.C_LANG: (
        (
            SemanticClass.BOUNDARY_MODULE,
            re.compile(
                r"^(?:(?:(imports?(_(directive|list|name|specifier))?|linkage_specification)))$"
            ),
        ),
        (
            SemanticClass.DEFINITION_DATA,
            re.compile(
                r"^(?:(?:(init_declarator|initializer_pair|subscript_range_designator|preproc_params))|(?:.+_designator))$"
            ),
        ),
        (SemanticClass.DEFINITION_TYPE, re.compile(r"^(?:(?:(enumerator|bitfield_clause)))$")),
        (
            SemanticClass.FLOW_BRANCHING,
            # spellchecker:off
            re.compile(r"^(?:(?:(switch(_case|_default)|seh_(except|finally)_clause)))$"),
            # spellchecker:on
        ),
        (SemanticClass.BOUNDARY_ERROR, re.compile(r"^(?:(?:she_except_clause))$")),
        (SemanticClass.BOUNDARY_RESOURCE, re.compile(r"^(?:(?:she_finally_clause))$")),
        (SemanticClass.OPERATION_OPERATOR, re.compile(r"^(?:(?:comma_expression))$")),
        (
            SemanticClass.SYNTAX_ANNOTATION,
            re.compile(
                r"^(?:(?:gnu_asm_(clobber_list|goto_list|input_operand(_list)?|output_operand(_list)?))|(?:(preproc_(call|def|function_def|include|else))))$"
            ),
        ),
    ),
    SemanticSearchLanguage.C_PLUS_PLUS: (
        (
            SemanticClass.BOUNDARY_MODULE,
            re.compile(
                r"^(?:(?:(imports?(_(directive|list|name|specifier))?|linkage_specification)))$"
            ),
        ),
        (
            SemanticClass.DEFINITION_DATA,
            re.compile(
                r"^(?:(?:(lambda_capture_initializer|preproc_params))|(?:(init_declarator|initializer_pair|subscript_range_designator))|(?:.+_designator))$"
            ),
        ),
        (
            SemanticClass.DEFINITION_TYPE,
            re.compile(
                r"^(?:(?:(alias_declaration|concept_definition|new_declarator|pointer_type_declarator|namespace_alias_definition|lambda_declarator|friend_declaration|simple_requirement|init_statement|module_(name|partition)|trailing_return_type|explicit_object_parameter_declaration|base_class_clause|bitfield_clause|dependent_name|compound_requirement|requirement_seq|variadic_declarator))|(?:optional_type_parameter_declaration)|(?:enumerator))$"
            ),
        ),
        (
            SemanticClass.FLOW_BRANCHING,
            # spellchecker:off
            re.compile(
                r"^(?:(?:(switch(_case|_default)|seh_(except|finally)_clause))|(?:catch_(clause|declaration))|(?:condition_clause))$"
                # spellchecker:on
            ),
        ),
        (SemanticClass.BOUNDARY_ERROR, re.compile(r"^(?:(?:she_except_clause))$")),
        (SemanticClass.BOUNDARY_RESOURCE, re.compile(r"^(?:(?:she_finally_clause))$")),
        (SemanticClass.OPERATION_OPERATOR, re.compile(r"^(?:(?:comma_expression))$")),
        (
            SemanticClass.SYNTAX_ANNOTATION,
            re.compile(
                r"^(?:(?:gnu_asm_(clobber_list|goto_list|input_operand(_list)?|output_operand(_list)?))|(?:(consteval_block|static_assert)_declaration)|(?:preproc_(call|def|function_def|include)))$"
            ),
        ),
    ),
    SemanticSearchLanguage.C_SHARP: (
        (SemanticClass.BOUNDARY_MODULE, re.compile(r"^(?:(?:file_scoped_namespace_declaration))$")),
        (SemanticClass.DEFINITION_TYPE, re.compile(r"^(?:(?:type_parameter_constraints_clause))$")),
        (SemanticClass.FLOW_BRANCHING, re.compile(r"^(?:(?:catch_(clause|declaration)))$")),
        (SemanticClass.OPERATION_OPERATOR, re.compile(r"^(?:(?:(unary|declaration)_expression))$")),
        (
            SemanticClass.SYNTAX_ANNOTATION,
            re.compile(r"^(?:(?:preproc_(region|endregion|define|else)))$"),
        ),
        (
            SemanticClass.SYNTAX_IDENTIFIER,
            re.compile(r"^(?:(?:member_binding_expression|tuple_element))$"),
        ),
        (
            SemanticClass.SYNTAX_KEYWORD,
            re.compile(
                r"^(?:(?:primary_constructor_base_type|parenthesized_variable_designation|arrow_expression_clause|subpattern|positional_pattern_clause|property_pattern_clause|interpolation_alignment_clause|argument|global_attribute|join_into_clause))$"
            ),
        ),
    ),
    SemanticSearchLanguage.CSS: (
        (SemanticClass.SYNTAX_IDENTIFIER, re.compile(r"^(?:(?:.+_selector))$")),
        (
            SemanticClass.SYNTAX_KEYWORD,
            re.compile(r"^(?:(?:at_rule|class_name|rule_set|selectors))$"),
        ),
        (SemanticClass.SYNTAX_LITERAL, re.compile(r"^(?:(?:.+_(query|statement|value)))$")),
    ),
    SemanticSearchLanguage.ELIXIR: (
        (SemanticClass.OPERATION_OPERATOR, re.compile(r"^(?:(?:(access_call|unary_operator)))$")),
        (SemanticClass.SYNTAX_IDENTIFIER, re.compile(r"^(?:(?:pair(_pattern)?))$")),
        (
            SemanticClass.SYNTAX_LITERAL,
            re.compile(
                r"^(?:(?:(bitstring|body|charlist|keywords|map_content|sigil|source|quoted_(atom|keyword))))$"
            ),
        ),
    ),
    SemanticSearchLanguage.GO: (
        (
            SemanticClass.BOUNDARY_MODULE,
            re.compile(
                r"^(?:(?:(imports?(_(directive|list|name|specifier))?|linkage_specification)))$"
            ),
        ),
        (
            SemanticClass.DEFINITION_TYPE,
            re.compile(r"^(?:(?:(implicit_length_array_type|method_elem|keyed_element)))$"),
        ),
        (
            SemanticClass.FLOW_BRANCHING,
            re.compile(r"^(?:(?:communication_case|default_case|literal_(element|value))))$"),
        ),
        (
            SemanticClass.FLOW_ITERATION,
            re.compile(
                r"^(?:(?:for(_clause|_in_clause|_numeric_clause)?)|(?:(range_clause|receive_statement)))$"
            ),
        ),
    ),
    SemanticSearchLanguage.HASKELL: (
        (
            SemanticClass.BOUNDARY_MODULE,
            re.compile(
                r"^(?:(?:(imports?(_(directive|list|name|specifier))?|linkage_specification)))$"
            ),
        ),
        (
            SemanticClass.DEFINITION_DATA,
            re.compile(
                r"^(?:(?:(lazy|strict)_field)|(?:(binding|binding_set|binding_list|local_binds))|(?:(equations|children|fields|header|match|prefix|qualifiers|quoted_decls)))$"
            ),
        ),
        (
            SemanticClass.DEFINITION_TYPE,
            re.compile(
                r"^(?:(?:(fundep|fundeps|kind_application|field_path))|(?:(full_)?enum(erators?|_case|_assignment|_entry))|(?:instance_declarations)|(?:class_(body|declarations?))|(?:(associated_type|constructor_synonym|explicit_type|gadt_constructor(s)?|newtype_constructor)))$"
            ),
        ),
        (
            SemanticClass.FLOW_BRANCHING,
            re.compile(
                r"^(?:(?:match(_conditional_expression|_default_expression))|(?:(alternative|alternatives)))$"
            ),
        ),
        (SemanticClass.FLOW_ITERATION, re.compile(r"^(?:(?:do_(block|module)))$")),
        (
            SemanticClass.OPERATION_INVOCATION,
            re.compile(r"^(?:(?:(construct_signature|data_constructors?)))$"),
        ),
        (
            SemanticClass.SYNTAX_KEYWORD,
            re.compile(
                r"^(?:(?:(annotated|constructor_synonyms|equation|quoter|field_(name|update)|function_head_parens|haskell|inferred|infix_id|special|quantified_variables|type_(params?|patterns?)|guards?)))$"
            ),
        ),
    ),
    SemanticSearchLanguage.HTML: (
        (
            SemanticClass.SYNTAX_ANNOTATION,
            re.compile(r"^(?:(?:(attribute|quoted_attribute_value)))$"),
        ),
        (
            SemanticClass.SYNTAX_PUNCTUATION,
            re.compile(
                r"^(?:(?:(element|script_element|style_element))|(?:erroneous_end_tag)|(?:(start|end|self_closing)_tag))$"
            ),
        ),
    ),
    SemanticSearchLanguage.TYPESCRIPT: (
        (
            SemanticClass.BOUNDARY_MODULE,
            re.compile(
                r"^(?:(?:(imports?(_(directive|list|name|specifier))?|linkage_specification)))$"
            ),
        ),
        (SemanticClass.DEFINITION_DATA, re.compile(r"^(?:(?:class_static_block))$")),
        (
            SemanticClass.DEFINITION_TYPE,
            re.compile(
                r"^(?:(?:(full_)?enum(erators?|_case|_assignment|_entry))|(?:class_(body|declarations?)))$"
            ),
        ),
        (
            SemanticClass.FLOW_BRANCHING,
            re.compile(
                # spellchecker:off
                r"^(?:(?:finally_clause)|(?:(switch(_case|_default)|seh_(except|finally)_clause))|(?:catch_(clause|declaration)))$"
                # spellchecker:on
            ),
        ),
        (
            SemanticClass.SYNTAX_IDENTIFIER,
            re.compile(
                r"^(?:(?:assignment_pattern)|(?:(variable(_declarator|_declaration|_list))|value_binding_pattern)|(?:(nested_identifier|field_definition|object_assignment_pattern))|(?:(jsx_(attribute|expression|namespace_name)|namespace_(import|export)|named_imports|import_require_clause|constraint|default_type|rest_type|class_heritage|computed_property_name|sequence_expression))|(?:pair(_pattern)?))$"
            ),
        ),
        (SemanticClass.SYNTAX_LITERAL, re.compile(r"^(?:(?:jsx_(closing|opening)_element))$")),
    ),
    SemanticSearchLanguage.JSX: (
        (
            SemanticClass.BOUNDARY_MODULE,
            re.compile(
                r"^(?:(?:(imports?(_(directive|list|name|specifier))?|linkage_specification)))$"
            ),
        ),
        (SemanticClass.DEFINITION_DATA, re.compile(r"^(?:(?:class_static_block))$")),
        (
            SemanticClass.DEFINITION_TYPE,
            re.compile(
                r"^(?:(?:(full_)?enum(erators?|_case|_assignment|_entry))|(?:class_(body|declarations?)))$"
            ),
        ),
        (
            SemanticClass.FLOW_BRANCHING,
            re.compile(
                # spellchecker:off
                r"^(?:(?:finally_clause)|(?:(switch(_case|_default)|seh_(except|finally)_clause))|(?:catch_(clause|declaration)))$"
                # spellchecker:on
            ),
        ),
        (
            SemanticClass.SYNTAX_IDENTIFIER,
            re.compile(
                r"^(?:(?:assignment_pattern)|(?:(variable(_declarator|_declaration|_list))|value_binding_pattern)|(?:(nested_identifier|field_definition|object_assignment_pattern))|(?:(jsx_(attribute|expression|namespace_name)|namespace_(import|export)|named_imports|import_require_clause|constraint|default_type|rest_type|class_heritage|computed_property_name|sequence_expression))|(?:pair(_pattern)?))$"
            ),
        ),
        (SemanticClass.SYNTAX_LITERAL, re.compile(r"^(?:(?:jsx_(closing|opening)_element))$")),
    ),
    SemanticSearchLanguage.JAVASCRIPT: (
        (
            SemanticClass.BOUNDARY_MODULE,
            re.compile(
                r"^(?:(?:(imports?(_(directive|list|name|specifier))?|linkage_specification)))$"
            ),
        ),
        (SemanticClass.DEFINITION_DATA, re.compile(r"^(?:(?:class_static_block))$")),
        (
            SemanticClass.DEFINITION_TYPE,
            re.compile(
                r"^(?:(?:(full_)?enum(erators?|_case|_assignment|_entry))|(?:class_(body|declarations?)))$"
            ),
        ),
        (
            SemanticClass.FLOW_BRANCHING,
            re.compile(
                # spellchecker:off
                r"^(?:(?:finally_clause)|(?:(switch(_case|_default)|seh_(except|finally)_clause))|(?:catch_(clause|declaration)))$"
                # spellchecker:on
            ),
        ),
        (
            SemanticClass.SYNTAX_IDENTIFIER,
            re.compile(
                r"^(?:(?:assignment_pattern)|(?:(variable(_declarator|_declaration|_list))|value_binding_pattern)|(?:(nested_identifier|field_definition|object_assignment_pattern))|(?:(jsx_(attribute|expression|namespace_name)|namespace_(import|export)|named_imports|import_require_clause|constraint|default_type|rest_type|class_heritage|computed_property_name|sequence_expression))|(?:pair(_pattern)?))$"
            ),
        ),
        (SemanticClass.SYNTAX_LITERAL, re.compile(r"^(?:(?:jsx_(closing|opening)_element))$")),
    ),
    SemanticSearchLanguage.JSON: (
        (SemanticClass.SYNTAX_IDENTIFIER, re.compile(r"^(?:(?:pair))$")),
    ),
    SemanticSearchLanguage.JSX: (
        (
            SemanticClass.BOUNDARY_MODULE,
            re.compile(
                r"^(?:(?:(imports?(_(directive|list|name|specifier))?|linkage_specification)))$"
            ),
        ),
        (SemanticClass.DEFINITION_DATA, re.compile(r"^(?:(?:class_static_block))$")),
        (
            SemanticClass.DEFINITION_TYPE,
            re.compile(
                r"^(?:(?:(full_)?enum(erators?|_case|_assignment|_entry))|(?:class_(body|declarations?)))$"
            ),
        ),
        (
            SemanticClass.FLOW_BRANCHING,
            re.compile(
                # spellchecker:off
                r"^(?:(?:finally_clause)|(?:(switch(_case|_default)|seh_(except|finally)_clause))|(?:catch_(clause|declaration)))$"
                # spellchecker:on
            ),
        ),
        (
            SemanticClass.SYNTAX_IDENTIFIER,
            re.compile(
                r"^(?:(?:assignment_pattern)|(?:(variable(_declarator|_declaration|_list))|value_binding_pattern)|(?:(nested_identifier|field_definition|object_assignment_pattern))|(?:(jsx_(attribute|expression|namespace_name)|namespace_(import|export)|named_imports|import_require_clause|constraint|default_type|rest_type|class_heritage|computed_property_name|sequence_expression))|(?:pair(_pattern)?))$"
            ),
        ),
        (SemanticClass.SYNTAX_LITERAL, re.compile(r"^(?:(?:jsx_(closing|opening)_element))$")),
    ),
    SemanticSearchLanguage.KOTLIN: (
        (
            SemanticClass.DEFINITION_DATA,
            re.compile(
                r"^(?:(?:(primary_constructor|when_(subject|entry)|annotated_lambda|multi_variable_declaration|property_delegate|range_test|getter|function_type_parameters)))$"
            ),
        ),
        (
            SemanticClass.DEFINITION_TYPE,
            re.compile(r"^(?:(?:(full_)?enum(erators?|_case|_assignment|_entry)))$"),
        ),
        (
            SemanticClass.EXPRESSION_ANONYMOUS,
            re.compile(
                r"^(?:(?:(annotated_lambda|anonymous_class|anonymous_function_use_clause)))$"
            ),
        ),
    ),
    SemanticSearchLanguage.LUA: (
        (
            SemanticClass.FLOW_BRANCHING,
            re.compile(r"^(?:(?:(if_)?guards?)|(?:else_(clause|statement)))$"),
        ),
        (
            SemanticClass.FLOW_ITERATION,
            re.compile(
                r"^(?:(?:for_generic_clause)|(?:for(_clause|_in_clause|_numeric_clause)?))$"
            ),
        ),
        (SemanticClass.OPERATION_INVOCATION, re.compile(r"^(?:(?:method_index_expression))$")),
        (
            SemanticClass.SYNTAX_IDENTIFIER,
            re.compile(r"^(?:(?:variable(_declarator|_declaration|_list))|value_binding_pattern)$"),
        ),
    ),
    SemanticSearchLanguage.NIX: (
        (
            SemanticClass.DEFINITION_DATA,
            re.compile(r"^(?:(?:(binding|binding_set|binding_list|local_binds)))$"),
        ),
        (
            SemanticClass.SYNTAX_IDENTIFIER,
            re.compile(
                r"^(?:(?:(attrpath|formal|formals|inherit_from|inherited_attrs|interpolation|source_code)))$"
            ),
        ),
    ),
    SemanticSearchLanguage.PHP: (
        (
            SemanticClass.DEFINITION_DATA,
            re.compile(r"^(?:(?:property_element|static_variable_declaration))$"),
        ),
        (SemanticClass.DEFINITION_TYPE, re.compile(r"^(?:(?:(simple_)?enum_case))$")),
        (
            SemanticClass.EXPRESSION_ANONYMOUS,
            re.compile(
                r"^(?:(?:(annotated_lambda|anonymous_class|anonymous_function_use_clause)))$"
            ),
        ),
        (
            SemanticClass.FLOW_BRANCHING,
            re.compile(
                r"^(?:(?:(finally_clause|default_statement))|(?:match(_conditional_expression|_default_expression))|(?:else_(clause|statement)))$"
            ),
        ),
        (SemanticClass.SYNTAX_ANNOTATION, re.compile(r"^(?:(?:attribute_group))$")),
        (
            SemanticClass.SYNTAX_IDENTIFIER,
            re.compile(r"^(?:(?:variable(_declarator|_declaration|_list))|value_binding_pattern)$"),
        ),
        (
            SemanticClass.SYNTAX_KEYWORD,
            re.compile(
                r"^(?:(?:(anonymous_class|use_instead_of_clause|property_(hook|promotion_parameter)|class_interface_clause|const_element|by_ref|declare_directive|list_literal)))$"
            ),
        ),
    ),
    SemanticSearchLanguage.PYTHON: (
        (SemanticClass.BOUNDARY_RESOURCE, re.compile(r"^(?:(?:with_item))$")),
        (
            SemanticClass.FLOW_BRANCHING,
            re.compile(r"^(?:(?:(if|unless)_guard|(block|in_clause|rescue|case_clause)))$"),
        ),
        (SemanticClass.FLOW_ITERATION, re.compile(r"^(?:(?:(do_(block|module)|for_in_clause)))$")),
        (SemanticClass.OPERATION_OPERATOR, re.compile(r"^(?:(?:dictionary_splat))$")),
        (
            SemanticClass.SYNTAX_IDENTIFIER,
            re.compile(
                r"^(?:(?:(exception_variable|exceptions|destructured_(left_assignment|parameter)|rest_assignment|method_parameters|block_parameters|body_statement|bare_(string|symbol)|dotted_name))|(?:pair(_pattern)?))$"
            ),
        ),
        (
            SemanticClass.SYNTAX_KEYWORD,
            re.compile(
                r"^(?:(?:constrained_type|member_type|parenthesized_list_splat|chevron|if_clause|slice|relative_import|except_clause))$"
            ),
        ),
        (SemanticClass.SYNTAX_LITERAL, re.compile(r"^(?:(?:format_expression))$")),
    ),
    SemanticSearchLanguage.RUBY: (
        (
            SemanticClass.FLOW_BRANCHING,
            re.compile(r"^(?:(?:(if|unless)_guard)|(?:(block|in_clause|rescue)))$"),
        ),
        (SemanticClass.FLOW_ITERATION, re.compile(r"^(?:(?:do_(block|module)))$")),
        (
            SemanticClass.SYNTAX_IDENTIFIER,
            re.compile(
                r"^(?:(?:(exception_variable|exceptions|destructured_(left_assignment|parameter)|rest_assignment|method_parameters|block_parameters|body_statement|bare_(string|symbol)))|(?:pair(_pattern)?))$"
            ),
        ),
    ),
    SemanticSearchLanguage.RUST: (
        (
            SemanticClass.BOUNDARY_MODULE,
            re.compile(r"^(?:(?:(macro_rule|scoped_use_list|use_as_clause)))$"),
        ),
        (
            SemanticClass.DEFINITION_TYPE,
            re.compile(
                r"^(?:(?:lifetime_parameter)|(?:(use_(wildcard|bounds)|trait_bounds|self_parameter|token_(tree|repetition)|for_lifetimes|match_arm|let_chain))|(?:(higher_ranked_trait_bound|generic_type_with_turbofish|where_predicate)))$"
            ),
        ),
        (SemanticClass.FLOW_BRANCHING, re.compile(r"^(?:(?:let_condition))$")),
    ),
    SemanticSearchLanguage.SCALA: (
        (
            SemanticClass.DEFINITION_TYPE,
            re.compile(
                r"^(?:(?:(lazy|repeated)_parameter_type)|(?:(contravariant|covariant)_type_parameter)|(?:(simple_)?enum_case)|(?:(full_)?enum(erators?|_case|_assignment|_entry))|(?:(compound_type|applied_constructor_type|named_tuple_type|structural_type|match_type|singleton_type|type_case_clause|self_type|stable_type_identifier|identifiers|bindings|refinement|namespace_selectors|given_conditional|annotated_lambda|indented_cases|literal_type|parameter_types|access_(modifier|qualifier)))|(?:(name_and_type|view_bound))|(?:(context|lower|upper)_bound))$"
            ),
        ),
        (SemanticClass.SYNTAX_ANNOTATION, re.compile(r"^(?:(?:annotation))$")),
        (SemanticClass.SYNTAX_IDENTIFIER, re.compile(r"^(?:(?:arrow|as)_renamed_identifier)$")),
    ),
    SemanticSearchLanguage.SOLIDITY: (
        (
            SemanticClass.BOUNDARY_MODULE,
            re.compile(
                r"^(?:(?:(imports?(_(directive|list|name|specifier))?|linkage_specification)))$"
            ),
        ),
        (
            SemanticClass.DEFINITION_DATA,
            re.compile(
                r"^(?:(?:(call_struct_argument|parameter))|(?:(struct_field_assignment|struct_member)))$"
            ),
        ),
        (
            SemanticClass.DEFINITION_TYPE,
            re.compile(r"^(?:(?:(full_)?enum(erators?|_case|_assignment|_entry)))$"),
        ),
        (
            SemanticClass.OPERATION_OPERATOR,
            re.compile(
                r"^(?:(?:update_expression)|(?:member_expression)|(?:(array|slice)_access)|(?:(unary|declaration)_expression))$"
            ),
        ),
        (
            SemanticClass.SYNTAX_ANNOTATION,
            re.compile(
                r"^(?:(?:solidity_pragma_token)|(?:(pragma_directive|assembly_statement|revert_(statement|arguments)|emit_statement)))$"
            ),
        ),
        (
            SemanticClass.SYNTAX_IDENTIFIER,
            re.compile(r"^(?:(?:variable(_declarator|_declaration|_list))|value_binding_pattern)$"),
        ),
        (
            SemanticClass.SYNTAX_KEYWORD,
            re.compile(
                r"^(?:(?:(error_declaration|event_definition|constructor_definition|fallback_receive_definition|meta_type_expression|constructor_conversion_expression|inline_array_expression|user_defined_type(_definition)?|using_alias|return_type_definition|assembly_flags|any_pragma_token|type_name|expression|statement|block_statement))|(?:yul_.+))$"
            ),
        ),
    ),
    SemanticSearchLanguage.SWIFT: (
        (
            SemanticClass.DEFINITION_TYPE,
            re.compile(
                r"^(?:(?:protocol_(body|function_declaration|property_declaration|property_requirements)))$"
            ),
        ),
        (
            SemanticClass.OPERATION_OPERATOR,
            re.compile(
                r"^(?:(?:bitwise_operation)|(?:(additive|multiplicative|bitwise_operation|comparison|equality|conjunction|disjunction)_expression)|(?:(unary|declaration)_expression))$"
            ),
        ),
        (
            SemanticClass.SYNTAX_ANNOTATION,
            re.compile(r"^(?:(?:navigation_suffix|suppressed_constraint))$"),
        ),
        (
            SemanticClass.SYNTAX_IDENTIFIER,
            re.compile(r"^(?:(?:variable(_declarator|_declaration|_list))|value_binding_pattern)$"),
        ),
        (
            SemanticClass.SYNTAX_KEYWORD,
            re.compile(
                r"^(?:(?:computed_(getter|setter|modify|property)|call_suffix|capture_list_item|key_path_(expression|string_expression)|constructor_(expression|suffix)|typealias_declaration|precedence_group_(declaration|attribute|attributes)|playground_literal|raw_str_interpolation|interpolated_expression|deinit_declaration|directly_assignable_expression|guard_statement|repeat_while_statement|availability_condition|directive|control_transfer_statement|statements|associatedtype_declaration|external_macro_definition|macro_declaration|macro_invocation|enum_type_parameters|equality_constraint|subscript_declaration|tuple_type_item|value_(argument_label|pack_expansion|parameter_pack)|type_pack_expansion|type_parameter_pack|opaque_type|protocol_composition_type|metatype))$"
            ),
        ),
        (
            SemanticClass.SYNTAX_LITERAL,
            re.compile(
                r"^(?:(?:array|dictionary)_literal)|(?:(line|multi_line)_string_literal)|(?:(tuple|array_literal|dictionary_literal|nil_coalescing|open_(end|start)_range|range)_expression)$"
            ),
        ),
    ),
    SemanticSearchLanguage.TSX: (
        (
            SemanticClass.BOUNDARY_MODULE,
            re.compile(
                r"^(?:(?:(imports?(_(directive|list|name|specifier))?|linkage_specification)))$"
            ),
        ),
        (SemanticClass.DEFINITION_DATA, re.compile(r"^(?:(?:class_static_block))$")),
        (
            SemanticClass.DEFINITION_TYPE,
            re.compile(
                r"^(?:(?:mapped_type_clause)|(?:(full_)?enum(erators?|_case|_assignment|_entry)))$"
            ),
        ),
        (
            SemanticClass.FLOW_BRANCHING,
            re.compile(
                # spellchecker:off
                r"^(?:(?:finally_clause)|(?:(switch(_case|_default)|seh_(except|finally)_clause))|(?:catch_(clause|declaration)))$"
                # spellchecker:on
            ),
        ),
        (
            SemanticClass.OPERATION_INVOCATION,
            re.compile(r"^(?:(?:call_signature)|(?:(construct_signature|data_constructors?)))$"),
        ),
        (
            SemanticClass.SYNTAX_IDENTIFIER,
            re.compile(
                r"^(?:(?:assignment_pattern)|(?:(variable(_declarator|_declaration|_list))|value_binding_pattern)|(?:(nested_identifier|field_definition|object_assignment_pattern))|(?:(jsx_(attribute|expression|namespace_name)|namespace_(import|export)|named_imports|import_require_clause|constraint|default_type|rest_type|class_heritage|computed_property_name|sequence_expression))|(?:pair(_pattern)?))$"
            ),
        ),
        (SemanticClass.SYNTAX_LITERAL, re.compile(r"^(?:(?:jsx_(closing|opening)_element))$")),
    ),
    SemanticSearchLanguage.TYPESCRIPT: (
        (
            SemanticClass.BOUNDARY_MODULE,
            re.compile(
                r"^(?:(?:(imports?(_(directive|list|name|specifier))?|linkage_specification)))$"
            ),
        ),
        (SemanticClass.DEFINITION_DATA, re.compile(r"^(?:(?:class_static_block))$")),
        (
            SemanticClass.DEFINITION_TYPE,
            re.compile(
                r"^(?:(?:mapped_type_clause)|(?:(full_)?enum(erators?|_case|_assignment|_entry)))$"
            ),
        ),
        (
            SemanticClass.FLOW_BRANCHING,
            re.compile(
                # spellchecker:off
                r"^(?:(?:finally_clause)|(?:(switch(_case|_default)|seh_(except|finally)_clause))|(?:catch_(clause|declaration)))$"
                # spellchecker:on
            ),
        ),
        (
            SemanticClass.OPERATION_INVOCATION,
            re.compile(r"^(?:(?:call_signature)|(?:(construct_signature|data_constructors?)))$"),
        ),
        (
            SemanticClass.SYNTAX_IDENTIFIER,
            re.compile(
                r"^(?:(?:assignment_pattern)|(?:(variable(_declarator|_declaration|_list))|value_binding_pattern)|(?:(nested_identifier|field_definition|object_assignment_pattern))|(?:(jsx_(attribute|expression|namespace_name)|namespace_(import|export)|named_imports|import_require_clause|constraint|default_type|rest_type|class_heritage|computed_property_name|sequence_expression))|(?:pair(_pattern)?))$"
            ),
        ),
        (SemanticClass.SYNTAX_LITERAL, re.compile(r"^(?:(?:jsx_(closing|opening)_element))$")),
    ),
    SemanticSearchLanguage.YAML: ((SemanticClass.SYNTAX_LITERAL, re.compile(r"^(?:(?:scalar))$")),),
}

# Generic cross-language patterns
# Structure: tuple[(SemanticClass, compiled_pattern), ...]
GENERIC_PATTERNS: tuple[tuple[SemanticClass, re.Pattern[str]], ...] = (
    (
        SemanticClass.BOUNDARY_MODULE,
        re.compile(
            r"^(?:(?:(aliased_import|extern_alias_directive|import_spec))|(?:(import|export|namespace)_(clause|attribute|spec_list|use_clause|use_group)))$"
        ),
    ),
    (
        SemanticClass.DEFINITION_CALLABLE,
        re.compile(r"^(?:(?:(method|property|function|abstract_method|index)_signature))$"),
    ),
    (
        SemanticClass.DEFINITION_DATA,
        re.compile(
            r"^(?:(?:(formal|lambda|class|function_value|bracketed)_parameters?)|(?:(block|error|event|return|call_struct_argument|function_pointer|hash_splat|keyword|optional|simple|splat|variadic|yul_variable_declaration)_parameter)|(?:.+_declaration)|(?:.+_initializer(_list)?))$"
        ),
    ),
    (
        SemanticClass.DEFINITION_TYPE,
        re.compile(
            r"^(?:(?:type_(argument|parameter|constraint|projection|bound|test|case|requirement|elem)s?(_list)?)|(?:(adding|omitting|opting|asserts|type_predicate)_type_annotation)|(?:(extends_type_clause|derives_clause|inheritance_specifier))|(?:(array|dictionary|optional|function|generic|projected|qualified)_type)|(?:template_(argument_list|parameter_list|declaration|body|substitution|template_parameter_declaration))|(?:type_(alias|annotation|application|binder|binding|lambda|parameter(_declaration)?|predicate|spec|family_(result|injectivity)))|(?:(extends|implements|base|super|delegation)_(clause|list|interfaces|class|specifiers?))|(?:.+_constraint))$"
        ),
    ),
    (
        SemanticClass.FLOW_BRANCHING,
        re.compile(
            r"^(?:(?:(switch|case)_(body|block|entry|section|label|rule|expression_arm|pattern|block_statement_group))|(?:(keyword|token_binding|view)_pattern)|(?:(catch|finally|rescue|after|else)_(block|clause|formal_parameter))|(?:(with|from|where|let|join|order_by|group|select|when|catch_filter)_clause)|(?:.+_pattern))$"
        ),
    ),
    (
        SemanticClass.OPERATION_OPERATOR,
        re.compile(
            r"^(?:(?:(spread|splat|hash_splat|dictionary_splat|variadic)_(element|argument|parameter|unpacking|pattern|type))|(?:(prefix|postfix|navigation|check)_expression))$"
        ),
    ),
    (
        SemanticClass.OPERATION_INVOCATION,
        re.compile(
            r"^(?:(?:(getter|setter|modify|didset|willset)_(specifier|clause))|(?:.+_invocation))$"
        ),
    ),
    (
        SemanticClass.SYNTAX_ANNOTATION,
        re.compile(
            r"^(?:(?:decorator)|(?:preproc_(elif|ifdef|elifdef|defined|error|line|pragma|undef|warning))|(?:.+_(modifier|modifiers|specifier|qualifier)))$"
        ),
    ),
    (
        SemanticClass.SYNTAX_LITERAL,
        re.compile(
            r"^(?:(?:(heredoc|nowdoc)_(body|redirect))|(?:(bare|quoted)_(string|symbol|atom|keyword|expression|pattern|type)))$"
        ),
    ),
    (
        SemanticClass.SYNTAX_PUNCTUATION,
        re.compile(
            r"^(?:(?:(field|ordered_field)_declaration_list)|(?:(expression|statement)_(list|case))|(?:(arguments?|parameters))|(?:(program|source_file|compilation_unit|translation_unit|document|stylesheet|chunk))|(?:.+_(list|arguments?))|(?:.+_(body|block|block_list)))$"
        ),
    ),
)

# Predicate-based special cases (preserved from original COMPOSITE_CHECKS)
# These require runtime predicates and cannot be converted to pure regex patterns
PREDICATE_CHECKS: tuple[CompositeCheck, ...] = (
    # Export pattern - Token vs CompositeThing classification
    CompositeCheck(
        name_pattern=re.compile(r"^(module_)?export(_specifier)?$"),
        classification=SemanticClass.BOUNDARY_MODULE,
        languages=JavaScriptFamily | frozenset({SemanticSearchLanguage.HASKELL}),
        predicate=lambda thing: SemanticClass.SYNTAX_KEYWORD  # type: ignore
        if isinstance(thing, Token)
        else SemanticClass.BOUNDARY_MODULE,
    ),
    # Constructor pattern - Conditional classification based on name content
    CompositeCheck(
        name_pattern=re.compile(
            r"^(constructor_(definition|delegation_call|expression|invocation|suffix|synonyms))$"
        ),
        classification=SemanticClass.DEFINITION_DATA,
        languages=frozenset({
            SemanticSearchLanguage.SOLIDITY,
            SemanticSearchLanguage.KOTLIN,
            SemanticSearchLanguage.SWIFT,
            SemanticSearchLanguage.HASKELL,
        }),
        predicate=lambda thing: SemanticClass.OPERATION_DATA
        if "suffix" in thing.name or "synonyms" in thing.name
        else SemanticClass.OPERATION_INVOCATION
        if "invocation" in thing.name or "delegation_call" in thing.name
        else SemanticClass.DEFINITION_DATA,  # type: ignore
    ),
)


def get_checks(thing_name: str, language: SemanticSearchLanguage) -> Iterator[SemanticClass]:
    """Get all classifications for a thing name using optimized tiered lookup.

    Tiered lookup strategy (language is always known):
    1. Language-specific patterns (fastest, most specific)
    2. Generic cross-language patterns (broader coverage)
    3. Predicate-based checks (slowest, for special cases)

    Args:
        thing_name: The name of the thing to classify
        language: The programming language (always known per user confirmation)

    Yields:
        Matching SemanticClass values
    """
    # Tier 1: Language-specific patterns (if available for this language)
    if lang_patterns := LANG_SPECIFIC_PATTERNS.get(language):
        for classification, pattern in lang_patterns:
            if pattern.match(thing_name):
                yield classification

    # Tier 2: Generic cross-language patterns
    for classification, pattern in GENERIC_PATTERNS:
        if pattern.match(thing_name):
            yield classification

    # Tier 3: Predicate-based special cases (note: requires full CompositeThing, not just name)
    # These will be handled in the classifier where we have access to the full CompositeThing


__all__ = (
    "GENERIC_PATTERNS",
    "IS_ANNOTATION",
    "IS_IDENTIFIER",
    "IS_KEYWORD",
    "IS_LITERAL",
    "IS_OPERATOR",
    "LANGUAGE_SPECIFIC_TOKEN_EXCEPTIONS",
    "LANG_SPECIFIC_PATTERNS",
    "NAMED_NODE_COUNTS",
    "NOT_SYMBOL",
    "PREDICATE_CHECKS",
    "get_checks",
)
