"""Signatures of the C runtime helpers callable via ``RtCall`` (runtime/devara_rt.c)."""

from __future__ import annotations

from compiler.ir.ir import IRType as T

# name -> (parameter types, return type)
RUNTIME: dict[str, tuple[tuple[T, ...], T]] = {
    "dv_rt_output_i64": ((T.I64,), T.VOID),
    "dv_rt_output_f64": ((T.F64,), T.VOID),
    "dv_rt_output_bool": ((T.BOOL,), T.VOID),
    "dv_rt_output_char": ((T.CHAR,), T.VOID),
    "dv_rt_output_str": ((T.STR,), T.VOID),
    "dv_rt_input_i64": ((), T.I64),
    "dv_rt_input_f64": ((), T.F64),
    "dv_rt_input_bool": ((), T.BOOL),
    "dv_rt_input_char": ((), T.CHAR),
    "dv_rt_input_str": ((), T.STR),
    "dv_rt_strcat": ((T.STR, T.STR), T.STR),
    "dv_rt_streq": ((T.STR, T.STR), T.BOOL),
    "dv_rt_strindex": ((T.STR, T.I64), T.CHAR),
    "dv_rt_strlen": ((T.STR,), T.I64),
    "dv_rt_char2str": ((T.CHAR,), T.STR),
    "dv_rt_str2char": ((T.STR,), T.CHAR),
    "dv_rt_checkdim": ((T.I64,), T.VOID),
    # heap arrays (P22): allocation is explicit in the IR, freed at scope exit
    "dv_rt_newarray": ((T.I64,), T.ADDR),
    "dv_rt_freearray": ((T.ADDR,), T.VOID),
    "dv_rt_freearray_str": ((T.ADDR, T.I64), T.VOID),      # releases the elements, then frees
    "dv_rt_release_elems": ((T.ADDR, T.I64), T.VOID),      # releases elements of a frame/static array
    # padham reference counting (P22): results of producing calls are owned (+1)
    "dv_rt_retain": ((T.STR,), T.VOID),
    "dv_rt_release": ((T.STR,), T.VOID),
    # immortal runtime string for a compiler string constant; the only legal use of a str Const
    "dv_rt_strlit": ((T.STR,), T.STR),
    # end of the program entry: leak accounting hook (DEVARA_RT_STATS=1)
    "dv_rt_shutdown": ((), T.VOID),
}

# Calls with no observable effect and no possible runtime error: removable when unused.
# (A removable call that produces an owned padham is only ever removed together with its
# consumers: the release that balances it uses the result, which keeps the call alive.)
PURE: frozenset[str] = frozenset({
    "dv_rt_strcat", "dv_rt_streq", "dv_rt_strlen", "dv_rt_char2str",
})

# Reference-count and allocation effects. These are side effects in the IR effect model: they are
# never in PURE (so never removed), and the optimizer never moves instructions across calls, so
# a retain/release stays in place relative to the uses it guards.
MEMORY_EFFECTS: frozenset[str] = frozenset({
    "dv_rt_retain", "dv_rt_release", "dv_rt_release_elems", "dv_rt_newarray",
    "dv_rt_freearray", "dv_rt_freearray_str", "dv_rt_strlit", "dv_rt_shutdown",
})


def has_side_effects(name: str) -> bool:
    return name not in PURE
