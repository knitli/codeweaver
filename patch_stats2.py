with open("src/codeweaver/core/statistics.py", "r") as f:
    code = f.read()

code = code.replace('''    def add_operation(
        self,
        language: LanguageNameT | SemanticSearchLanguage | ConfigLanguage,
        operation: OperationsKey,
        path: Path | None = None,
    ) -> None:
        """Add an operation for a specific language in this category."""
        lang_stats = self.get_language_stats(language)
        lang_stats.add_operation(operation, path)
        self.__dict__.pop("total_operations", None)''',
'''    def _invalidate_category_caches(self) -> None:
        """Invalidate the cached values when underlying language stats are mutated."""
        self.__dict__.pop("total_operations", None)
        self.__dict__.pop("unique_files", None)
        self.__dict__.pop("operations_with_semantic_support", None)

    def add_operation(
        self,
        language: LanguageNameT | SemanticSearchLanguage | ConfigLanguage,
        operation: OperationsKey,
        path: Path | None = None,
    ) -> None:
        """Add an operation for a specific language in this category."""
        lang_stats = self.get_language_stats(language)
        lang_stats.add_operation(operation, path)
        self._invalidate_category_caches()''')

code = code.replace('''        # Track the chunk
        lang_stats.add_chunk(chunk, operation)
        self.categories[kind].__dict__.pop("total_operations", None)''',
'''        # Track the chunk
        lang_stats.add_chunk(chunk, operation)
        self.categories[kind]._invalidate_category_caches()''')

with open("src/codeweaver/core/statistics.py", "w") as f:
    f.write(code)
