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
  primary_expression: 8/25 languages (32.0%)
  statement: 14/25 languages (56.0%)
  abstract_declarator: 2/25 languages (8.0%)
  declarator: 2/25 languages (8.0%)
  field_declarator: 2/25 languages (8.0%)
  type_declarator: 2/25 languages (8.0%)
  type_specifier: 2/25 languages (8.0%)
  declaration: 8/25 languages (32.0%)
  literal: 4/25 languages (16.0%)
  lvalue_expression: 1/25 languages (4.0%)
  non_lvalue_expression: 1/25 languages (4.0%)
  pattern: 8/25 languages (32.0%)
  type: 9/25 languages (36.0%)
  type_declaration: 1/25 languages (4.0%)
  simple_statement: 2/25 languages (8.0%)
  simple_type: 2/25 languages (8.0%)
  class_decl: 1/25 languages (4.0%)
  constraint: 1/25 languages (4.0%)
  constraints: 1/25 languages (4.0%)
  decl: 1/25 languages (4.0%)
  guard: 1/25 languages (4.0%)
  instance_decl: 1/25 languages (4.0%)
  qualifier: 1/25 languages (4.0%)
  quantified_type: 1/25 languages (4.0%)
  type_param: 1/25 languages (4.0%)
  unannotated_type: 1/25 languages (4.0%)
  module_directive: 1/25 languages (4.0%)
  value: 1/25 languages (4.0%)
  class_member_declaration: 1/25 languages (4.0%)
  variable: 2/25 languages (8.0%)
  compound_statement: 1/25 languages (4.0%)
  expression_statement: 1/25 languages (4.0%)
  parameter: 1/25 languages (4.0%)
  arg: 1/25 languages (4.0%)
  call_operator: 1/25 languages (4.0%)
  lhs: 1/25 languages (4.0%)
  method_name: 1/25 languages (4.0%)
  nonlocal_variable: 1/25 languages (4.0%)
  pattern_constant: 1/25 languages (4.0%)
  pattern_expr: 1/25 languages (4.0%)
  pattern_expr_basic: 1/25 languages (4.0%)
  pattern_primitive: 1/25 languages (4.0%)
  pattern_top_expr_body: 1/25 languages (4.0%)
  primary: 1/25 languages (4.0%)
  simple_numeric: 1/25 languages (4.0%)
  declaration_statement: 1/25 languages (4.0%)
  literal_pattern: 1/25 languages (4.0%)
  definition: 1/25 languages (4.0%)
  primary_type: 2/25 languages (8.0%)

### Universal Field Names
  left: 84 total occurrences
  operator: 89 total occurrences
  right: 86 total occurrences
  body: 281 total occurrences
  condition: 102 total occurrences
  initializer: 15 total occurrences
  update: 8 total occurrences
  fallthrough: 1 total occurrences
  termination: 1 total occurrences
  value: 151 total occurrences
  argument: 34 total occurrences
  name: 381 total occurrences
  redirect: 5 total occurrences
  descriptor: 3 total occurrences
  destination: 1 total occurrences
  variable: 4 total occurrences
  index: 8 total occurrences
  alternative: 45 total occurrences
  consequence: 30 total occurrences
  declarator: 38 total occurrences
  size: 4 total occurrences
  parameters: 87 total occurrences
  type: 217 total occurrences
  prefix: 4 total occurrences
  arguments: 34 total occurrences
  function: 19 total occurrences
  underlying_type: 1 total occurrences
  field: 18 total occurrences
  register: 2 total occurrences
  assembly_code: 2 total occurrences
  clobbers: 2 total occurrences
  goto_labels: 2 total occurrences
  input_operands: 2 total occurrences
  output_operands: 2 total occurrences
  label: 17 total occurrences
  constraint: 12 total occurrences
  symbol: 4 total occurrences
  operand: 14 total occurrences
  designator: 2 total occurrences
  member: 3 total occurrences
  directive: 2 total occurrences
  path: 9 total occurrences
  filter: 2 total occurrences
  end: 9 total occurrences
  start: 8 total occurrences
  namespace: 4 total occurrences
  default_value: 14 total occurrences
  base: 4 total occurrences
  header: 1 total occurrences
  partition: 2 total occurrences
  captures: 2 total occurrences
  template_parameters: 1 total occurrences
  length: 4 total occurrences
  placement: 1 total occurrences
  default_type: 2 total occurrences
  pattern: 43 total occurrences
  scope: 5 total occurrences
  delimiter: 1 total occurrences
  requirements: 1 total occurrences
  message: 1 total occurrences
  indices: 1 total occurrences
  alias: 22 total occurrences
  rank: 1 total occurrences
  type_parameters: 73 total occurrences
  expression: 27 total occurrences
  subscript: 2 total occurrences
  accessors: 3 total occurrences
  returns: 2 total occurrences
  content: 4 total occurrences
  qualifier: 2 total occurrences
  key: 20 total occurrences
  target: 7 total occurrences
  quoted_end: 5 total occurrences
  quoted_start: 5 total occurrences
  element: 16 total occurrences
  type_arguments: 26 total occurrences
  communication: 1 total occurrences
  tag: 1 total occurrences
  result: 11 total occurrences
  receiver: 2 total occurrences
  package: 4 total occurrences
  channel: 1 total occurrences
  capacity: 1 total occurrences
  binds: 6 total occurrences
  match: 5 total occurrences
  patterns: 16 total occurrences
  kind: 15 total occurrences
  constructor: 10 total occurrences
  from: 2 total occurrences
  step: 2 total occurrences
  to: 2 total occurrences
  bind: 2 total occurrences
  arrow: 7 total occurrences
  implicit: 2 total occurrences
  alternatives: 4 total occurrences
  context: 8 total occurrences
  declarations: 3 total occurrences
  fundeps: 1 total occurrences
  declaration: 6 total occurrences
  else: 3 total occurrences
  if: 1 total occurrences
  then: 1 total occurrences
  forall: 8 total occurrences
  constructors: 3 total occurrences
  deriving: 2 total occurrences
  signature: 3 total occurrences
  classes: 1 total occurrences
  strategy: 2 total occurrences
  via: 2 total occurrences
  statement: 2 total occurrences
  id: 2 total occurrences
  module: 8 total occurrences
  synonym: 2 total occurrences
  equation: 1 total occurrences
  children: 2 total occurrences
  export: 1 total occurrences
  parameter: 9 total occurrences
  subfield: 1 total occurrences
  associativity: 1 total occurrences
  precedence: 1 total occurrences
  quantifier: 2 total occurrences
  variables: 2 total occurrences
  calling_convention: 2 total occurrences
  entity: 2 total occurrences
  safety: 1 total occurrences
  parens: 2 total occurrences
  determined: 2 total occurrences
  matched: 1 total occurrences
  fundep: 1 total occurrences
  names: 3 total occurrences
  classifier: 1 total occurrences
  guard: 3 total occurrences
  imports: 1 total occurrences
  exports: 1 total occurrences
  import: 1 total occurrences
  left_operand: 2 total occurrences
  right_operand: 2 total occurrences
  multiplicity: 1 total occurrences
  qualifiers: 1 total occurrences
  decl: 1 total occurrences
  guards: 1 total occurrences
  minus: 1 total occurrences
  number: 1 total occurrences
  quoter: 2 total occurrences
  fields: 1 total occurrences
  role: 1 total occurrences
  transformation: 1 total occurrences
  closed_family: 1 total occurrences
  dimensions: 9 total occurrences
  array: 1 total occurrences
  interfaces: 3 total occurrences
  permits: 2 total occurrences
  superclass: 2 total occurrences
  object: 22 total occurrences
  modules: 2 total occurrences
  init: 1 total occurrences
  provided: 1 total occurrences
  provider: 1 total occurrences
  modifiers: 1 total occurrences
  template_argument: 1 total occurrences
  template_processor: 1 total occurrences
  resources: 1 total occurrences
  optional_chain: 7 total occurrences
  decorator: 21 total occurrences
  source: 10 total occurrences
  property: 7 total occurrences
  increment: 3 total occurrences
  close_tag: 3 total occurrences
  open_tag: 3 total occurrences
  attribute: 8 total occurrences
  flags: 3 total occurrences
  finalizer: 3 total occurrences
  handler: 4 total occurrences
  table: 3 total occurrences
  clause: 1 total occurrences
  method: 2 total occurrences
  attr: 2 total occurrences
  attrpath: 3 total occurrences
  binding: 1 total occurrences
  default: 2 total occurrences
  ellipses: 1 total occurrences
  formal: 1 total occurrences
  formals: 1 total occurrences
  universal: 1 total occurrences
  attrs: 2 total occurrences
  environment: 1 total occurrences
  attributes: 16 total occurrences
  reference_modifier: 6 total occurrences
  return_type: 43 total occurrences
  static_modifier: 2 total occurrences
  initialize: 1 total occurrences
  end_tag: 2 total occurrences
  identifier: 2 total occurrences
  conditional_expressions: 1 total occurrences
  return_expression: 2 total occurrences
  final: 1 total occurrences
  readonly: 1 total occurrences
  visibility: 2 total occurrences
  superclasses: 1 total occurrences
  operators: 1 total occurrences
  definition: 2 total occurrences
  code: 1 total occurrences
  format_specifier: 2 total occurrences
  type_conversion: 2 total occurrences
  module_name: 1 total occurrences
  subject: 1 total occurrences
  cause: 1 total occurrences
  class: 3 total occurrences
  locals: 1 total occurrences
  block: 2 total occurrences
  clauses: 1 total occurrences
  begin: 1 total occurrences
  exceptions: 1 total occurrences
  trait: 4 total occurrences
  bounds: 5 total occurrences
  doc: 2 total occurrences
  inner: 2 total occurrences
  outer: 2 total occurrences
  macro: 1 total occurrences
  list: 1 total occurrences
  class_parameters: 4 total occurrences
  derive: 5 total occurrences
  extend: 7 total occurrences
  lambda_start: 1 total occurrences
  extra: 1 total occurrences
  bound: 5 total occurrences
  enumerators: 1 total occurrences
  parameter_types: 1 total occurrences
  interpolator: 1 total occurrences
  selector: 1 total occurrences
  initial: 1 total occurrences
  import_name: 1 total occurrences
  ancestor: 1 total occurrences
  ancestor_arguments: 1 total occurrences
  location: 4 total occurrences
  error: 2 total occurrences
  version_constraint: 1 total occurrences
  attempt: 1 total occurrences
  key_identifier: 1 total occurrences
  key_type: 1 total occurrences
  value_identifier: 1 total occurrences
  value_type: 1 total occurrences
  lhs: 8 total occurrences
  op: 10 total occurrences
  rhs: 8 total occurrences
  expr: 4 total occurrences
  must_inherit: 1 total occurrences
  declaration_kind: 2 total occurrences
  constructed_type: 1 total occurrences
  data_contents: 1 total occurrences
  raw_value: 1 total occurrences
  constrained_type: 2 total occurrences
  must_equal: 1 total occurrences
  collection: 1 total occurrences
  item: 1 total occurrences
  params: 1 total occurrences
  bound_identifier: 5 total occurrences
  inherits_from: 2 total occurrences
  reference_specifier: 2 total occurrences
  external_name: 2 total occurrences
  interpolation: 4 total occurrences
  text: 3 total occurrences
  suffix: 2 total occurrences
  if_nil: 1 total occurrences
  wrapped: 1 total occurrences
  operation: 2 total occurrences
  computed_value: 1 total occurrences
  suppressed: 1 total occurrences
  if_false: 1 total occurrences
  if_true: 1 total occurrences
  mutability: 1 total occurrences
  index_type: 2 total occurrences
  sign: 2 total occurrences

### Field Semantic Patterns

Shows which semantic categories commonly use each field name:

  name [201 uses]: callable(54), operation(7), control_flow(25), type_def(93), boundary(22)
  body [171 uses]: control_flow(75), callable(45), type_def(43), boundary(8)
  type [87 uses]: callable(8), type_def(69), control_flow(6), boundary(3), operation(1)
  condition [73 uses]: control_flow(73)
  parameters [70 uses]: callable(60), type_def(8), operation(2)
  type_parameters [64 uses]: type_def(32), callable(30), operation(2)
  right [60 uses]: operation(48), control_flow(7), callable(1), type_def(4)
  left [59 uses]: operation(48), callable(1), control_flow(6), type_def(4)
  operator [56 uses]: operation(50), boundary(2), control_flow(3), type_def(1)
  value [45 uses]: control_flow(22), operation(3), callable(2), type_def(15), boundary(3)
  return_type [40 uses]: callable(37), type_def(1), operation(2)
  alternative [31 uses]: control_flow(29), type_def(2)
  arguments [20 uses]: operation(13), callable(5), type_def(2)
  consequence [19 uses]: control_flow(17), type_def(2)
  alias [16 uses]: control_flow(3), type_def(4), boundary(9)
  function [14 uses]: operation(10), callable(4)
  type_arguments [14 uses]: operation(3), type_def(8), callable(3)
  decorator [14 uses]: type_def(10), boundary(3), callable(1)
  declarator [13 uses]: callable(7), type_def(5), control_flow(1)
  argument [13 uses]: operation(13)
  initializer [12 uses]: control_flow(11), type_def(1)
  result [9 uses]: callable(6), type_def(2), operation(1)
  patterns [9 uses]: type_def(6), callable(3)
  source [9 uses]: boundary(9)
  update [8 uses]: control_flow(8)
  element [8 uses]: type_def(8)
  attributes [8 uses]: type_def(4), callable(4)
  operand [7 uses]: operation(5), type_def(2)
  pattern [7 uses]: type_def(3), control_flow(4)
  module [7 uses]: boundary(4), control_flow(1), type_def(2)
  object [7 uses]: type_def(1), callable(2), operation(2), control_flow(2)
  kind [6 uses]: type_def(3), control_flow(3)
  dimensions [6 uses]: type_def(2), control_flow(3), callable(1)
  constraint [5 uses]: callable(1), type_def(3), control_flow(1)
  path [5 uses]: boundary(3), control_flow(1), type_def(1)
  context [5 uses]: type_def(5)
  constructor [5 uses]: type_def(5)
  forall [5 uses]: type_def(5)
  parameter [5 uses]: callable(5)
  bound [5 uses]: type_def(4), callable(1)
  key [4 uses]: operation(1), type_def(2), control_flow(1)
  package [4 uses]: type_def(1), boundary(3)
  declaration [4 uses]: type_def(1), boundary(3)
  bounds [4 uses]: type_def(3), control_flow(1)
  default_value [4 uses]: type_def(2), callable(2)
  variable [3 uses]: control_flow(1), boundary(2)
  scope [3 uses]: control_flow(2), operation(1)
  target [3 uses]: operation(3)
  namespace [3 uses]: type_def(1), boundary(2)
  match [3 uses]: type_def(1), callable(1), control_flow(1)
  expression [3 uses]: callable(1), control_flow(2)
  increment [3 uses]: control_flow(3)
  trait [3 uses]: type_def(2), callable(1)
  derive [3 uses]: type_def(2), boundary(1)
  extend [3 uses]: type_def(2), boundary(1)
  bound_identifier [3 uses]: control_flow(3)
  directive [2 uses]: operation(2)
  base [2 uses]: control_flow(1), type_def(1)
  partition [2 uses]: boundary(2)
  captures [2 uses]: callable(2)
  default_type [2 uses]: type_def(2)
  returns [2 uses]: callable(2)
  qualifier [2 uses]: control_flow(2)
  length [2 uses]: type_def(2)
  receiver [2 uses]: callable(1), operation(1)
  binds [2 uses]: type_def(1), callable(1)
  constructors [2 uses]: type_def(2)
  deriving [2 uses]: type_def(2)
  id [2 uses]: boundary(1), control_flow(1)
  children [2 uses]: boundary(2)
  quantifier [2 uses]: control_flow(2)
  variables [2 uses]: control_flow(2)
  calling_convention [2 uses]: boundary(2)
  entity [2 uses]: boundary(2)
  signature [2 uses]: boundary(2)
  arrow [2 uses]: callable(2)
  parens [2 uses]: callable(2)
  names [2 uses]: type_def(1), boundary(1)
  alternatives [2 uses]: callable(2)
  permits [2 uses]: type_def(2)
  superclass [2 uses]: type_def(2)
  modules [2 uses]: boundary(2)
  method [2 uses]: callable(1), operation(1)
  reference_modifier [2 uses]: callable(2)
  static_modifier [2 uses]: callable(2)
  return_expression [2 uses]: control_flow(2)
  else [2 uses]: control_flow(2)
  class_parameters [2 uses]: type_def(2)
  property [2 uses]: control_flow(2)
  redirect [1 uses]: callable(1)
  underlying_type [1 uses]: control_flow(1)
  header [1 uses]: boundary(1)
  template_parameters [1 uses]: callable(1)
  rank [1 uses]: type_def(1)
  declarations [1 uses]: type_def(1)
  fundeps [1 uses]: type_def(1)
  implicit [1 uses]: type_def(1)
  export [1 uses]: boundary(1)
  safety [1 uses]: boundary(1)
  import [1 uses]: boundary(1)
  multiplicity [1 uses]: callable(1)
  guards [1 uses]: control_flow(1)
  field [1 uses]: type_def(1)
  transformation [1 uses]: control_flow(1)
  closed_family [1 uses]: type_def(1)
  determined [1 uses]: type_def(1)
  interfaces [1 uses]: type_def(1)
  init [1 uses]: control_flow(1)
  provided [1 uses]: boundary(1)
  provider [1 uses]: boundary(1)
  modifiers [1 uses]: boundary(1)
  optional_chain [1 uses]: operation(1)
  member [1 uses]: type_def(1)
  end [1 uses]: control_flow(1)
  start [1 uses]: control_flow(1)
  step [1 uses]: control_flow(1)
  clause [1 uses]: control_flow(1)
  table [1 uses]: callable(1)
  default [1 uses]: control_flow(1)
  ellipses [1 uses]: control_flow(1)
  formal [1 uses]: control_flow(1)
  formals [1 uses]: callable(1)
  universal [1 uses]: callable(1)
  initialize [1 uses]: control_flow(1)
  conditional_expressions [1 uses]: control_flow(1)
  prefix [1 uses]: control_flow(1)
  superclasses [1 uses]: type_def(1)
  format_specifier [1 uses]: control_flow(1)
  type_conversion [1 uses]: control_flow(1)
  module_name [1 uses]: boundary(1)
  subject [1 uses]: control_flow(1)
  block [1 uses]: operation(1)
  clauses [1 uses]: control_flow(1)
  handler [1 uses]: control_flow(1)
  extra [1 uses]: type_def(1)
  enumerators [1 uses]: control_flow(1)
  parameter_types [1 uses]: callable(1)
  selector [1 uses]: type_def(1)
  initial [1 uses]: control_flow(1)
  import_name [1 uses]: boundary(1)
  ancestor [1 uses]: control_flow(1)
  ancestor_arguments [1 uses]: control_flow(1)
  key_identifier [1 uses]: type_def(1)
  key_type [1 uses]: type_def(1)
  value_identifier [1 uses]: type_def(1)
  value_type [1 uses]: type_def(1)
  must_inherit [1 uses]: type_def(1)
  declaration_kind [1 uses]: type_def(1)
  constructed_type [1 uses]: type_def(1)
  collection [1 uses]: control_flow(1)
  item [1 uses]: control_flow(1)
  params [1 uses]: callable(1)
  inherits_from [1 uses]: control_flow(1)
  external_name [1 uses]: callable(1)
  wrapped [1 uses]: type_def(1)
  expr [1 uses]: control_flow(1)

## Q1: Category vs Concrete References in Connections

Analysis of whether connections (fields/children) reference Categories (abstract types)
or only concrete Things.

### Direct Connections (fields)
  Category references: 761
  Concrete references: 8845
  Percentage Category: 7.9%

Examples of Category references in fields:
  - bash: binary_expression → _expression (Category)
  - bash: case_item → _primary_expression (Category)
  - bash: case_statement → _primary_expression (Category)
  - c: abstract_array_declarator → _abstract_declarator (Category)
  - c: abstract_array_declarator → expression (Category)
  - c: abstract_function_declarator → _abstract_declarator (Category)
  - cpp: abstract_array_declarator → _abstract_declarator (Category)
  - cpp: abstract_array_declarator → expression (Category)
  - cpp: abstract_function_declarator → _abstract_declarator (Category)
  - csharp: and_pattern → pattern (Category)

Examples of Concrete references in fields:
  - bash: binary_expression → << (Concrete)
  - bash: binary_expression → ^= (Concrete)
  - bash: binary_expression → <<= (Concrete)
  - c: abstract_array_declarator → * (Concrete)
  - c: abstract_function_declarator → parameter_list (Concrete)
  - c: alignof_expression → type_descriptor (Concrete)
  - cpp: abstract_array_declarator → * (Concrete)
  - cpp: abstract_function_declarator → parameter_list (Concrete)
  - cpp: alias_declaration → type_identifier (Concrete)
  - csharp: accessor_declaration → get (Concrete)

### Positional Connections (children)
  Category references: 621
  Concrete references: 5408
  Percentage Category: 10.3%

Examples of Category references in children:
  - bash: array → _primary_expression (Category)
  - bash: case_item → _statement (Category)
  - bash: command_name → _primary_expression (Category)
  - c: abstract_parenthesized_declarator → _abstract_declarator (Category)
  - c: alignas_qualifier → expression (Category)
  - c: argument_list → expression (Category)
  - cpp: abstract_parenthesized_declarator → _abstract_declarator (Category)
  - cpp: abstract_reference_declarator → _abstract_declarator (Category)
  - cpp: alignas_qualifier → expression (Category)
  - csharp: anonymous_object_creation_expression → expression (Category)

Examples of Concrete references in children:
  - bash: arithmetic_expansion → simple_expansion (Concrete)
  - bash: arithmetic_expansion → command_substitution (Concrete)
  - bash: arithmetic_expansion → string (Concrete)
  - c: abstract_array_declarator → type_qualifier (Concrete)
  - c: abstract_parenthesized_declarator → ms_call_modifier (Concrete)
  - c: abstract_pointer_declarator → type_qualifier (Concrete)
  - cpp: abstract_array_declarator → type_qualifier (Concrete)
  - cpp: abstract_function_declarator → trailing_return_type (Concrete)
  - cpp: abstract_function_declarator → virtual_specifier (Concrete)
  - csharp: accessor_declaration → attribute_list (Concrete)

## Q2: Things with Multiple Category Membership

Analysis of whether concrete Things can belong to multiple Categories
(i.e., appear in multiple abstract types' subtypes lists).

Total Things with category membership: 736
Things belonging to multiple Categories: 99
Percentage multi-category: 13.5%
Maximum categories per Thing: 5

Distribution of category membership:
  1 category/categories: 637 Things
  2 category/categories: 68 Things
  3 category/categories: 18 Things
  4 category/categories: 12 Things
  5 category/categories: 1 Things

Examples of Things with multiple Category membership:
  - bash: word → [_expression, _primary_expression]
  - c: array_declarator → [_declarator, _field_declarator, _type_declarator]
  - c: attributed_declarator → [_declarator, _field_declarator, _type_declarator]
  - c: function_declarator → [_declarator, _field_declarator, _type_declarator]
  - c: identifier → [_declarator, expression]
  - c: parenthesized_declarator → [_declarator, _field_declarator, _type_declarator]
  - c: pointer_declarator → [_declarator, _field_declarator, _type_declarator]
  - c: primitive_type → [_type_declarator, type_specifier]
  - c: type_identifier → [_type_declarator, type_specifier]
  - cpp: array_declarator → [_declarator, _field_declarator, _type_declarator]
  - cpp: attributed_declarator → [_declarator, _field_declarator, _type_declarator]
  - cpp: function_declarator → [_declarator, _field_declarator, _type_declarator]
  - cpp: identifier → [_declarator, expression]
  - cpp: operator_name → [_declarator, _field_declarator]
  - cpp: parenthesized_declarator → [_declarator, _field_declarator, _type_declarator]
  - cpp: pointer_declarator → [_declarator, _field_declarator, _type_declarator]
  - cpp: qualified_identifier → [_declarator, expression, type_specifier]
  - cpp: reference_declarator → [_declarator, _field_declarator, _type_declarator]
  - cpp: template_function → [_declarator, expression]
  - cpp: primitive_type → [_type_declarator, type_specifier]

## Conclusions

### Q1: Category References
**Answer: YES** - Connections CAN reference Categories (abstract types).
- Fields reference Categories in 761 cases
- Children reference Categories in 621 cases
- This is a common pattern used for polymorphic type constraints

### Q2: Multiple Category Membership
**Answer: YES** - Things CAN belong to multiple Categories, but it's uncommon.
- Only 13.5% of Things belong to multiple Categories
- Maximum observed: 5 categories for a single Thing
- This typically occurs for nodes that serve multiple grammatical roles