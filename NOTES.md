<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# A Place for Random Thoughts Until I can Either Turn Them Into an Issue or Decide They're Not Good

AKA: The half-baked idea spot

## Multiple Indexing

### Idea

The overall plan is to eventually support resolution from multiple vector indexes across providers, but more specifically, I'm wondering if there's value to creating targeted indexes so that you can weight results from one over another. 

The main use case I thought of was for general search -- we could, for example, try just indexing the symbol graph, or create a graph of symbols, and use that as a search source that gets weighted more or less based on the task. For a config task, it might have a very low weight, but for a debug task, a very high one.


## Use Distance Matrix API for Semantic Visualization and Clustering

Qdrant's distance matrix API produces a sparse matrix of distances between sampled vectors. We could use this to:
- Create code maps and similar exploratory visualizations that are grounded in *structure*, *semantic relationships*, and *concept similarity*.
- Identify similar, but *different* functions across a codebase
- Recommend utilities and common patterns seen in the codebase relative to a search
- Identify out-of-pattern or code out of line with the codebase's style (measurably).
- Identify leaks of business logic into API layer



