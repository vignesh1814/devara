# Devara Stage 2 Design Specification
## Syntax Analysis / Parsing

**Document status:** Design baseline  
**Version:** 1.0  
**Language:** Devara  
**Formal grammar notation:** ISO/IEC 14977 EBNF  
**Compiler stage:** Stage 2 — Syntax Analysis / Parsing  
**Input:** Stage 1 Token Stream  
**Output:** Stage 2 Abstract Syntax Tree (AST)

---

## 1. Purpose

This document is the authoritative design specification for Stage 2 of the Devara compiler.

Stage 2 is responsible for:

1. recognizing Devara syntax from the Stage 1 token stream;
2. enforcing the Devara grammar;
3. constructing the Devara Abstract Syntax Tree (AST);
4. preserving source spans on AST nodes;
5. producing structured syntax diagnostics;
6. performing controlled syntax-error recovery where appropriate; and
7. providing a clean AST contract for the next compiler stage.

Stage 2 does **not** perform semantic analysis, intermediate-code generation, optimization, or target-code generation.

This document may provide compiler-design material for incorporation into the canonical `DEVARA_LANGUAGE_SPEC.md` where appropriate. The canonical language specification remains authoritative.

---

# 2. Compiler Pipeline Context

The compiler pipeline is:

```text
Devara Source
    |
    v
Stage 1: Lexical Analysis
    |
    | Token Stream
    v
Stage 2: Syntax Analysis / Parsing
    |
    | AST
    v
Stage 3 (R22 grouping): Semantics + Syntax-Directed Translation / Intermediate Code
    |
    | Intermediate Code
    v
Stage 4: Code Optimization
    |
    | Optimized Intermediate Code
    v
Stage 5: Code Generation
    |
    | x86-64 Assembly
    v
Assembler + Linker
    |
    v
Executable
```

---

# 3. Stage 2 Contract

## 3.1 Input Contract

Stage 2 consumes only the token stream produced by Stage 1.

It must not rescan source characters or duplicate lexical analysis.

Each token is assumed to provide the lexical information and source location required by the parser.

Conceptually:

```text
Token
├── kind
├── lexeme / lexical data
└── source location
```

The exact Token representation remains governed by the Stage 1 location contract.

## 3.2 Output Contract

For syntactically valid input:

```text
Token Stream
    |
    v
Parser
    |
    v
AST
```

For syntactically invalid input:

```text
Token Stream
    |
    v
Parser
    |
    +--> structured syntax diagnostics
    |
    v
parse failure
```

A parse containing syntax errors must not be reported as successfully parsed.

---

# 4. Formal Grammar Standard

The Devara grammar is specified using **EBNF notation adapted from ISO/IEC 14977:1996**.

ISO/IEC 14977 defines the metalanguage used to express the grammar. It does not define the Devara language itself and does not prescribe the parser implementation. This wording intentionally matches the canonical language specification.

Therefore:

```text
ISO/IEC 14977
      |
      v
EBNF notation
      |
      v
Devara grammar
      |
      v
Recursive-descent parser
```

The grammar reproduced here is the Stage 2 implementation mapping of the canonical syntactic description of Devara.

The implementation must be checked against the grammar rather than silently changing the grammar to match implementation behavior.

## 4.1 EBNF Conventions

The grammar uses the following EBNF conventions, adapted from ISO/IEC 14977:1996:

```ebnf
definition = ... ;
```

Concatenation:

```ebnf
A = B, C ;
```

Alternative:

```ebnf
A = B | C ;
```

Optional:

```ebnf
A = [ B ] ;
```

Repetition:

```ebnf
A = { B } ;
```

Grouping:

```ebnf
A = ( B | C ), D ;
```

Terminal strings:

```ebnf
"pettu"
"chupi"
"ayite"
```

The grammar must not mix incompatible EBNF dialects without an explicit notation rule.

---

# 5. Parser Strategy

Stage 2 uses a **hand-written recursive-descent parser**.

The parser is grammar-directed: parser functions correspond to grammar constructs and consume tokens while constructing AST nodes.

Conceptually:

```text
parseProgram()
parseDeclaration()
parseStatement()
parseExpression()
parsePrimaryExpression()
parseIfStatement()
parseWhileStatement()
parseRangeForStatement()
parseForStatement()
parseFunctionDeclaration()
...
```

Recursive descent is an implementation choice. ISO/IEC 14977 does not require recursive descent.

## 5.1 Parser Requirements

The parser shall:

- consume the Stage 1 token stream;
- recognize only syntax defined by the canonical grammar;
- respect expression precedence;
- construct AST nodes directly;
- attach source spans;
- produce structured syntax diagnostics;
- recover only at controlled synchronization points;
- reject the parse if any syntax errors were recorded.

The parser shall not:

- perform symbol resolution;
- perform type checking;
- generate IR;
- perform optimization;
- generate assembly.

---

# 6. AST Design

The AST is a **syntax-oriented representation**.

Every AST node contains:

```text
AST Node
├── syntactic information
├── child nodes
└── source span
```

The AST must not embed semantic information that belongs to later stages.

## 6.1 AST Invariants

Every successfully constructed AST node must:

1. represent a construct permitted by the grammar;
2. contain all syntactically relevant child nodes;
3. carry a valid source span;
4. contain no unresolved semantic assumptions;
5. be independent of parser-internal state after parsing completes.

---

# 7. Frozen AST Design Decisions

The following decisions are part of the Stage 2 contract.

| Decision | Design |
|---|---|
| D1 | Literals retain raw lexical spelling |
| D2 | Literal kind is explicit |
| D3 | Array dimensions use `Expression \| None` |
| D4 | AST nodes carry full source spans |
| D5 | Semantic types are not stored in syntax AST |
| D6 | Identifiers store only their names |
| D7 | `break` / `continue` context is checked later |
| D8 | Structured diagnostics + controlled recovery |
| D9 | Parentheses establish structure but are not unnecessarily retained |
| D10 | Parser directly constructs AST; no persistent parse tree |

These decisions are frozen for the Stage 2 implementation unless the language specification is deliberately revised.

---

# 8. Source Spans

Every AST node carries a complete source span:

```text
Span
├── start
└── end
```

A node representing a syntactic construct should cover the complete source region corresponding to that construct.

For a construct spanning:

```text
start-token ... end-token
```

the node span is conceptually:

```text
[start-token.start, end-token.end]
```

Source spans exist to support:

- syntax diagnostics;
- later semantic diagnostics;
- tooling;
- source mapping;
- debugging and inspection.

The exact source-location type is inherited from the Stage 1 location contract.

---

# 9. Literal Representation

The syntax AST represents literals as:

```text
Literal
├── kind
└── lexeme
```

The lexeme is the raw lexical spelling supplied by the token.

Examples:

```text
42
3.14
nijam
abaddham
'a'
"hello"
```

The parser does not prematurely convert these into machine-level or semantic representations.

Literal interpretation required for semantic processing belongs to later stages.

The explicit literal kind prevents later stages from having to infer the category from the spelling.

---

# 10. Identifier Representation

Identifiers store only their source-level name:

```text
Identifier
└── name
```

The AST must not contain:

- symbol-table entries;
- declaration references;
- scope identifiers;
- memory locations;
- stack offsets;
- registers.

Those belong to semantic analysis and later compiler stages.

---

# 11. Array Dimension Representation

Array dimensions are represented as:

```text
list[Expression | None]
```

Meaning:

- `Expression` — an explicit dimension expression exists;
- `None` — an unsized array parameter dimension.

The `None` representation is scoped to function-parameter syntax, where the
canonical grammar uses `array-parameter = "[", "]" ;`. Ordinary array
declarations use `array-dimension = "[", expression, "]" ;` and therefore
do not permit an unsized dimension.

Example conceptually:

```text
dimensions = [Expression(10)]
```

or:

```text
dimensions = [None]
```

This is a syntax representation, not a semantic array type.

Multidimensional arrays may contain multiple sized dimensions in declarations:

```text
dimensions = [Expression(10), Expression(20)]
```

The semantic validity of those dimensions is handled later. The current
function-parameter syntax does not permit multidimensional array parameters.

---

# 12. Parentheses

Parentheses are syntactically significant because they establish grouping.

For example:

```text
(a + b) * c
```

must produce a structure corresponding to:

```text
(a + b) * c
```

rather than:

```text
a + (b * c)
```

However, parentheses do not require a persistent AST wrapper merely to record that they existed.

The AST retains the structural effect of the grouping.

---

# 13. Direct AST Construction

Stage 2 does not retain a persistent full parse tree.

The parser directly constructs AST nodes while recognizing grammar productions.

```text
Token Stream
     |
     v
Recursive-Descent Parser
     |
     v
AST
```

This avoids an unnecessary persistent representation between the parser and AST.

The parser may use internal call frames and temporary structures during parsing; these are implementation details and are not part of the Stage 2 output contract.

---

# 14. Canonical Grammar Mapping

The following grammar establishes the intended syntactic structure and follows the canonical grammar terminology. Terminal names corresponding to lexer token categories must be mapped to the actual Stage 1 token definitions.

## 14.1 Program

```ebnf
program =
    { top-level-item } ;

top-level-item =
    declaration
  | function-declaration
  | statement ;
```

The exact declaration/statement alternatives must remain consistent with the canonical language specification.

---

# 15. Blocks

```ebnf
block =
    "{", { statement }, "}" ;

statement =
    declaration-statement
  | assignment-statement
  | input-statement
  | output-statement
  | if-statement
  | while-statement
  | range-loop-statement
  | for-loop-statement
  | break-statement
  | continue-statement
  | return-statement
  | expression-statement ;
```

The contents permitted inside a block are exactly those defined by the canonical Devara specification.

The parser must not broaden the language merely because a construct is convenient to support.

---

# 16. Assignment

The canonical assignment form is:

```text
target lo value pettu
```

Grammar:

```ebnf
declaration-statement =
    declaration ;

declaration =
    type, identifier, { array-dimension } ;

array-dimension =
    "[", expression, "]" ;

assignment-statement =
    assignment-target,
    "lo",
    expression,
    "pettu" ;
```

Assignment target:

```ebnf
assignment-target =
      identifier
    | array-access ;
```

---

# 17. Input

Canonical input syntax:

```text
n ni chaduvu
```

Grammar:

```ebnf
input-statement =
    input-target, "ni", "chaduvu" ;

input-target =
    identifier
  | array-access ;
```

The semantic validity of the input target is checked later.

---

# 18. Output

Canonical output syntax:

```text
expression ni chupi
```

Grammar:

```ebnf
output-statement =
    expression,
    "ni",
    "chupi" ;
```

Because the first component is an expression, both simple and compound expressions are syntactically valid:

```text
n ni chupi
```

```text
n + 1 ni chupi
```

---

# 19. Conditional Statement

Canonical form:

```text
condition ayite {
    ...
}
```

Optional alternative:

```text
condition ayite {
    ...
} lekunte {
    ...
}
```

Grammar:

```ebnf
if-statement =
    expression, "ayite", block,
    [ "lekunte", ( block | if-statement ) ] ;
```

The condition is syntactically an expression.

Whether that expression is semantically suitable as a condition belongs to later stages.

---

# 20. While Statement

Canonical form:

```text
condition unnanta varaku {
    ...
}
```

Grammar:

```ebnf
while-statement =
    expression,
    "unnanta",
    "varaku",
    block ;
```

The parser recognizes the complete phrase as the while construct.

---

# 21. Range Loop

Canonical form:

```text
prati i 1 nundi n varaku {
    ...
}
```

Grammar:

```ebnf
range-loop-statement =
    "prati",
    identifier,
    expression,
    "nundi",
    expression,
    "varaku",
    block ;
```

The parser establishes the syntactic relationship among:

- loop variable;
- starting expression;
- ending expression;
- loop body.

Semantic interpretation of the range is not performed here.

---

# 22. `pratisari` Loop

Canonical form:

```text
pratisari (init; condition; update) {
    ...
}
```

Grammar:

```ebnf
for-loop-statement =
    "pratisari",
    "(",
    for-init,
    ";",
    expression,
    ";",
    for-update,
    ")",
    block ;
```

The condition is an ordinary expression.

It must **not** use the `unnanta varaku` phrase.

This distinction is part of the language contract.

---

# 23. `pratisari` Initialization

The initialization component is represented according to the supported assignment/declaration forms.

The canonical `for-init` has exactly three alternatives:

```ebnf
for-init =
    for-tho-modhalu-init
  | for-assignment-init
  | for-declaration-init ;

for-tho-modhalu-init =
    identifier, expression, "tho", "modhalu" ;

for-assignment-init =
    identifier, "lo", expression, "pettu" ;

for-declaration-init =
    type, identifier, [ assignment-initializer ] ;

assignment-initializer =
    "lo", expression, "pettu" ;
```

There is no empty `for-init` alternative in the current language grammar.
The `tho modhalu` form is specifically a `pratisari` initialization form;
it is not a general standalone statement. The loop semicolon separators are
outside these productions, so these productions represent the initialization
clause itself rather than a complete statement.

The `for-tho-modhalu-init` form is intended as an initialization of an
already-declared identifier; it does not introduce a declaration. This is a
semantic/design rule and is not encoded by the grammar production itself.

---

# 24. `pratisari` Update

The update component supports the forms defined by the canonical specification.

```ebnf
for-update =
      assignment-update
    | increment-update
    | decrement-update ;
```

Increment:

```ebnf
increment-update =
      "++", assignment-target
    | assignment-target, "++" ;
```

Decrement:

```ebnf
decrement-update =
      "--", assignment-target
    | assignment-target, "--" ;
```

The existence of these productions inside `for-update` does not make standalone increment/decrement statements generally valid.

---

# 25. Control Statements

Break:

```ebnf
break-statement =
    "aapu" ;
```

Continue:

```ebnf
continue-statement =
    "saagu" ;
```

Return:

```ebnf
return-statement =
    expression, "ivvu" ;
```

A bare `ivvu` is not part of the current language grammar.

Expression statements are currently limited to standalone function calls:

```ebnf
expression-statement =
    function-call ;
```

The parser recognizes these syntactically.

The parser does not determine whether a `break` or `continue` occurs inside an enclosing loop.

That is a semantic/contextual check.

---

# 26. Function Declarations

Functions use the `charya` construct.

The function declaration production must be defined in the canonical language grammar with its complete parameter, return, and body syntax.

The canonical function declaration syntax is:

```ebnf
function-declaration =
    type, identifier, "charya",
    "(", [ parameter-list ], ")", block ;

parameter-list =
    parameter, { ",", parameter } ;

parameter =
    type, identifier, [ array-parameter ] ;

array-parameter =
    "[", "]" ;
```

The current language specification permits only one unsized array dimension
in a function parameter. Multidimensional array parameters such as
`int matrix[][20]` are not currently part of the specified function-parameter
syntax. The parser is responsible for recognizing the syntax only.

The following are later semantic checks:

- function uniqueness;
- parameter compatibility;
- return-type compatibility;
- call compatibility;
- declaration/use relationships.

---

# 27. Types

The syntactic type names are:

```ebnf
type =
    "int"
  | "float"
  | "bool"
  | "char"
  | "padham"
  | "void" ;
```

Type compatibility and whether a particular use of a type is semantically
valid are handled by later semantic analysis.

---

# 28. Expressions

Expression precedence is defined by the following grammar hierarchy:

```ebnf
expression =
    logical-or-expression ;

logical-or-expression =
    logical-and-expression,
    { "||", logical-and-expression } ;

logical-and-expression =
    equality-expression,
    { "&&", equality-expression } ;

equality-expression =
    relational-expression,
    { equality-operator, relational-expression } ;

relational-expression =
    additive-expression,
    { relational-operator, additive-expression } ;

additive-expression =
    multiplicative-expression,
    { additive-operator, multiplicative-expression } ;

multiplicative-expression =
    unary-expression,
    { multiplicative-operator, unary-expression } ;

unary-expression =
    cast-expression
  | unary-operator, unary-expression
  | primary-expression ;

cast-expression =
    "(", type, ")", unary-expression ;

primary-expression =
      literal
    | identifier
    | grouped-expression
    | array-access
    | function-call ;

grouped-expression =
    "(", expression, ")" ;
```

This grammar establishes the required precedence hierarchy:

```text
logical OR
    ↓
logical AND
    ↓
equality
    ↓
relational
    ↓
additive
    ↓
multiplicative
    ↓
unary
    ↓
primary
```

---

# 29. Operators

The operator productions must correspond exactly to the Stage 1 token definitions and canonical language specification.

Representative grammar:

```ebnf
equality-operator =
      "=="
    | "!=" ;

relational-operator =
      "<"
    | "<="
    | ">"
    | ">=" ;

additive-operator =
      "+"
    | "-" ;

multiplicative-operator =
      "*"
    | "/"
    | "%" ;

unary-operator =
      "+"
    | "-"
    | "!" ;
```

Logical operators:

```ebnf
logical-or-operator =
    "||" ;

logical-and-operator =
    "&&" ;
```

Where named operator non-terminals are used, the implementation should use the actual token kinds rather than reparsing operator text.

---

# 30. Function Calls

Function calls are expressions.

```ebnf
function-call =
    identifier,
    "(",
    [ argument-list ],
    ")" ;

argument-list =
    expression,
    { ",", expression } ;
```

Therefore a call may occur wherever an expression is permitted.

Example:

```text
x lo foo(a + b) pettu
```

is syntactically an assignment whose value is a function-call expression.

Semantic validation of the call is later.

---

# 31. Array Access

Array access requires at least one index:

```ebnf
array-access =
    identifier,
    "[",
    expression,
    "]",
    { "[", expression, "]" } ;
```

Therefore:

```text
a[i]
```

and:

```text
matrix[i][j]
```

are supported.

An empty access:

```text
a[]
```

is not syntactically valid.

The parser does not determine whether the identifier actually denotes an array or whether the number of indices is semantically valid.

---

# 32. Literals

The Stage 2 parser shall recognize the literal token categories produced by Stage 1.

Conceptually:

```ebnf
literal =
      integer-literal
    | floating-literal
    | boolean-literal
    | character-literal
    | string-literal ;
```

The lexical grammar and tokenization of these forms remain the responsibility of Stage 1.

The parser constructs the literal AST node using:

```text
kind
lexeme
```

without unnecessarily converting the spelling into a semantic value.

---

# 33. Identifiers

Identifiers are tokenized by Stage 1 and consumed by the parser as identifier tokens.

Conceptually:

```ebnf
identifier =
    identifier-token ;
```

The AST stores only the identifier's source-level name.

---

# 34. AST Node Categories

The implementation should provide AST nodes corresponding to the language's syntactic categories.

At minimum, the design must account for:

### Program / declarations

- Program
- declaration nodes
- function declaration
- parameter representation

### Statements

- assignment
- input
- output
- if
- while
- range-for
- `pratisari`
- break
- continue
- return, according to the canonical return syntax

### Expressions

- literal
- identifier
- array access
- function call
- cast expression
- unary expression
- binary expression

### Supporting structures

- blocks
- array dimensions
- function parameters
- source spans

The exact class names are implementation details unless explicitly made part of the language/tooling API.

---

# 35. Semantic Information Excluded from AST

The following must not be stored as syntax AST state merely for convenience:

```text
resolved type
symbol-table entry
scope
declaration binding
memory address
stack offset
register
IR temporary
machine instruction
```

The syntax AST represents syntax.

Later compiler stages may construct enriched semantic representations without changing this fundamental contract.

---

# 36. Error Diagnostics

The parser uses structured diagnostics.

Conceptually:

```text
ParserDiagnostic
├── category
├── message
└── source span
```

The category should distinguish the nature of the syntax failure where practical.

Examples:

```text
unexpected-token
expected-token
invalid-expression
invalid-statement
missing-delimiter
invalid-declaration
```

The final category vocabulary should be kept small and useful rather than creating a category for every possible parser branch.

---

# 37. Diagnostic Requirements

Every syntax diagnostic should provide enough information to answer:

1. What went wrong?
2. Where did it happen?
3. What syntax was expected, where useful?

For example:

```text
Syntax error: expected 'pettu' after assignment
at line 4, column 12
```

The exact wording may evolve during implementation, but diagnostics must remain structured and source-located.

---

# 38. Error Recovery

The parser uses controlled synchronization recovery.

Recovery is intended to allow multiple independent syntax errors to be reported without making the parser excessively complex.

Potential synchronization points include:

```text
";"
"}"
EOF
```

and appropriate declaration/statement boundaries.

The parser must avoid aggressive speculative repair.

The intended behavior is:

```text
syntax error
     |
     v
record diagnostic
     |
     v
advance to safe synchronization point
     |
     v
continue parsing where safe
```

At the end:

```text
if diagnostics exist:
    parse failure
else:
    parse success + AST
```

Recovery does not imply that the recovered AST is valid.

---

# 39. Parser Invariants

The parser must maintain the following invariants.

## 38.1 Token Consumption

The parser consumes tokens in source order.

It must not silently skip tokens that belong to an unrecognized construct.

## 38.2 Grammar Conformance

Every successfully constructed AST construct must correspond to a valid grammar production.

## 38.3 Complete Consumption

A successful parse of a program must consume the complete token stream through `EOF`.

Trailing unrecognized tokens constitute a syntax error.

## 38.4 Source Span Validity

Every AST node must have a valid source span corresponding to the tokens that formed it.

## 38.5 No Semantic Resolution

Parser success must never imply semantic validity.

---

# 40. Parser / AST Traceability

Every major grammar construct should have an explicit implementation mapping.

| Grammar construct | Parser function | AST result |
|---|---|---|
| `program` | `parse_program()` | `Program` |
| `block` | `parse_block()` | `Block` |
| assignment | `parse_assignment()` | `Assignment` |
| `if-statement` | `parse_if()` | `If` |
| `while-statement` | `parse_while()` | `While` |
| range loop | `parse_range_for()` | `RangeFor` |
| `for-loop-statement` | `parse_for()` | `For` |
| function declaration | `parse_function()` | `FunctionDeclaration` |
| expression | `parse_expression()` | expression tree |
| function call | `parse_call()` | `Call` |
| array access | `parse_array_access()` | `ArrayAccess` |
| literal | `parse_literal()` | `Literal` |

Actual implementation names may differ, but the mapping must remain traceable.

---

# 41. Grammar-to-Implementation Rule

The formal grammar is the reference against which the parser is implemented.

The implementation process is:

```text
Language specification
       |
       v
ISO/IEC 14977 EBNF grammar
       |
       v
Parser design
       |
       v
AST construction
       |
       v
Implementation
       |
       v
Exhaustive tests
```

Not:

```text
Existing parser
       |
       v
Infer whatever grammar it currently accepts
       |
       v
Declare that to be the language
```

If implementation and specification disagree, the discrepancy must be explicitly identified and resolved.

---

# 42. Testing Design

After implementation is aligned with this design, Stage 2 must undergo an exhaustive parser test pass.

Testing is a separate activity from this design document.

The test plan must cover:

## 41.1 Positive Grammar Coverage

Every production should have at least one valid test.

## 41.2 Boundary Variations

Test:

- minimum valid forms;
- nested forms;
- combinations of constructs;
- empty/optional components where permitted;
- deeply nested expressions;
- multidimensional arrays;
- nested blocks;
- nested control flow;
- function calls inside expressions;
- expressions inside loop components.

## 41.3 Expression Coverage

Every operator category and every precedence boundary must be tested.

Examples:

```text
a + b * c
(a + b) * c
a < b == c
a && b || c
-a * b
!(a == b)
```

The expected AST structure should be checked, not merely parser success.

## 41.4 Error Coverage

Tests must include malformed forms for:

- missing delimiters;
- unexpected tokens;
- incomplete expressions;
- malformed assignments;
- malformed loops;
- malformed functions;
- malformed return statements;
- malformed array access;
- malformed else-if chains;
- invalid statement boundaries;
- missing required keywords.

## 41.5 Recovery Coverage

Tests should verify that controlled recovery:

- records diagnostics;
- resumes at an appropriate synchronization point;
- does not falsely report success;
- can report multiple independent syntax errors where recovery is safe.

## 41.6 Regression Coverage

All existing Stage 2 tests must be retained unless they are demonstrably inconsistent with the authoritative language specification.

Tests that encode obsolete syntax must be identified rather than silently preserved as language requirements.

---

# 43. Acceptance Criteria

Stage 2 implementation is considered conformant only when all of the following hold.

### Grammar

- The formal grammar uses EBNF notation adapted from ISO/IEC 14977:1996 consistently with the canonical language specification.
- The grammar matches the canonical Devara language specification.
- No undocumented syntax is accepted intentionally.

### Parser

- Recursive-descent parser follows the grammar.
- Expression precedence is correct.
- Complete token consumption is enforced.
- Syntax errors are detected.

### AST

- AST is directly constructed by the parser.
- Required node categories exist.
- Literal kind + raw lexeme are preserved.
- Identifiers contain names only.
- Array dimensions use `Expression | None`.
- Full source spans are attached.
- Semantic information is excluded.

### Diagnostics

- Syntax errors are structured.
- Diagnostics contain source locations.
- Controlled recovery is implemented.
- Any syntax error causes overall parse failure.

### Testing

- Every grammar production has coverage.
- Positive and negative cases are covered.
- Precedence and nesting are tested.
- Error recovery is tested.
- Existing regression tests pass.
- Additional exhaustive tests are completed before Stage 2 is frozen.

---

# 44. Stage Boundary

Stage 2 ends here:

```text
                 STAGE 2
          Syntax Analysis / Parsing

Token Stream
     |
     v
Recursive-Descent Parser
     |
     +---- syntax diagnostics ----> Parse Failure
     |
     v
    AST
     |
     v
STAGE 3
Semantics + Syntax-Directed Translation
+ Intermediate Code
```

Stage 2 does not decide what the program means.

It establishes the syntactic structure that the next stage will interpret.

---

# 45. Relationship to the Language Specification

This document is the **authoritative Stage 2 compiler-design specification**.
The canonical language definition remains `DEVARA_LANGUAGE_SPEC.md`.

The authority hierarchy is:

```text
DEVARA_LANGUAGE_SPEC.md
        |
        v
Stage 2 Design
        |
        v
Implementation
        |
        v
Tests
```

The Stage 2 design derives its syntax requirements from the canonical language
specification and defines the compiler-stage contract, AST design, parser
behavior, diagnostics, recovery, and testing requirements.

Where this document restates grammar for implementation purposes, the
canonical language specification remains authoritative. A deliberate language
change must therefore be made in the canonical specification first, followed
by corresponding Stage 2 design and implementation updates.

This Stage 2 document can be reviewed independently as the compiler-stage
design baseline.

After approval:

```text
Stage 2 Design
      |
      v
Review / corrections
      |
      v
Update DEVARA_LANGUAGE_SPEC.md
      |
      v
Implementation alignment
      |
      v
Exhaustive Stage 2 verification
      |
      v
Stage 2 freeze
```

---

# 46. Design Freeze

The following are frozen as the Stage 2 baseline:

```text
Formal notation:
    EBNF notation adapted from ISO/IEC 14977:1996

Parsing:
    Hand-written recursive descent

Input:
    Stage 1 token stream

Output:
    Syntax-oriented AST

Literal:
    kind + raw lexeme

Identifier:
    name only

Array dimensions:
    Expression | None

Source locations:
    complete start/end spans

Semantic types in AST:
    no

Identifier resolution:
    no

break/continue context:
    later semantic analysis

Parentheses:
    establish structure; no unnecessary AST wrapper

Persistent parse tree:
    no

Error handling:
    structured diagnostics +
    controlled synchronization recovery

Successful parse:
    requires zero syntax errors

Target:
    clean AST contract for Stage 3
```

This document is the **Stage 2 design baseline**. Implementation changes should be evaluated against it, and the subsequent exhaustive test suite should verify conformance to it.
