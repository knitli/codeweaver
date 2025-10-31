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



TODO: Registry methods for getting complete provider information (caps, provider, client, provider name)