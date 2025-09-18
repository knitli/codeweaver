# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Finds codeblocks in Markdown files with no language specified and adds 'plaintext' to them."""

import re

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


CODEBLOCK = """```"""

MATCHED_BLOCK = re.compile(r"``` ?\w*\n.+?```", re.DOTALL | re.MULTILINE)

HAS_LANG = re.compile(r" ?\w+")

CHANGED_FILES = []


def add_plaintext_to_empty_language(codeblock: str) -> str:
    """
    Add 'plaintext' to code blocks with no language specified.
    """
    if not codeblock.startswith(CODEBLOCK):
        return codeblock
    return (
        codeblock if HAS_LANG.match(codeblock[3:]) else f"{codeblock[:3]}plaintext{codeblock[3:]}"
    )


def find_blocks_in_file(file_path: Path) -> list[re.Match | None]:
    """
    Find all code blocks in a file.
    """
    content = file_path.read_text(encoding="utf-8")
    if matches := list(MATCHED_BLOCK.finditer(content)):
        print(f"Found {len(matches)} code blocks in file: {file_path}")
        return matches
    return []


def process_file(file_path: Path) -> None:
    """
    Process a file to add 'plaintext' to code blocks with no language specified.
    """
    content = file_path.read_text(encoding="utf-8")
    matches = find_blocks_in_file(file_path)
    changes = False
    if matches := find_blocks_in_file(file_path):
        print(f"Found {len(matches)} code blocks in file: {file_path}")
        matches = reversed(matches)  # Reverse to avoid index issues while modifying content
        for match in matches:
            original_block = match.group(0)
            updated_block = add_plaintext_to_empty_language(original_block)
            if original_block != updated_block:
                changes = True
                print("Updating block in file:", file_path)
                print("Original block:", original_block)
                print("Updated block:", updated_block)
                content = content[: match.start()] + updated_block + content[match.end() :]
                CHANGED_FILES.append(file_path)

    if changes:
        file_path.write_text(content, encoding="utf-8")
        print(f"Updated file: {file_path}")
    return


def main() -> None:
    """
    Main function to process all files in the current directory.
    """
    with ThreadPoolExecutor() as executor:
        if files := list((Path.cwd() / "docs").rglob("**/*.md")):
            executor.map(lambda f: process_file(f), files)
            if CHANGED_FILES:
                print(f"Updated {len(CHANGED_FILES)} files with 'plaintext' code blocks.")
                print("Changed files:", ", ".join(str(f) for f in CHANGED_FILES))
            else:
                print("No changes made to any files.")
        else:
            print("No Markdown files found in the current directory.")


if __name__ == "__main__":
    main()
