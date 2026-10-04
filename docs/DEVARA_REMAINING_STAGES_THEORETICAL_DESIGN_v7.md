# DEVARA --- Theoretical Design of Remaining Compiler Stages

## Stages 3--6: Semantic Analysis, Intermediate Representation, Optimization, and x86-64 Code Generation

**Document status:** Theoretical design baseline — semantic and Stage 2 interface decisions frozen\
**Source-language authority:** `DEVARA_LANGUAGE_SPEC.md`\
**Previous-stage contracts:** Stage 1 lexical-analysis design and Stage
2 parser/AST design\
**Target:** x86-64 executable on the supported Linux/System V AMD64
environment

------------------------------------------------------------------------

# 1. Purpose and Scope

The first two compiler stages establish the lexical and syntactic
structure of a Devara program.

The remaining compiler stages answer four different theoretical
questions:

1.  **Stage 3 --- Semantic Analysis:** Does the syntactically valid
    program make sense according to Devara's language rules?
2.  **Stage 4 --- Intermediate Representation:** How can that valid
    program be represented as explicit executable intermediate
    operations independent of the source syntax?
3.  **Stage 5 --- Optimization:** How can that IR be transformed into an
    equivalent but more efficient form without changing observable
    program behavior?
4.  **Stage 6 --- Code Generation:** How can the optimized IR be mapped
    to the target x86-64 machine and ABI?

``` text
Devara Source
      ↓
Lexical Analysis
      ↓ Token Stream
Syntax Analysis / Parsing
      ↓ AST
Semantic Analysis
      ↓ Semantically Validated Representation
IR Generation
      ↓ IR + CFG
Optimization
      ↓ Optimized IR + CFG
x86-64 Code Generation
      ↓ Assembly
Assembler + Linker
      ↓
Executable
```

------------------------------------------------------------------------

# 2. Design Principles

## 2.1 Separation of concerns

  -----------------------------------------------------------------------
  Stage                               Principal question
  ----------------------------------- -----------------------------------
  Lexer                               What tokens occur in the source?

  Parser                              How are those tokens structurally
                                      organized?

  Semantic analyzer                   Is that structure semantically
                                      valid?

  IR generator                        What executable operations
                                      represent the valid program?

  Optimizer                           Can those operations be transformed
                                      without changing behavior?

  Code generator                      How are those operations realized
                                      on x86-64?
  -----------------------------------------------------------------------

## 2.2 Specification authority

The canonical language specification defines source syntax and
source-language rules.

This document defines the theoretical architecture and freezes
implementation-level choices where the canonical specification
intentionally leaves them open.

A contradiction must be resolved at the design level. The implementation
agent must not invent a new rule.

## 2.3 Representation separation

``` text
Syntax representation
    AST

Semantic representation
    AST + symbols + types + semantic metadata

Executable representation
    IR + CFG
```

The AST is not turned into a machine-code data structure.

------------------------------------------------------------------------

# 3. Cross-Stage Contracts

## 3.1 Stage 2 → Stage 3

Stage 2 guarantees:

-   grammar validity;
-   syntactic structure;
-   precedence/associativity;
-   source spans.

Stage 3 adds:

-   declaration/use validity;
-   symbol resolution;
-   scope;
-   types;
-   conversions;
-   function semantics;
-   control-context validity;
-   initialization analysis.

## 3.2 Stage 3 → Stage 4

Stage 3 guarantees:

-   identifiers resolve;
-   types are known;
-   conversions are legal;
-   function calls are valid;
-   array operations are valid;
-   returns are valid;
-   loop-control statements occur in valid contexts.

Stage 4 therefore performs translation rather than rediscovering source
semantics.

## 3.3 Stage 4 → Stage 5

Stage 4 guarantees verified IR:

-   valid operands;
-   valid types;
-   valid control-flow targets;
-   valid calls;
-   valid returns;
-   explicit memory operations;
-   explicit conversions.

## 3.4 Stage 5 → Stage 6

Stage 5 guarantees semantics-preserving optimized IR.

Stage 6 maps that IR to machine operations while preserving its
behavior.

------------------------------------------------------------------------

## 3.5 Stage 2 AST Interface — normative field-level contract

The Stage 2 parser/AST boundary is part of the compiler architecture, not an implementation suggestion. Class names may vary, but the following semantic field shapes are frozen. An implementation agent may choose different class names or equivalent tagged-union representations only if the observable field information and invariants below are preserved.

### 3.5.1 Common AST metadata

Every AST node carries:

```text
Span
 ├── start_line
 ├── start_column
 ├── end_line
 └── end_column
```

The span is **half-open**: `[start, end)`. `start` is the first source character belonging to the construct and `end` is the first source character after the construct. For a construct ending at a token, the end position is derived from that token's source position and lexeme length. Nodes with a single keyword token use that token for both boundaries.

The AST contains source syntax information only. It does not contain resolved symbols, inferred semantic types, implicit conversions, or control-flow facts.

### 3.5.2 Type syntax

`TypeSyntax` is a syntax node, not a semantic type:

```text
TypeSyntax
 ├── primitive
 └── array_dimensions: list[Expression | None]
```

For ordinary declarations every array dimension is an `Expression`. For the single unsized function-parameter form, the corresponding dimension is `None`.

### 3.5.3 Program and blocks

```text
Program
 └── items: list[TopLevelItem]

Block
 └── statements: list[Statement]
```

`TopLevelItem` is one of `Declaration`, `FunctionDeclaration`, or a `Statement`.

### 3.5.4 Names and literals

```text
Identifier
 └── name: str

Literal
 ├── kind: LiteralKind
 └── lexeme: str
```

Literal lexemes are retained exactly as emitted by the lexer, including boolean spellings. Semantic interpretation of the lexeme belongs to Stage 3.

### 3.5.5 Declarations and assignments

```text
Declaration
 ├── type: TypeSyntax
 └── name: Identifier

Assignment
 ├── target: AssignableTarget
 └── value: Expression

Input
 └── target: AssignableTarget

Output
 └── value: Expression
```

`AssignableTarget` is exactly `Identifier | ArrayAccess`.

### 3.5.6 Conditional and loop statements

```text
IfStatement
 ├── condition: Expression
 ├── then_block: Block
 └── else_branch: Block | IfStatement | None

WhileStatement
 ├── condition: Expression
 └── body: Block

RangeLoop
 ├── variable: Identifier
 ├── start: Expression
 ├── end: Expression
 └── body: Block

ForLoop
 ├── init: ForInit
 ├── condition: Expression
 ├── update: ForUpdate
 └── body: Block
```

`else_branch` is recursive rather than flattened so the AST mirrors the canonical grammar's `block | if-statement` alternative exactly.

### 3.5.7 Three-part-loop initializer variants

`ForInit` is a tagged union with exactly three variants:

```text
ForThoModhaluInit
 ├── target: Identifier
 └── value: Expression

ForAssignmentInit
 ├── target: Identifier
 └── value: Expression

ForDeclarationInit
 ├── type: TypeSyntax
 ├── name: Identifier
 └── initializer: Expression | None
```

The variant tag is structural (the concrete node type or an equivalent explicit tag). No fourth empty initializer exists.

### 3.5.8 Three-part-loop update variants

`ForUpdate` is a tagged union with exactly five grammar alternatives: one assignment form, prefix/postfix increment, and prefix/postfix decrement.

```text
AssignmentUpdate
 ├── target: AssignableTarget
 └── value: Expression

IncrementUpdate
 ├── target: AssignableTarget
 └── prefix: bool

DecrementUpdate
 ├── target: AssignableTarget
 └── prefix: bool
```

The assignment, increment, and decrement forms are distinguished by their operator/update tag. `prefix=true` means the operator precedes the target; `prefix=false` means it follows it. There is no standalone increment or decrement statement node.

### 3.5.9 Control-transfer and expression statements

```text
BreakStatement
 └── no semantic fields

ContinueStatement
 └── no semantic fields

ReturnStatement
 └── value: Expression

ExpressionStatement
 └── expression: FunctionCall
```

A bare source return is not represented because the canonical grammar requires an expression before `ivvu`.

### 3.5.10 Functions and parameters

```text
FunctionDeclaration
 ├── return_type: TypeSyntax
 ├── name: Identifier
 ├── parameters: list[Parameter]
 └── body: Block

Parameter
 ├── type: TypeSyntax
 └── name: Identifier
```

For an unsized array parameter, the current grammar represents the unsized
parameter dimension as `None`. The current source grammar provides only the
single unsized-array-parameter form; this is a syntax/grammar boundary, not a
separate semantic prohibition against multidimensional array parameter types.
The semantic model must not introduce an additional restriction merely because
that syntax is not currently expressible.

### 3.5.11 Calls, indexing, and expressions

```text
FunctionCall
 ├── callee: Identifier
 └── arguments: list[Expression]

ArrayAccess
 ├── base: Identifier
 └── indices: list[Expression]

BinaryExpression
 ├── operator: BinaryOperator
 ├── left: Expression
 └── right: Expression

UnaryExpression
 ├── operator: UnaryOperator
 └── operand: Expression

CastExpression
 ├── target_type: TypeSyntax
 └── expression: Expression
```

Parenthesized grouping does not create a separate AST wrapper; the grouped expression's child is returned directly, as required by the approved Stage 2 D9 decision.

`CastExpression` represents the approved C-style explicit-cast extension: `(type) expression`. The synchronized canonical language specification v0.7 now contains the corresponding production.

### 3.5.12 AST invariants

The following are mandatory:

1. Every node has a complete half-open source span.
2. Every expression child is an `Expression` node; semantic types are absent.
3. Every assignment/input/update target is either `Identifier` or `ArrayAccess` as required by the corresponding grammar production.
4. `ForLoop.init`, `condition`, and `update` are never `None` in a successful parse.
5. `IfStatement.else_branch` is only `None`, `Block`, or `IfStatement`.
6. `ExpressionStatement.expression` is always a `FunctionCall`.
7. Boolean literals retain their original lexeme rather than being normalized by the parser.
8. The parser never constructs a syntax AST node for a construct not admitted by the canonical grammar or an explicitly approved grammar extension.

------------------------------------------------------------------------

## 3.6 Stage 2 diagnostic interface — normative contract

Parser diagnostics use exactly this closed category set:

```text
SyntaxDiagnosticCategory
 ├── UNEXPECTED_TOKEN
 ├── UNEXPECTED_EOF
 ├── MISSING_TOKEN
 ├── INVALID_EXPRESSION
 ├── INVALID_STATEMENT
 └── INVALID_DECLARATION
```

A diagnostic has:

```text
ParserDiagnostic
 ├── category: SyntaxDiagnosticCategory
 ├── message: str
 ├── span: Span
 ├── expected: optional list[TokenKind]
 └── related: optional list[Span]
```

`expected` is populated when the parser can state a finite expected-token set; `related` is reserved for additional source locations relevant to the same syntax error. Neither field changes the diagnostic category vocabulary.

Lexer failures remain Stage 1 diagnostics and are not converted into parser diagnostic categories.

------------------------------------------------------------------------

## 3.7 Stage 2 panic-mode recovery — normative algorithm

Recovery is context-sensitive. There is no global semicolon statement boundary because Devara statements are not semicolon-terminated.

### 3.7.1 General statement/block recovery

When a statement-level parse fails:

1. Record exactly one primary diagnostic for that failed production.
2. Consume at least one token unless already at `EOF` or the current token is a designated synchronization token.
3. Then consume until one of these exact tokens is reached at the current syntactic nesting level: `RBRACE`, `EOF`, a token in the grammar-derived `FIRST(statement)` set, or a token in the grammar-derived `FIRST(declaration)` set.
4. Leave the synchronization token unconsumed when it can begin the next construct or close the current block.
5. Resume parsing from that token.

For this purpose, the frozen token sets are:

```text
FIRST(statement) = {
    IDENTIFIER,
    INT_LITERAL,
    FLOAT_LITERAL,
    CHAR_LITERAL,
    STRING_LITERAL,
    BOOL_LITERAL,
    LPAREN,
    BANG,
    PLUS,
    MINUS,
    AAPU,
    SAAGU,
    PRATI,
    PRATISARI,
    IVVU
}

FIRST(declaration) = {
    INT,
    FLOAT,
    BOOL,
    CHAR,
    PADHAM,
    VOID
}
```

`INCREMENT` and `DECREMENT` are deliberately absent from `FIRST(statement)`
because standalone increment/decrement statements are not part of the
language. `FIRST(statement)` already includes the first token of every
expression that can begin an output statement or function-call expression
statement.

### 3.7.2 For-header recovery

Inside `pratisari (...)`, synchronization is delimiter-aware. The exact recovery delimiters are:

```text
SEMICOLON
RPAREN
RBRACE
EOF
```

`SEMICOLON` is a synchronization point **only while parsing a `pratisari` header**. It is never treated as a general statement boundary.

The parser tracks nested `(`, `[`, and `{` delimiters while recovering so a semicolon or right parenthesis belonging to a nested expression is not treated as the outer `pratisari` boundary.

### 3.7.3 Delimited-list recovery

For function arguments and parameter lists, the exact synchronization set is:

```text
COMMA
RPAREN
EOF
```

For array indexing/dimensions, the exact set is:

```text
RBRACKET
RPAREN
COMMA
SEMICOLON   (only when inside a pratisari header)
RBRACE
EOF
```

The parser respects nested delimiter depth before treating a delimiter as the current construct's synchronization point.

### 3.7.4 Recovery termination invariant

Every recovery loop must either consume a token or terminate at a recognized synchronization token/`EOF`. Therefore malformed input cannot cause an infinite recovery loop.

Recovery is for continued diagnostic collection only. It must never construct an AST node that violates the field-level AST invariants in §3.5.

------------------------------------------------------------------------

# 4. Stage 3 --- Semantic Analysis

## 4.1 Purpose

Parsing determines whether source text has valid syntactic structure.

Semantic analysis determines whether that structure has a valid meaning.

For:

``` text
x lo y + 1 pettu
```

semantic analysis determines whether `x` and `y` exist, whether the
expression is valid, and whether its value can be assigned to `x`.

------------------------------------------------------------------------

## 4.2 Input and output

### Input

A valid Stage 2 AST.

### Output

A semantically validated representation containing:

-   resolved symbols;
-   scope information;
-   expression/statement types;
-   required conversion information;
-   function signatures;
-   initialization information;
-   semantic metadata.

The syntax AST remains available.

------------------------------------------------------------------------

## 4.3 Symbol tables

A symbol conceptually contains:

``` text
Symbol
 ├── name
 ├── category
 ├── declared type
 ├── source location
 └── declaration metadata
```

Categories:

``` text
variable
parameter
function
```

Function symbols additionally contain:

``` text
return type
parameter types
parameter metadata
```

------------------------------------------------------------------------

## 4.4 Scope management

Devara uses lexical scope:

``` text
Global
  ↓
Function
  ↓
Block
  ↓
Nested blocks
```

Lookup searches the current scope and then enclosing scopes.

Inner declarations may shadow outer names.

Conflicting same-scope redeclarations are semantic errors.

------------------------------------------------------------------------

## 4.5 Function collection

Function signatures are collected before function bodies are analyzed.

Therefore:

-   a function may be called before its textual definition;
-   mutual recursion is possible;
-   recursion is allowed.

Function overloading is not supported.

------------------------------------------------------------------------

## 4.6 Type system

Primitive types:

``` text
int
float
bool
char
padham
void
```

Composite array types contain:

``` text
element type
ordered dimensions
```

Function types contain:

``` text
parameter types
return type
```

`void` is legal only as a function return type. It is not a variable type,
parameter type, array element type, or expression value type.

------------------------------------------------------------------------

## 4.7 Primitive representation semantics

The source-level primitive representations are frozen for the baseline
compiler:

| Type | Semantic representation |
|---|---|
| `int` | signed 64-bit integer |
| `float` | IEEE-754 binary64 |
| `bool` | semantic values `true` and `false` |
| `char` | 8-bit character unit |
| `padham` | immutable sequence of 8-bit character units |
| `void` | absence of a value; function return type only |

Integer arithmetic uses signed 64-bit two's-complement representation. The
results of `+`, `-`, and `*` wrap modulo 2^64 and are interpreted as signed
64-bit values; overflow is not a compiler diagnostic or runtime exception.
Division and remainder by zero are defined runtime errors. The singular signed
division case `INT64_MIN / -1`, which has no representable signed 64-bit
quotient, is also a defined runtime arithmetic error. Floating-point arithmetic
follows IEEE-754 binary64 behavior, including its standard exceptional values.

------------------------------------------------------------------------

## 4.8 Type checking

Semantic analysis determines expression types and verifies:

-   arithmetic operations;
-   relational/equality operations;
-   logical operations;
-   assignments;
-   function calls;
-   returns;
-   array indexing;
-   conditions.

------------------------------------------------------------------------

## 4.9 Conversion model

The following conversion decisions were explicitly approved earlier in the
design process.

Where Devara has a corresponding C++ conversion situation, Devara uses the
**literal C++ conversion system**, rather than a custom subset, for:

- assignment conversions;
- condition conversions;
- arithmetic conversions;
- equality comparisons;
- relational comparisons;
- function-argument conversions;
- function-return conversions;
- bool↔numeric conversions;
- char↔numeric conversions.

These are approved semantic decisions and form part of the Stage 3 baseline.

Explicit casts are supported using C-style source syntax:

```text
(type) expression
```

This is a source-language decision. The conversion semantics of the cast use
the already-approved C++-style conversion system where a corresponding C++
conversion exists. The cast syntax is synchronized with canonical language specification v0.7
and the Stage 2 grammar; implementation consumes that frozen production.

The compiler may represent the operation internally as an explicit
`convert` operation; that internal name is not source syntax.


## 4.10 Condition semantics

Conditions use the selected C++ truth-conversion model:

``` text
zero numeric     → false
nonzero numeric  → true
bool             → itself
```

This applies to `ayite`, `unnanta varaku`, and `pratisari` conditions.

------------------------------------------------------------------------

## 4.11 Assignment analysis

Canonical assignment:

``` text
target lo expression pettu
```

The analyzer verifies:

1.  target resolution;
2.  target assignability;
3.  source expression validity;
4.  source-to-target conversion;
5.  conversion legality.

Assignment is statement-only and is not an expression.

------------------------------------------------------------------------

## 4.12 Expression analysis

For:

``` text
lhs operator rhs
```

semantic analysis recursively:

``` text
analyze lhs
    ↓
obtain lhs type

analyze rhs
    ↓
obtain rhs type

check operator
    ↓
perform required conversions
    ↓
determine result type
```

For:

``` text
f(a, b)
```

the analyzer resolves `f`, checks argument count and conversions, and
determines the return type.

------------------------------------------------------------------------

## 4.13 Array semantic analysis

For:

``` text
int a[3][4][5]
```

partial indexing removes dimensions:

``` text
a[i]       → reference to int[4][5]
a[i][j]    → reference to int[5]
a[i][j][k] → int lvalue
```

Partial indexing is non-owning; no subarray copy occurs.

The analyzer verifies that:

-   the base is indexable;
-   each index expression is usable as an integral array index under the
    approved conversion rules in §4.9. Do not introduce a separate hard-coded
    whitelist of source types here; the normal conversion model determines
    whether a value can be used as an index. A type for which the language
    provides no valid path to an integral index value is rejected by semantic
    analysis;
-   the number of indices does not exceed available dimensions.

Array storage is contiguous row-major.

No automatic runtime bounds checking is generated.

------------------------------------------------------------------------

## 4.14 `padham` semantic analysis

`padham` is an immutable text value. Its source-facing design is deliberately
small and uses Romanized-Telugu naming for language/library facilities rather
than introducing an English-heavy string sublanguage.

### Literal values

Quoted string literals produce `padham` values.

### Assignment and value semantics

`padham` assignment has value semantics. Assigning one `padham` to another
produces an independent logical value; the source language does not expose
string object identity or reference equality.

### Supported operations

The baseline language supports:

- `+` for `padham + padham` concatenation;
- `==` and `!=` for content equality/inequality;
- indexing with `[]`, producing a `char`;
- a standard-library length facility named `podavu(...)`;
- existing input/output constructs for reading and displaying text.

`padham` is immutable. Character-level mutation is not supported.

### Standard-library length facility

The baseline standard library provides:

```text
podavu(padham value) → int
```

`podavu` is a normal function call from the source-language grammar; its
implementation may be an intrinsic/runtime helper. For semantic analysis, the
baseline standard library is represented by a set of predeclared global
symbols. `podavu` is registered in that global symbol environment before
user declarations are collected. It therefore participates in ordinary name
lookup and same-scope redeclaration checking. A user declaration of a
function named `podavu` in the global scope is a same-scope redeclaration
error. Inner scopes follow the general shadowing rule: an inner declaration
may shadow the global `podavu`, and a call in that scope resolves the nearest
visible declaration rather than bypassing normal lookup. Calls that resolve
to the builtin are checked against the signature `padham -> int`.

### Input

Reading into a `padham` obtains one complete input line.

### Output

Displaying a `padham` outputs its complete text value.

### Conversion policy

Implicit numeric-to-`padham` and `padham`-to-numeric conversions are not
performed. Such conversions, where supported, are explicit conversions.
`char` to `padham` is likewise explicit rather than an implicit promotion.

The baseline explicitly permits character/text conversion in these directions:

```text
char   ↔ padham
```

`char → padham` produces a one-character text value. `padham → char` requires
the source text to contain exactly one character unit; otherwise conversion is
a defined runtime conversion failure. Numeric↔`padham` conversion is not part
of the baseline language. Numeric text parsing/formatting can be added later as
ordinary library functionality without changing the core type system.

### Character representation

For the baseline x86-64 implementation, `char` is an 8-bit character unit and
`padham` is represented as a sequence of those character units. Full Unicode
code-point semantics are outside the baseline language contract.

### Runtime representation boundary

The concrete storage representation, allocation strategy, and runtime helper
ABI are backend/runtime concerns, but they must implement the semantic
contract above. The source language does not expose pointers, ownership, or
manual string memory management.

------------------------------------------------------------------------

## 4.15 Initialization analysis

Local variables begin uninitialized.

A read before definite initialization is a semantic error. The analysis is
path-sensitive: a variable is considered definitely initialized only when every
reachable path to the read has initialized it.

Global declarations without explicit initialization are zero-initialized using
the type's zero value (`0`, `0.0`, `false`, zero character, or empty
`padham`).

For arrays, initialization tracking must distinguish individual elements
where necessary.

------------------------------------------------------------------------

## 4.16 Function analysis

Each function is analyzed through:

``` text
signature
 ↓
parameter scope
 ↓
body
 ↓
return-path analysis
```

The analyzer checks parameters, locals, calls, returns, and return
conversions.

Every reachable path of a non-void function must return a value.

A void function may complete without a value return.

------------------------------------------------------------------------

## 4.17 Loop context

Semantic analysis tracks whether a loop is active.

Entering a:

-   while loop;
-   range loop;
-   three-part loop

activates loop context.

`aapu` and `saagu` are legal only in an active loop and affect the
nearest enclosing loop.

------------------------------------------------------------------------

## 4.18 Range-loop semantics

Canonical form:

```text
prati identifier expression nundi expression varaku block
```

The baseline semantics are:

1. The start expression is evaluated exactly once before the first iteration.
2. The end expression is evaluated exactly once before the first iteration.
3. The loop variable is implicitly introduced by the range loop.
4. The loop variable is scoped to the loop construct and its body; it is not
   visible after the loop.
5. The start bound is inclusive.
6. The end bound is exclusive.
7. The step is exactly `+1`.
8. If the start value is greater than or equal to the end value, the loop
   executes zero times. Descending iteration is not supported by this
   construct.

Conceptually:

```text
start = evaluate(start-expression)
end   = evaluate(end-expression)
i = start

while i < end:
    body
    i = i + 1
```

These semantics are lowered to ordinary CFG operations. The source spelling
remains the canonical language syntax; no new range syntax is introduced.

## 4.19 Three-part loop semantics

Canonical form:

``` text
pratisari (init; condition; update) block
```

Execution:

``` text
init
 ↓
condition
 ↓
body
 ↓
update
 ↓
condition
```

Initializer declarations have loop scope.

The condition is an ordinary expression.

------------------------------------------------------------------------

### `pratisari` initializer semantics

The three canonical initializer alternatives have distinct declaration
semantics:

- `for-tho-modhalu-init` initializes an already-declared, assignable scalar
  variable; it does not declare a new variable.
- `for-assignment-init` assigns to an already-declared, assignable target; it
  does not declare a new variable.
- `for-declaration-init` declares a new variable whose scope is the
  three-part loop, including its condition, update, and body. If its optional
  initializer is absent, the new variable begins uninitialized and the normal
  definite-initialization rules apply.

The range-loop variable is likewise a mutable loop-local variable. Its value is
advanced by one after each body execution.

------------------------------------------------------------------------

## 4.20 Semantic diagnostics

Diagnostics are structured:

``` text
SemanticDiagnostic
 ├── category
 ├── message
 ├── source span
 └── optional related information
```

Examples:

``` text
undeclared identifier
same-scope redeclaration
invalid assignment
invalid conversion
wrong argument count
invalid return
invalid array access
break outside loop
continue outside loop
use before initialization
```

------------------------------------------------------------------------

## 4.21 Stage 3 contract

### Input

Valid AST.

### Success output

Semantically validated program representation.

### Failure output

Structured semantic diagnostics.

### Invariant

Stage 4 receives no unresolved source-level semantic question.

------------------------------------------------------------------------

# 5. Stage 4 --- Intermediate Representation

## 5.1 Purpose

ASTs represent source syntax. IR represents executable operations.

The transformation is:

``` text
high-level construct
       ↓
explicit primitive operations
```

------------------------------------------------------------------------

## 5.2 Why IR is required

Without IR, the x86-64 backend would need to understand every Devara
construct.

With IR:

``` text
Devara semantics
      ↓
generic IR
      ↓
optimizer
      ↓
x86-64 backend
```

Source semantics and machine representation are therefore separated.

------------------------------------------------------------------------

## 5.3 IR design goals

The IR is:

-   explicit;
-   typed;
-   deterministic;
-   verifiable;
-   source-syntax independent;
-   optimization-friendly;
-   backend-friendly.

------------------------------------------------------------------------

## 5.4 Three-address representation

The baseline uses non-SSA three-address-style IR.

Example:

``` text
a + b * c
```

becomes:

``` text
t1 = b * c
t2 = a + t1
```

This exposes data dependencies explicitly.

------------------------------------------------------------------------

## 5.5 IR types

Baseline IR types:

``` text
int64
float64
bool
char
string
address(T)
void
```

Array/reference information is represented through explicit
references/addresses.

The IR uses the frozen language representations: signed 64-bit `int` and
IEEE-754 binary64 `float`.

------------------------------------------------------------------------

## 5.6 Operands

IR operands include:

``` text
constant
temporary
local
parameter
global
function symbol
address
```

------------------------------------------------------------------------

## 5.7 Core instructions

``` text
const
copy

add
sub
mul
div
mod
neg

compare
convert

address
load
store

label
jump
branch

param
call
return

input
output
```

------------------------------------------------------------------------

## 5.8 Basic blocks

A basic block has:

-   one entry;
-   sequential operations;
-   one terminator.

Terminators:

``` text
jump
branch
return
```

------------------------------------------------------------------------

## 5.9 Control-flow graph

A function becomes:

``` text
basic blocks = vertices
control-flow edges = directed edges
```

CFGs support:

-   reachability;
-   loops;
-   branch analysis;
-   dead-code elimination;
-   later backend analysis.

------------------------------------------------------------------------

## 5.10 Expression translation

For:

``` text
a + b * c
```

the IR follows the AST grouping:

``` text
t1 = b * c
t2 = a + t1
```

Stage 4 does not re-decide precedence.

------------------------------------------------------------------------

## 5.11 Evaluation order

Devara evaluation is left-to-right.

For:

``` text
f() + g()
```

the conceptual IR must execute:

``` text
call f
call g
add
```

Observable operations cannot be reversed.

------------------------------------------------------------------------

## 5.12 Conversion translation

Semantic conversions become explicit IR operations:

``` text
t1 = convert x → float64
```

or an equivalent typed conversion sequence.

------------------------------------------------------------------------

## 5.13 Assignment translation

For:

``` text
x lo expression pettu
```

conceptually:

``` text
t1 = evaluate expression
store x, t1
```

For an array target, Stage 4 computes the target address and emits a
store.

------------------------------------------------------------------------

## 5.14 Array address calculation

For row-major:

``` text
A[D0][D1][D2]
```

element `[i][j][k]` has element offset:

``` text
i × (D1 × D2)
+ j × D2
+ k
```

Byte offset:

``` text
element offset × sizeof(element)
```

The calculation becomes explicit IR operations.

------------------------------------------------------------------------

## 5.15 Partial array references

For:

``` text
a[i]
```

on:

``` text
int a[3][4][5]
```

the generated reference points at the selected `int[4][5]` region.

No copy is generated.

------------------------------------------------------------------------

## 5.16 Conditional translation

A condition becomes explicit branching:

``` text
evaluate condition
branch condition, TRUE, FALSE
```

------------------------------------------------------------------------

## 5.17 Short-circuit translation

For:

``` text
a && b
```

`b` is reachable only when `a` is true.

For:

``` text
a || b
```

`b` is reachable only when `a` is false.

Branch-based lowering preserves this directly.

------------------------------------------------------------------------

## 5.18 `if` translation

Conceptually:

``` text
evaluate condition
branch condition, THEN, ELSE

THEN:
    body
    jump MERGE

ELSE:
    body
    jump MERGE

MERGE:
```

------------------------------------------------------------------------

## 5.19 `while` translation

``` text
COND:
    evaluate condition
    branch condition, BODY, EXIT

BODY:
    body
    jump COND

EXIT:
```

`aapu` targets `EXIT`.

`saagu` targets `COND`.

------------------------------------------------------------------------

## 5.20 Range-loop translation

``` text
evaluate start once
evaluate end once
initialize i

COND:
    compare i < end
    branch condition, BODY, EXIT

BODY:
    body
    i = i + 1
    jump COND

EXIT:
```

------------------------------------------------------------------------

## 5.21 Three-part-loop translation

``` text
INIT
 ↓
COND
 ├── false → EXIT
 └── true  → BODY
                ↓
              UPDATE
                ↓
               COND
```

`aapu` targets `EXIT`.

`saagu` targets `UPDATE`.

------------------------------------------------------------------------

## 5.22 Function translation

Each function becomes:

``` text
IRFunction
 ├── signature
 ├── parameters
 ├── locals
 ├── entry block
 └── basic blocks
```

A call becomes:

``` text
param a
param b
t1 = call f
```

------------------------------------------------------------------------

## 5.23 Return translation

The canonical source grammar currently defines:

```text
expression ivvu
```

and does not define a bare `ivvu`.

Therefore Stage 4 represents a value return after Stage 3 has validated its
type.

The IR may have a parameterless `return` terminator as an internal control-flow
operation where the function contract permits completion without a source
value, but that does not introduce a bare `ivvu` source construct.


## 5.24 Top-level executable region

Because the canonical grammar permits top-level statements, the compiler
generates a top-level executable entry region.

Conceptually:

``` text
_generated_entry:
    runtime initialization
    top-level executable statements
    program termination
```

User-defined functions remain separate.

------------------------------------------------------------------------

## 5.25 Input/output translation

Canonical input/output constructs are lowered to explicit IR operations:

```text
input
output
```

Their runtime implementation remains a backend/runtime concern.

The IR contract must nevertheless record their side effects so that
optimization cannot remove or reorder observable I/O.


## 5.26 IR verification

The IR verifier checks:

-   operand validity;
-   type compatibility;
-   existing branch targets;
-   valid block terminators;
-   call arity/types;
-   return compatibility;
-   valid memory operand types.

Verification is a correctness barrier before optimization.

------------------------------------------------------------------------

## 5.27 Stage 4 contract

### Input

Semantically validated program.

### Output

Verified typed IR + CFG.

### Invariants

IR preserves:

-   source evaluation order;
-   conversions;
-   control flow;
-   memory operations;
-   function semantics.

------------------------------------------------------------------------

# 6. Stage 5 --- Optimization

## 6.1 Purpose

Optimization transforms valid IR while preserving observable behavior.

``` text
observable(original IR)
=
observable(optimized IR)
```

------------------------------------------------------------------------

## 6.2 Baseline pipeline

``` text
Verified IR
 ↓
Constant folding
 ↓
Constant propagation
 ↓
Copy propagation
 ↓
Algebraic simplification
 ↓
Branch simplification
 ↓
Unreachable-block elimination
 ↓
Dead-code elimination
 ↓
Redundant-conversion elimination
 ↓
Verified optimized IR
```

------------------------------------------------------------------------

## 6.3 Constant folding

Compile-time evaluation of safe constant expressions:

``` text
t1 = 2 * 3
```

becomes:

``` text
t1 = 6
```

Only transformations with exactly valid language semantics are
permitted.

------------------------------------------------------------------------

## 6.4 Constant propagation

Known values are propagated through uses when definitions cannot change.

------------------------------------------------------------------------

## 6.5 Copy propagation

Copies can be bypassed when safe:

``` text
t1 = x
t2 = t1 + 1
```

→

``` text
t2 = x + 1
```

------------------------------------------------------------------------

## 6.6 Algebraic simplification

Examples:

``` text
x + 0 → x
x * 1 → x
```

but floating-point transformations require IEEE-754 safety analysis.

------------------------------------------------------------------------

## 6.7 Branch simplification

Known conditions can replace conditional branches with unconditional
jumps.

------------------------------------------------------------------------

## 6.8 Unreachable-block elimination

CFG reachability identifies blocks that cannot execute.

Those blocks can be removed.

------------------------------------------------------------------------

## 6.9 Dead-code elimination

A computation can be removed only if:

-   its result is unused;
-   it has no observable side effect;
-   removing it does not remove a required runtime failure.

Calls, I/O, stores, and required runtime errors are therefore treated
conservatively.

------------------------------------------------------------------------

## 6.10 Redundant conversion elimination

A conversion proven to have no observable effect may be removed.

------------------------------------------------------------------------

## 6.11 Evaluation-order preservation

Optimization cannot turn:

``` text
f() + g()
```

into:

``` text
g() + f()
```

when the order is observable.

Mathematical equivalence is not sufficient.

------------------------------------------------------------------------

## 6.12 Short-circuit preservation

Optimization must preserve the fact that:

``` text
a && b
```

may not evaluate `b`, and:

``` text
a || b
```

may not evaluate `b`.

------------------------------------------------------------------------

## 6.13 Runtime-error preservation

Integer division by zero and other language-defined runtime failures
cannot be removed merely because their result is unused.

------------------------------------------------------------------------

## 6.14 Floating-point safety

IEEE-754 binary64 semantics mean real-number algebra is not
automatically valid floating-point algebra. The optimizer therefore uses an
explicit baseline whitelist rather than asking an implementation to infer
which algebraic identities are safe.

### Baseline permitted set

For expressions whose operands or result may have type `float`, the baseline
algebraic-simplification transformation set is **empty**. In particular, the
following transformations are **not** permitted merely from algebraic
identity:

```text
x + 0.0 -> x
x - 0.0 -> x
x * 1.0 -> x
x / 1.0 -> x
x * 0.0 -> 0.0
```

This conservative rule preserves observable IEEE-754 behavior, including
signed zero, NaN behavior, infinities, and floating-point operation effects.
For example, `-0.0 + 0.0` produces `+0.0`, so `x + 0.0 -> x` is not a
valid identity for all binary64 values.

Other optimization classes described in §§6.5–6.13 remain governed by their
own effect and semantic-preservation contracts. A future language/design
revision may add individual floating-point transformations only by explicitly
proving and freezing them; an implementation may not add them locally.

------------------------------------------------------------------------

## 6.15 Function calls

Calls are potentially observable.

The optimizer cannot remove or reorder a call without a proof that doing
so preserves observable behavior.

------------------------------------------------------------------------

## 6.16 Stage 5 contract

### Input

Verified typed IR.

### Output

Verified optimized typed IR.

### Invariant

Observable language behavior is preserved.

------------------------------------------------------------------------

# 7. Stage 6 --- x86-64 Code Generation

## 7.1 Purpose

Code generation maps optimized IR to x86-64 machine operations.

Target:

``` text
x86-64
System V AMD64 ABI
GNU toolchain
ELF executable
```

The backend does not understand source keywords.

------------------------------------------------------------------------

## 7.2 Backend pipeline

``` text
Optimized IR
 ↓
Machine-level lowering
 ↓
Instruction selection
 ↓
Register allocation
 ↓
Spill insertion
 ↓
Stack-frame layout
 ↓
Prologue / epilogue
 ↓
Assembly emission
```

------------------------------------------------------------------------

## 7.3 Machine-level representation

IR operations are lowered to operations involving:

-   physical registers;
-   stack slots;
-   machine instructions;
-   ABI locations.

Example:

``` text
t1 = add x, y
```

becomes a machine sequence that places `x` in a register and adds `y`.

------------------------------------------------------------------------

## 7.4 Instruction selection

Examples:

``` text
add → add
sub → sub
mul → imul
load/store → mov
jump → jmp
conditional branch → conditional jump
```

Instruction choice depends on operand type and location.

------------------------------------------------------------------------

## 7.5 Register classes

General-purpose registers handle integer/address values.

SSE floating-point registers handle `float`.

ABI-reserved and caller/callee-saved registers must be respected.

------------------------------------------------------------------------

## 7.6 Register allocation

IR temporaries are mapped to physical registers or stack slots.

A baseline linear-scan-style allocator is sufficient.

The allocator uses liveness information to determine simultaneously live
values.

------------------------------------------------------------------------

## 7.7 Spilling

When register pressure exceeds available registers:

``` text
live value
   ↓
stack slot
   ↓
reload
```

Spills must preserve semantics and ABI alignment.

------------------------------------------------------------------------

## 7.8 Stack frames

Frames may contain:

``` text
locals
spills
saved registers
outgoing call requirements
alignment padding
```

------------------------------------------------------------------------

## 7.9 Function entry/exit

Conceptually:

``` text
entry
 ↓
prologue
 ↓
body
 ↓
epilogue
 ↓
return
```

------------------------------------------------------------------------

## 7.10 System V AMD64 ABI

The backend implements:

-   integer/pointer argument locations;
-   floating-point argument locations;
-   return-value locations;
-   caller/callee-saved registers;
-   stack alignment;
-   call/return conventions.

------------------------------------------------------------------------

## 7.11 Integer operations

Integer arithmetic maps to x86-64 integer instructions.

Division requires architectural dividend/divisor handling.

The backend/runtime must additionally implement Devara's required
behavior for:

-   divide by zero;
-   remainder by zero;
-   fixed-width signed integer overflow according to the language arithmetic
    model.

------------------------------------------------------------------------

## 7.12 Floating-point operations

`float` uses IEEE-754 binary64.

Arithmetic and conversion operations use the appropriate x86-64 SSE
instructions.

------------------------------------------------------------------------

## 7.13 Boolean operations

Booleans are normalized to false/true values.

Comparisons may produce normalized boolean results or feed branches
directly where equivalent.

------------------------------------------------------------------------

## 7.14 Comparisons

Comparison lowering may use:

``` text
cmp
conditional jump
setcc
```

or equivalent instruction sequences.

------------------------------------------------------------------------

## 7.15 Arrays

Array addressing becomes:

``` text
base
 +
row-major byte offset
```

followed by load/store.

No automatic bounds-check sequence is emitted.

------------------------------------------------------------------------

## 7.16 Strings

The backend implements the frozen `padham` contract. The runtime boundary
provides helpers for concatenation, content comparison, indexing, `podavu`,
line input, and output.

The concrete representation and allocation strategy are backend/runtime
details; the source language does not expose pointers or manual string memory
management. Runtime failures for invalid text conversion or indexing follow
the frozen runtime-error contract.

Operations requiring loops or allocation may be implemented in runtime support
rather than expanded directly into generated source-level code.


## 7.17 Function calls

Calls follow:

``` text
evaluate arguments left-to-right
 ↓
apply semantic conversions
 ↓
place arguments according to ABI
 ↓
call
 ↓
obtain result
```

Evaluation order is language semantics; ABI placement is backend
mechanics.

------------------------------------------------------------------------

## 7.18 Return values

Integer/address-like values use ABI-defined integer return locations.

Floating-point values use the ABI floating-point return location.

Void functions return without a value.

------------------------------------------------------------------------

## 7.19 Runtime support

Runtime support provides:

``` text
input
output
string operations
string length
string concatenation
runtime diagnostics
divide-by-zero handling
overflow handling
```

Standard C library facilities may be used where appropriate.

------------------------------------------------------------------------

## 7.20 Program entry

Generated entry performs required runtime initialization, executes
top-level executable code, and terminates the program.

User functions are not automatically executed.

------------------------------------------------------------------------

## 7.21 Assembly

The backend emits GNU assembler source using:

``` text
.intel_syntax noprefix
```

------------------------------------------------------------------------

## 7.22 Assembly verification

Generated assembly must actually pass:

``` text
assembler
 ↓
object file
 ↓
linker
 ↓
executable
```

Textual assembly emission alone is not sufficient evidence of successful
code generation.

------------------------------------------------------------------------

## 7.23 Stage 6 contract

### Input

Verified optimized IR.

### Output

Valid x86-64 assembly that assembles and links on the supported target.

### Invariants

Generated code preserves:

-   language semantics;
-   evaluation order;
-   control flow;
-   conversions;
-   memory behavior;
-   ABI requirements;
-   required runtime errors.

------------------------------------------------------------------------

# 8. End-to-End Translation Example

For:

``` text
int x
x lo 5 pettu

x > 0 ayite {
    x ni chupi
}
```

the conceptual progression is:

``` text
Source
 ↓
Tokens
 ↓
AST
 ↓
Semantic representation
 ↓
IR
 ↓
Optimized IR
 ↓
x86-64 assembly
```

IR can conceptually be:

``` text
const t1, 5
store x, t1

t2 = load x
t3 = compare t2 > 0
branch t3, THEN, END

THEN:
    t4 = load x
    output t4
    jump END

END:
```

The example demonstrates:

``` text
source syntax
    ↓
semantic meaning
    ↓
explicit operations
    ↓
optimized operations
    ↓
machine instructions
```

------------------------------------------------------------------------

# 9. Cross-Stage Invariants

## 9.1 Name resolution

By Stage 4, every identifier has a resolved meaning.

## 9.2 Types

By Stage 4, required expression types and conversions are known.

## 9.3 Evaluation order

Left-to-right observable evaluation survives all later stages.

## 9.4 Control flow

Source control constructs become explicit CFG structure before
optimization.

## 9.5 Memory

Source memory operations become explicit IR memory operations.

## 9.6 Conversions

Semantic conversions are represented explicitly before machine lowering.

## 9.7 Optimization

Optimization cannot change observable behavior.

## 9.8 Backend

The backend cannot reinterpret source-level semantics.

------------------------------------------------------------------------

# 10. Error Propagation

``` text
Lexical error
    → Lexer

Syntax error
    → Parser

Semantic error
    → Semantic analyzer

IR structural error
    → IR verifier/compiler-internal failure

Runtime error
    → Generated runtime
```

A later stage must not fabricate an earlier-stage source diagnostic.

------------------------------------------------------------------------

# 11. Testing Strategy

## Stage 3

Test:

-   declarations;
-   scopes;
-   shadowing;
-   redeclarations;
-   types;
-   conversions;
-   initialization;
-   functions;
-   recursion;
-   returns;
-   arrays;
-   loops;
-   strings.

## Stage 4

Test:

-   expression lowering;
-   evaluation order;
-   short-circuiting;
-   array address calculation;
-   CFG construction;
-   calls;
-   returns;
-   top-level execution;
-   IR verification.

## Stage 5

Compare observable behavior between unoptimized and optimized IR.

## Stage 6

Test the complete path:

``` text
source
 ↓
compiler
 ↓
assembly
 ↓
executable
 ↓
expected output/status
```

Include runtime-error cases.

------------------------------------------------------------------------

# 12. Complexity Considerations

With hash-based scope tables, symbol lookup is expected:

``` text
O(1) average
```

Recursive-descent parsing is approximately:

``` text
O(n)
```

for token count under the deterministic grammar.

Semantic analysis is generally linear in AST size for the baseline
checks.

CFG construction is approximately linear in generated IR size.

Standard iterative data-flow optimizations depend on CFG size and
analysis lattice but remain within conventional compiler analysis
techniques.

Linear-scan register allocation is approximately linear in the number of
live intervals.

------------------------------------------------------------------------

# 13. Decision Status and Semantic Freeze Boundary

This section distinguishes decisions explicitly approved earlier from the additional semantic decisions frozen in this design. No source-language semantic decision remains open within the current baseline.

A theoretical compiler design must not silently convert an implementation preference into a language rule.

## 13.1 Explicitly approved earlier

The following conversion decisions were explicitly approved:

| ID | Decision | Status |
|---|---|---|
| D1 | Assignment conversion | **APPROVED — literal C++ conversion system** |
| D2 | Condition conversion | **APPROVED — literal C++ conversion system** |
| D3 | Arithmetic conversion | **APPROVED — literal C++ conversion system** |
| D4 | Equality conversion | **APPROVED — literal C++ conversion system** |
| D5 | Relational conversion | **APPROVED — literal C++ conversion system** |
| D6 | Function argument conversion | **APPROVED — literal C++ conversion system** |
| D7 | Function return conversion | **APPROVED — literal C++ conversion system** |
| D8 | Bool ↔ numeric conversion | **APPROVED — literal C++ conversion system** |
| D9 | Char ↔ numeric conversion | **APPROVED — literal C++ conversion system** |

These are part of the Stage 3 semantic baseline.

## 13.2 Explicit cast syntax — APPROVED

| ID | Decision | Status |
|---|---|---|
| D10 | Explicit cast syntax | **APPROVED — C-style `(type) expression`** |

The syntax is now frozen. The conversion semantics remain the previously
approved literal C++ conversion system where a corresponding conversion exists.
The synchronized canonical language specification v0.7 and Stage 2 grammar
now contain this production.

## 13.3 Language-semantic decisions frozen in this design

The following decisions are now explicitly frozen for implementation:

| ID | Decision | Frozen choice |
|---|---|---|
| L1 | Explicit conversion | Supported; C-style syntax; approved C++-style conversion semantics |
| L2 | `padham` meaning | Immutable text value |
| L3 | `padham` literal | Quoted string literal |
| L4 | `padham` operations | `+`, `==`, `!=`, indexing, `podavu`, input/output |
| L5 | `padham` equality | Content equality |
| L6 | `padham` assignment | Value semantics |
| L7 | `padham` mutation | Not supported |
| L8 | `padham` indexing | Returns `char` |
| L9 | `padham` length | Standard-library facility `podavu(...)` |
| L10 | `padham` input | Complete line |
| L11 | `padham` conversions | `char ↔ padham` explicit conversion only; numeric↔text is not part of the baseline |
| L48 | `podavu` symbol resolution | Predeclared global builtin; registered before user declarations; ordinary lookup; same-scope user redeclaration is an error |
| L49 | Float algebraic optimization | Empty baseline whitelist; no algebraic identity involving potentially-float operands is permitted unless explicitly added by a future design revision |
| L12 | Range bounds | Start inclusive, end exclusive |
| L13 | Range variable | Implicitly introduced |
| L14 | Range variable scope | Loop construct/body only |
| L15 | Range step | Fixed `+1` |
| L16 | Descending range | Zero iterations when start ≥ end; no descending mode |
| L17 | Range-bound evaluation | Start/end evaluated once |
| L18 | Shadowing | Inner declarations may shadow outer declarations |
| L19 | Same-scope redeclaration | Semantic error |
| L20 | Local initialization | Definite initialization required before read |
| L21 | Global initialization | Zero-initialized |
| L22 | Forward function calls | Allowed; signatures collected first |
| L23 | Recursion | Allowed, including mutual recursion |
| L24 | Scalar parameters | Pass-by-value semantics |
| L25 | Array parameters | Non-copying array view/reference semantics |
| L26 | Non-void return | Every reachable path must return a value |
| L27 | Void return | May complete without a source value return |
| L28 | `void` usage | Function return type only |
| L29 | Logical operators | `&&` and `\|\|` are short-circuiting |
| L30 | Evaluation order | Left-to-right |
| L31 | Function arguments | Left-to-right |
| L32 | Array bounds | No automatic runtime bounds checking |
| L33 | Array layout | Contiguous row-major |
| L34 | Partial indexing | Produces a non-owning lower-dimensional view/reference |
| L35 | `int` | Signed 64-bit |
| L36 | `float` | IEEE-754 binary64 |
| L37 | Integer overflow | `+`, `-`, `*` wrap modulo 2^64 as signed 64-bit two's-complement arithmetic |
| L38 | Division/remainder errors | Divide/remainder by zero, and `INT64_MIN / -1`, are defined runtime arithmetic errors |
| L39 | Floating-point exceptional values | IEEE-754 behavior |
| L40 | `char` | 8-bit character unit |
| L41 | Top-level statements | Execute in source order in generated entry region |
| L42 | Runtime input conversion failure | Defined runtime error |
| L43 | Runtime error exit | Runtime diagnostic where available + non-zero termination status |
| L44 | `for-tho-modhalu-init` | Existing assignable scalar variable; no declaration |
| L45 | `for-assignment-init` | Existing assignable target; no declaration |
| L46 | `for-declaration-init` | Declares a loop-scoped variable; optional initializer follows definite-initialization rules |
| L47 | Range-loop variable mutability | Mutable within the loop; increment occurs after each body execution |

These are language-level or observable semantic choices. Backend mechanisms
used to realize them may vary without changing the source contract.

## 13.4 Decisions inherited from the canonical specification

The following are not newly invented here:

- source syntax and formal grammar, including the synchronized C-style
  explicit-cast production;
- expression precedence;
- `pratisari` having the three canonical initializer alternatives;
- `pratisari` requiring a normal expression as its condition;
- `unnanta varaku` belonging to `while`, not `pratisari`;
- `++`/`--` being available in `for-update`;
- standalone increment/decrement statements not being introduced;
- function calls being expressions;
- standalone expression statements being function calls;
- `expression ivvu` as the current return syntax;
- the current grammar provides one unsized array dimension in a function parameter; this is a syntax boundary, not an additional semantic ban on multidimensional array parameter types;
- top-level statements being permitted by `program`.

## 13.5 Implementation-level choices versus source semantics

The following are deliberately implementation choices rather than additional
language decisions:

- symbol-table data structures;
- AST metadata storage;
- semantic metadata representation;
- exact IR instruction class names;
- CFG data structures;
- optimization pass ordering when semantics are preserved;
- register allocation algorithm;
- stack-slot layout;
- runtime helper implementation;
- assembler syntax, provided the target contract is preserved.

The implementation agent must not change any frozen language-semantic choice
while making these decisions.

# 14. Deferred Features

The baseline excludes:

-   bitwise operators;
-   ternary operator;
-   comma operator;
-   compound assignment;
-   function overloading;
-   dynamic heap arrays as a source construct;
-   manual source-level memory management;
-   automatic array bounds checking;
-   arbitrary range-loop steps.

These are excluded features, not incomplete implementation requirements.

------------------------------------------------------------------------

# 15. Implementation Boundary

After this design is frozen:

``` text
Design owner
    ↓
freezes semantics
    ↓
Implementation agent
    ↓
implements exact design
    ↓
tests
    ↓
audit
```

The implementation agent must never decide what an unspecified language
construct means.

It may report:

``` text
"The design specifies X, but the current implementation requires Y."
```

The design owner resolves that contradiction before implementation
continues.

------------------------------------------------------------------------

# 16. Implementation-Readiness Criterion

The theoretical design is implementation-ready when:

1.  every source semantic choice is frozen;
2.  every Stage 3 analysis has a defined role;
3.  every source construct has a defined IR lowering;
4.  every IR operation has defined semantics;
5.  CFG construction is defined;
6.  optimization transformations and safety constraints are defined;
7.  memory representation is defined;
8.  function calling and return conventions are defined;
9.  runtime support boundaries are defined;
10. x86-64 ABI integration is defined;
11. stage contracts are explicit;
12. the implementation agent is not required to invent semantics.

This document is the theoretical bridge from the canonical Devara
language specification to an executable x86-64 compiler. All currently
identified language-semantic decisions for the remaining stages are frozen;
remaining implementation work must not invent source semantics. The canonical
language specification v0.7 and the Stage 2 syntax contract are synchronized
with the approved explicit-cast production and `podavu` library facility.
