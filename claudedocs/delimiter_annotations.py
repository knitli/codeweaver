# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""
Delimiter Semantic Annotations
Complete mapping of 78 unique delimiters to their semantic metadata.

Priority ranges (0-100):
- 90-100: Comments and documentation (highest priority - exclude from code analysis)
- 70-89:  Declarations (functions, classes, modules)
- 50-69:  Control flow and structural blocks
- 30-49:  Data structures and literals
- 10-29:  Generic structural delimiters

Nesting rules:
- Comments: nestable=False (prevent nesting comments inside themselves)
- Strings/literals: nestable=False (prevent nested string confusion)
- Code blocks: nestable=True (allow nested structures)
"""

from codeweaver._constants import Delimiter, DelimiterKind


# ============================================================================
# ANNOTATED DELIMITERS (78 unique)
# ============================================================================

ANNOTATED_DELIMITERS = {
    # ========================================================================
    # COMMENTS & DOCUMENTATION (Priority: 90-100)
    # ========================================================================
    # Line comments
    Delimiter("#", "\n"): {
        "kind": DelimiterKind.COMMENT_LINE,
        "description": "Single-line comment (Python, Ruby, Bash, etc.)",
        "nestable": False,
        "priority": 95,
    },
    Delimiter("//", "\n"): {
        "kind": DelimiterKind.COMMENT_LINE,
        "description": "Single-line comment (C, C++, Java, JavaScript, etc.)",
        "nestable": False,
        "priority": 95,
    },
    Delimiter("///", "\n"): {
        "kind": DelimiterKind.COMMENT_LINE,
        "description": "Documentation comment (Rust, C#)",
        "nestable": False,
        "priority": 96,  # Higher than regular comments
    },
    Delimiter("--", "\n"): {
        "kind": DelimiterKind.COMMENT_LINE,
        "description": "Single-line comment (Haskell, SQL, Lua)",
        "nestable": False,
        "priority": 95,
    },
    Delimiter("%", "\n"): {
        "kind": DelimiterKind.COMMENT_LINE,
        "description": "Single-line comment (MATLAB, Erlang, Prolog)",
        "nestable": False,
        "priority": 95,
    },
    Delimiter("%%", "\n"): {
        "kind": DelimiterKind.COMMENT_LINE,
        "description": "Cell/section comment (MATLAB)",
        "nestable": False,
        "priority": 96,
    },
    Delimiter(";", "\n"): {
        "kind": DelimiterKind.COMMENT_LINE,
        "description": "Single-line comment (Assembly, Lisp, Clojure)",
        "nestable": False,
        "priority": 95,
    },
    Delimiter("!", "\n"): {
        "kind": DelimiterKind.COMMENT_LINE,
        "description": "Single-line comment (Fortran)",
        "nestable": False,
        "priority": 95,
    },
    # Block comments
    Delimiter("/*", "*/"): {
        "kind": DelimiterKind.COMMENT_BLOCK,
        "description": "Block comment (C, C++, Java, JavaScript, etc.)",
        "nestable": False,
        "priority": 94,
    },
    Delimiter("/**", "*/"): {
        "kind": DelimiterKind.COMMENT_BLOCK,
        "description": "Documentation block comment (JavaDoc style)",
        "nestable": False,
        "priority": 96,  # Higher priority than regular block comments
    },
    Delimiter("(*", "*)"): {
        "kind": DelimiterKind.COMMENT_BLOCK,
        "description": "Block comment (OCaml, Pascal, Coq)",
        "nestable": True,  # OCaml allows nested comments
        "priority": 94,
    },
    Delimiter("{-", "-}"): {
        "kind": DelimiterKind.COMMENT_BLOCK,
        "description": "Block comment (Haskell)",
        "nestable": True,  # Haskell allows nested comments
        "priority": 94,
    },
    Delimiter("#|", "|#"): {
        "kind": DelimiterKind.COMMENT_BLOCK,
        "description": "Block comment (Lisp)",
        "nestable": True,
        "priority": 94,
    },
    Delimiter("#=", "=#"): {
        "kind": DelimiterKind.COMMENT_BLOCK,
        "description": "Block comment (Julia)",
        "nestable": True,
        "priority": 94,
    },
    Delimiter("#[", "#]"): {
        "kind": DelimiterKind.COMMENT_BLOCK,
        "description": "Block comment (Nim)",
        "nestable": False,
        "priority": 94,
    },
    Delimiter("%{", "%}"): {
        "kind": DelimiterKind.COMMENT_BLOCK,
        "description": "Block comment (MATLAB)",
        "nestable": False,
        "priority": 94,
    },
    Delimiter("<!--", "-->"): {
        "kind": DelimiterKind.COMMENT_BLOCK,
        "description": "HTML/XML comment",
        "nestable": False,
        "priority": 94,
    },
    # Docstrings
    Delimiter('"""', '"""'): {
        "kind": DelimiterKind.DOCSTRING,
        "description": "Docstring (Python, Dart)",
        "nestable": False,
        "priority": 97,  # Highest documentation priority
    },
    Delimiter("'''", "'''"): {
        "kind": DelimiterKind.DOCSTRING,
        "description": "Docstring (Python)",
        "nestable": False,
        "priority": 97,
    },
    Delimiter("=begin", "=end"): {
        "kind": DelimiterKind.DOCSTRING,
        "description": "Documentation block (Ruby, Perl, Raku)",
        "nestable": False,
        "priority": 97,
    },
    Delimiter("@doc", "@doc"): {
        "kind": DelimiterKind.DOCSTRING,
        "description": "Documentation annotation (Elixir)",
        "nestable": False,
        "priority": 97,
    },
    # ========================================================================
    # DECLARATIONS (Priority: 70-89)
    # ========================================================================
    # Functions
    Delimiter("def", "end"): {
        "kind": DelimiterKind.FUNCTION,
        "description": "Function definition (Python, Ruby, etc.)",
        "nestable": True,
        "priority": 85,
    },
    Delimiter("function", "end"): {
        "kind": DelimiterKind.FUNCTION,
        "description": "Function definition (Julia, MATLAB, Lua)",
        "nestable": True,
        "priority": 85,
    },
    Delimiter("function", "end function"): {
        "kind": DelimiterKind.FUNCTION,
        "description": "Function definition (Fortran)",
        "nestable": True,
        "priority": 85,
    },
    Delimiter("fn", "end"): {
        "kind": DelimiterKind.FUNCTION,
        "description": "Function definition (Elixir)",
        "nestable": True,
        "priority": 85,
    },
    Delimiter("fun", "end"): {
        "kind": DelimiterKind.FUNCTION,
        "description": "Function definition (Erlang, SML)",
        "nestable": True,
        "priority": 85,
    },
    Delimiter("subroutine", "end subroutine"): {
        "kind": DelimiterKind.FUNCTION,
        "description": "Subroutine definition (Fortran)",
        "nestable": True,
        "priority": 85,
    },
    Delimiter("macro", "end"): {
        "kind": DelimiterKind.FUNCTION,
        "description": "Macro definition (Julia)",
        "nestable": True,
        "priority": 85,
    },
    # Classes and structs
    Delimiter("class", "end"): {
        "kind": DelimiterKind.CLASS,
        "description": "Class definition (Python, Ruby, etc.)",
        "nestable": True,
        "priority": 88,  # Higher than functions (classes contain functions)
    },
    Delimiter("struct", "end"): {
        "kind": DelimiterKind.STRUCT,
        "description": "Struct definition (Julia, OCaml, F#)",
        "nestable": True,
        "priority": 88,
    },
    Delimiter("sig", "end"): {
        "kind": DelimiterKind.INTERFACE,
        "description": "Signature/interface definition (OCaml, F#)",
        "nestable": True,
        "priority": 88,
    },
    # Modules and namespaces
    Delimiter("module", "end"): {
        "kind": DelimiterKind.MODULE,
        "description": "Module definition (Ruby, Elixir, etc.)",
        "nestable": True,
        "priority": 89,  # Highest declaration priority (modules contain everything)
    },
    # ========================================================================
    # CONTROL FLOW (Priority: 50-69)
    # ========================================================================
    # Conditionals
    Delimiter("if", "end"): {
        "kind": DelimiterKind.CONDITIONAL,
        "description": "Conditional block (Ruby, Lua, Julia, etc.)",
        "nestable": True,
        "priority": 60,
    },
    Delimiter("if", "end if"): {
        "kind": DelimiterKind.CONDITIONAL,
        "description": "Conditional block (Fortran)",
        "nestable": True,
        "priority": 60,
    },
    Delimiter("if", "fi"): {
        "kind": DelimiterKind.CONDITIONAL,
        "description": "Conditional block (Bash)",
        "nestable": True,
        "priority": 60,
    },
    Delimiter("if", "then"): {
        "kind": DelimiterKind.CONDITIONAL,
        "description": "Conditional expression (Haskell, Elm, R)",
        "nestable": True,
        "priority": 60,
    },
    Delimiter("else", "end"): {
        "kind": DelimiterKind.CONDITIONAL,
        "description": "Else block (Elm, Ruby, etc.)",
        "nestable": True,
        "priority": 59,  # Slightly lower than if
    },
    Delimiter("unless", "end"): {
        "kind": DelimiterKind.CONDITIONAL,
        "description": "Unless block (Ruby, Perl)",
        "nestable": True,
        "priority": 60,
    },
    Delimiter("case", "end"): {
        "kind": DelimiterKind.CONDITIONAL,
        "description": "Case statement (Ruby, Elixir, etc.)",
        "nestable": True,
        "priority": 60,
    },
    Delimiter("case", "esac"): {
        "kind": DelimiterKind.CONDITIONAL,
        "description": "Case statement (Bash)",
        "nestable": True,
        "priority": 60,
    },
    Delimiter("switch", "end"): {
        "kind": DelimiterKind.CONDITIONAL,
        "description": "Switch statement (MATLAB)",
        "nestable": True,
        "priority": 60,
    },
    Delimiter("select case", "end select"): {
        "kind": DelimiterKind.CONDITIONAL,
        "description": "Select case statement (Fortran)",
        "nestable": True,
        "priority": 60,
    },
    Delimiter("match", "end"): {
        "kind": DelimiterKind.CONDITIONAL,
        "description": "Pattern matching (Coq, OCaml)",
        "nestable": True,
        "priority": 60,
    },
    # Loops
    Delimiter("for", "end"): {
        "kind": DelimiterKind.LOOP,
        "description": "For loop (Julia, MATLAB, etc.)",
        "nestable": True,
        "priority": 58,
    },
    Delimiter("for", "done"): {
        "kind": DelimiterKind.LOOP,
        "description": "For loop (Bash)",
        "nestable": True,
        "priority": 58,
    },
    Delimiter("while", "end"): {
        "kind": DelimiterKind.LOOP,
        "description": "While loop (Ruby, Julia, etc.)",
        "nestable": True,
        "priority": 58,
    },
    Delimiter("while", "done"): {
        "kind": DelimiterKind.LOOP,
        "description": "While loop (Bash)",
        "nestable": True,
        "priority": 58,
    },
    Delimiter("until", "done"): {
        "kind": DelimiterKind.LOOP,
        "description": "Until loop (Bash)",
        "nestable": True,
        "priority": 58,
    },
    Delimiter("do", "end"): {
        "kind": DelimiterKind.LOOP,
        "description": "Do block (Ruby, Elixir, Haskell, etc.)",
        "nestable": True,
        "priority": 57,
    },
    Delimiter("do", "done"): {
        "kind": DelimiterKind.LOOP,
        "description": "Do block (Bash)",
        "nestable": True,
        "priority": 57,
    },
    Delimiter("do", "end do"): {
        "kind": DelimiterKind.LOOP,
        "description": "Do block (Fortran)",
        "nestable": True,
        "priority": 57,
    },
    Delimiter("parfor", "end"): {
        "kind": DelimiterKind.LOOP,
        "description": "Parallel for loop (MATLAB)",
        "nestable": True,
        "priority": 58,
    },
    # Error handling
    Delimiter("try", "end"): {
        "kind": DelimiterKind.TRY_CATCH,
        "description": "Try-catch block (Ruby, Julia, MATLAB)",
        "nestable": True,
        "priority": 55,
    },
    Delimiter("receive", "end"): {
        "kind": DelimiterKind.TRY_CATCH,
        "description": "Receive block (Erlang)",
        "nestable": True,
        "priority": 55,
    },
    # Other control structures
    Delimiter("let", "end"): {
        "kind": DelimiterKind.BLOCK,
        "description": "Let binding block (Julia)",
        "nestable": True,
        "priority": 54,
    },
    Delimiter("let", "in"): {
        "kind": DelimiterKind.BLOCK,
        "description": "Let expression (Haskell, Elm, Dhall)",
        "nestable": True,
        "priority": 54,
    },
    Delimiter("begin", "end"): {
        "kind": DelimiterKind.BLOCK,
        "description": "Begin-end block (Ruby, Julia, OCaml, F#)",
        "nestable": True,
        "priority": 53,
    },
    Delimiter("where", "\n"): {
        "kind": DelimiterKind.BLOCK,
        "description": "Where clause (Haskell)",
        "nestable": True,
        "priority": 52,
    },
    # ========================================================================
    # STRUCTURAL DELIMITERS (Priority: 30-49)
    # ========================================================================
    Delimiter("{", "}"): {
        "kind": DelimiterKind.BLOCK,
        "description": "Generic code block or object literal",
        "nestable": True,
        "priority": 40,
    },
    Delimiter("(", ")"): {
        "kind": DelimiterKind.TUPLE,
        "description": "Parentheses - grouping, tuples, function calls",
        "nestable": True,
        "priority": 35,
    },
    Delimiter("[", "]"): {
        "kind": DelimiterKind.ARRAY,
        "description": "Array or list literal",
        "nestable": True,
        "priority": 35,
    },
    Delimiter("{|", "|}"): {
        "kind": DelimiterKind.OBJECT,
        "description": "Record/object syntax (OCaml, F#, Coq)",
        "nestable": True,
        "priority": 38,
    },
    # ========================================================================
    # STRING LITERALS & DATA (Priority: 30-49)
    # ========================================================================
    Delimiter('"', '"'): {
        "kind": DelimiterKind.STRING,
        "description": "Double-quoted string",
        "nestable": False,
        "priority": 45,  # Higher than structural delimiters
    },
    Delimiter("'", "'"): {
        "kind": DelimiterKind.STRING,
        "description": "Single-quoted string",
        "nestable": False,
        "priority": 45,
    },
    Delimiter("`", "`"): {
        "kind": DelimiterKind.TEMPLATE_STRING,
        "description": "Template string or backtick string (JavaScript, Go, Haskell)",
        "nestable": False,
        "priority": 46,
    },
    Delimiter("''", "''"): {
        "kind": DelimiterKind.STRING,
        "description": "Empty string or string escape (Dhall)",
        "nestable": False,
        "priority": 44,
    },
    Delimiter('"`', '"`'): {
        "kind": DelimiterKind.STRING,
        "description": "Quasi-quoted string (Lisp)",
        "nestable": False,
        "priority": 46,
    },
    Delimiter('#"', '"'): {
        "kind": DelimiterKind.STRING,
        "description": "Reader macro string (Clojure)",
        "nestable": False,
        "priority": 46,
    },
    Delimiter("#'", "'"): {
        "kind": DelimiterKind.STRING,
        "description": "Reader macro quote (Clojure)",
        "nestable": False,
        "priority": 46,
    },
    Delimiter("r#", "#"): {
        "kind": DelimiterKind.STRING,
        "description": "Raw string literal (Rust, R)",
        "nestable": False,
        "priority": 46,
    },
    # ========================================================================
    # MARKUP & TEMPLATES (Priority: 40-49)
    # ========================================================================
    Delimiter("<", ">"): {
        "kind": DelimiterKind.TEMPLATE_STRING,
        "description": "HTML/XML tag or template",
        "nestable": True,
        "priority": 42,
    },
    Delimiter("\\begin{", "\\end{"): {
        "kind": DelimiterKind.BLOCK,
        "description": "LaTeX environment",
        "nestable": True,
        "priority": 43,
    },
    Delimiter("\\if", "\\fi"): {
        "kind": DelimiterKind.CONDITIONAL,
        "description": "LaTeX conditional",
        "nestable": True,
        "priority": 43,
    },
    # ========================================================================
    # PROOF SYSTEMS (Priority: 70-79)
    # ========================================================================
    Delimiter("Proof", "Qed"): {
        "kind": DelimiterKind.BLOCK,
        "description": "Completed proof (Coq)",
        "nestable": False,
        "priority": 75,
    },
    Delimiter("Proof", "Defined"): {
        "kind": DelimiterKind.BLOCK,
        "description": "Transparent proof (Coq)",
        "nestable": False,
        "priority": 75,
    },
    Delimiter("Proof", "Admitted"): {
        "kind": DelimiterKind.BLOCK,
        "description": "Admitted proof (Coq)",
        "nestable": False,
        "priority": 75,
    },
    # ========================================================================
    # SPECIAL/UTILITY (Priority: 10-29)
    # ========================================================================
    Delimiter("*", ";"): {
        "kind": DelimiterKind.COMMENT_BLOCK,
        "description": "SAS block comment",
        "nestable": False,
        "priority": 94,
    },
    # Empty/newline delimiters (lowest priority)
    Delimiter("", ""): {
        "kind": DelimiterKind.UNKNOWN,
        "description": "Empty delimiter (fallback)",
        "nestable": True,
        "priority": 1,
    },
    Delimiter("\n", "\n"): {
        "kind": DelimiterKind.UNKNOWN,
        "description": "Line-based splitting",
        "nestable": True,
        "priority": 5,
    },
}

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def get_annotated_delimiter(start: str, end: str) -> Delimiter:
    """Get a delimiter with full semantic annotations.

    Args:
        start: Start delimiter string
        end: End delimiter string

    Returns:
        Delimiter with kind, description, nestable, and priority set
    """
    key = Delimiter(start, end)
    annotations = ANNOTATED_DELIMITERS.get(key)

    if annotations:
        return Delimiter(
            start=start,
            end=end,
            kind=annotations["kind"],
            description=annotations["description"],
            nestable=annotations["nestable"],
            priority=annotations["priority"],
        )

    # Fallback: return unannotated delimiter
    return Delimiter(start, end)


def generate_delimiter_definitions() -> str:
    """Generate Python code for delimiter definitions with annotations.

    Returns:
        Python code string with annotated Delimiter instantiations
    """
    lines = []

    # Group by priority ranges
    priority_groups = {
        "Comments & Documentation (90-100)": [],
        "Declarations (70-89)": [],
        "Control Flow (50-69)": [],
        "Structural & Data (30-49)": [],
        "Utility (1-29)": [],
    }

    for delim, annot in ANNOTATED_DELIMITERS.items():
        priority = annot["priority"]
        if priority >= 90:
            group = "Comments & Documentation (90-100)"
        elif priority >= 70:
            group = "Declarations (70-89)"
        elif priority >= 50:
            group = "Control Flow (50-69)"
        elif priority >= 30:
            group = "Structural & Data (30-49)"
        else:
            group = "Utility (1-29)"

        code = (
            f"Delimiter({delim.start!r}, {delim.end!r}, "
            f"kind=DelimiterKind.{annot['kind'].name}, "
            f"description={annot['description']!r}, "
            f"nestable={annot['nestable']}, "
            f"priority={annot['priority']})"
        )
        priority_groups[group].append(code)

    # Generate output
    for group_name, items in priority_groups.items():
        if items:
            lines.append(f"\n# {group_name}")
            lines.extend(items)

    return "\n".join(lines)


if __name__ == "__main__":
    # Print generated delimiter definitions
    print("# ============================================================================")
    print("# ANNOTATED DELIMITER DEFINITIONS")
    print("# ============================================================================")
    print(generate_delimiter_definitions())

    # Statistics
    print(f"\n\n# Total delimiters annotated: {len(ANNOTATED_DELIMITERS)}")

    # Count by kind
    from collections import Counter

    kinds = Counter(annot["kind"] for annot in ANNOTATED_DELIMITERS.values())
    print("\n# Delimiters by kind:")
    for kind, count in kinds.most_common():
        print(f"#   {kind.value}: {count}")
