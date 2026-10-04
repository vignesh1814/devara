"""Compatibility shim: use ``./devara`` or ``python3 -m compiler.cli``."""

from compiler.cli import run_main

if __name__ == "__main__":
    run_main()
