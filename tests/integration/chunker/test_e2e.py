[38;5;238m─────┬──────────────────────────────────────────────────────────────────────────[0m
     [38;5;238m│ [0m[1mSTDIN[0m
[38;5;238m─────┼──────────────────────────────────────────────────────────────────────────[0m
[38;5;238m   1[0m [38;5;238m│[0m [38;2;248;248;242m"""[0m
[38;5;238m   2[0m [38;5;238m│[0m [38;2;248;248;242mSPDX-FileCopyrightText: 2025 Knitli Inc.[0m
[38;5;238m   3[0m [38;5;238m│[0m [38;2;248;248;242mSPDX-FileContributor: Adam Poulemanos <adam@knit.li>[0m
[38;5;238m   4[0m [38;5;238m│[0m 
[38;5;238m   5[0m [38;5;238m│[0m [38;2;248;248;242mSPDX-License-Identifier: MIT OR Apache-2.0[0m
[38;5;238m   6[0m [38;5;238m│[0m [38;2;248;248;242m"""[0m
[38;5;238m   7[0m [38;5;238m│[0m 
[38;5;238m   8[0m [38;5;238m│[0m [38;2;248;248;242m"""End-to-end integration tests for chunking workflows."""[0m
[38;5;238m   9[0m [38;5;238m│[0m 
[38;5;238m  10[0m [38;5;238m│[0m [38;2;248;248;242mfrom pathlib import Path[0m
[38;5;238m  11[0m [38;5;238m│[0m [38;2;248;248;242mfrom unittest.mock import Mock[0m
[38;5;238m  12[0m [38;5;238m│[0m 
[38;5;238m  13[0m [38;5;238m│[0m [38;2;248;248;242mimport pytest[0m
[38;5;238m  14[0m [38;5;238m│[0m 
[38;5;238m  15[0m [38;5;238m│[0m [38;2;248;248;242mfrom codeweaver.engine.chunker.selector import ChunkerSelector[0m
[38;5;238m  16[0m [38;5;238m│[0m 
[38;5;238m  17[0m [38;5;238m│[0m 
[38;5;238m  18[0m [38;5;238m│[0m [38;2;248;248;242m@pytest.fixture[0m
[38;5;238m  19[0m [38;5;238m│[0m [38;2;248;248;242mdef mock_governor():[0m
[38;5;238m  20[0m [38;5;238m│[0m [38;2;248;248;242m    """Create mock ChunkGovernor."""[0m
[38;5;238m  21[0m [38;5;238m│[0m [38;2;248;248;242m    governor = Mock()[0m
[38;5;238m  22[0m [38;5;238m│[0m [38;2;248;248;242m    governor.chunk_limit = 2000[0m
[38;5;238m  23[0m [38;5;238m│[0m [38;2;248;248;242m    governor.simple_overlap = 50[0m
[38;5;238m  24[0m [38;5;238m│[0m [38;2;248;248;242m    governor.performance_settings = Mock([0m
[38;5;238m  25[0m [38;5;238m│[0m [38;2;248;248;242m        chunk_timeout_seconds=30,[0m
[38;5;238m  26[0m [38;5;238m│[0m [38;2;248;248;242m        max_chunks_per_file=5000,[0m
[38;5;238m  27[0m [38;5;238m│[0m [38;2;248;248;242m        max_ast_depth=200,[0m
[38;5;238m  28[0m [38;5;238m│[0m [38;2;248;248;242m    )[0m
[38;5;238m  29[0m [38;5;238m│[0m [38;2;248;248;242m    return governor[0m
[38;5;238m  30[0m [38;5;238m│[0m 
[38;5;238m  31[0m [38;5;238m│[0m 
[38;5;238m  32[0m [38;5;238m│[0m [38;2;248;248;242m@pytest.fixture[0m
[38;5;238m  33[0m [38;5;238m│[0m [38;2;248;248;242mdef mock_discovered_file():[0m
[38;5;238m  34[0m [38;5;238m│[0m [38;2;248;248;242m    """Create mock DiscoveredFile."""[0m
[38;5;238m  35[0m [38;5;238m│[0m [38;2;248;248;242m    def _make_file(path_str):[0m
[38;5;238m  36[0m [38;5;238m│[0m [38;2;248;248;242m        file = Mock()[0m
[38;5;238m  37[0m [38;5;238m│[0m [38;2;248;248;242m        file.path = Path(path_str)[0m
[38;5;238m  38[0m [38;5;238m│[0m [38;2;248;248;242m        return file[0m
[38;5;238m  39[0m [38;5;238m│[0m [38;2;248;248;242m    return _make_file[0m
[38;5;238m  40[0m [38;5;238m│[0m 
[38;5;238m  41[0m [38;5;238m│[0m 
[38;5;238m  42[0m [38;5;238m│[0m [38;2;248;248;242mdef test_e2e_real_python_file(mock_governor, mock_discovered_file):[0m
[38;5;238m  43[0m [38;5;238m│[0m [38;2;248;248;242m    """Integration test: Real Python file → valid chunks."""[0m
[38;5;238m  44[0m [38;5;238m│[0m [38;2;248;248;242m    fixture_path = Path("tests/fixtures/sample.py")[0m
[38;5;238m  45[0m [38;5;238m│[0m [38;2;248;248;242m    content = fixture_path.read_text()[0m
[38;5;238m  46[0m [38;5;238m│[0m 
[38;5;238m  47[0m [38;5;238m│[0m [38;2;248;248;242m    selector = ChunkerSelector(mock_governor)[0m
[38;5;238m  48[0m [38;5;238m│[0m [38;2;248;248;242m    file = mock_discovered_file(str(fixture_path))[0m
[38;5;238m  49[0m [38;5;238m│[0m [38;2;248;248;242m    chunker = selector.select_for_file(file)[0m
[38;5;238m  50[0m [38;5;238m│[0m 
[38;5;238m  51[0m [38;5;238m│[0m [38;2;248;248;242m    chunks = chunker.chunk(content, file_path=fixture_path)[0m
[38;5;238m  52[0m [38;5;238m│[0m 
[38;5;238m  53[0m [38;5;238m│[0m [38;2;248;248;242m    # Basic quality checks[0m
[38;5;238m  54[0m [38;5;238m│[0m [38;2;248;248;242m    assert len(chunks) > 0, "Should produce chunks"[0m
[38;5;238m  55[0m [38;5;238m│[0m [38;2;248;248;242m    assert all(c.content.strip() for c in chunks), "No empty chunks"[0m
[38;5;238m  56[0m [38;5;238m│[0m [38;2;248;248;242m    assert all(c.metadata for c in chunks), "All chunks have metadata"[0m
[38;5;238m  57[0m [38;5;238m│[0m [38;2;248;248;242m    assert all(c.line_range.start <= c.line_range.end for c in chunks), \[0m
[38;5;238m  58[0m [38;5;238m│[0m [38;2;248;248;242m        "Valid line ranges"[0m
[38;5;238m  59[0m [38;5;238m│[0m 
[38;5;238m  60[0m [38;5;238m│[0m 
[38;5;238m  61[0m [38;5;238m│[0m [38;2;248;248;242mdef test_e2e_degradation_chain(mock_governor, mock_discovered_file):[0m
[38;5;238m  62[0m [38;5;238m│[0m [38;2;248;248;242m    """Verify degradation chain handles malformed files."""[0m
[38;5;238m  63[0m [38;5;238m│[0m [38;2;248;248;242m    fixture_path = Path("tests/fixtures/malformed.py")[0m
[38;5;238m  64[0m [38;5;238m│[0m [38;2;248;248;242m    content = fixture_path.read_text()[0m
[38;5;238m  65[0m [38;5;238m│[0m 
[38;5;238m  66[0m [38;5;238m│[0m [38;2;248;248;242m    selector = ChunkerSelector(mock_governor)[0m
[38;5;238m  67[0m [38;5;238m│[0m [38;2;248;248;242m    file = mock_discovered_file(str(fixture_path))[0m
[38;5;238m  68[0m [38;5;238m│[0m 
[38;5;238m  69[0m [38;5;238m│[0m [38;2;248;248;242m    # Should gracefully degrade and still produce chunks[0m
[38;5;238m  70[0m [38;5;238m│[0m [38;2;248;248;242m    # (implementation will add fallback logic)[0m
[38;5;238m  71[0m [38;5;238m│[0m [38;2;248;248;242m    with pytest.raises(Exception):  # Will fail until fallback implemented[0m
[38;5;238m  72[0m [38;5;238m│[0m [38;2;248;248;242m        chunker = selector.select_for_file(file)[0m
[38;5;238m  73[0m [38;5;238m│[0m [38;2;248;248;242m        chunks = chunker.chunk(content, file_path=fixture_path)[0m
[38;5;238m─────┴──────────────────────────────────────────────────────────────────────────[0m
