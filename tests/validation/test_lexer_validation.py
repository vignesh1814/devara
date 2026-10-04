"""Lexical structure validation (spec §2, §3, §4, §5, §11.16-11.17; P13-P15, P30)."""
import json
import pytest
from tests.validation.helpers import cli, rejects, accepts, LEX_CATS


def lex(src):
    """-> list of (line, col, type, lexeme) excluding EOF, via `lex --json`."""
    p = cli("lex", src, ("--json",))
    assert p.rc == 0, p.err
    toks = json.loads(p.out)["data"]
    assert toks[-1]["type"] == "EOF"
    return [(t["line"], t["column"], t["type"], t["lexeme"]) for t in toks[:-1]]


def lexemes(src):
    return [t[3] for t in lex(src)]


# ---------------------------------------------------------------- whitespace / comments (§2.1, §2.2)
@pytest.mark.parametrize("src,expected", [
    ("a b", ["a", "b"]),
    ("a\tb", ["a", "b"]),
    ("a\nb", ["a", "b"]),
    ("a   \t \n\n  b", ["a", "b"]),
    ("a#comment\nb", ["a", "b"]),
    ("# only comment", []),
    ("#c1\n#c2\nx", ["x"]),
    ("x # trailing ## # still comment ' \" \\ @ $\ny", ["x", "y"]),
    ("", []),
    ("   \n\n\t", []),
    ("a\r\nb\r\n", ["a", "b"]),          # P30: CRLF is a newline
    ("x#c\r\ny", ["x", "y"]),
])
def test_whitespace_and_comments(src, expected):
    assert lexemes(src) == expected


def test_crlf_positions_count_lines_once():
    toks = lex("a\r\nb\r\n  c")
    assert [(t[0], t[1]) for t in toks] == [(1, 1), (2, 1), (3, 3)]


def test_lone_carriage_return_is_invalid_character():
    rejects("a\rb\n", "lexical", "INVALID_CHARACTER", upto="lex")


def test_positions_are_one_based_and_columns_advance():
    toks = lex("int xyz lo 5 pettu\n  y")
    assert [(t[0], t[1], t[3]) for t in toks] == [
        (1, 1, "int"), (1, 5, "xyz"), (1, 9, "lo"), (1, 12, "5"), (1, 14, "pettu"), (2, 3, "y")]


def test_tab_counts_as_one_column():
    toks = lex("\tx")
    assert toks[0][1] == 2


# ---------------------------------------------------------------- identifiers & keywords (§2.3, §2.4; P14)
@pytest.mark.parametrize("ident", ["a", "A", "_", "_x", "x_", "abc123", "a1b2c3", "__init__", "X_Y_Z", "i", "n0",
                                   "ayit", "ayitee", "intx", "int_", "pettu1", "podavu", "main", "printf",
                                   "x" * 200])
def test_identifier_forms(ident):
    t = lex(ident)
    assert len(t) == 1 and t[0][3] == ident and t[0][2] == "IDENTIFIER"


KEYWORDS = ["int", "float", "bool", "char", "padham", "void", "nijam", "abaddham", "ayite", "lekunte",
            "unnanta", "varaku", "prati", "pratisari", "nundi", "modhalu", "lo", "pettu", "ni", "tho",
            "chaduvu", "chupi", "charya", "ivvu", "aapu", "saagu"]


def test_keyword_count_is_26():
    assert len(KEYWORDS) == 26


@pytest.mark.parametrize("kw", KEYWORDS)
@pytest.mark.parametrize("variant", ["lower", "upper", "title", "mixed"])
def test_keywords_are_case_insensitive_and_reserved(kw, variant):
    v = {"lower": kw, "upper": kw.upper(), "title": kw.capitalize(),
         "mixed": "".join(c.upper() if i % 2 else c for i, c in enumerate(kw))}[variant]
    t = lex(v)
    assert len(t) == 1
    assert t[0][2] != "IDENTIFIER", f"{v} must be a keyword token"
    assert t[0][3] == v   # lexeme spelling preserved


@pytest.mark.parametrize("kw", KEYWORDS)
def test_keyword_cannot_be_identifier_in_declaration(kw):
    if kw in ("int", "float", "bool", "char", "padham", "void"):
        src = f"int {kw}\n"
    else:
        src = f"int {kw}\n"
    p = cli("parse", src)
    assert p.rc == 1


def test_keyword_prefix_is_identifier():
    for w in ["integer", "intx", "lox", "nijams", "prati2", "pratisarii", "ivvuu", "ni_", "tho1"]:
        assert lex(w)[0][2] == "IDENTIFIER", w


def test_identifiers_are_case_sensitive():
    p = cli("sema", "int x\nint X\nx lo 1 pettu\nX lo 2 pettu\n")
    assert p.rc == 0


# ---------------------------------------------------------------- integer literals (§3.1; P15, P36)
@pytest.mark.parametrize("lit", ["0", "1", "42", "10", "123456789", "9223372036854775807", "007", "075", "00",
                                 "0777", "0x0", "0xFF", "0Xff", "0X2A", "0xdeadBEEF", "0x7FFFFFFFFFFFFFFF",
                                 "0x1", "0XAbCdEf"])
def test_integer_literals_single_token(lit):
    t = lex(lit)
    assert len(t) == 1 and t[0][3] == lit and "INT" in t[0][2]


@pytest.mark.parametrize("src,expected", [
    ("123abc", ["123", "abc"]),           # P15
    ("0x", ["0", "x"]),
    ("0xg", ["0", "xg"]),
    ("1_000", ["1", "_000"]),
    ("12.", None),
])
def test_integer_adjacent_tokens(src, expected):
    if expected is None:
        return
    assert lexemes(src) == expected


@pytest.mark.parametrize("src", ["09", "078", "0189"])
def test_non_octal_digit_after_leading_zero(src):
    # No grammar rule covers this: either two tokens (maximal munch of the lexical grammar, P15) or the
    # dedicated INVALID_NUMBER lexical error is acceptable; a crash or silent merge is not.
    p = cli("lex", src + "\n", ("--json",))
    if p.rc == 0:
        toks = json.loads(p.out)["data"]
        assert len(toks) > 2
    else:
        assert p.rc == 1 and any(d[1] == "INVALID_NUMBER" for d in p.diags())


def test_lexer_preserves_literal_spelling():
    assert lexemes("0XFF 075 0") == ["0XFF", "075", "0"]


# ---------------------------------------------------------------- float literals (§3.2)
@pytest.mark.parametrize("lit", ["0.0", "3.14", "0.5", "10.0", "123.456", "00.5", "1.0", "999999.000001"])
def test_float_literals(lit):
    t = lex(lit)
    assert len(t) == 1 and t[0][3] == lit and "FLOAT" in t[0][2]


@pytest.mark.parametrize("src", ["1.", ".5", "1.e5", "1e5", "1.5e3"])
def test_non_grammar_float_forms_not_a_single_float(src):
    # No exponent, no bare "1." / ".5" forms exist in the lexical grammar.
    p = cli("lex", src + "\n", ("--json",))
    if p.rc == 0:
        toks = json.loads(p.out)["data"]
        assert not (len(toks) == 2 and "FLOAT" in toks[0]["type"] and toks[0]["lexeme"] == src)
    else:
        assert p.rc == 1


# ---------------------------------------------------------------- booleans (§3.3)
def test_bool_literal_tokens():
    t = lex("nijam abaddham NIJAM Abaddham")
    assert [x[3] for x in t] == ["nijam", "abaddham", "NIJAM", "Abaddham"]


# ---------------------------------------------------------------- char literals (§3.4; P13)
@pytest.mark.parametrize("lit", ["'A'", "'7'", "' '", "'\\n'", "'\\t'", "'\\r'", "'\\b'", "'\\f'", "'\\0'",
                                 "'\\\\'", "'\\''", "'\\\"'", "'\\x41'", "'\\x00'", "'\\xFF'", "'\\xaB'",
                                 "'\"'", "'{'", "'#'", "'('", "'@'", "'$'"])
def test_char_literals_valid(lit):
    t = lex(lit)
    assert len(t) == 1 and t[0][3] == lit and "CHAR" in t[0][2]


@pytest.mark.parametrize("src,cats", [
    ("''", {"INVALID_CHAR_LITERAL"}),
    ("'ab'", {"INVALID_CHAR_LITERAL", "UNTERMINATED_CHAR"}),
    ("'a", {"UNTERMINATED_CHAR", "INVALID_CHAR_LITERAL"}),
    ("'", {"UNTERMINATED_CHAR", "INVALID_CHAR_LITERAL"}),
    ("'\\q'", {"INVALID_ESCAPE"}),
    ("'\\x4'", {"INVALID_ESCAPE", "INVALID_CHAR_LITERAL", "UNTERMINATED_CHAR"}),
    ("'\\xZZ'", {"INVALID_ESCAPE", "INVALID_CHAR_LITERAL"}),
    ("'\\", {"UNTERMINATED_CHAR", "INVALID_ESCAPE", "INVALID_CHAR_LITERAL"}),
    ("'\n'", {"UNTERMINATED_CHAR", "INVALID_CHAR_LITERAL"}),
    ("'\\a'", {"INVALID_ESCAPE"}),
    ("'\\v'", {"INVALID_ESCAPE"}),
    ("'\\1'", {"INVALID_ESCAPE"}),
])
def test_char_literals_invalid(src, cats):
    rejects(src + "\n", "lexical", cats, upto="lex")


# ---------------------------------------------------------------- string literals (§3.5)
@pytest.mark.parametrize("lit", ['""', '"Hello"', '"a b c"', '"tab\\there"', '"nl\\n"', '"q\\"q"', '"b\\\\s"',
                                 '"\\x41\\x42"', '"it\'s"', '"# not a comment"', '"{}[]()"', '"\\0"', '"\\r\\b\\f"',
                                 '"' + "x" * 500 + '"'])
def test_string_literals_valid(lit):
    t = lex(lit)
    assert len(t) == 1 and t[0][3] == lit and "STRING" in t[0][2]


@pytest.mark.parametrize("src,cats", [
    ('"abc', {"UNTERMINATED_STRING"}),
    ('"', {"UNTERMINATED_STRING"}),
    ('"abc\ndef"', {"UNTERMINATED_STRING"}),
    ('"\\q"', {"INVALID_ESCAPE"}),
    ('"\\x4"', {"INVALID_ESCAPE", "UNTERMINATED_STRING"}),
    ('"\\xGG"', {"INVALID_ESCAPE"}),
    ('"ends with backslash\\', {"UNTERMINATED_STRING", "INVALID_ESCAPE"}),
    ('"\\a"', {"INVALID_ESCAPE"}),
])
def test_string_literals_invalid(src, cats):
    rejects(src + "\n", "lexical", cats, upto="lex")


# ---------------------------------------------------------------- operators / punctuation (§4, §5)
@pytest.mark.parametrize("src,expected", [
    ("+ - * / %", ["+", "-", "*", "/", "%"]),
    ("< > <= >=", ["<", ">", "<=", ">="]),
    ("== !=", ["==", "!="]),
    ("&& || !", ["&&", "||", "!"]),
    ("++ --", ["++", "--"]),
    ("( ) [ ] { } ; ,", ["(", ")", "[", "]", "{", "}", ";", ","]),
    ("<=>", ["<=", ">"]),                    # maximal munch
    ("a<=b", ["a", "<=", "b"]),
    ("a+++b", ["a", "++", "+", "b"]),
    ("a---b", ["a", "--", "-", "b"]),
    ("!==", ["!=", None]) if False else ("!=!", ["!=", "!"]),
    ("a&&b||c", ["a", "&&", "b", "||", "c"]),
    ("x[1][2]", ["x", "[", "1", "]", "[", "2", "]"]),
    ("a>=b>c", ["a", ">=", "b", ">", "c"]),
    ("-5", ["-", "5"]),
    ("a-1", ["a", "-", "1"]),
    ("1+-2", ["1", "+", "-", "2"]),
    ("!!x", ["!", "!", "x"]),
    ("a==b!=c", ["a", "==", "b", "!=", "c"]),
    ("a<b>c", ["a", "<", "b", ">", "c"]),
])
def test_operator_tokenization(src, expected):
    assert lexemes(src) == expected


@pytest.mark.parametrize("ch", list("@#$^~`?:.\\=&|") if False else list("@$^~`?:.\\=&|"))
def test_invalid_characters(ch):
    rejects(f"x {ch} y\n", "lexical", "INVALID_CHARACTER", upto="lex")


def test_assignment_equals_sign_is_not_part_of_the_language():
    rejects("x = 1\n", "lexical", "INVALID_CHARACTER", upto="lex")


def test_non_ascii_byte_outside_literals_is_invalid():
    p = cli("lex", "int \xe9 \n")
    assert p.rc == 1


def test_nul_free_long_program_tokenizes():
    src = "\n".join(f"int v{i}" for i in range(2000)) + "\n"
    assert len(lex(src)) == 4000


def test_error_recovery_reports_multiple_lexical_errors():
    p = cli("lex", "@ int $ x ^\n")
    cats = [d for d in p.diags() if d[0] == "lexical"]
    assert len(cats) >= 3


def test_lexical_error_columns_point_at_the_character():
    p = cli("lex", "ab @ cd\n")
    d = p.diags()[0]
    assert (d[2], d[3]) == (1, 4)


def test_eof_token_is_last_and_unique():
    p = cli("lex", "int x\n", ("--json",))
    toks = json.loads(p.out)["data"]
    assert [t["type"] for t in toks].count("EOF") == 1 and toks[-1]["type"] == "EOF"


def test_token_lexeme_equals_source_slice_and_stays_on_one_line():
    src = "int abc lo 0x1F pettu\n\"str\" 'c' 3.5\n"
    lines = src.split("\n")
    for line, col, ty, lx in lex(src):
        assert lines[line - 1][col - 1: col - 1 + len(lx)] == lx


def test_lex_text_format_line_col_type_lexeme():
    p = cli("lex", "int x\n")
    first = p.text.splitlines()[0]
    assert first.startswith("1:1 ") and first.endswith("'int'")
