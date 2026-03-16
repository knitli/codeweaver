import sys
import codeweaver
import pytest
from codeweaver import get_version

def test_mock(monkeypatch):
    monkeypatch.setitem(sys.modules, "codeweaver._version", None)
    if hasattr(codeweaver, "_version"):
        monkeypatch.delattr(codeweaver, "_version")

    try:
        print(get_version())
    except Exception as e:
        print(f"Exception: {e}")

pytest.main(["-s", "test_import_final.py"])
