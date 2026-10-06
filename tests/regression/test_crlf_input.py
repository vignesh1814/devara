"""Input handling treats CRLF like LF on every platform (strip a CR before LF in line reads)."""

from pathlib import Path

from tests.helpers.native import build_and_run

CORPUS = Path(__file__).parent.parent / "corpus" / "misc"


def test_crlf_input_matches_lf_input():
    tel = CORPUS / "108_input_kinds.tel"
    src = tel.read_bytes().decode("latin-1")
    lf = tel.with_suffix(".in").read_bytes().replace(b"\r\n", b"\n")   # a CRLF checkout must not matter
    crlf = lf.replace(b"\n", b"\r\n")
    out_lf, rc_lf, _ = build_and_run(src, lf)
    out_crlf, rc_crlf, _ = build_and_run(src, crlf)
    assert (out_crlf, rc_crlf) == (out_lf, rc_lf) == (tel.with_suffix(".out").read_bytes(), 0)


def test_crlf_line_read_has_no_carriage_return():
    src = "padham s\ns ni chaduvu\ns ni chupi\n(s == \"hi\") ni chupi\n"
    out, rc, _ = build_and_run(src, b"hi\r\n")
    assert rc == 0 and out == b"hi\nnijam\n"
