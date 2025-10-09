# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Constants and patterns used in semantic analysis."""

import re

from types import MappingProxyType

from codeweaver.language import SemanticSearchLanguage


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
"""Count of top-level named nodes in each language's grammar. It took me awhile to come to this approach, but it's fast, reliable, and way less complicated than anything else I tried."""

LANGUAGE_SPECIFIC_TOKEN_EXCEPTIONS = MappingProxyType({
    SemanticSearchLanguage.C_LANG: {
        'L"': "structural",
        'U"': "structural",
        'u"': "structural",
        'u8"': "structural",
        "L'": "structural",
        "U'": "structural",
        "u'": "structural",
        "u8'": "structural",
        "LR'": "structural",
        "UR'": "structural",
        "uR'": "structural",
        "u8R'": "structural",
        'LR"': "structural",
        'UR"': "structural",
        'R"': "structural",
        'uR"': "structural",
        'u8R"': "structural",
    },
    SemanticSearchLanguage.C_PLUS_PLUS: {
        'L"': "structural",
        'U"': "structural",
        'u"': "structural",
        'u8"': "structural",
        "L'": "structural",
        "U'": "structural",
        "u'": "structural",
        "u8'": "structural",
        "LR'": "structural",
        "UR'": "structural",
        "uR'": "structural",
        "u8R'": "structural",
        'LR"': "structural",
        'UR"': "structural",
        'R"': "structural",
        'uR"': "structural",
        'u8R"': "structural",
        "literal_suffix": "structural",
    },
    SemanticSearchLanguage.C_SHARP: {"string_literal_encoding": "structural"},
    SemanticSearchLanguage.GO: {"blank_identifier": "structural"},
    SemanticSearchLanguage.TYPESCRIPT: {"unique symbol": "identifier"},
    SemanticSearchLanguage.JSX: {"unique symbol": "identifier"},
    SemanticSearchLanguage.JAVASCRIPT: {"...": "operator", "static get": "identifier"},
    SemanticSearchLanguage.RUST: {"macro_rule!": "structural"},
    SemanticSearchLanguage.SOLIDITY: {"evmasm": "structural", "int": "structural"}
    | {f"int{bits}": "structural" for bits in range(8, 257, 8)}
    | {f"uint{bits}": "structural" for bits in range(8, 257, 8)},
    SemanticSearchLanguage.RUBY: {
        "defined?": "structural",
        r"%w": "structural",
        r"%i": "structural",
    },
    SemanticSearchLanguage.PHP: {"yield_from": "structural", "@": "structural"},
    SemanticSearchLanguage.JAVA: {"non-sealed": "structural"},
    SemanticSearchLanguage.KOTLIN: {
        "as?": "structural",
        "return@": "structural",
        "super@": "structural",
        "this@": "structural",
    },
    SemanticSearchLanguage.SWIFT: {
        r"unowned\(safe\)": "structural",
        r"unowned\(unsafe\)": "structural",
    },
})
"""Exceptions to the general rules for token classification. These are language-specific tokens that would otherwise be misclassified by the general regex patterns below and other classification logic."""

"""
The only potential issue is if the nodes are not a complete set.
"""
# spellchecker:off
IS_OPERATOR = re.compile(
    r"""^
        (
            (
                [\+\-\*/%&?|\^~!=<>]+
            )
            |
            \.\.\.|not\sin|in|-(a|o)|!?i(n|s)|as(!|\?)|is|gt|(bit)?(and|xor|or)|lt|le|ge|eq|not_eq|s?div|x?or_eq
        )
        $""",
    re.VERBOSE,
)
"""Not perfect but should get us >90% with a couple false positives."""

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
        [Tt]rue|[Ff]alse|[nN](ull(ptr)?|il|one(Type)?)|(\(\))?|const(expr)?|0x[0-9a-f]+|\d+(\.\d+)?|\\x00|1|.*literal.*
    )
    $""",
    re.IGNORECASE | re.VERBOSE,
)
"""Literal tokens in supported languages."""

IS_KEYWORD = re.compile(
    r"""^
    (
    \#
        (defined?|el(if((in)?def)?|se)?|end(if|region)|region|if|pragma|ifndef|undef|warning)?
        |
    @
        (escaping|keyframes)?
        |
        _
        |
    abstract|accessor|actor|add(mod|ress)?|alignof|all|any|ascending|ass(embly|ert)|async|a(s|t)|await
        |
    ba(lance|se)|begin|blockhash|bool(ean)?|break(_statement)?
        |
    by(
        tes(
            [1-3][0-9]?
            )?
        )?
        |
    ca(se|tch(_keyword)?)
        |
    cha(n|r)(acter)?
    |
    cl(ass|one)
    |
    con(st(ant|init|ructor)?|tinue)
    de(clare|f|fault(_keyword)?|fer|l(ete)?)|difficulty|disable|do(ne)?|dyn(amic?|lete)
        |
    e
        (ach|cho|lif|llipsis|ls((e(\s?if )?| if)?
            |nabled?|nd(switch|foreach)?)|num
        |
    ex
        (cept|p(ect|ort)?|it|r|tern(al)?|tglob_pattern|tends?)
        |
    fallthrough
        |
    fi
      (
      (le(_description|private)?)
        |
      (n(ally|ish)?|xed)
      )?
        |
    float
        |
    fn
        |
    for
        (ever|each|m(ember|odifier))?
        |
    from
        |
    gen|get(ter)?|global|goto
        |
    haddock|hash_bang_line|heredoc(_end|_start)?|hex|hi(ding|dden)?
        |
    id_name|if|impl(ements)?|import(ant)?
        |
    in
        (clude|herits?|lines?|out(put)?|ternal(_ref)|st(ance|ead)of|teger|terface|to)?
        |
    key
        ([oO]f|[Pp]ath|frames?(_name)?|word)?
        |
    lazy|let|lifetime|lo(ck|g[1-9]|ng)?
        |
    ma(p|tch)|me(ta|thod)|mod(ule)?|move|mutable
        |
    namespace|new|no[Rr]eturn
        |
    of|only|option(al)?|override
        |
    p
     (ackage|ayable|ragma|rivate|roperty|rotected|ublic|ure)?
        |
    r(aise|eadonly)
    |
    ref | re(p(eat|lace)?|quires?|strict|turn)?
    |
    [Ss]e
         (aled|conds|lf|t(tter)?|tparam)
        |
    s
     (hort|igil_name|igned|ized|tackalloc|ta(rt|tic)|tring|truct|uper|witch|ynchronized)
        |
    t (hen|hrows?|o|rans(itive|parent)|rait|ry)
        |
    type ([oO]f|alias|def|name)?
        |
    un
      (checked|less|ion|safe|set|signed|til)
        |
    us(ed?|ing)
        |
    v
     (ar|ia|iew|irtual|oid|olatile)
    w
     (here(_keyword)?|ith|hile)
        |
    yield(\sfrom)?
    )
    $""",
    re.VERBOSE,
)
"""keywords in supported languages, with some variations and suffixes to catch more cases."""
# spellchecker:on
