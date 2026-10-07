"""Audit F14: the Windows-target tests retry a run only when wine itself lost its server connection."""

from tests.validation.stress_util import Out, is_wine_transport_error


def test_wine_connection_reset_is_recognised():
    assert is_wine_transport_error(Out(1, b"", "wine: could not load kernel32.dll, status c0000135\nConnection reset by peer\n"))
    assert is_wine_transport_error(Out(1, b"", "err:ntdll:server_connect failed: Connection reset by peer"))


def test_program_results_and_diagnostics_are_never_retried():
    assert not is_wine_transport_error(Out(0, b"3\n", ""))                                       # success
    assert not is_wine_transport_error(Out(1, b"", "devara: runtime error: division by zero\n"))  # a program error
    assert not is_wine_transport_error(Out(2, b"", "x.tel:1:1: syntax error [UNEXPECTED_TOKEN]: ...\n"))
    assert not is_wine_transport_error(Out(1, b"", ""))                                           # silent failure: real
    assert not is_wine_transport_error(Out(0, b"", "Connection reset by peer"))                   # exited 0: not a failure
