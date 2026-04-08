"""Unit tests for language detection and configuration mapping.

Covers:
- ConfigLanguage enum: extension mapping and properties
- SemanticSearchLanguage enum: aliases, AST Grep targets, injection languages
- Helper functions for language detection from paths and config files
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from codeweaver.core.language import (
    ConfigLanguage,
    SemanticSearchLanguage,
    has_semantic_extension,
    is_semantic_config_ext,
    language_from_config_file,
    language_from_path,
)


@pytest.mark.parametrize(
    ("ext", "expected"),
    [
        (".json", ConfigLanguage.JSON),
        ("json", None),
        (".toml", ConfigLanguage.TOML),
        ("Makefile", ConfigLanguage.MAKE),
        (".JSON", ConfigLanguage.JSON),
        (
            "MAKEFILE",
            None,
        ),  # Case matters for exact filename matches in ConfigLanguage (e.g. Makefile)
        (".unknown", None),
    ],
)
def test_config_language_from_extension(ext, expected):
    assert ConfigLanguage.from_extension(ext) == expected


def test_config_language_extensions():
    assert ".json" in ConfigLanguage.JSON.extensions
    assert "Makefile" in ConfigLanguage.MAKE.extensions
    assert ".toml" in ConfigLanguage.TOML.extensions


def test_config_language_is_semantic_search_language():
    assert ConfigLanguage.JSON.is_semantic_search_language is True
    assert ConfigLanguage.MAKE.is_semantic_search_language is False


def test_semantic_search_language_alias():
    assert SemanticSearchLanguage.PYTHON.alias == "py"
    assert SemanticSearchLanguage.JAVASCRIPT.alias == "js"
    assert SemanticSearchLanguage.C_PLUS_PLUS.alias == "c++"
    assert SemanticSearchLanguage.JAVA.alias is None


@pytest.mark.parametrize(
    ("ext", "expected"),
    [
        (".py", SemanticSearchLanguage.PYTHON),
        ("py", SemanticSearchLanguage.PYTHON),
        (".js", SemanticSearchLanguage.JAVASCRIPT),
        (".PY", SemanticSearchLanguage.PYTHON),
        (".unknown", None),
    ],
)
def test_semantic_search_language_from_extension(ext, expected):
    assert SemanticSearchLanguage.from_extension(ext) == expected


def test_semantic_search_language_ast_grep():
    assert SemanticSearchLanguage.PYTHON.ast_grep == "python"
    assert SemanticSearchLanguage.C_PLUS_PLUS.ast_grep == "cpp"
    assert SemanticSearchLanguage.JAVASCRIPT.ast_grep == "javascript"


def test_semantic_search_language_injection_languages():
    injections = SemanticSearchLanguage.injection_languages()
    assert SemanticSearchLanguage.HTML in injections
    assert SemanticSearchLanguage.JAVASCRIPT in injections
    assert SemanticSearchLanguage.PYTHON not in injections


def test_semantic_search_language_is_injection_language():
    assert SemanticSearchLanguage.HTML.is_injection_language is True
    assert SemanticSearchLanguage.PYTHON.is_injection_language is False


def test_semantic_search_language_injected_languages():
    assert SemanticSearchLanguage.HTML.injected_languages is not None
    assert SemanticSearchLanguage.JAVASCRIPT in SemanticSearchLanguage.HTML.injected_languages
    assert SemanticSearchLanguage.JAVASCRIPT.injected_languages is not None
    assert SemanticSearchLanguage.HTML in SemanticSearchLanguage.JAVASCRIPT.injected_languages
    assert SemanticSearchLanguage.PYTHON.injected_languages is None


def test_semantic_search_language_is_config_language():
    assert SemanticSearchLanguage.JSON.is_config_language is True
    assert SemanticSearchLanguage.PYTHON.is_config_language is False


@pytest.mark.parametrize(
    ("ext", "expected"),
    [
        (".py", SemanticSearchLanguage.PYTHON),
        (".js", SemanticSearchLanguage.JAVASCRIPT),
        (
            "py",
            None,
        ),  # has_semantic_extension expects actual dots, the from_extension maps logic handles string variations.
        (
            ".PY",
            None,
        ),  # has_semantic_extension checks exact list match and since extensions in map are lowercased it fails unless normalized.
        (".unknown", None),
    ],
)
def test_has_semantic_extension(ext, expected):
    assert has_semantic_extension(ext) == expected


def test_is_semantic_config_ext():
    assert is_semantic_config_ext(".json") is True
    assert is_semantic_config_ext(".yaml") is True
    assert is_semantic_config_ext(".py") is False


@patch("codeweaver.core.language.Path.exists")
def test_language_from_config_file_direct(mock_exists):
    mock_exists.return_value = True
    language_from_config_file.cache_clear()

    with patch(
        "codeweaver.core.language.SemanticSearchLanguage._language_from_config_file"
    ) as mock_internal:
        mock_internal.return_value = SemanticSearchLanguage.JAVASCRIPT
        assert language_from_config_file(Path("package.json")) == SemanticSearchLanguage.JAVASCRIPT


@pytest.mark.parametrize(
    ("path_str", "expected"),
    [
        ("src/main.py", SemanticSearchLanguage.PYTHON),
        ("src/index.js", SemanticSearchLanguage.JAVASCRIPT),
        ("package.json", SemanticSearchLanguage.JSON),
        ("Makefile", "make"),
        ("component.test.ts", SemanticSearchLanguage.TYPESCRIPT),
        (".eslintrc.json", SemanticSearchLanguage.JSON),
        (
            "MAKEFILE",
            None,
        ),  # Testing case variants (Makefile relies on case sensitive matching or specific extension)
        ("unknown.file", None),
    ],
)
def test_language_from_path(path_str, expected):
    assert language_from_path(Path(path_str)) == expected
