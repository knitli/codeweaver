import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from codeweaver.core.language import (
    ConfigLanguage,
    SemanticSearchLanguage,
    has_semantic_extension,
    is_semantic_config_ext,
    language_from_config_file,
    language_from_path,
)

def test_config_language_from_extension():
    assert ConfigLanguage.from_extension(".json") == ConfigLanguage.JSON
    assert ConfigLanguage.from_extension("json") is None
    assert ConfigLanguage.from_extension(".toml") == ConfigLanguage.TOML
    assert ConfigLanguage.from_extension("Makefile") == ConfigLanguage.MAKE
    assert ConfigLanguage.from_extension(".unknown") is None

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

def test_semantic_search_language_from_extension():
    assert SemanticSearchLanguage.from_extension(".py") == SemanticSearchLanguage.PYTHON
    assert SemanticSearchLanguage.from_extension("py") == SemanticSearchLanguage.PYTHON
    assert SemanticSearchLanguage.from_extension(".js") == SemanticSearchLanguage.JAVASCRIPT
    assert SemanticSearchLanguage.from_extension(".unknown") is None

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
    assert SemanticSearchLanguage.JAVASCRIPT in SemanticSearchLanguage.HTML.injected_languages
    assert SemanticSearchLanguage.HTML in SemanticSearchLanguage.JAVASCRIPT.injected_languages
    assert SemanticSearchLanguage.PYTHON.injected_languages is None

def test_semantic_search_language_is_config_language():
    assert SemanticSearchLanguage.JSON.is_config_language is True
    assert SemanticSearchLanguage.PYTHON.is_config_language is False

def test_has_semantic_extension():
    assert has_semantic_extension(".py") == SemanticSearchLanguage.PYTHON
    assert has_semantic_extension(".js") == SemanticSearchLanguage.JAVASCRIPT
    assert has_semantic_extension(".unknown") is None

def test_is_semantic_config_ext():
    assert is_semantic_config_ext(".json") is True
    assert is_semantic_config_ext(".yaml") is True
    assert is_semantic_config_ext(".py") is False


@patch("codeweaver.core.language.Path.exists")
def test_language_from_config_file(mock_exists):
    mock_exists.return_value = True
    language_from_config_file.cache_clear()

    with patch("codeweaver.core.language.SemanticSearchLanguage._language_from_config_file") as mock_internal:
        mock_internal.return_value = SemanticSearchLanguage.JAVASCRIPT
        assert language_from_config_file(Path("package.json")) == SemanticSearchLanguage.JAVASCRIPT

def test_language_from_path():
    assert language_from_path(Path("src/main.py")) == SemanticSearchLanguage.PYTHON
    assert language_from_path(Path("src/index.js")) == SemanticSearchLanguage.JAVASCRIPT
    assert language_from_path(Path("package.json")) == SemanticSearchLanguage.JSON
    assert language_from_path(Path("Makefile")) == "make"
    assert language_from_path(Path("unknown.file")) is None
