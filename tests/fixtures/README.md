<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

[38;5;238m─────┬──────────────────────────────────────────────────────────────────────────[0m
     [38;5;238m│ [0m[1mSTDIN[0m
[38;5;238m─────┼──────────────────────────────────────────────────────────────────────────[0m
[38;5;238m   1[0m [38;5;238m│[0m [38;2;248;248;242m# Test Fixtures for Chunker Validation[0m
[38;5;238m   2[0m [38;5;238m│[0m 
[38;5;238m   3[0m [38;5;238m│[0m [38;2;248;248;242mThis directory contains comprehensive test fixtures for validating chunker functionality across various scenarios.[0m
[38;5;238m   4[0m [38;5;238m│[0m 
[38;5;238m   5[0m [38;5;238m│[0m [38;2;248;248;242m## Files Created[0m
[38;5;238m   6[0m [38;5;238m│[0m 
[38;5;238m   7[0m [38;5;238m│[0m [38;2;248;248;242m### 1. Realistic Code Samples[0m
[38;5;238m   8[0m [38;5;238m│[0m 
[38;5;238m   9[0m [38;5;238m│[0m [38;2;248;248;242m#### `sample.py` (~129 lines)[0m
[38;5;238m  10[0m [38;5;238m│[0m [38;2;248;248;242m- Multiple classes (`DataProcessor`, `CacheManager`)[0m
[38;5;238m  11[0m [38;5;238m│[0m [38;2;248;248;242m- Async methods and nested functions[0m
[38;5;238m  12[0m [38;5;238m│[0m [38;2;248;248;242m- Docstrings and type hints[0m
[38;5;238m  13[0m [38;5;238m│[0m [38;2;248;248;242m- Realistic Python patterns for testing AST parsing[0m
[38;5;238m  14[0m [38;5;238m│[0m 
[38;5;238m  15[0m [38;5;238m│[0m [38;2;248;248;242m#### `sample.js` (~103 lines)[0m
[38;5;238m  16[0m [38;5;238m│[0m [38;2;248;248;242m- ES6 class definitions[0m
[38;5;238m  17[0m [38;5;238m│[0m [38;2;248;248;242m- Nested functions and closures[0m
[38;5;238m  18[0m [38;5;238m│[0m [38;2;248;248;242m- Higher-order functions (factory pattern, decorators)[0m
[38;5;238m  19[0m [38;5;238m│[0m [38;2;248;248;242m- Module exports[0m
[38;5;238m  20[0m [38;5;238m│[0m 
[38;5;238m  21[0m [38;5;238m│[0m [38;2;248;248;242m#### `sample.rs` (~96 lines)[0m
[38;5;238m  22[0m [38;5;238m│[0m [38;2;248;248;242m- Trait definitions (`Cacheable`)[0m
[38;5;238m  23[0m [38;5;238m│[0m [38;2;248;248;242m- Generic structs with type parameters[0m
[38;5;238m  24[0m [38;5;238m│[0m [38;2;248;248;242m- Impl blocks for multiple traits[0m
[38;5;238m  25[0m [38;5;238m│[0m [38;2;248;248;242m- Macros (`data_item!`)[0m
[38;5;238m  26[0m [38;5;238m│[0m [38;2;248;248;242m- Test module[0m
[38;5;238m  27[0m [38;5;238m│[0m 
[38;5;238m  28[0m [38;5;238m│[0m [38;2;248;248;242m#### `sample.go` (~121 lines)[0m
[38;5;238m  29[0m [38;5;238m│[0m [38;2;248;248;242m- Interface definitions (`Processor`)[0m
[38;5;238m  30[0m [38;5;238m│[0m [38;2;248;248;242m- Struct definitions with methods[0m
[38;5;238m  31[0m [38;5;238m│[0m [38;2;248;248;242m- Goroutines and channels (concurrency patterns)[0m
[38;5;238m  32[0m [38;5;238m│[0m [38;2;248;248;242m- Mutex-based thread safety[0m
[38;5;238m  33[0m [38;5;238m│[0m 
[38;5;238m  34[0m [38;5;238m│[0m [38;2;248;248;242m### 2. Error Condition Fixtures[0m
[38;5;238m  35[0m [38;5;238m│[0m 
[38;5;238m  36[0m [38;5;238m│[0m [38;2;248;248;242m#### `malformed.py` (~27 lines)[0m
[38;5;238m  37[0m [38;5;238m│[0m [38;2;248;248;242m- **Purpose**: Trigger `ParseError` in chunker[0m
[38;5;238m  38[0m [38;5;238m│[0m [38;2;248;248;242m- **Issues**: Unclosed parentheses, brackets, invalid indentation[0m
[38;5;238m  39[0m [38;5;238m│[0m [38;2;248;248;242m- **Expected**: Should gracefully handle syntax errors[0m
[38;5;238m  40[0m [38;5;238m│[0m 
[38;5;238m  41[0m [38;5;238m│[0m [38;2;248;248;242m#### `huge_function.py` (~266 lines)[0m
[38;5;238m  42[0m [38;5;238m│[0m [38;2;248;248;242m- **Purpose**: Test token limit enforcement (>2000 tokens)[0m
[38;5;238m  43[0m [38;5;238m│[0m [38;2;248;248;242m- **Content**: Single massive function with 250+ repetitive lines[0m
[38;5;238m  44[0m [38;5;238m│[0m [38;2;248;248;242m- **Expected**: Should trigger `ChunkExceedsTokenLimitError`[0m
[38;5;238m  45[0m [38;5;238m│[0m 
[38;5;238m  46[0m [38;5;238m│[0m [38;2;248;248;242m#### `deep_nesting.py` (~259 lines)[0m
[38;5;238m  47[0m [38;5;238m│[0m [38;2;248;248;242m- **Purpose**: Test AST depth limit (>200 levels)[0m
[38;5;238m  48[0m [38;5;238m│[0m [38;2;248;248;242m- **Content**: 250 levels of nested if statements[0m
[38;5;238m  49[0m [38;5;238m│[0m [38;2;248;248;242m- **Expected**: Should trigger `ASTDepthExceededError`[0m
[38;5;238m  50[0m [38;5;238m│[0m 
[38;5;238m  51[0m [38;5;238m│[0m [38;2;248;248;242m### 3. Edge Case Fixtures[0m
[38;5;238m  52[0m [38;5;238m│[0m 
[38;5;238m  53[0m [38;5;238m│[0m [38;2;248;248;242m#### `empty.py` (0 bytes)[0m
[38;5;238m  54[0m [38;5;238m│[0m [38;2;248;248;242m- **Purpose**: Test empty file handling[0m
[38;5;238m  55[0m [38;5;238m│[0m [38;2;248;248;242m- **Expected**: Should return empty chunk list or single empty chunk[0m
[38;5;238m  56[0m [38;5;238m│[0m 
[38;5;238m  57[0m [38;5;238m│[0m [38;2;248;248;242m#### `single_line.py` (1 line)[0m
[38;5;238m  58[0m [38;5;238m│[0m [38;2;248;248;242m- **Content**: `x = 1`[0m
[38;5;238m  59[0m [38;5;238m│[0m [38;2;248;248;242m- **Expected**: Should parse as single statement[0m
[38;5;238m  60[0m [38;5;238m│[0m 
[38;5;238m  61[0m [38;5;238m│[0m [38;2;248;248;242m#### `whitespace_only.py` (10 lines)[0m
[38;5;238m  62[0m [38;5;238m│[0m [38;2;248;248;242m- **Content**: Only whitespace and newlines[0m
[38;5;238m  63[0m [38;5;238m│[0m [38;2;248;248;242m- **Expected**: Should handle gracefully, possibly empty result[0m
[38;5;238m  64[0m [38;5;238m│[0m 
[38;5;238m  65[0m [38;5;238m│[0m [38;2;248;248;242m#### `binary_mock.txt` (132 bytes)[0m
[38;5;238m  66[0m [38;5;238m│[0m [38;2;248;248;242m- **Purpose**: Test binary content detection[0m
[38;5;238m  67[0m [38;5;238m│[0m [38;2;248;248;242m- **Content**: Contains null bytes (`\x00`) embedded in text[0m
[38;5;238m  68[0m [38;5;238m│[0m [38;2;248;248;242m- **Expected**: Should detect as binary and skip or handle appropriately[0m
[38;5;238m  69[0m [38;5;238m│[0m 
[38;5;238m  70[0m [38;5;238m│[0m [38;2;248;248;242m## Usage in Tests[0m
[38;5;238m  71[0m [38;5;238m│[0m 
[38;5;238m  72[0m [38;5;238m│[0m [38;2;248;248;242m```python[0m
[38;5;238m  73[0m [38;5;238m│[0m [38;2;248;248;242mimport pytest[0m
[38;5;238m  74[0m [38;5;238m│[0m [38;2;248;248;242mfrom pathlib import Path[0m
[38;5;238m  75[0m [38;5;238m│[0m 
[38;5;238m  76[0m [38;5;238m│[0m [38;2;248;248;242mFIXTURES_DIR = Path(__file__).parent / "fixtures"[0m
[38;5;238m  77[0m [38;5;238m│[0m 
[38;5;238m  78[0m [38;5;238m│[0m [38;2;248;248;242mdef test_parse_realistic_python():[0m
[38;5;238m  79[0m [38;5;238m│[0m [38;2;248;248;242m    """Test chunker on realistic Python code."""[0m
[38;5;238m  80[0m [38;5;238m│[0m [38;2;248;248;242m    sample = FIXTURES_DIR / "sample.py"[0m
[38;5;238m  81[0m [38;5;238m│[0m [38;2;248;248;242m    chunks = chunker.chunk_file(sample)[0m
[38;5;238m  82[0m [38;5;238m│[0m [38;2;248;248;242m    assert len(chunks) > 0[0m
[38;5;238m  83[0m [38;5;238m│[0m [38;2;248;248;242m    # Verify classes and methods are properly extracted[0m
[38;5;238m  84[0m [38;5;238m│[0m 
[38;5;238m  85[0m [38;5;238m│[0m [38;2;248;248;242mdef test_malformed_syntax():[0m
[38;5;238m  86[0m [38;5;238m│[0m [38;2;248;248;242m    """Test error handling for malformed code."""[0m
[38;5;238m  87[0m [38;5;238m│[0m [38;2;248;248;242m    malformed = FIXTURES_DIR / "malformed.py"[0m
[38;5;238m  88[0m [38;5;238m│[0m [38;2;248;248;242m    with pytest.raises(ParseError):[0m
[38;5;238m  89[0m [38;5;238m│[0m [38;2;248;248;242m        chunker.chunk_file(malformed)[0m
[38;5;238m  90[0m [38;5;238m│[0m 
[38;5;238m  91[0m [38;5;238m│[0m [38;2;248;248;242mdef test_huge_function_token_limit():[0m
[38;5;238m  92[0m [38;5;238m│[0m [38;2;248;248;242m    """Test token limit enforcement."""[0m
[38;5;238m  93[0m [38;5;238m│[0m [38;2;248;248;242m    huge = FIXTURES_DIR / "huge_function.py"[0m
[38;5;238m  94[0m [38;5;238m│[0m [38;2;248;248;242m    with pytest.raises(ChunkExceedsTokenLimitError):[0m
[38;5;238m  95[0m [38;5;238m│[0m [38;2;248;248;242m        chunker.chunk_file(huge)[0m
[38;5;238m  96[0m [38;5;238m│[0m 
[38;5;238m  97[0m [38;5;238m│[0m [38;2;248;248;242mdef test_deep_nesting_limit():[0m
[38;5;238m  98[0m [38;5;238m│[0m [38;2;248;248;242m    """Test AST depth limit enforcement."""[0m
[38;5;238m  99[0m [38;5;238m│[0m [38;2;248;248;242m    deep = FIXTURES_DIR / "deep_nesting.py"[0m
[38;5;238m 100[0m [38;5;238m│[0m [38;2;248;248;242m    with pytest.raises(ASTDepthExceededError):[0m
[38;5;238m 101[0m [38;5;238m│[0m [38;2;248;248;242m        chunker.chunk_file(deep)[0m
[38;5;238m 102[0m [38;5;238m│[0m 
[38;5;238m 103[0m [38;5;238m│[0m [38;2;248;248;242mdef test_empty_file():[0m
[38;5;238m 104[0m [38;5;238m│[0m [38;2;248;248;242m    """Test empty file handling."""[0m
[38;5;238m 105[0m [38;5;238m│[0m [38;2;248;248;242m    empty = FIXTURES_DIR / "empty.py"[0m
[38;5;238m 106[0m [38;5;238m│[0m [38;2;248;248;242m    chunks = chunker.chunk_file(empty)[0m
[38;5;238m 107[0m [38;5;238m│[0m [38;2;248;248;242m    assert chunks == [] or len(chunks) == 1[0m
[38;5;238m 108[0m [38;5;238m│[0m 
[38;5;238m 109[0m [38;5;238m│[0m [38;2;248;248;242mdef test_binary_detection():[0m
[38;5;238m 110[0m [38;5;238m│[0m [38;2;248;248;242m    """Test binary content detection."""[0m
[38;5;238m 111[0m [38;5;238m│[0m [38;2;248;248;242m    binary = FIXTURES_DIR / "binary_mock.txt"[0m
[38;5;238m 112[0m [38;5;238m│[0m [38;2;248;248;242m    # Should detect and skip binary files[0m
[38;5;238m 113[0m [38;5;238m│[0m [38;2;248;248;242m    result = chunker.chunk_file(binary)[0m
[38;5;238m 114[0m [38;5;238m│[0m [38;2;248;248;242m    assert result is None or result == [][0m
[38;5;238m 115[0m [38;5;238m│[0m [38;2;248;248;242m```[0m
[38;5;238m 116[0m [38;5;238m│[0m 
[38;5;238m 117[0m [38;5;238m│[0m [38;2;248;248;242m## Validation Checklist[0m
[38;5;238m 118[0m [38;5;238m│[0m 
[38;5;238m 119[0m [38;5;238m│[0m [38;2;248;248;242m- [x] Realistic multi-language samples (Python, JavaScript, Rust, Go)[0m
[38;5;238m 120[0m [38;5;238m│[0m [38;2;248;248;242m- [x] Syntax error cases (malformed.py)[0m
[38;5;238m 121[0m [38;5;238m│[0m [38;2;248;248;242m- [x] Token limit violations (huge_function.py)[0m
[38;5;238m 122[0m [38;5;238m│[0m [38;2;248;248;242m- [x] Depth limit violations (deep_nesting.py)[0m
[38;5;238m 123[0m [38;5;238m│[0m [38;2;248;248;242m- [x] Empty file edge case (empty.py)[0m
[38;5;238m 124[0m [38;5;238m│[0m [38;2;248;248;242m- [x] Minimal content edge case (single_line.py)[0m
[38;5;238m 125[0m [38;5;238m│[0m [38;2;248;248;242m- [x] Whitespace-only edge case (whitespace_only.py)[0m
[38;5;238m 126[0m [38;5;238m│[0m [38;2;248;248;242m- [x] Binary content detection (binary_mock.txt)[0m
[38;5;238m 127[0m [38;5;238m│[0m [38;2;248;248;242m- [x] SPDX headers on code files[0m
[38;5;238m 128[0m [38;5;238m│[0m [38;2;248;248;242m- [x] Varied and realistic content[0m
[38;5;238m 129[0m [38;5;238m│[0m 
[38;5;238m 130[0m [38;5;238m│[0m [38;2;248;248;242m## Notes[0m
[38;5;238m 131[0m [38;5;238m│[0m 
[38;5;238m 132[0m [38;5;238m│[0m [38;2;248;248;242m- All code fixtures include SPDX license headers (MIT OR Apache-2.0)[0m
[38;5;238m 133[0m [38;5;238m│[0m [38;2;248;248;242m- Files are designed to be self-contained and require no external dependencies[0m
[38;5;238m 134[0m [38;5;238m│[0m [38;2;248;248;242m- Token counts estimated based on typical tokenization (~4 chars per token)[0m
[38;5;238m 135[0m [38;5;238m│[0m [38;2;248;248;242m- Nesting depth carefully calibrated to exceed governance limits (>200)[0m
[38;5;238m─────┴──────────────────────────────────────────────────────────────────────────[0m
