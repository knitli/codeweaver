#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Tests for import categorization and re-export detection.

Tests the enhanced import categorization in ast_parser.py that adds
is_likely_reexport metadata to help distinguish re-exports from internal imports.
"""

import tempfile

from pathlib import Path

import pytest

from tools.exportify.analysis.ast_parser import ASTParser
from tools.exportify.common.types import SymbolProvenance


@pytest.fixture
def parser():
    """Create AST parser."""
    return ASTParser()


def create_temp_file(content: str) -> Path:
    """Create temporary Python file with content."""
    temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False)  # noqa: SIM115
    temp_file.write(content)
    temp_file.close()
    return Path(temp_file.name)


class TestAliasedImportDetection:
    """Test detection of aliased imports as likely re-exports."""

    def test_aliased_module_import_is_likely_reexport(self, parser) -> None:
        """Aliased module imports should be marked as likely re-exports."""
        content = """
import numpy as np
import pandas as pd
"""
        file_path = create_temp_file(content)
        try:
            result = parser.parse_file(file_path, "test.module")

            # Find the aliased imports
            np_import = next(s for s in result.symbols if s.name == "np")
            pd_import = next(s for s in result.symbols if s.name == "pd")

            # Both should be marked as likely re-exports
            assert np_import.metadata.get("is_likely_reexport") is True
            assert pd_import.metadata.get("is_likely_reexport") is True

            # Verify provenance is also correct
            assert np_import.provenance == SymbolProvenance.ALIAS_IMPORTED
            assert pd_import.provenance == SymbolProvenance.ALIAS_IMPORTED
        finally:
            file_path.unlink()

    def test_aliased_from_import_is_likely_reexport(self, parser) -> None:
        """Aliased from imports should be marked as likely re-exports."""
        content = """
from pathlib import Path as P
from typing import Dict as D
"""
        file_path = create_temp_file(content)
        try:
            result = parser.parse_file(file_path, "test.module")

            # Find the aliased imports
            p_import = next(s for s in result.symbols if s.name == "P")
            d_import = next(s for s in result.symbols if s.name == "D")

            # Both should be marked as likely re-exports
            assert p_import.metadata.get("is_likely_reexport") is True
            assert d_import.metadata.get("is_likely_reexport") is True

            # Verify provenance
            assert p_import.provenance == SymbolProvenance.ALIAS_IMPORTED
            assert d_import.provenance == SymbolProvenance.ALIAS_IMPORTED
        finally:
            file_path.unlink()


class TestNonAliasedImportDetection:
    """Test detection of non-aliased imports as internal use."""

    def test_non_aliased_module_import_not_reexport(self, parser) -> None:
        """Non-aliased module imports should not be marked as re-exports."""
        content = """
import os
import sys
"""
        file_path = create_temp_file(content)
        try:
            result = parser.parse_file(file_path, "test.module")

            # Find the non-aliased imports
            os_import = next(s for s in result.symbols if s.name == "os")
            sys_import = next(s for s in result.symbols if s.name == "sys")

            # Neither should be marked as likely re-exports
            assert os_import.metadata.get("is_likely_reexport") is False
            assert sys_import.metadata.get("is_likely_reexport") is False

            # Verify provenance
            assert os_import.provenance == SymbolProvenance.IMPORTED
            assert sys_import.provenance == SymbolProvenance.IMPORTED
        finally:
            file_path.unlink()

    def test_non_aliased_from_import_not_reexport(self, parser) -> None:
        """Non-aliased from imports should not be marked as re-exports."""
        content = """
from pathlib import Path
from typing import Dict
"""
        file_path = create_temp_file(content)
        try:
            result = parser.parse_file(file_path, "test.module")

            # Find the non-aliased imports
            path_import = next(s for s in result.symbols if s.name == "Path")
            dict_import = next(s for s in result.symbols if s.name == "Dict")

            # Neither should be marked as likely re-exports
            assert path_import.metadata.get("is_likely_reexport") is False
            assert dict_import.metadata.get("is_likely_reexport") is False

            # Verify provenance
            assert path_import.provenance == SymbolProvenance.IMPORTED
            assert dict_import.provenance == SymbolProvenance.IMPORTED
        finally:
            file_path.unlink()


class TestStandardLibraryDetection:
    """Test standard library import detection."""

    def test_stdlib_aliased_import_is_reexport_candidate(self, parser) -> None:
        """Aliased stdlib imports should be marked as re-export candidates.

        The is_stdlib metadata helps rules decide whether to actually re-export,
        but aliasing indicates intent to expose the import publicly.
        """
        content = """
import os as operating_system
import sys as system
from pathlib import Path as P
from typing import Dict as D
"""
        file_path = create_temp_file(content)
        try:
            result = parser.parse_file(file_path, "test.module")

            # Find all imports
            os_import = next(s for s in result.symbols if s.name == "operating_system")
            sys_import = next(s for s in result.symbols if s.name == "system")
            path_import = next(s for s in result.symbols if s.name == "P")
            dict_import = next(s for s in result.symbols if s.name == "D")

            # Aliased imports are likely re-exports (even stdlib)
            assert os_import.metadata.get("is_likely_reexport") is True
            assert sys_import.metadata.get("is_likely_reexport") is True
            assert path_import.metadata.get("is_likely_reexport") is True
            assert dict_import.metadata.get("is_likely_reexport") is True

            # All should be marked as stdlib
            assert os_import.metadata.get("is_stdlib") is True
            assert sys_import.metadata.get("is_stdlib") is True
            assert path_import.metadata.get("is_stdlib") is True
            assert dict_import.metadata.get("is_stdlib") is True
        finally:
            file_path.unlink()

    def test_common_stdlib_modules_detected(self, parser) -> None:
        """Test detection of common stdlib modules."""
        content = """
import abc
import ast
import asyncio
import collections
import dataclasses
import datetime
import enum
import functools
import json
import logging
import os
import pathlib
import re
import sys
import typing
import unittest
"""
        file_path = create_temp_file(content)
        try:
            result = parser.parse_file(file_path, "test.module")

            # All should be marked as stdlib and not re-exports (not aliased)
            for symbol in result.symbols:
                assert symbol.metadata.get("is_stdlib") is True
                assert symbol.metadata.get("is_likely_reexport") is False
        finally:
            file_path.unlink()


class TestThirdPartyImportDetection:
    """Test detection of third-party imports."""

    def test_third_party_aliased_import_is_reexport(self, parser) -> None:
        """Aliased third-party imports should be marked as re-exports."""
        content = """
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score as acc
from django.http import HttpRequest as Request
"""
        file_path = create_temp_file(content)
        try:
            result = parser.parse_file(file_path, "test.module")

            # Find the imports
            np_import = next(s for s in result.symbols if s.name == "np")
            pd_import = next(s for s in result.symbols if s.name == "pd")
            acc_import = next(s for s in result.symbols if s.name == "acc")
            req_import = next(s for s in result.symbols if s.name == "Request")

            # All should be likely re-exports (not stdlib)
            assert np_import.metadata.get("is_likely_reexport") is True
            assert pd_import.metadata.get("is_likely_reexport") is True
            assert acc_import.metadata.get("is_likely_reexport") is True
            assert req_import.metadata.get("is_likely_reexport") is True

            # None should be stdlib
            assert np_import.metadata.get("is_stdlib") is False
            assert pd_import.metadata.get("is_stdlib") is False
            assert acc_import.metadata.get("is_stdlib") is False
            assert req_import.metadata.get("is_stdlib") is False
        finally:
            file_path.unlink()

    def test_third_party_non_aliased_import_not_reexport(self, parser) -> None:
        """Non-aliased third-party imports should not be marked as re-exports."""
        content = """
import numpy
from pandas import DataFrame
from sklearn.metrics import accuracy_score
"""
        file_path = create_temp_file(content)
        try:
            result = parser.parse_file(file_path, "test.module")

            # Find the imports
            numpy_import = next(s for s in result.symbols if s.name == "numpy")
            df_import = next(s for s in result.symbols if s.name == "DataFrame")
            acc_import = next(s for s in result.symbols if s.name == "accuracy_score")

            # None should be likely re-exports (non-aliased)
            assert numpy_import.metadata.get("is_likely_reexport") is False
            assert df_import.metadata.get("is_likely_reexport") is False
            assert acc_import.metadata.get("is_likely_reexport") is False
        finally:
            file_path.unlink()


class TestRelativeImports:
    """Test handling of relative imports."""

    def test_relative_import_aliased_is_reexport(self, parser) -> None:
        """Aliased relative imports should be marked as re-exports."""
        content = """
from . import utils as u
from ..core import types as t
from ...common import constants as c
"""
        file_path = create_temp_file(content)
        try:
            result = parser.parse_file(file_path, "test.module")

            # Find the imports
            u_import = next(s for s in result.symbols if s.name == "u")
            t_import = next(s for s in result.symbols if s.name == "t")
            c_import = next(s for s in result.symbols if s.name == "c")

            # All should be likely re-exports (aliased)
            assert u_import.metadata.get("is_likely_reexport") is True
            assert t_import.metadata.get("is_likely_reexport") is True
            assert c_import.metadata.get("is_likely_reexport") is True
        finally:
            file_path.unlink()

    def test_relative_import_non_aliased_not_reexport(self, parser) -> None:
        """Non-aliased relative imports should not be marked as re-exports."""
        content = """
from . import utils
from ..core import types
from ...common import constants
"""
        file_path = create_temp_file(content)
        try:
            result = parser.parse_file(file_path, "test.module")

            # Find the imports
            utils_import = next(s for s in result.symbols if s.name == "utils")
            types_import = next(s for s in result.symbols if s.name == "types")
            consts_import = next(s for s in result.symbols if s.name == "constants")

            # None should be likely re-exports (non-aliased)
            assert utils_import.metadata.get("is_likely_reexport") is False
            assert types_import.metadata.get("is_likely_reexport") is False
            assert consts_import.metadata.get("is_likely_reexport") is False
        finally:
            file_path.unlink()


class TestMixedImports:
    """Test files with mixed import patterns."""

    def test_mixed_import_patterns(self, parser) -> None:
        """Test file with various import patterns."""
        content = """
# Standard library - no alias
import os
import sys

# Standard library - aliased
import pathlib as pl

# Third-party - no alias
import numpy

# Third-party - aliased
import pandas as pd
from sklearn.metrics import accuracy_score as acc

# Relative - no alias
from . import utils

# Relative - aliased
from ..core import types as t
"""
        file_path = create_temp_file(content)
        try:
            result = parser.parse_file(file_path, "test.module")

            # Standard library - no alias → not re-export
            os_import = next(s for s in result.symbols if s.name == "os")
            assert os_import.metadata.get("is_likely_reexport") is False
            assert os_import.metadata.get("is_stdlib") is True

            # Standard library - aliased → likely re-export (aliasing indicates intent)
            pl_import = next(s for s in result.symbols if s.name == "pl")
            assert pl_import.metadata.get("is_likely_reexport") is True
            assert pl_import.metadata.get("is_stdlib") is True

            # Third-party - no alias → not re-export
            numpy_import = next(s for s in result.symbols if s.name == "numpy")
            assert numpy_import.metadata.get("is_likely_reexport") is False
            assert numpy_import.metadata.get("is_stdlib") is False

            # Third-party - aliased → likely re-export
            pd_import = next(s for s in result.symbols if s.name == "pd")
            assert pd_import.metadata.get("is_likely_reexport") is True
            assert pd_import.metadata.get("is_stdlib") is False

            acc_import = next(s for s in result.symbols if s.name == "acc")
            assert acc_import.metadata.get("is_likely_reexport") is True
            assert acc_import.metadata.get("is_stdlib") is False

            # Relative - no alias → not re-export
            utils_import = next(s for s in result.symbols if s.name == "utils")
            assert utils_import.metadata.get("is_likely_reexport") is False

            # Relative - aliased → likely re-export
            t_import = next(s for s in result.symbols if s.name == "t")
            assert t_import.metadata.get("is_likely_reexport") is True
        finally:
            file_path.unlink()


class TestMetadataStructure:
    """Test that metadata is properly structured."""

    def test_metadata_contains_all_fields(self, parser) -> None:
        """Metadata should contain all expected fields."""
        content = """
import numpy as np
from pathlib import Path
"""
        file_path = create_temp_file(content)
        try:
            result = parser.parse_file(file_path, "test.module")

            for symbol in result.symbols:
                # All imports should have these metadata fields
                assert "import_type" in symbol.metadata
                assert "is_likely_reexport" in symbol.metadata
                assert "is_stdlib" in symbol.metadata

                # import_type should be "module" or "from"
                assert symbol.metadata["import_type"] in {"module", "from"}

                # is_likely_reexport should be boolean
                assert isinstance(symbol.metadata["is_likely_reexport"], bool)

                # is_stdlib should be boolean
                assert isinstance(symbol.metadata["is_stdlib"], bool)
        finally:
            file_path.unlink()

    def test_import_type_correct(self, parser) -> None:
        """Test import_type metadata is correct."""
        content = """
import os
from pathlib import Path
"""
        file_path = create_temp_file(content)
        try:
            result = parser.parse_file(file_path, "test.module")

            os_import = next(s for s in result.symbols if s.name == "os")
            path_import = next(s for s in result.symbols if s.name == "Path")

            assert os_import.metadata["import_type"] == "module"
            assert path_import.metadata["import_type"] == "from"
        finally:
            file_path.unlink()


class TestEdgeCases:
    """Test edge cases in import categorization."""

    def test_empty_module_from_import(self, parser) -> None:
        """Test from . import with no module name."""
        content = """
from . import utils
"""
        file_path = create_temp_file(content)
        try:
            result = parser.parse_file(file_path, "test.module")

            utils_import = next(s for s in result.symbols if s.name == "utils")

            # Should have all metadata fields
            assert "is_likely_reexport" in utils_import.metadata
            assert "is_stdlib" in utils_import.metadata

            # Not aliased, so not likely re-export
            assert utils_import.metadata["is_likely_reexport"] is False
        finally:
            file_path.unlink()

    def test_underscore_internal_modules_are_stdlib(self, parser) -> None:
        """Modules starting with underscore should be treated as stdlib/internal."""
        content = """
import _thread
from _collections import deque
"""
        file_path = create_temp_file(content)
        try:
            result = parser.parse_file(file_path, "test.module")

            thread_import = next(s for s in result.symbols if s.name == "_thread")
            deque_import = next(s for s in result.symbols if s.name == "deque")

            # Internal modules should be treated as stdlib
            assert thread_import.metadata.get("is_stdlib") is True
            assert deque_import.metadata.get("is_stdlib") is True
        finally:
            file_path.unlink()
