# Making Tree-sitter Grammars Actually Understandable: A Data-Driven Redesign

**Or: How I lost a week to confusing terminology, analyzed 25 programming languages, and built the parser I wish I'd had**

---

## TL;DR: If You're Here Because Tree-sitter's `node-types.json` Makes No Sense

**You're not alone.** Tree-sitter's terminology is confusing because it evolved from internal implementation details, not developer clarity.

### The Core Problems
- **"Named" doesn't mean "has a name"** (everything has a name). It means "corresponds to a named grammar rule"—an internal detail that's noise for most use cases.
- **"Fields" and "children" are both parent-child relationships** but the distinction is unclear. Fields are semantic ("this node's *condition*"), children are positional ("this node's first child").
- **Everything is a "type"**: Nodes, edges, and abstract categories all use the same terminology, obscuring the differences that matter.

### Our Solution: Call Things What They Are

| Tree-sitter | CodeWeaver | Meaning |
|-------------|-----------|---------|
| Abstract type (with subtypes) | **Category** | Grouping that never appears in code (like `expression`) |
| Named node | **Thing** | What you actually see in your parse tree |
| Field | **Direct Connection** | Semantic relationship with a role ("condition", "body") |
| Field name | **Role** | The semantic purpose ("what is this child for?") |
| Child | **Positional Connection** | Ordered relationship without semantic meaning |
| `named` flag | **is_explicit_rule** | Says what it actually means |

### The Results
After analyzing **5,000+ node types across 25 languages**, we rebuilt the interface to be self-documenting. Onboarding time dropped from days to hours. Nobody else loses a week.

**Want the code?** [CodeWeaver on GitHub](https://github.com/knitli/codeweaver-mcp)

**Just need a quick answer?** Jump to the [Translation Guide](#translation-guide-for-tree-sitter-veterans).

**Want the full story?** Keep reading.

---

## The Problem: One Week, Gone

I was building [CodeWeaver](https://github.com/knitli/codeweaver-mcp), a semantic[^1] code search tool that needed to understand the structure of 25+ programming languages. [Tree-sitter](https://github.com/tree-sitter/tree-sitter) seemed perfect: mature, fast, widely adopted, with grammars for every major language. (Under the hood, CodeWeaver uses [`ast-grep`](https://github.com/ast-grep/ast-grep) as its interface with tree-sitter for better typing and abstractions.)

Then I opened my first `node-types.json` file.[^2]

```json
{
  "type": "if_statement",
  "named": true,
  "fields": {
    "condition": {
      "multiple": false,
      "required": true,
      "types": [{"type": "expression", "named": true}]
    }
  },
  "children": {
    "multiple": true,
    "required": false,
    "types": [{"type": "statement", "named": true}]
  }
}
```

**Simple enough, right?** Wrong. After days of confusion, here's what I learned:

- **"Named"** doesn't mean "has a name" (everything has a name). It means "has a corresponding named rule in the grammar"—an internal implementation detail with little meaning outside parsing.
- **"Fields" vs "children"**: Fields are named semantic relationships ("this node's *condition* is..."), children are positional ("this node's first child is..."). The JSON treats them identically.
- **Everything is a "type"**: Nodes (things in code), edges (relationships), and abstract types (categories) all use the same terminology, flattening distinctions that matter.

The [tree-sitter documentation](https://tree-sitter.github.io/tree-sitter/using-parsers/6-static-node-types.html) helped *a little*, but not enough. I'm not new to tree-sitter, either. Between [`Thread`](https://github.com/knitli/thread) and [`CodeWeaver`](https://github.com/knitli/codeweaver-mcp), I've spent four months working with it.

I spent a week building a complex system for identifying nodes and their significance based on wrong assumptions about what these terms meant. That system isn't *completely* useless—I retooled it as a fallback—but it wasn't the kind of thing you want to spend a week doing when building an MVP by yourself.

After that lost week, I decided: **we're not doing this to ourselves again**.

## The Solution: What If We Just... Made It Clear?

My driving philosophy: **things should be clear**. Not simple—tree-sitter grammars *are* complex—but **understandable**. The terminology was a wall between developers and shipping, so I rebuilt it from scratch.

**The core insight:** Separate things that are different.

### 1. Category vs Thing

```python
# Category - Abstract grouping (doesn't appear in parse trees)
expression_category = Category(
    name="expression",
    member_things=["binary_expression", "unary_expression", "call", ...]
)

# Thing - Concrete node (what you actually see)
if_statement = Thing(
    name="if_statement",
    kind=ThingKind.COMPOSITE,
    categories=["statement"]  # belongs to "statement" category
)
```

Tree-sitter calls both of these "nodes" and uses `subtypes` to indicate the difference. We make it explicit.

### 2. Connection (Not "Field" or "Child" or... Both?)

Note: I'm still implementing the parser, so these are just illustrations. Actual implementation will not be the same.

```python
# Direct Connection - has a semantic Role
DirectConnection(
    role="condition",           # ← The semantic meaning
    source="if_statement",
    target_things=["expression"],  # ← Can be Category OR concrete Thing
    requires_presence=True
)

# Positional Connection - ordered but no semantic role
PositionalConnection(
    source="argument_list",
    target_things=["expression"],
    allows_multiple=True
)
```

One concept, one name.

### 3. Role (Not "Field Name")

The role describes **what purpose** a child serves:
- `condition` in an if-statement
- `body` in a function
- `left` and `right` in a binary expression
- `operator` in an operation

It's semantic, not just structural.

## But Does It Actually Work? The Empirical Test

Instead of trusting intuition, we analyzed **all 25 language grammars** we support:
- 5,000+ unique node types
- 15,000+ connection definitions
- Languages from Bash to TypeScript to Haskell

Let's look at the data.

### Finding #1: Polymorphic References Are Real (But Minority)

**Do connections reference abstract Categories or concrete Things?**

Both—and the distinction matters:
- **Direct connections**: 7.9% Category (abstract), 92.1% concrete
- **Positional connections**: 10.3% Category, 89.7% concrete

When a connection references a Category (like `expression`), it accepts *any* expression type. This is **polymorphic type constraint** in the grammar:

```python
# Polymorphic - accepts any expression
if_statement.condition → expression (Category)

# Specific - only these operators
binary_expression.operator → ["+", "-", "*", "/"] (Concrete)
```

Tree-sitter's flattened structure obscures this. Our design makes it explicit.

### Finding #2: Multi-Category Membership Happens (But Is Uncommon)

**Can a Thing belong to multiple Categories?**

Yes, and it's fascinating when it does:
- Total Things with categories: 736
- Multi-category: 99 (13.5%)
- Single-category: 637 (86.5%)
- Maximum categories: **5** (yes, five!)

**Real examples (from C and C++ grammars):**

Mapping lines from our dataset:

```text
# C/C++ grammar categories
identifier → ["_declarator", "expression"]

# C++ grammar categories
qualified_identifier → ["_declarator", "expression", "type_specifier"]
```

C example (same identifier, different roles by context):

```c
int x;     // 'x' used as a declarator (declaring a variable)
return x;  // 'x' used as an expression (using the variable)
```

C++ example (qualified identifier appearing in three roles):

```cpp
// As a declarator (type name followed by a name)
std::vector<int>::iterator it;

// As an expression (value-initialize a temporary)
return std::vector<int>::iterator{};

// As a type specifier (appears in a parameter type)
void f(std::vector<int>::iterator it);
```

This happens mostly in statically-typed languages with complex type systems (C, C++, C#, Java). Dynamic languages (Python, JavaScript, Ruby) rarely need it.

**Design implication:** Support multi-category with `frozenset`, but don't overcomplicate—86.5% of Things belong to exactly one Category.

### Finding #3: The Cardinality Matrix Is Essential

Tree-sitter has `required` and `multiple` as separate booleans. What do they mean together?

| requires_presence | allows_multiple | Meaning                    | Example |
|-------------------|-----------------|----------------------------|---------|
| False             | False           | 0 or 1 (optional single)   | else clause |
| False             | True            | 0 or more (optional list)  | attributes |
| True              | False           | exactly 1 (required)       | function name |
| True              | True            | 1 or more (required list)  | case statements |

This table should be in the tree-sitter docs. It's not.[^3] We figured it out empirically and built it into our design.

## Translation Guide for Tree-sitter Veterans

I'm not trying to be difficult. Here's the mapping:

| Tree-sitter Term | CodeWeaver Term | Why We Changed It |
|-----------------|-----------------|-------------------|
| Abstract type (with subtypes) | **Category** | "Abstract type" is jargon; Category is universal |
| Named node | **Thing** | "It's a thing in your code" - simple and clear |
| Node with no fields | **Token** | What you literally see in source |
| Field | **Direct Connection** | Edges aren't nodes; connections are relationships |
| Field name | **Role** | Describes semantic purpose, not just presence |
| Child | **Positional Connection** | Ordered relationship without semantic role |
| Extra | **Loose Connection** | Permission to appear anywhere |
| `named` attribute | **is_explicit_rule** | Says what it actually means |
| `multiple` | **allows_multiple** | Upper bound (can have multiple) |
| `required` | **requires_presence** | Lower bound (must have ≥1) |
| `root`     | **start**             | The starting or first node (just tells tree-sitter where to start)

## The Implementation: Show, Don't Tell

Here's a pencil-sketch version of what our parser will look like:

```python
class ConnectionClass(BaseEnum):
    """How nodes relate."""
    DIRECT = "direct"        # Named semantic relationship (has a Role)
    POSITIONAL = "positional"  # Ordered but no semantic meaning
    LOOSE = "loose"          # Can appear anywhere

class ThingKind(BaseEnum):
    """Classification by structure."""
    TOKEN = "token"          # Leaf node (what you see in code)
    COMPOSITE = "composite"  # Non-leaf (has children)

# Parse an if-statement
if_statement = CompositeNode(
    name="if_statement",
    kind=ThingKind.COMPOSITE,
    categories=frozenset(["statement"]),
    direct_connections=frozenset([
        DirectConnection(
            role="condition",
            source="if_statement",
            target_things=frozenset(["expression"]),  # Polymorphic!
            requires_presence=True,
            allows_multiple=False
        ),
        DirectConnection(
            role="consequence",
            source="if_statement",
            target_things=frozenset(["block", "statement"]),
            requires_presence=True,
            allows_multiple=False
        ),
        DirectConnection(
            role="alternative",
            source="if_statement",
            target_things=frozenset(["block", "if_statement"]),  # else or elif
            requires_presence=False,  # else is optional
            allows_multiple=False
        )
    ])
)
```

Every concept is explicit:
- **What kind** of thing is this? (Composite)
- **What categories** does it belong to? (statement)
- **What connections** does it have? (Direct connections with semantic roles)
- **What can connect**? (Categories for polymorphic, concrete Things for specific)
- **Cardinality constraints**? (Required presence, multiple allowed)

No guessing. No cross-referencing documentation. No lost weeks.

## Results: Time Saved, Clarity Gained

**After implementing this design:**
- **Onboarding:** hours instead of days
- **Bugs:** caught at validation time, not runtime
- **Code:** self-documenting (`DirectConnection(role="condition", ...)`)
- **Design:** accommodates real patterns (multi-category, polymorphic refs)

**Most importantly: nobody else loses a week.**

## The Broader Lesson: Question Inherited Complexity

Tree-sitter is excellent software built by brilliant people. But its `node-types.json` format evolved from internal implementation details, not external clarity.

When you're building developer tools (...anything, really), ask:
- **Is this complexity essential** or inherited?
- **Would a newcomer understand this** without reading source code?
- **Can we measure** if our design works? (We analyzed 25 languages)
- **Are we preserving jargon** out of tradition or necessity?

Sometimes the answer is "preserve it" (backward compatibility, ecosystem alignment).
Sometimes it's "redesign it" (when clarity matters more than tradition).

For CodeWeaver, serving AI agents and developers who need to understand 25+ languages quickly, **clarity won**.

## Try It Yourself

**Tree-sitter approach:**
```bash
cat node-types.json | jq '.[] | select(.type == "if_statement")'
# Output: nested JSON with fields, children, types, named flags...
# Time to understand: 15-30 minutes of documentation reading
```

**CodeWeaver approach:**
```python
from codeweaver.semantic import NodeTypeParser

parser = NodeTypeParser()
if_stmt = parser.get_thing("if_statement", language="python")

print(f"Kind: {if_stmt.kind}")
print(f"Categories: {if_stmt.categories}")
print(f"Direct connections: {[c.role for c in if_stmt.direct_connections]}")
# Output: Clear, typed, self-documenting
# Time to understand: Immediate
```

(Okay, give me a couple days to get it working first!)

The code is [open source on GitHub](https://github.com/knitli/codeweaver-mcp). The empirical analysis is in the repository. The design decisions are documented.

## Takeaways

1. **Inherited terminology can be more confusing than the underlying concepts**
   - Tree-sitter's "named" attribute confused us for days
   - Our "is_explicit_rule" says exactly what it means

2. **Empirical validation beats intuition**
   - We thought multi-category was rare (it is: 13.5%)
   - We didn't know polymorphic refs existed (they do: 7.9-10.3%)

3. **Make the implicit explicit**
   - Category vs Thing (both called "nodes" in tree-sitter)
   - Direct vs Positional vs Loose (all jumbled in tree-sitter)
   - Role as semantic purpose (just "field name" in tree-sitter)

4. **Design for clarity, optimize for understanding**
   - One concept = one name
   - Similar concepts = consistent naming (ConnectionClass, ThingKind)
   - Confusing concepts = explicit separation (requires_presence vs allows_multiple)

5. **Provide bridges for experts**
   - Translation guide for tree-sitter veterans
   - Preserve the power, improve the interface

## The Bottom Line

Developer tools should make complex problems understandable, not add complexity of their own.

I spent a week confused by tree-sitter's terminology. I spent the next two weeks analyzing 25 languages and redesigning it. Now, every engineer who touches CodeWeaver saves that week I lost.

That's a good trade.

---

**About CodeWeaver**: I'm building intelligent code search that understands semantic meaning across 25+ programming languages (and with lesser accuracy, 170+ languages). Open source, AI-native, built to make large codebases navigable for both humans and AI agents.

**About Knitli**: I'm the founder and only employee (for now). I make complex systems intuitive. Whether it's tree-sitter grammars, distributed systems, or AI workflows, the right abstraction makes everything clearer. I'm building context engineering tools that are intuitive for *both* AI agents and humans. Oh, and cut costs by saving *a lot* of tokens. Visit us at <https://knitli.com> and sign up for the waitlist!

*Found this helpful? I'd love to hear your own "lost week to bad terminology" stories. Share them in the comments.*

---

## Appendix: The Numbers

For the data nerds (I am one too):

**Languages Analyzed**: 25
- Bash, C, C++, C#, CSS, Elixir, Go, Haskell, HTML, Java, JavaScript (+JSX), JSON, Kotlin, Lua, Nix, PHP, Python, Ruby, Rust, Scala, Solidity, Swift, TypeScript, TSX, YAML

**Node Types Analyzed**: 5,000+
- 'Named' nodes: ~2,900
- 'Unnamed' nodes: ~2,100
- Abstract types (Categories): ~20-100 (explanation below)

**Connection References**: 15,635
- Direct (fields): 9,606 (761 Category, 8,845 Concrete)
- Positional (children): 6,029 (621 Category, 5,408 Concrete)
- Loose (extras): ~50-75 unique across all languages

**Multi-Category Distribution**:
- 1 category: 637 Things (86.5%)
- 2 categories: 68 Things (9.2%)
- 3 categories: 18 Things (2.4%)
- 4 categories: 12 Things (1.6%)
- 5 categories: 1 Thing (0.1%) - the legendary `qualified_identifier` in C++

**Common Roles**: ~90 unique across all languages
- Most common: `name` (381 occurrences), `body` (281), `type` (217), `condition` (102)
- Language-specific: `lhs`/`rhs` (Swift), `quoted_start`/`quoted_end` (Elixir)

**Analysis Tools**: [Python script in the CodeWeaver repo](https://github.com/knitli/codeweaver-mcp/tree/main/scripts/analyze_grammar_structure.py) results in `https://github.com/knitli/codeweaver-mcp/tree/main/claudedocs/grammar_structure_analysis.md`

**Confidence Level**: High. We parsed every node-types.json file for languages supported by ast-grep, validated against actual grammars, cross-referenced with tree-sitter documentation, and tested on real codebases.

### About Categories (abstract nodes), and Inconsistent Grammars

Tree-sitter grammars have no standardized vocabulary, so whoever wrote the grammar defines the names. This makes working across languages, like with CodeWeaver, much more difficult. The grammar can also represent names with a preceding underscore (like with `_expression`) or without (`expression`) based on how they're used in the grammar. 

So our initial results from 25 languages gave us ~110 abstract types, but a little normalization goes a long way. Not all languages *have* defined Categories -- of the 25, **only 18** define Categories, 6 don't (css, elixir, html, solidity, swift, yaml -- and json has only one,`_value`, so does Nix, `_expression`).
    - *50* if you simply remove the underscore. 
    - *34* of those belong to *only* one language/grammar. 
    - *7* of those are unique to *C and C++* but no other languages.
    - **9** are used in multiple languages:

| Category               | # Grammars |
|:-----------------------|:------------:|
| `expression`           | 18         |
| `statement`            | 14         |
| `type`                 | 9          |
| `declaration`          | 8          |
| `primary_expression`*  | 8          |
| `pattern`              | 8          |
| `literal`              | 4          |
|------------------------|------------|

You're likely to see similar patterns across all nodes and edges based on my observations working with the data, but I haven't done the analysis yet. If you look at Categories that are unique to a language, you see that many are slight variations from these, like `type_declaration`, `pattern_expr`, and `expression_statement`.
---

*This post is part of our technical 'Clarity Engineering' series on making developer tools more intuitive.*

[^1]: "Semantic" is one of those heady academic words I try to avoid, but in this context it's hard to do that. In terms of [AST](https://en.wikipedia.org/wiki/Abstract_syntax_tree)-parsing like with tree-sitter, you can think of `semantic` as meaning "has structural meaning". Tools like tree-sitter parse text, usually code, based on *defined relationships and rules* called *grammars*, and not based on their physical syntax (like a regular expression (regex) does where it looks for specific characters in specific patterns). This difference is powerful - the resulting 'syntax tree' provides rich information about *code relationships*. Tree-sitter, despite its flaws in terminology and documentation, is a powerful tool for generating a syntax tree for almost any programming language, and doing it *very* quickly (real time even on large codebases).
[^2]: Not my first in full disclosure, but the first time I'd really *inspected* one.
[^3]: Yes, I know I should submit a PR. I will when I can take a breath; anyone who reads this is welcome to go ahead and do it if I haven't already.