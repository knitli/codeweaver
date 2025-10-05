# Grammar Structure Analysis Report

## Per-Language Statistics


Language: bash
============================================================
Total Nodes: 184
  Named: 62 (33.7%)
  Unnamed: 122 (66.3%)

Abstract Types: 3
  Top abstract categories: _expression, _primary_expression, _statement

Structural Patterns:
  Nodes with fields: 46 (74.2% of named)
  Nodes with children: 37
  Nodes with both: 37

Common Field Names (top 10):
  operator: 5
  body: 5
  redirect: 5
  condition: 4
  value: 4
  name: 4
  descriptor: 3
  right: 2
  argument: 2
  left: 1

Extra Nodes: 1
  Examples: comment

Root Nodes: program


Language: c
============================================================
Total Nodes: 275
  Named: 132 (48.0%)
  Unnamed: 143 (52.0%)

Abstract Types: 7
  Top abstract categories: _abstract_declarator, _declarator, _field_declarator, _type_declarator, expression, statement, type_specifier

Structural Patterns:
  Nodes with fields: 107 (81.1% of named)
  Nodes with children: 58
  Nodes with both: 58

Common Field Names (top 10):
  declarator: 13
  type: 13
  value: 12
  body: 12
  name: 10
  condition: 8
  operator: 6
  alternative: 6
  argument: 6
  parameters: 3

Extra Nodes: 1
  Examples: comment

Root Nodes: translation_unit


Language: cpp
============================================================
Total Nodes: 430
  Named: 230 (53.5%)
  Unnamed: 200 (46.5%)

Abstract Types: 7
  Top abstract categories: _abstract_declarator, _declarator, _field_declarator, _type_declarator, expression, statement, type_specifier

Structural Patterns:
  Nodes with fields: 199 (86.5% of named)
  Nodes with children: 124
  Nodes with both: 124

Common Field Names (top 10):
  declarator: 22
  name: 21
  type: 20
  body: 20
  value: 14
  operator: 10
  right: 9
  condition: 9
  parameters: 8
  left: 7

Extra Nodes: 1
  Examples: comment

Root Nodes: translation_unit


Language: csharp
============================================================
Total Nodes: 407
  Named: 220 (54.1%)
  Unnamed: 187 (45.9%)

Abstract Types: 9
  Top abstract categories: declaration, expression, literal, lvalue_expression, non_lvalue_expression, pattern, statement, type, type_declaration

Structural Patterns:
  Nodes with fields: 192 (87.3% of named)
  Nodes with children: 137
  Nodes with both: 137

Common Field Names (top 10):
  name: 39
  type: 37
  body: 22
  parameters: 10
  condition: 9
  operator: 8
  left: 7
  right: 7
  value: 6
  alternative: 5

Extra Nodes: 0
  Examples: 

Root Nodes: compilation_unit


Language: css
============================================================
Total Nodes: 105
  Named: 64 (61.0%)
  Unnamed: 41 (39.0%)

Abstract Types: 0
  Top abstract categories: 

Structural Patterns:
  Nodes with fields: 44 (68.8% of named)
  Nodes with children: 41
  Nodes with both: 41

Common Field Names (top 10):
  

Extra Nodes: 2
  Examples: comment, js_comment

Root Nodes: stylesheet


Language: elixir
============================================================
Total Nodes: 128
  Named: 45 (35.2%)
  Unnamed: 83 (64.8%)

Abstract Types: 0
  Top abstract categories: 

Structural Patterns:
  Nodes with fields: 34 (75.6% of named)
  Nodes with children: 24
  Nodes with both: 24

Common Field Names (top 10):
  quoted_end: 5
  quoted_start: 5
  operator: 4
  left: 3
  right: 3
  key: 2
  target: 2
  value: 1
  operand: 1

Extra Nodes: 0
  Examples: 

Root Nodes: source


Language: go
============================================================
Total Nodes: 188
  Named: 112 (59.6%)
  Unnamed: 76 (40.4%)

Abstract Types: 5
  Top abstract categories: _expression, _simple_statement, _simple_type, _statement, _type

Structural Patterns:
  Nodes with fields: 89 (79.5% of named)
  Nodes with children: 48
  Nodes with both: 48

Common Field Names (top 10):
  type: 14
  name: 13
  value: 9
  operand: 6
  left: 5
  right: 5
  body: 5
  parameters: 5
  result: 5
  initializer: 4

Extra Nodes: 1
  Examples: comment

Root Nodes: source_file


Language: haskell
============================================================
Total Nodes: 280
  Named: 187 (66.8%)
  Unnamed: 93 (33.2%)

Abstract Types: 14
  Top abstract categories: class_decl, constraint, constraints, decl, declaration, expression, guard, instance_decl, pattern, qualifier, quantified_type, statement, type, type_param

Structural Patterns:
  Nodes with fields: 156 (83.4% of named)
  Nodes with children: 51
  Nodes with both: 51

Common Field Names (top 10):
  name: 26
  type: 24
  patterns: 16
  expression: 15
  pattern: 13
  field: 9
  kind: 8
  context: 8
  forall: 8
  arrow: 7

Extra Nodes: 0
  Examples: 

Root Nodes: haskell


Language: html
============================================================
Total Nodes: 28
  Named: 19 (67.9%)
  Unnamed: 9 (32.1%)

Abstract Types: 0
  Top abstract categories: 

Structural Patterns:
  Nodes with fields: 11 (57.9% of named)
  Nodes with children: 10
  Nodes with both: 10

Common Field Names (top 10):
  

Extra Nodes: 0
  Examples: 

Root Nodes: document


Language: java
============================================================
Total Nodes: 265
  Named: 151 (57.0%)
  Unnamed: 114 (43.0%)

Abstract Types: 9
  Top abstract categories: _literal, _simple_type, _type, _unannotated_type, declaration, expression, module_directive, primary_expression, statement

Structural Patterns:
  Nodes with fields: 121 (80.1% of named)
  Nodes with children: 91
  Nodes with both: 91

Common Field Names (top 10):
  name: 21
  body: 20
  type: 12
  dimensions: 9
  value: 7
  condition: 6
  arguments: 5
  type_parameters: 5
  parameters: 4
  left: 3

Extra Nodes: 0
  Examples: 

Root Nodes: program


Language: javascript
============================================================
Total Nodes: 226
  Named: 119 (52.7%)
  Unnamed: 107 (47.3%)

Abstract Types: 5
  Top abstract categories: declaration, expression, pattern, primary_expression, statement

Structural Patterns:
  Nodes with fields: 91 (76.5% of named)
  Nodes with children: 42
  Nodes with both: 42

Common Field Names (top 10):
  body: 21
  name: 13
  value: 8
  parameters: 6
  left: 6
  right: 6
  operator: 5
  decorator: 5
  condition: 5
  label: 3

Extra Nodes: 2
  Examples: comment, html_comment

Root Nodes: program


Language: json
============================================================
Total Nodes: 20
  Named: 13 (65.0%)
  Unnamed: 7 (35.0%)

Abstract Types: 1
  Top abstract categories: _value

Structural Patterns:
  Nodes with fields: 5 (38.5% of named)
  Nodes with children: 4
  Nodes with both: 4

Common Field Names (top 10):
  key: 1
  value: 1

Extra Nodes: 0
  Examples: 

Root Nodes: document


Language: kotlin
============================================================
Total Nodes: 244
  Named: 120 (49.2%)
  Unnamed: 124 (50.8%)

Abstract Types: 6
  Top abstract categories: class_member_declaration, declaration, expression, primary_expression, statement, type

Structural Patterns:
  Nodes with fields: 104 (86.7% of named)
  Nodes with children: 88
  Nodes with both: 88

Common Field Names (top 10):
  left: 5
  right: 5
  name: 4
  condition: 4
  operator: 3
  label: 1
  type: 1
  argument: 1

Extra Nodes: 0
  Examples: 

Root Nodes: source_file


Language: lua
============================================================
Total Nodes: 105
  Named: 50 (47.6%)
  Unnamed: 55 (52.4%)

Abstract Types: 4
  Top abstract categories: declaration, expression, statement, variable

Structural Patterns:
  Nodes with fields: 36 (72.0% of named)
  Nodes with children: 15
  Nodes with both: 15

Common Field Names (top 10):
  body: 7
  name: 6
  condition: 4
  table: 3
  end: 3
  start: 3
  operator: 2
  field: 2
  content: 2
  consequence: 2

Extra Nodes: 1
  Examples: comment

Root Nodes: chunk


Language: nix
============================================================
Total Nodes: 84
  Named: 42 (50.0%)
  Unnamed: 42 (50.0%)

Abstract Types: 1
  Top abstract categories: _expression

Structural Patterns:
  Nodes with fields: 30 (71.4% of named)
  Nodes with children: 8
  Nodes with both: 8

Common Field Names (top 10):
  expression: 7
  body: 4
  operator: 3
  attrpath: 3
  argument: 2
  condition: 2
  attr: 2
  default: 2
  name: 2
  attrs: 2

Extra Nodes: 0
  Examples: 

Root Nodes: 


Language: php
============================================================
Total Nodes: 304
  Named: 161 (53.0%)
  Unnamed: 143 (47.0%)

Abstract Types: 5
  Top abstract categories: expression, literal, primary_expression, statement, type

Structural Patterns:
  Nodes with fields: 144 (89.4% of named)
  Nodes with children: 93
  Nodes with both: 93

Common Field Names (top 10):
  body: 25
  name: 21
  attributes: 16
  type: 9
  condition: 8
  parameters: 6
  reference_modifier: 6
  value: 6
  return_type: 4
  left: 4

Extra Nodes: 2
  Examples: text_interpolation, comment

Root Nodes: program


Language: python
============================================================
Total Nodes: 218
  Named: 129 (59.2%)
  Unnamed: 89 (40.8%)

Abstract Types: 7
  Top abstract categories: _compound_statement, _simple_statement, expression, expression_statement, parameter, pattern, primary_expression

Structural Patterns:
  Nodes with fields: 110 (85.3% of named)
  Nodes with children: 70
  Nodes with both: 70

Common Field Names (top 10):
  body: 13
  name: 10
  value: 9
  left: 7
  right: 7
  operator: 4
  alternative: 4
  alias: 3
  type: 3
  consequence: 3

Extra Nodes: 2
  Examples: comment, line_continuation

Root Nodes: module


Language: ruby
============================================================
Total Nodes: 253
  Named: 149 (58.9%)
  Unnamed: 104 (41.1%)

Abstract Types: 15
  Top abstract categories: _arg, _call_operator, _expression, _lhs, _method_name, _nonlocal_variable, _pattern_constant, _pattern_expr, _pattern_expr_basic, _pattern_primitive, _pattern_top_expr_body, _primary, _simple_numeric, _statement, _variable

Structural Patterns:
  Nodes with fields: 113 (75.8% of named)
  Nodes with children: 56
  Nodes with both: 56

Common Field Names (top 10):
  body: 19
  name: 14
  value: 12
  condition: 12
  operator: 5
  parameters: 5
  pattern: 5
  alternative: 4
  consequence: 4
  class: 3

Extra Nodes: 0
  Examples: 

Root Nodes: program


Language: rust
============================================================
Total Nodes: 280
  Named: 169 (60.4%)
  Unnamed: 111 (39.6%)

Abstract Types: 6
  Top abstract categories: _declaration_statement, _expression, _literal, _literal_pattern, _pattern, _type

Structural Patterns:
  Nodes with fields: 146 (86.4% of named)
  Nodes with children: 104
  Nodes with both: 104

Common Field Names (top 10):
  name: 24
  type: 20
  body: 16
  value: 14
  type_parameters: 10
  pattern: 7
  left: 6
  right: 5
  bounds: 5
  type_arguments: 5

Extra Nodes: 0
  Examples: 

Root Nodes: source_file


Language: scala
============================================================
Total Nodes: 236
  Named: 148 (62.7%)
  Unnamed: 88 (37.3%)

Abstract Types: 3
  Top abstract categories: _definition, _pattern, expression

Structural Patterns:
  Nodes with fields: 137 (92.6% of named)
  Nodes with children: 86
  Nodes with both: 86

Common Field Names (top 10):
  name: 27
  type: 22
  body: 17
  type_parameters: 13
  pattern: 8
  extend: 7
  return_type: 6
  arguments: 5
  derive: 5
  bound: 5

Extra Nodes: 0
  Examples: 

Root Nodes: compilation_unit


Language: solidity
============================================================
Total Nodes: 433
  Named: 124 (28.6%)
  Unnamed: 309 (71.4%)

Abstract Types: 0
  Top abstract categories: 

Structural Patterns:
  Nodes with fields: 114 (91.9% of named)
  Nodes with children: 65
  Nodes with both: 65

Common Field Names (top 10):
  name: 21
  body: 15
  type: 9
  value: 5
  left: 4
  right: 4
  condition: 4
  location: 4
  operator: 3
  base: 2

Extra Nodes: 1
  Examples: comment

Root Nodes: source_file


Language: swift
============================================================
Total Nodes: 348
  Named: 182 (52.3%)
  Unnamed: 166 (47.7%)

Abstract Types: 0
  Top abstract categories: 

Structural Patterns:
  Nodes with fields: 164 (90.1% of named)
  Nodes with children: 104
  Nodes with both: 104

Common Field Names (top 10):
  name: 37
  op: 10
  value: 9
  lhs: 8
  rhs: 8
  type: 7
  body: 7
  default_value: 6
  element: 5
  target: 5

Extra Nodes: 2
  Examples: comment, multiline_comment

Root Nodes: source_file


Language: tsx
============================================================
Total Nodes: 334
  Named: 191 (57.2%)
  Unnamed: 143 (42.8%)

Abstract Types: 7
  Top abstract categories: declaration, expression, pattern, primary_expression, primary_type, statement, type

Structural Patterns:
  Nodes with fields: 161 (84.3% of named)
  Nodes with children: 90
  Nodes with both: 90

Common Field Names (top 10):
  name: 34
  body: 26
  type_parameters: 18
  value: 14
  parameters: 13
  type: 13
  return_type: 11
  decorator: 8
  left: 7
  right: 7

Extra Nodes: 0
  Examples: 

Root Nodes: program


Language: typescript
============================================================
Total Nodes: 334
  Named: 191 (57.2%)
  Unnamed: 143 (42.8%)

Abstract Types: 7
  Top abstract categories: declaration, expression, pattern, primary_expression, primary_type, statement, type

Structural Patterns:
  Nodes with fields: 161 (84.3% of named)
  Nodes with children: 90
  Nodes with both: 90

Common Field Names (top 10):
  name: 34
  body: 26
  type_parameters: 18
  value: 14
  parameters: 13
  type: 13
  return_type: 11
  decorator: 8
  left: 7
  right: 7

Extra Nodes: 0
  Examples: 

Root Nodes: program


Language: yaml
============================================================
Total Nodes: 5
  Named: 5 (100.0%)
  Unnamed: 0 (0.0%)

Abstract Types: 0
  Top abstract categories: 

Structural Patterns:
  Nodes with fields: 1 (20.0% of named)
  Nodes with children: 1
  Nodes with both: 1

Common Field Names (top 10):
  

Extra Nodes: 0
  Examples: 

Root Nodes: scalar


## Cross-Language Patterns

### Common Abstract Types (appears in multiple languages)
  expression: 18/25 languages (72.0%)
  statement: 14/25 languages (56.0%)
  type: 9/25 languages (36.0%)
  primary_expression: 8/25 languages (32.0%)
  declaration: 8/25 languages (32.0%)
  pattern: 8/25 languages (32.0%)
  literal: 4/25 languages (16.0%)
  abstract_declarator: 2/25 languages (8.0%)
  declarator: 2/25 languages (8.0%)
  field_declarator: 2/25 languages (8.0%)
  type_declarator: 2/25 languages (8.0%)
  type_specifier: 2/25 languages (8.0%)
  simple_statement: 2/25 languages (8.0%)
  simple_type: 2/25 languages (8.0%)
  variable: 2/25 languages (8.0%)
  primary_type: 2/25 languages (8.0%)
  lvalue_expression: 1/25 languages (4.0%)
  non_lvalue_expression: 1/25 languages (4.0%)
  type_declaration: 1/25 languages (4.0%)
  class_decl: 1/25 languages (4.0%)

### Universal Field Names (top 30)
  name: 381 total occurrences
  body: 281 total occurrences
  type: 217 total occurrences
  value: 151 total occurrences
  condition: 102 total occurrences
  operator: 89 total occurrences
  parameters: 87 total occurrences
  right: 86 total occurrences
  left: 84 total occurrences
  type_parameters: 73 total occurrences
  alternative: 45 total occurrences
  pattern: 43 total occurrences
  return_type: 43 total occurrences
  declarator: 38 total occurrences
  argument: 34 total occurrences
  arguments: 34 total occurrences
  consequence: 30 total occurrences
  expression: 27 total occurrences
  type_arguments: 26 total occurrences
  alias: 22 total occurrences
  object: 22 total occurrences
  decorator: 21 total occurrences
  key: 20 total occurrences
  function: 19 total occurrences
  field: 18 total occurrences
  label: 17 total occurrences
  element: 16 total occurrences
  patterns: 16 total occurrences
  attributes: 16 total occurrences
  initializer: 15 total occurrences

### Field Semantic Patterns

Shows which semantic categories commonly use each field name:

  name [201 uses]: type_def(93), callable(54), control_flow(25)
  body [171 uses]: control_flow(75), callable(45), type_def(43)
  type [87 uses]: type_def(69), callable(8), control_flow(6)
  condition [73 uses]: control_flow(73)
  parameters [70 uses]: callable(60), type_def(8), operation(2)
  type_parameters [64 uses]: type_def(32), callable(30), operation(2)
  right [60 uses]: operation(48), control_flow(7), type_def(4)
  left [59 uses]: operation(48), control_flow(6), type_def(4)
  operator [56 uses]: operation(50), control_flow(3), boundary(2)
  value [45 uses]: control_flow(22), type_def(15), operation(3)
  return_type [40 uses]: callable(37), operation(2), type_def(1)
  alternative [31 uses]: control_flow(29), type_def(2)
  arguments [20 uses]: operation(13), callable(5), type_def(2)
  consequence [19 uses]: control_flow(17), type_def(2)
  alias [16 uses]: boundary(9), type_def(4), control_flow(3)
  function [14 uses]: operation(10), callable(4)
  type_arguments [14 uses]: type_def(8), operation(3), callable(3)
  decorator [14 uses]: type_def(10), boundary(3), callable(1)
  declarator [13 uses]: callable(7), type_def(5), control_flow(1)
  argument [13 uses]: operation(13)