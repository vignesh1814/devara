"""Helpers to inspect `devara parse --json` output against the §3.5 contract."""
import json
from tests.validation.helpers import cli

EXPR_NODES = {"Literal", "Identifier", "ArrayAccess", "FunctionCall", "BinaryExpression",
              "UnaryExpression", "CastExpression"}
OPS = {"ADD": "+", "SUB": "-", "MUL": "*", "DIV": "/", "MOD": "%", "LT": "<", "GT": ">", "LE": "<=",
       "GE": ">=", "EQ": "==", "NE": "!=", "AND": "&&", "OR": "||"}
UOPS = {"NOT": "!", "NEGATE": "-", "POSITIVE": "+"}
PRIM = {"INT": "int", "FLOAT": "float", "BOOL": "bool", "CHAR": "char", "PADHAM": "padham", "VOID": "void"}


def ast(src: str):
    p = cli("parse", src, ("--json",))
    assert p.rc == 0, f"parse failed:\n{p.err}\n--- source ---\n{src}"
    return json.loads(p.out)["data"]


def first_item(src: str):
    return ast(src)["items"][0]


def sx(e) -> str:
    """Fully parenthesised rendering of an expression subtree."""
    n = e["_node"]
    if n == "Literal":
        return e["lexeme"]
    if n == "Identifier":
        return e["name"]
    if n == "ArrayAccess":
        return e["base"]["name"] + "".join("[" + sx(i) + "]" for i in e["indices"])
    if n == "FunctionCall":
        return e["callee"]["name"] + "(" + ", ".join(sx(a) for a in e["arguments"]) + ")"
    if n == "BinaryExpression":
        return "(" + sx(e["left"]) + " " + OPS[e["operator"]] + " " + sx(e["right"]) + ")"
    if n == "UnaryExpression":
        return "(" + UOPS[e["operator"]] + sx(e["operand"]) + ")"
    if n == "CastExpression":
        t = e["target_type"]
        return "((" + PRIM[t["primitive"]] + ")" + sx(e["expression"]) + ")"
    raise AssertionError("unexpected expression node " + n)


def expr_of(src_expr: str) -> str:
    """Parse `<expr> ni chupi` and render the expression."""
    it = first_item(src_expr + " ni chupi\n")
    assert it["_node"] == "Output", it["_node"]
    return sx(it["value"])


def walk(n, f, parent=None):
    if isinstance(n, dict):
        if "_node" in n:
            f(n, parent)
        for v in n.values():
            walk(v, f, n)
    elif isinstance(n, list):
        for v in n:
            walk(v, f, parent)


def check_invariants(data):
    """AST invariants 1-8 of design §3.5.12 (+ span sanity)."""
    errs = []

    def pos(sp):
        return (sp["start_line"], sp["start_column"]), (sp["end_line"], sp["end_column"])

    def f(n, parent):
        t = n["_node"]
        if t == "Span":
            return
        sp = n.get("span")
        if sp is None:
            errs.append(f"{t}: missing span")
        else:
            s, e = pos(sp)
            if not (s[0] >= 1 and s[1] >= 1 and e >= s):
                errs.append(f"{t}: bad span {sp}")
        if t in ("Assignment", "Input"):
            if n["target"]["_node"] not in ("Identifier", "ArrayAccess"):
                errs.append(f"{t}: bad target")
        if t in ("IncrementUpdate", "DecrementUpdate", "AssignmentUpdate"):
            if n["target"]["_node"] not in ("Identifier", "ArrayAccess"):
                errs.append(f"{t}: bad target")
        if t == "ForLoop":
            for k in ("init", "condition", "update"):
                if n.get(k) is None:
                    errs.append(f"ForLoop.{k} is None")
            if n["init"]["_node"] not in ("ForThoModhaluInit", "ForAssignmentInit", "ForDeclarationInit"):
                errs.append("ForLoop.init variant")
            if n["update"]["_node"] not in ("AssignmentUpdate", "IncrementUpdate", "DecrementUpdate"):
                errs.append("ForLoop.update variant")
        if t == "IfStatement":
            eb = n["else_branch"]
            if eb is not None and eb["_node"] not in ("Block", "IfStatement"):
                errs.append("else_branch variant")
        if t == "ExpressionStatement" and n["expression"]["_node"] != "FunctionCall":
            errs.append("ExpressionStatement not a call")
        if t == "ReturnStatement" and n.get("value") is None:
            errs.append("bare return")
        if t in ("ForThoModhaluInit", "ForAssignmentInit") and n["target"]["_node"] != "Identifier":
            errs.append("for-init target must be Identifier")
        if t == "FunctionCall" and n["callee"]["_node"] != "Identifier":
            errs.append("callee must be Identifier")
        if t == "ArrayAccess" and (n["base"]["_node"] != "Identifier" or not n["indices"]):
            errs.append("ArrayAccess shape")
        if t in ("Group", "Grouped", "Paren", "ParenExpression", "ParenthesizedExpression", "GroupedExpression"):
            errs.append("grouping wrapper node present")
        if t == "Literal" and n["kind"] == "BOOL" and n["lexeme"].lower() not in ("nijam", "abaddham"):
            errs.append("bool literal lexeme not preserved")

    walk(data, f)
    return errs
