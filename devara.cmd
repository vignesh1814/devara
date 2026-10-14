@echo off
rem Devara compiler wrapper for Windows: devara <command> [options] <file>
rem Set DEVARA_PYTHON to a python.exe to use instead of the first "python" on PATH. pyenv-win's python.bat
rem shim discards a redirected stdin (devara run prog.tel < input.txt), a real python.exe does not.
setlocal
set "PYTHONPATH=%~dp0;%PYTHONPATH%"
if defined DEVARA_PYTHON (
    "%DEVARA_PYTHON%" -m compiler.cli %*
) else (
    python -m compiler.cli %*
)
exit /b %ERRORLEVEL%
