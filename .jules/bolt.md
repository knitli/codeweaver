<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-License-Identifier: MIT OR Apache-2.0
-->

## 2025-03-19 - Fast generation of line pos lengths in Chunker
**Learning:** `sum(len(line) for line in lines)` is slower than `sum(map(len, lines))` because the Python generator creates an object overhead per iteration. While `len(''.join(lines))` is faster in C, it allocates memory for a new string just to evaluate its length, creating memory regressions. `sum(map(...))` is an optimal middle-ground that's ~2x faster than a generator comprehension and avoids the extra memory allocation overhead.
**Action:** Use `sum(map(len, lines))` instead of iterating a generator with `sum(len(line))` when evaluating large text lengths in chunkers.
