
## 2025-03-19 - Fast generation of line pos lengths in Chunker
**Learning:** `sum(len(line) for line in lines)` is typically slower than `sum(map(len, lines))` because the generator expression does more work in Python, incurring extra iteration and function-call overhead, whereas `map` and `sum` can push more of the loop into C. While `len(''.join(lines))` is faster in C, it allocates memory for a new string just to evaluate its length, creating memory regressions. `sum(map(...))` is an optimal middle-ground that's ~2x faster than a generator expression and avoids the extra memory allocation overhead.
**Action:** Use `sum(map(len, lines))` instead of a generator expression like `sum(len(line) for line in lines)` when evaluating large text lengths in chunkers.
