<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-License-Identifier: MIT OR Apache-2.0
-->

## 2026-03-19 - Redundant RegEx Caching and Unhashable `lru_cache` Arguments
**Learning:** Python natively caches up to 512 `re.compile` patterns automatically. Attempting to add `@lru_cache(maxsize=1)` over a simple `re.compile` is a redundant micro-optimization with practically zero measurable performance impact. Additionally, when using `@lru_cache` on functions that return or take sets as arguments, `frozenset` must be used instead, as standard Python `set` objects are unhashable and will throw a `TypeError` when cached.
**Action:** Avoid micro-optimizations on standard library functions that already implement internal caching (like `re.compile`). When implementing `lru_cache`, always verify that all arguments and return values (if recursive) are immutable and hashable (e.g., use `frozenset` instead of `set`, `tuple` instead of `list`).

## 2026-03-19 - Fast generation of line pos lengths in Chunker
**Learning:** `sum(len(line) for line in lines)` is slower than `sum(map(len, lines))` because the Python generator creates an object overhead per iteration. While `len(''.join(lines))` is faster in C, it allocates memory for a new string just to evaluate its length, creating memory regressions. `sum(map(...))` is an optimal middle-ground that's ~2x faster than a generator comprehension and avoids the extra memory allocation overhead.
**Action:** Use `sum(map(len, lines))` instead of iterating a generator with `sum(len(line))` when evaluating large text lengths in chunkers.

# 2026-03-29 -  Consider Readability and Possible Environment Limitations
**Learning** While some patterns are hypothetically faster, they may not improve performance in i/o bound contexts. Examples include embedding/reranking requests and database operations where the dominant limiting factors are i/o constraints.
**Action** Don't recommend changes that reduce readability or diverge from Python idioms for no or marginal gains in performance. 

## 2026-04-01 - Fast generation of line pos lengths in Chunker with itertools
**Learning:** itertools.accumulate(map(len, lines)) is significantly faster (~2-3x) than using a generator expression like (line_offsets[-1] + len(line) for line in lines) because it pushes the entire loop down to C level instead of creating generator overhead for each element.
**Action:** Prefer using itertools.accumulate and map for sequential aggregations of large list strings instead of list generator expressions.

## 2026-04-10 - Preventing List Allocations in Generators
**Learning:** Instantiating a list inside a generator expression for membership checks (e.g., `item in [a, b]`) forces Python to allocate and garbage-collect a new list object for every iteration of the generator. This can severely degrade performance in tight loops or large collections. Hoisting the check to a pre-computed tuple outside the generator (e.g., `targets = (a, b)` and then `item in targets`) prevents these repeated allocations and can improve performance by 2x or more.
**Action:** Pre-compute tuples for static membership checks outside of generators to eliminate redundant list allocation overhead.
## 2025-04-12 - Walrus Operator Optimization
**Learning:** Using the walrus operator inside a list comprehension to avoid redundant execution of string methods (like `.strip()`) is an effective and safe micro-optimization. The result of the assignment inside the list comprehension will intentionally leak into the scope of the caller function, but this standard Python behavior does not cause naming conflicts in non-recursive or non-global scopes.
**Action:** Always favor using the walrus operator `:=` in list comprehensions or conditionals when identical string manipulations (e.g., `.strip()`) or expensive evaluation calls appear repeatedly within the identical expression branch.

## 2026-04-18 - Replacing Generators with Standard Loops for Linear Lookups
**Learning:** In Python performance optimization, replacing a generator expression wrapped in `next()` (e.g., `next((x for x in iterable if condition), default)`) with a standard `for` loop that uses an early `return` can significantly speed up linear lookups by eliminating generator frame allocation overhead.
**Action:** When performing linear lookups or finding the first matching element in a collection on hot paths, prioritize using a standard `for` loop instead of `next(...)` with a generator expression.

## 2026-04-18 - Short-circuiting and Eliminating Generator Overhead in String Matching
**Learning:** When evaluating sequential string match conditions in hot loops (e.g., matching a start pattern, then an end pattern), using early returns to short-circuit the function if the first condition fails prevents unnecessary computations. Additionally, converting generator comprehensions (e.g., `target in (s.lower() for s in collection)`) into `any()` statements combined with pre-computed invariant variables (like `target.lower()`) eliminates the object overhead of generators and executes much faster.
**Action:** Use early returns to short-circuit logic, and replace generator comprehensions with `any()` checks and pre-computed loop invariants when validating complex conditions sequentially.
