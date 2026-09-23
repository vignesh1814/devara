
# Devara Language Specification

**Specification version:** 0.5  
**Status:** Canonical project specification; formal grammar reviewed for internal consistency and written in EBNF notation adapted from ISO/IEC 14977  
**Language:** Devara  
**Specification notation:** EBNF-style notation, following ISO/IEC 14977:1996

> This document is the canonical definition of the Devara language.
> Implementation behavior, tests, examples, and legacy documents should be
> brought into agreement with this specification. This version records the
> language currently established by the project; it does not intentionally
> introduce new language features.

---

# 1. Introduction

Devara is a Romanized-Telugu, statement-oriented programming language with
Subject–Object–Verb-style surface syntax.

Examples:

```text
x lo 10 pettu
n ni chaduvu
n ni chupi
condition ayite { ... }
condition unnanta varaku { ... }
prati i 1 nundi n varaku { ... }
pratisari (init; condition; update) { ... }
```

The language is intended to be compiled through distinct stages:

```text
Devara source
→ Lexer
→ Parser / AST
→ Semantic Analysis
→ IR
→ x86-64 Assembly
→ Assembler / Linker
→ Executable
```

This specification primarily defines the language itself. Compiler-internal
representations are not part of the source-language definition.

---

# 2. Lexical Structure

## 2.1 Whitespace

Spaces and tabs may separate tokens and are ignored.

Newlines separate source text and are ignored by the lexical grammar except
for their effect on source locations.

## 2.2 Comments

A comment begins with `#` and continues to the end of the line.

Example:

```text
x lo 10 pettu # assign ten to x
```

Comments do not produce language tokens.

---

## 2.3 Identifiers

An identifier begins with an ASCII letter or underscore and may then contain
ASCII letters, digits, and underscores.

Conceptually:

```text
identifier = letter | "_" , { letter | digit | "_" } ;
```

where:

```text
letter = "A" ... "Z" | "a" ... "z" ;
digit  = "0" ... "9" ;
```

Identifiers are distinct from reserved keywords.

---

## 2.4 Keywords

The following words are reserved:

```text
int
float
bool
char
padham
void

nijam
abaddham

ayite
lekunte
unnanta
varaku

prati
pratisari
nundi
modhalu

lo
pettu
ni
tho

chaduvu
chupi

charya
ivvu

aapu
saagu
```

Keyword recognition is case-insensitive in the current lexer. Consequently,
all case variants of a reserved keyword (for example `ayite`, `Ayite`, and
`AYITE`) are reserved and cannot be used as identifiers.

---

# 3. Literals

## 3.1 Integer literals

Integer literals may be written in decimal, octal, or hexadecimal form.
The formal lexical grammar makes these forms mutually exclusive.

Examples:

```text
10
42
075
0xFF
0X2A
```

The lexical spelling is preserved by the lexer.

## 3.2 Floating-point literals

A floating-point literal contains digits, a decimal point, and digits.

Examples:

```text
3.14
0.5
10.0
```

## 3.3 Boolean literals

The boolean literals are:

```text
nijam
abaddham
```

They represent true and false respectively.

## 3.4 Character literals

Character literals are enclosed in single quotes.

Examples:

```text
'A'
'7'
'\n'
'\x41'
```

The language supports escaped character forms accepted by the lexer.
A physical newline cannot occur inside a character literal; use `\n` instead.

## 3.5 String literals

String literals are enclosed in double quotes.

Example:

```text
"Hello"
```

Escaped characters may occur inside strings according to the lexical rules.
String literals are strictly single-line; a physical newline cannot occur inside a string literal. If a newline is required, the `\n` escape sequence must be used.

---

# 4. Operators

Devara defines the following operators.

## Arithmetic

```text
+
-
*
/
%
```

## Relational

```text
<
>
<=
>=
```

## Equality

```text
==
!=
```

## Logical

```text
&&
||
!
```

## Increment / decrement

```text
++
--
```

The language does not use `=` as its assignment operator.

---

# 5. Punctuation

The following punctuation symbols are used:

```text
(
)
[
]
{
}
;
,
```

---

# 6. Types

The primitive types are:

```text
int
float
bool
char
padham
void
```

`padham` represents the language's string/text type.

`void` represents the absence of a return value.

---

# 7. Arrays

Arrays are written by following a type/name with one or more dimensions.

Examples:

```text
int arr[10]
int matrix[10][20]
```

An array dimension is an expression.

Function parameters may specify an array dimension without a size:

```text
int arr[]
```

Multidimensional arrays are supported.

---

# 8. Expressions

Expressions include:

- literals
- identifiers
- grouped expressions
- array indexing
- function calls
- unary operators
- binary operators

## 8.1 Operator precedence

From lowest precedence to highest:

```text
1. logical OR        ||
2. logical AND       &&
3. equality          == !=
4. relational        < > <= >=
5. additive          + -
6. multiplicative    * / %
7. unary             ! + -
8. primary
```

Primary expressions include:

```text
literals
identifiers
grouped expressions
array indexing
function calls
```

Parentheses may be used to explicitly control grouping.

---

# 9. Statements

## 9.1 Variable declaration

A declaration specifies a type and identifier.

Examples:

```text
int x
float average
bool found
char c
padham name
```

Array declarations may include dimensions:

```text
int arr[10]
int matrix[10][20]
```

---

## 9.2 Assignment

Assignment uses:

```text
target lo value pettu
```

Examples:

```text
x lo 10 pettu
x lo x + 1 pettu
arr[0] lo 42 pettu
```

---

## 9.3 Input

Input uses:

```text
target ni chaduvu
```

Example:

```text
n ni chaduvu
```

---

## 9.4 Output

Output uses:

```text
expression ni chupi
```

Examples:

```text
n ni chupi
x + 1 ni chupi
"Hello" ni chupi
```

---

## 9.5 If / else

Conditional statements use:

```text
condition ayite {
    ...
}
```

With an else branch:

```text
condition ayite {
    ...
} lekunte {
    ...
}
```

The condition appears before `ayite`.

Else-if structures may be represented through nested conditional statements.

---

## 9.6 While loop

The while form is:

```text
condition unnanta varaku {
    ...
}
```

`unnanta varaku` belongs to the while syntax.

Example:

```text
x < 10 unnanta varaku {
    x lo x + 1 pettu
}
```

---

## 9.7 Range loop

The range-loop form is:

```text
prati identifier start nundi end varaku {
    ...
}
```

Example:

```text
prati i 1 nundi n varaku {
    i ni chupi
}
```

---

## 9.8 Three-part loop

The three-part loop uses:

```text
pratisari (init; condition; update) {
    ...
}
```

Example:

```text
pratisari (i 2 tho modhalu; i <= n; i lo i + 1 pettu) {
    i ni chupi
}
```

The condition is a normal expression.

`unnanta varaku` is **not** part of the `pratisari` condition.

The update may use the language's assignment or increment/decrement forms.

Examples:

```text
pratisari (i 0 tho modhalu; i < n; i lo i + 1 pettu) {
    ...
}
```

Prefix/postfix increment and decrement forms are supported by the loop-update
syntax.

---

## 9.9 Break

```text
aapu
```

terminates the nearest enclosing loop.

## 9.10 Continue

```text
saagu
```

continues with the next iteration of the nearest enclosing loop.

---

## 9.11 Return

A function returns a value using:

```text
expression ivvu
```

The current established syntax requires an expression before `ivvu`.
A bare `ivvu` form is not part of the current language grammar.

---

## 9.12 Blocks

A block is enclosed in braces:

```text
{
    ...
}
```

A block contains zero or more statements.

---

# 10. Functions

Functions use the keyword:

```text
charya
```

A function declaration has the general form:

```text
return_type identifier charya ( parameters ) {
    ...
}
```

Parameters have a type and identifier.

Example:

```text
int add charya (int a, int b) {
    a + b ivvu
}
```

Array parameters may be declared using:

```text
int arr[]
```

Function calls are expressions.

Example:

```text
add(2, 3)
```

A standalone function call may occur as an expression statement:

```text
add(2, 3)
```

---

# 11. Formal Grammar

This section gives the normative syntactic grammar of Devara using an
EBNF notation adapted from ISO/IEC 14977:1996. ISO/IEC 14977 defines EBNF
as a syntactic metalanguage for specifying the syntax of linear sequences
of symbols. See [ISO/IEC 14977:1996](https://www.iso.org/standard/26153.html).

The organization of this language specification also follows the general
principles in ISO/IEC TR 10176:2003 for programming-language standards,
including consistent terminology, structure, syntax, semantics, error
handling, options, processor dependence, and conformance. See
[ISO/IEC TR 10176:2003](https://www.iso.org/standard/37765.html).

## 11.1 EBNF notation used by this specification

The following ISO EBNF conventions are used:

```text
=       definition
;       end of definition
,       concatenation
|       alternation
[ ... ] optional sequence
{ ... } repetition (zero or more)
( ... ) grouping
"..."   terminal string
```

Nonterminal names are written in lowercase.

The grammar below describes syntactic structure. Lexical tokens such as
`identifier`, `integer-literal`, and `string-literal` are defined in the
lexical section.

## 11.2 Program structure

```text
program =
    { top-level-item } ;

top-level-item =
    declaration
  | function-declaration
  | statement ;
```

## 11.3 Blocks and statements

```text
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

## 11.4 Declarations

```text
declaration-statement =
    declaration ;

declaration =
    type, identifier, { array-dimension } ;

array-dimension =
    "[", expression, "]" ;
```

## 11.5 Assignment and input/output

```text
assignment-statement =
    assignment-target, "lo", expression, "pettu" ;

assignment-target =
    identifier
  | array-access ;

input-statement =
    input-target, "ni", "chaduvu" ;

input-target =
    identifier
  | array-access ;

output-statement =
    expression, "ni", "chupi" ;
```

## 11.6 Conditional statements

```text
if-statement =
    expression, "ayite", block,
    [ "lekunte", ( block | if-statement ) ] ;
```

## 11.7 While statements

```text
while-statement =
    expression, "unnanta", "varaku", block ;
```

The tokens `"unnanta"` and `"varaku"` occur only in this while-statement
production. They are not part of the `for-loop-statement` condition.

## 11.8 Range loops

```text
range-loop-statement =
    "prati", identifier, expression,
    "nundi", expression, "varaku", block ;
```

## 11.9 Three-part loops

```text
for-loop-statement =
    "pratisari", "(", for-init, ";",
    expression, ";", for-update, ")", block ;

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

for-update =
    assignment-update
  | increment-update
  | decrement-update ;

assignment-update =
    assignment-target, "lo", expression, "pettu" ;

increment-update =
    "++", assignment-target
  | assignment-target, "++" ;

decrement-update =
    "--", assignment-target
  | assignment-target, "--" ;
```

The implementation currently supports increment/decrement forms as loop
updates. Standalone increment/decrement statements are not introduced by
this grammar.

## 11.10 Break, continue, and return

```text
break-statement =
    "aapu" ;

continue-statement =
    "saagu" ;

return-statement =
    expression, "ivvu" ;
```

## 11.11 Expression statements

```text
expression-statement =
    function-call ;
```

A standalone expression statement is currently limited to a function call.

## 11.12 Functions

```text
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
syntax. Multidimensional arrays remain supported for array declarations and
array access.

## 11.13 Types

```text
type =
    "int"
  | "float"
  | "bool"
  | "char"
  | "padham"
  | "void" ;
```

## 11.14 Expressions

The expression grammar is written so that the precedence is explicit.

```text
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

equality-operator =
    "=="
  | "!=" ;

relational-expression =
    additive-expression,
    { relational-operator, additive-expression } ;

relational-operator =
    "<"
  | ">"
  | "<="
  | ">=" ;

additive-expression =
    multiplicative-expression,
    { additive-operator, multiplicative-expression } ;

additive-operator =
    "+"
  | "-" ;

multiplicative-expression =
    unary-expression,
    { multiplicative-operator, unary-expression } ;

multiplicative-operator =
    "*"
  | "/"
  | "%" ;

unary-expression =
    unary-operator, unary-expression
  | primary-expression ;

unary-operator =
    "!"
  | "+"
  | "-" ;
```

## 11.15 Primary expressions

```text
primary-expression =
    literal
  | identifier
  | grouped-expression
  | array-access
  | function-call ;

grouped-expression =
    "(", expression, ")" ;

array-access =
    identifier, "[", expression, "]",
    { "[", expression, "]" } ;

function-call =
    identifier, "(", [ argument-list ], ")" ;

argument-list =
    expression, { ",", expression } ;
```

## 11.16 Literals

The source forms of literals are introduced in Section 3 and formalized in Sections 11.16 and 11.17.

```text
literal =
    integer-literal
  | floating-literal
  | boolean-literal
  | character-literal
  | string-literal ;

boolean-literal =
    "nijam"
  | "abaddham" ;

character-literal =
    "'", character-content, "'" ;

string-literal =
    '"', { string-character }, '"' ;

character-content =
    character-literal-character
  | escape-sequence ;

string-character =
    string-literal-character
  | escape-sequence ;

character-literal-character =
    any-character-except-single-quote-backslash ;

string-literal-character =
    any-character-except-double-quote-backslash ;

escape-sequence =
    "\\", escape-character
  | "\\x", hexadecimal-digit, hexadecimal-digit ;

escape-character =
    any-character-except-single-quote-double-quote-backslash ;
```

## 11.17 Lexical grammar

The lexical grammar is stated separately from the syntactic grammar.

```text
identifier =
    identifier-start-character,
    { identifier-part-character } ;

identifier-start-character =
    letter
  | "_" ;

identifier-part-character =
    letter
  | digit
  | "_" ;

letter =
    "A" | "B" | "C" | "D" | "E" | "F" | "G" | "H" | "I" | "J"
  | "K" | "L" | "M" | "N" | "O" | "P" | "Q" | "R" | "S" | "T"
  | "U" | "V" | "W" | "X" | "Y" | "Z"
  | "a" | "b" | "c" | "d" | "e" | "f" | "g" | "h" | "i" | "j"
  | "k" | "l" | "m" | "n" | "o" | "p" | "q" | "r" | "s" | "t"
  | "u" | "v" | "w" | "x" | "y" | "z" ;

digit =
    "0" | "1" | "2" | "3" | "4" | "5" | "6" | "7" | "8" | "9" ;

integer-literal =
    decimal-integer
  | octal-integer
  | hexadecimal-integer ;

decimal-integer =
    "0"
  | nonzero-digit, { digit } ;

nonzero-digit =
    "1" | "2" | "3" | "4" | "5" | "6" | "7" | "8" | "9" ;

octal-integer =
    "0", octal-digit, { octal-digit } ;

octal-digit =
    "0" | "1" | "2" | "3" | "4" | "5" | "6" | "7" ;

hexadecimal-integer =
    "0", ( "x" | "X" ), hexadecimal-digit, { hexadecimal-digit } ;

hexadecimal-digit =
    digit
  | "a" | "b" | "c" | "d" | "e" | "f"
  | "A" | "B" | "C" | "D" | "E" | "F" ;

floating-literal =
    digit, { digit }, ".", digit, { digit } ;
```

The productions above make the currently documented escape forms explicit.
The terminal `any-character-except-single-quote-double-quote-backslash` is a
character-class placeholder for lexical characters accepted by the current
lexer; a future revision may replace it with an explicit character-set
production if the language needs a fully character-by-character lexical
grammar.

---

# 12. Semantic Rules

Semantic analysis is a separate compiler stage.

The following are language-level concerns to be enforced by semantic
analysis rather than by the lexer:

- type compatibility
- identifier declaration and use
- scope
- function signatures
- function return types
- array indexing validity
- array dimensionality
- validity of `break` and `continue` contexts
- validity of return statements
- other context-dependent constraints

The lexer is responsible for tokenization.
The parser is responsible for syntactic structure.
Semantic analysis is responsible for context-dependent meaning.

---

# 13. Stage Boundaries

The compiler stages have independent outputs.

## Lexer

```text
source text → token stream
```

The lexer defines tokens, lexical spelling, and source locations.

## Parser

```text
token stream → AST
```

The parser constructs the syntactic structure of the program.

## Semantic analysis

```text
AST → semantically validated representation
```

Semantic analysis determines whether the parsed program is meaningful
according to the language rules.

## IR generation

```text
semantic representation → IR
```

## Code generation

```text
IR → target assembly
```

No later stage's internal representation should redefine the contract of an
earlier stage.

---

# 14. Specification Authority

This document is the canonical Devara language specification.

The following sources are subordinate to this document:

- implementation code
- tests
- examples
- previous prompts
- legacy specification documents

If implementation and specification disagree, the disagreement must be
identified and resolved deliberately; implementation behavior must not
silently redefine the language.

If this specification is changed, the language version should be updated and
affected implementation/tests should be reviewed.

---

# 15. Current Known Status

The currently established implementation status is:

```text
Lexer                 implemented
Parser / AST          implemented
Semantic analysis     future stage
IR                    future stage
x86-64 code generation future stage
```

The parser currently supports the established language constructs described
above, including arrays, multidimensional arrays, functions, conditionals,
loops, break/continue, expressions, and function calls.

This specification should be expanded only when a language rule is actually
decided. It should not be used to silently introduce new syntax or semantics.
