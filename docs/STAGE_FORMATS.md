# Stage formats and CLI artifacts

Every stage output can be printed (`devara <stage> FILE`), serialized (`--json`) and fed back
into the next stage (`devara <next-stage> artifact.json`). Source files are read as bytes and
decoded as latin-1 (one byte = one character unit).

## Envelope

```json
{"devara": "tokens|ast|typed|ir", "version": 1, "file": "<origin>", "data": <payload>}
```

`data` is a generic dataclass encoding: an object `{"_node": "<ClassName>", <field>: ...}` per
dataclass; enums are their string values; lists are arrays; non-finite floats are
`{"_float": "nan|inf|-inf"}`; bytes are `{"_bytes": "<hex>"}`. Class names are unique across
stages (`compiler/serialize.py` refuses duplicates).

| Command | Input accepted | `--json` payload |
|---|---|---|
| `lex` | source | `list[Token]` (`type`, `lexeme`, `line`, `column`) |
| `parse` | source, tokens JSON | `Program` (design §3.5; every node has a half-open `span`) |
| `sema` | source, tokens/AST JSON | `TypedProgram` |
| `ir` | source, tokens/AST/typed JSON | `IRModule` (unoptimized) |
| `opt` | any of the above, IR JSON | `IRModule` (optimized, `-O1` pipeline) |
| `asm` | any of the above, IR JSON | (text) x86-64 assembly; `-O0` skips optimization |
| `build` | any of the above, IR JSON, `.s` | executable |
| `run` | source (or any of the above) | program output / exit status pass through |

Asking for an earlier stage than the input artifact holds is a usage error (exit 2).

## Typed tree (`TypedProgram`)

* `symbols: list[Symbol]` — `id` (= list index), `name`, `kind` (`variable|parameter|function|builtin`),
  `type`, `scope_depth`, `is_global`, `owner` (defining function / `__entry`), `span`. Symbol 0 is
  the builtin `podavu`.
* `globals: list[int]` — global variable symbol ids in declaration order.
* `functions: list[TFunction]` — `symbol`, `name`, `params` (symbol ids), `ret`, `body: TBlock`.
* `entry: TBlock` — top-level statements in source order (global declarations included).
* Types: `PrimType{name}` (`int float bool char padham void`), `ArrayType{element, rank}`,
  `FuncType{params, ret}`.
* Expressions all carry `type`: `TLiteral` (int/char → int, float, bool, padham → bytes), `TVar`,
  `TIndex` (element lvalue when `len(indices) == rank`, else a partial view), `TStringIndex`, `TUnary`
  (`NEG|NOT`), `TBinary`, `TConvert` (`explicit` flag; every implicit conversion is one of these),
  `TCall`.
* Statements: `TDecl`, `TAssign`, `TInput`, `TOutput`, `TIncDec`, `TIf`, `TWhile`, `TRange`, `TFor`,
  `TBreak`/`TContinue` (carry the target `loop_id`), `TReturn`, `TExprStmt`, `TBlock`.
* Guarantees: conditions are `bool`; assignment values already have the target type; array
  dimensions/indices are `int`; operands of a binary operator share one type.

## IR (`IRModule`)

Non-SSA three-address code. `globals: list[IRGlobal]` (`scalar | array_static | array_ptr`),
`functions: list[IRFunction]` (user functions + the generated `$entry`). Blocks (`BasicBlock`) end
in exactly one of `Jump | Branch | Return`. Operands: `Const`, `Reg` (variables and temporaries,
each name has one type), `GlobalRef` (address of global storage). Instructions: `Copy`, `UnOp`,
`BinOp`, `Cmp`, `Convert`, `Load`, `Store`, `PtrAdd` (`base + index*8`), `NewArray`, `Call`,
`RtCall` (runtime helpers, signatures in `compiler/ir/runtime.py`). `devara ir` prints a stable text
form. The verifier (`compiler/ir/verify.py`) runs after lowering and after every optimizer pass;
a failure is an internal compiler error (exit 3).

## Exit status

`0` success · `1` user-program error (lexical/syntax/semantic; stderr lines
`FILE:LINE:COL: <stage> error [CATEGORY]: message`) · `2` usage/I-O error · `3` internal compiler error.
`run` returns the program's own status (runtime error: stderr `devara: runtime error: <msg>`, status 1).
