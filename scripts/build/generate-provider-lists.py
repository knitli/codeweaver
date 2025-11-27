# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Generate provider lists for CodeWeaver."""
from __future__ import annotations

from pathlib import Path

from codeweaver.providers.capabilities import PROVIDER_CAPABILITIES
from codeweaver.providers.provider import Provider, ProviderKind


def generate_category(category: str) -> list[str]:
    """Generate a list of providers for a given category."""
    providers = {provider for provider in Provider if provider != Provider.NOT_SET}
    kind = ProviderKind.from_string(category.lower())
    listing = [f"## {category.capitalize().replace('_', ' ')} Providers", ""]
    listing.extend(f"- {provider.as_title}" for provider in providers if kind in PROVIDER_CAPABILITIES[provider])
    return sorted(listing)

def get_heading() -> list[str]:
    """Get the heading for the provider lists."""
    # REUSE-IgnoreStart
    return [
        "<!-- SPDX-FileCopyrightText: 2025 Knitli Inc.",
        "SPDX-FileContributor: Adam Poulemanos <adam@knit.li>",
        "",
        " SPDX-License-Identifier: MIT OR Apache-2.0",
        "-->",
        "# CodeWeaver Supported Providers",
        "",
    ]
    # REUSE-IgnoreEnd

def generate_provider_lists() -> str:
    """Generate the provider lists markdown content."""
    categories = ("embedding", "sparse_embedding", "reranking", "vector_store") # we'll add data and agents when integrated
    content: list[str] = get_heading()
    for category in categories:
        content.extend(generate_category(category))
    return "\n".join(content).replace("\n\n\n", "\n\n")

def main() -> None:
    """Main function to generate provider lists and write to file."""
    markdown_path = Path(__file__).parent.parent.parent / "overrides" / "partials" / "providers.md"
    content = generate_provider_lists()
    markdown_path.write_text(content)

if __name__ == "__main__":
    main()
