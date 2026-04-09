with open("src/codeweaver/core/statistics.py", "r") as f:
    code = f.read()

# Replace operations_with_semantic_support
code = code.replace('''    @property
    def operations_with_semantic_support(self) -> NonNegativeInt:
        """Get the total operations with semantic support across all languages in this category."""
        return sum(lang_stats.total_operations for lang_stats in self.semantic_languages.values())''',
'''    @functools.cached_property
    def operations_with_semantic_support(self) -> NonNegativeInt:
        """Get the total operations with semantic support across all languages in this category.

        Cached for performance. Cache is invalidated when operations are added.
        """
        return sum(lang_stats.total_operations for lang_stats in self.semantic_languages.values())''')

# Replace unique_files
code = code.replace('''    @property
    def unique_files(self) -> frozenset[Path]:
        """Get the unique files across all languages in this category."""
        all_files: set[Path] = set()
        for lang_stats in self.languages.values():
            all_files.update(lang_stats.unique_files)
        return frozenset(all_files)''',
'''    @functools.cached_property
    def unique_files(self) -> frozenset[Path]:
        """Get the unique files across all languages in this category.

        Cached for performance. Cache is invalidated when operations are added.
        """
        all_files: set[Path] = set()
        for lang_stats in self.languages.values():
            all_files.update(lang_stats.unique_files)
        return frozenset(all_files)''')

# Replace total_operations
code = code.replace('''    @functools.cached_property
    def total_operations(self) -> NonNegativeInt:
        """Get the total operations across all languages in this category."""
        return sum(lang_stats.total_operations for lang_stats in self.languages.values())''',
'''    @functools.cached_property
    def total_operations(self) -> NonNegativeInt:
        """Get the total operations across all languages in this category.

        Cached for performance. Cache is invalidated when operations are added.
        """
        return sum(lang_stats.total_operations for lang_stats in self.languages.values())''')

with open("src/codeweaver/core/statistics.py", "w") as f:
    f.write(code)
