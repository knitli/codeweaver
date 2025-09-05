# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

def compress_schema(
    schema: dict,
    prune_params: list[str] | None = ...,
    prune_defs: bool = ...,
    prune_additional_properties: bool = ...,
    prune_titles: bool = ...,
) -> dict:
    ...
