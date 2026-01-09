<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

Changes to account for:

1. Moved to creating instances for different configuration vice trying to handle multiple configs within a single instance, this change affects. This means all backup logic will be removed in favor of a `Backup` prefixed subclass:
    - Embedding Registry (done)
    - Embedding providers (sparse and dense) (done)
    - vector store (not done)
    - possibly reranking (not done)

    - Each of these classes now have shadowed `Backup` prefixed versions and they all have `is_backup_provider` flags to help differentiate behavior. This greatly simplifies the logic within each class.
    - The only thing that *potentially* retains references to both primary and backups is `CodeChunk`, but only under the unlikely circumstance of primary and backup chunks being identical (the two have different size context windows in most cases and so have different size chunks -- we don't currently try to map between the two, though our `SpanGroup` class could potentially do this without much pain)

2. Complete breaking refactor of provider settings
    - Each SDK Client now has its own settings class that is responsible for validating and holding configuration specific to that client.
    - There's now a unified base for any model, embed/rerank, or constructor settings -- each of these are provider specific and implementations for each field value must mirror the formats expected by the underlying SDKs (i.e. `embedding` field produces kwarg-ready values for the client's `embed` or similar method).

3. DI system now uses `@dependency_provider` decorator to register types and factories in a decentralized fashion. Each package should have a root-level `dependencies` module where associated types are created and exported.  

4. Everything realigned into a pre-package structure for phase 3 -- consolidating similar logic in packages. Everything is ready to move.

5. As part of #4 configuration modules were parted out to each package they pertained to, and we added a CodeWeaverBaseSettings class to handle situations where not all members are available. We needed a solution for handling situations when not all configurations were available, so we created the settings wrapper and loader in codeweaver.config.loader and codeweaver.config.core_settings   -- providers.config has a class for when it is the top-level settings object, and so does engine.config for when engine is the lead -- CodeWeaverSettings itself is only available when the full server package is installed (or will be once we make that move). 

6. New DI-driven defaults and interdependency-resolution system in codeweaver.core.config.resolver and codeweaver.core.registry. These are largely unimplemented, but are intended to replace complex configuration resolution that current happens within config classes and provider classes -- one example is vector dimensions for a dense provider, which must align with the vector configuration in the vector store, or the datatype in a sparse or dense providers' config can't actually be sent as a config setting to that provider because a quirk in qdrant, but needs to be reconciled to qdrant for quantization config.

7. The provider configuration system, now in providers.config was completely refactored to align config fields with the fields their associated SDK clients, models, and methods would expect. This eliminates a large amount of code dedicated to "cleaning" or "reconciling" passed kwargs. 


The situation:
    - We decided that we essentially couldn't confidently move forward with new features for codeweaver until the DI system was complete, which according to plans, also called for completing the repo's transition to a monorepo.
       - We had no confidence in testing because it was clear we couldn't effectively control leaks and the testing environment effectively
    - The repo is now structure in *prep* for the move to monorepo -- codeweaver_daemon and codeweaver_tokenizers are their own packages in packages/
    - Every other package is now consolidated into what its final state will be
    - there are a **lot** of odds and ends to tie up, I want your help doing some of the leg work as I architect. I want you to keep your scope very narrow to what I specifically ask because I know that there's a **lot** broken right now, and that's OK. There's a method to my madness here.
    - You'll see what are effectively DI placeholders like `client: ClientDep = INJECTED` with no corresponding import of ClientDep. Those are like that on purpose -- I want to define the factories later once we know exactly what the structure is and what we need.
    - don't expect anything to actually run right now. 

    Specific structural changes:
    - There are no registries anymore (provider/model/services) -- everything will be handled by the @dependency_provider decorator in core/di/utils.py
        - There are probably still plenty of reference to them. 
    - I'm in the middle of overhauling the provider settings system to have classes that mirror their providers/clients/etc
        - Clients are all done (providers/config/clients.py), but other settings I've only done a few classes in providers/embeddings/providers/config.py
    
If something doesn't make sense or doesn't align with your expectations -- stop and ask. I'm trying to be very deliberate in how I work through this refactor, so I don't want you making changes I don't ask for trying to be helpful. If you see something that is genuinely wrong (not a missing import, but a logic issue), please bring it up. 

We're not concerned with breaking changes -- CodeWeaver has essentially no userbase and we're going to go big on PR after this release. Now is the time to get changes in the way they should be.

If I were to pick a theme for this refactor, it'd be "let's just pull of the bandaid and get as much right as quickly as we can where we know we made structural mistakes"