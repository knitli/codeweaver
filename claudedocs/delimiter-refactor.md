Delimiter Pattern Matching Refactoring Plan

Problem Statement

The delimiter chunker is currently unable to detect language-specific code structures (functions, classes, methods) because the pattern matching algorithm doesn't
handle empty end delimiters (end="").

Current Behavior

When a pattern like FUNCTION_PATTERN is defined:
DelimiterPattern(
    starts=["def", "function", "fn"],
    ends="ANY",  # Means "match with any structural delimiter"
    kind=DelimiterKind.FUNCTION
)

It expands to delimiters with empty end strings:
Delimiter(start="function", end="", kind=FUNCTION, ...)

The current regex-based matching in _find_delimiter_matches() expects explicit start/end pairs like {...} or (...) and fails silently when end="".

Impact

5 tests failing due to this issue:
- JavaScript nested functions not detected
- Python class/function boundaries not found
- Generic fallback not triggering
- Line metadata missing
- Nesting level tracking broken

User-visible impact: Semantic chunking works fine, but delimiter chunking (the fallback for non-parseable code or languages without AST support) only finds generic
delimiters like braces, not actual code structures.

---
Root Cause Analysis

Technical Issue

File: src/codeweaver/engine/chunker/delimiter.pyMethods: _find_delimiter_matches(), _extract_boundaries()

1. Pattern Expansion (works correctly):
- DelimiterPattern with ends="ANY" correctly expands to end=""
- Located in: src/codeweaver/engine/chunker/delimiters/patterns.py:expand_pattern()
2. Regex Matching (broken for empty ends):
# Current implementation (line ~240-280)
pattern = re.compile(rf'\b{re.escape(delimiter.start)}\b')  # Finds "function"
# But then tries to find delimiter.end which is ""
# Empty string matches everywhere, causing incorrect boundaries
3. Boundary Extraction (incomplete):
- Algorithm assumes matched start/end pairs
- Doesn't know how to find "the next structural delimiter" after keyword

Example Failure

Input:
function createDataProcessor(config) {
const cache = new Map();
return { cache };
}

Current Behavior:
- Finds: {...} as BLOCK (generic)
- Finds: (...) as GENERIC
- Misses: function...{ as FUNCTION

Expected Behavior:
- Should find: function createDataProcessor(config) { ... } as FUNCTION
- Should track that this is a FUNCTION chunk, not just a BLOCK

---
Solution Design

Approach: Two-Phase Matching

Implement a keyword + structure matching strategy:

Phase 1: Keyword Detection

Find occurrences of keyword delimiters (function, def, class, etc.)

Phase 2: Structure Binding

For each keyword, find the next structural delimiter that completes the construct:
- For function → find next { or :
- For def → find next :
- For class → find next { or :

Algorithm Pseudocode

def _find_delimiter_matches(self, content: str, delimiters: list[Delimiter]) -> list[DelimiterMatch]:
    """Find delimiter matches with support for empty end delimiters."""

    # Separate delimiters by type
    explicit_delimiters = [d for d in delimiters if d.end != ""]
    keyword_delimiters = [d for d in delimiters if d.end == ""]

    matches = []

    # Phase 1: Handle explicit start/end pairs (existing logic)
    matches.extend(self._match_explicit_delimiters(content, explicit_delimiters))

    # Phase 2: Handle keyword delimiters with empty ends
    matches.extend(self._match_keyword_delimiters(content, keyword_delimiters))

    return sorted(matches, key=lambda m: m.start_pos)

def _match_keyword_delimiters(
    self, content: str, keyword_delimiters: list[Delimiter]
) -> list[DelimiterMatch]:
    """Match keywords and bind them to structural delimiters."""
    matches = []

    # Define structural delimiters that can complete keywords
    STRUCTURAL_CHARS = {'{', ':', '=>', 'do', 'then'}

    for delimiter in keyword_delimiters:
        # Find all keyword occurrences
        pattern = rf'\b{re.escape(delimiter.start)}\b'
        for match in re.finditer(pattern, content):
            keyword_pos = match.start()

            # Find the next structural character after the keyword
            struct_pos = self._find_next_structural(
                content,
                start=keyword_pos + len(delimiter.start),
                allowed=STRUCTURAL_CHARS
            )

            if struct_pos is not None:
                # Create match with keyword as start, structural char as end
                matches.append(
                    DelimiterMatch(
                        delimiter=delimiter,
                        start_pos=keyword_pos,
                        end_pos=struct_pos,
                        nesting_level=0  # Calculate proper nesting
                    )
                )

    return matches

def _find_next_structural(
    self, content: str, start: int, allowed: set[str]
) -> int | None:
    """Find the position of the next structural delimiter."""
    # Search for any of the allowed structural characters
    # Skip over:
    # - Comments
    # - String literals
    # - Nested parentheses (for function parameters)

    pos = start
    in_string = False
    paren_depth = 0

    while pos < len(content):
        char = content[pos]

        # Handle string boundaries
        if char in ('"', "'", '`'):
            in_string = not in_string

        # Skip if inside string
        if in_string:
            pos += 1
            continue

        # Track parenthesis depth (for skipping parameter lists)
        if char == '(':
            paren_depth += 1
        elif char == ')':
            paren_depth -= 1

        # Check for structural delimiter (only at paren depth 0)
        if paren_depth == 0:
            for struct in allowed:
                if content[pos:pos+len(struct)] == struct:
                    return pos + len(struct) - 1  # Return end position

        pos += 1

    return None  # No structural delimiter found

---
Implementation Plan

Files to Modify

1. src/codeweaver/engine/chunker/delimiter.py (Primary)

Current Lines: ~580Methods to Modify:
- _find_delimiter_matches() (line ~240-280)
- _extract_boundaries() (line ~280-320)

New Methods to Add:
- _match_explicit_delimiters() - Extract existing logic
- _match_keyword_delimiters() - New two-phase logic
- _find_next_structural() - Structural delimiter detection
- _is_inside_string() - String literal detection helper
- _skip_comment() - Comment detection helper

Estimated Changes: ~200 lines (100 new, 100 modified)

2. src/codeweaver/engine/chunker/delimiter_model.py (Minor)

Modification: Add helper method to Delimiter class:
@property
def is_keyword_delimiter(self) -> bool:
    """Check if this delimiter uses keyword matching (empty end)."""
    return self.end == ""

Estimated Changes: ~5 lines

3. Test Files (Validation)

Files:
- tests/unit/engine/chunker/test_delimiter_basic.py
- tests/unit/engine/chunker/test_delimiter_edge_cases.py

Action: Run to validate fixes (no changes needed)

---
Implementation Steps

Step 1: Refactor Existing Logic (30 min)

Extract current delimiter matching into _match_explicit_delimiters():
def _match_explicit_delimiters(
    self, content: str, delimiters: list[Delimiter]
) -> list[DelimiterMatch]:
    """Match delimiters with explicit start/end pairs."""
    # Move existing logic here (lines 240-280)
    # This is the current working code for {}, (), etc.

Step 2: Implement Structural Finder (1 hour)

Create _find_next_structural() with proper:
- String literal handling ("...", '...', `...`)
- Comment skipping (//..., /* ... */, #...)
- Parenthesis depth tracking for parameter lists

Step 3: Implement Keyword Matcher (1 hour)

Create _match_keyword_delimiters():
- Find keyword occurrences
- Bind to structural delimiters
- Handle edge cases (keywords in strings/comments)

Step 4: Integrate Two-Phase Matching (30 min)

Update _find_delimiter_matches():
- Separate delimiters by type
- Call both matchers
- Merge and sort results

Step 5: Update Boundary Extraction (30 min)

Ensure _extract_boundaries() handles keyword delimiters:
- Correct content extraction
- Proper line range calculation
- Metadata tagging with delimiter kind

Step 6: Test and Debug (1 hour)

Run tests and fix edge cases:
uv run pytest tests/unit/engine/chunker/test_delimiter_basic.py -xvs
uv run pytest tests/unit/engine/chunker/test_delimiter_edge_cases.py -xvs

Total Estimated Time: 4-5 hours

---
Edge Cases to Handle

1. Keywords in Strings

text = "The function keyword is tricky"  # Should NOT match "function"
Solution: Skip matches inside string literals

2. Keywords in Comments

// function example() { }  // Should NOT match
Solution: Skip matches inside comments

3. Nested Structures

function outer() {
function inner() { }  // Both should be found
}
Solution: Track nesting level correctly

4. Multiple Structural Options

def foo():  # Python uses ":"
function foo() {  // JavaScript uses "{"
Solution: Allow multiple structural delimiters per language family

5. Lambda/Arrow Functions

const foo = (x) => x * 2;  # Uses "=>" not "{"
Solution: Include => in structural delimiters for JavaScript family

---
Testing Strategy

Unit Tests (Existing)

Run these to validate:
# Should all pass after refactoring
uv run pytest tests/unit/engine/chunker/test_delimiter_basic.py::TestDelimiterChunksJavaScriptNested
uv run pytest tests/unit/engine/chunker/test_delimiter_basic.py::TestDelimiterChunksPython
uv run pytest tests/unit/engine/chunker/test_delimiter_edge_cases.py::TestGenericFallback

Manual Testing

from codeweaver.engine.chunker.delimiter import DelimiterChunker
from codeweaver.engine.chunker.governance import ResourceGovernor

code = '''
function createProcessor(config) {
const process = (item) => item * 2;
return { process };
}
'''

chunker = DelimiterChunker(governor, 'javascript')
chunks = chunker.chunk(code, file=discovered_file)

# Should find:
# 1. FUNCTION chunk: "function createProcessor(config) { ... }"
# 2. Nested arrow function (optional, depending on implementation)
assert any(c.metadata.get('kind') == DelimiterKind.FUNCTION for c in chunks)

---
Acceptance Criteria

Must Have

- All 5 failing delimiter tests pass
- JavaScript functions detected correctly
- Python classes/functions detected correctly
- Generic fallback triggers when no specific patterns match
- No regression in existing delimiter tests (7 currently passing)

Should Have

- Proper nesting level tracking in metadata
- Line metadata correctly populated
- Comments and strings properly skipped
- Support for arrow functions (=>)

Nice to Have

- Performance comparable to existing implementation (<10% slower)
- Debug logging for delimiter matching process
- Configuration option to enable/disable keyword matching

---
Risk Assessment

Low Risk

- Refactoring existing logic into _match_explicit_delimiters() (no behavior change)
- Adding helper methods (isolated, testable)

Medium Risk

- String/comment detection might have edge cases
- Parenthesis depth tracking could be complex

High Risk

- Integration with existing boundary extraction
- Ensuring no regression in working tests

Mitigation: Test incrementally, keep existing code path as fallback during development

---
Alternative Approaches Considered

Option 1: Pattern-based replacement (Rejected)

Replace ends="ANY" with explicit structural delimiters in pattern definitions.

Pros: No algorithm changes neededCons: Loses flexibility, requires many pattern variants per language

Option 2: Full AST parsing for delimiters (Rejected)

Use AST parsing for delimiter detection.

Pros: Most accurateCons: Defeats purpose of delimiter chunker (lightweight fallback), circular dependency

Option 3: Two-phase matching (Selected)

Implement keyword + structure binding as described above.

Pros: Maintains flexibility, handles diverse languages, clear separation of concernsCons: More complex implementation, requires careful edge case handling

---
Success Metrics

Test Pass Rate:
- Current: 7/12 delimiter tests passing (58%)
- Target: 12/12 passing (100%)
- Overall: +5 tests fixed

Performance:
- Delimiter matching: <100ms for 1000-line files
- No more than 10% slower than current implementation

Code Quality:
- Maintainability: Clear separation of matching strategies
- Testability: Each helper function independently testable
- Documentation: Inline comments explaining algorithm

---
Dependencies

Required

- No new external dependencies
- Uses existing re module for regex
- Uses existing Delimiter and DelimiterMatch models

Optional

- Could leverage tree-sitter for more accurate comment/string detection (future enhancement)
- Could use language-specific parsers for structural validation (future enhancement)

---
Handoff Checklist

- Read and understand this entire document
- Review current delimiter.py implementation (lines 240-320)
- Review failing test expectations
- Set up development environment (mise run setup)
- Run failing tests to see current behavior
- Implement step-by-step per Implementation Steps
- Run tests after each step
- Document any deviations from this plan
- Update this document with actual implementation notes

---
Questions to Resolve

1. Should arrow functions be detected as separate FUNCTION chunks or just as BLOCKS?
- Recommendation: Detect as FUNCTION for consistency (user: I agree)
2. How deep should parenthesis tracking go for parameter lists?
- Recommendation: Track depth, but match first structural after depth returns to 0 (user: agreed, makes sense)
3. Should keyword matching be configurable (on/off per language)?
- Recommendation: Always on, but priority system handles conflicts (user: agreed, always on)
4. What if multiple keywords appear on same line before structural delimiter? 
- Recommendation: First keyword wins, or highest priority if pattern system used (user: agreed, highest priority if we have it, otherwise first)

---
Contact for Questions

- Implementation questions: Reference this document first
- Test failures: Check test file comments for expected behavior
- Design decisions: Refer to "Alternative Approaches" and "Success Metrics" sections

---
Document Version: 1.0Last Updated: 2025-10-26Estimated Total Effort: 4-5 hoursDifficulty: Medium-HighPriority: High (fixes 5 tests, 11% improvement in test pass
rate)