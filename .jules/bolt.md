<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-License-Identifier: MIT OR Apache-2.0
-->

## 2025-02-19 - Redundant RegEx Caching and Unhashable `lru_cache` Arguments
**Learning:** Python natively caches up to 512 `re.compile` patterns automatically. Attempting to add `@lru_cache(maxsize=1)` over a simple `re.compile` is a redundant micro-optimization with practically zero measurable performance impact. Additionally, when using `@lru_cache` on functions that return or take sets as arguments, `frozenset` must be used instead, as standard Python `set` objects are unhashable and will throw a `TypeError` when cached.
**Action:** Avoid micro-optimizations on standard library functions that already implement internal caching (like `re.compile`). When implementing `lru_cache`, always verify that all arguments and return values (if recursive) are immutable and hashable (e.g., use `frozenset` instead of `set`, `tuple` instead of `list`).


## 2025-03-19 - Fast generation of line pos lengths in Chunker
**Learning:** `sum(len(line) for line in lines)` is slower than `sum(map(len, lines))` because the Python generator creates an object overhead per iteration. While `len(''.join(lines))` is faster in C, it allocates memory for a new string just to evaluate its length, creating memory regressions. `sum(map(...))` is an optimal middle-ground that's ~2x faster than a generator comprehension and avoids the extra memory allocation overhead.
**Action:** Use `sum(map(len, lines))` instead of iterating a generator with `sum(len(line))` when evaluating large text lengths in chunkers.

## 2025-04-19 - Fast generation of line pos lengths in Chunker with itertools
**Learning:** itertools.accumulate(map(len, lines)) is significantly faster (~2-3x) than using a generator expression like (line_offsets[-1] + len(line) for line in lines) because it pushes the entire loop down to C level instead of creating generator overhead for each element.
**Action:** Prefer using itertools.accumulate and map for sequential aggregations of large list strings instead of list generator expressions.
