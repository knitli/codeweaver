#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Example usage of the new statistics system."""

from pathlib import Path

from src.codeweaver._statistics import FileStatistics, SessionStatistics


def main() -> None:
    """Demonstrate the statistics system."""
    # Create file statistics
    file_stats = FileStatistics()

    # Add some sample files
    sample_files = [
        Path("src/main.py"),  # Python code
        Path("package.json"),  # JavaScript config
        Path("README.md"),  # Documentation
        Path("Makefile"),  # Build config
        Path("src/utils.ts"),  # TypeScript code
        Path("config.yaml"),  # YAML config
        Path("data.txt"),  # Other file
    ]

    # Create mock files for demonstration
    for file_path in sample_files:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.touch()

    # Add file operations
    for file_path in sample_files:
        file_stats.add_file(file_path, "indexed")
        file_stats.add_file(file_path, "processed")

    # Add some additional operations
    file_stats.add_file(sample_files[0], "retrieved")  # main.py retrieved
    file_stats.add_file(sample_files[1], "reindexed")  # package.json reindexed

    # Display statistics
    print("=== File Statistics Summary ===")
    print(f"Total unique files: {file_stats.total_unique_files}")
    print(f"Total operations: {file_stats.total_operations}")
    print()

    print("=== By Category ===")
    category_summary = file_stats.get_summary_by_category()
    for category, stats in category_summary.items():
        print(
            f"{category.title()}: {stats['unique_files']} files, {stats['total_operations']} operations, {stats['languages']} languages"
        )
    print()

    print("=== By Language ===")
    language_summary = file_stats.get_summary_by_language()
    for language, stats in language_summary.items():
        print(f"{language}: {stats['unique_files']} files, {stats['total_operations']} operations")
        print(
            f"  - indexed: {stats['indexed']}, processed: {stats['processed']}, retrieved: {stats['retrieved']}"
        )
    print()

    print("=== Detailed Category Breakdown ===")
    for category_name, category_stats in file_stats.categories.items():
        if category_stats.languages:
            print(f"\n{category_name.title()} Category:")
            for lang_name, lang_stats in category_stats.languages.items():
                print(f"  {lang_name}: {lang_stats.unique_count} unique files")
                print(
                    f"    Operations: indexed={lang_stats.indexed}, processed={lang_stats.processed}, retrieved={lang_stats.retrieved}"
                )

    # Create session statistics
    print("\n=== Session Statistics ===")
    session_stats = SessionStatistics()
    session_stats.index_statistics = file_stats

    # Add some request data
    session_stats.add_successful_request()
    session_stats.add_successful_request()
    session_stats.add_failed_request()

    session_stats.add_response_time(150.0)
    session_stats.add_response_time(200.0)
    session_stats.add_response_time(100.0)

    print(f"Total requests: {session_stats.total_requests}")
    print(f"Successful: {session_stats.successful_requests}")
    print(f"Failed: {session_stats.failed_requests}")
    print(f"Success rate: {session_stats.get_success_rate():.2%}")
    print(f"Average response time: {session_stats.average_response_time_ms:.1f}ms")
    print(
        f"Min/Max response time: {session_stats.min_response_time_ms:.1f}ms / {session_stats.max_response_time_ms:.1f}ms"
    )

    # Cleanup
    for file_path in sample_files:
        if file_path.exists():
            file_path.unlink()

    # Remove directories if empty
    for file_path in sample_files:
        try:
            file_path.parent.rmdir()
        except OSError:
            pass  # Directory not empty or doesn't exist


if __name__ == "__main__":
    main()
