@echo off
rem Devara compiler wrapper for Windows: devara <command> [options] <file>
setlocal
set "PYTHONPATH=%~dp0;%PYTHONPATH%"
python -m compiler.cli %*
exit /b %ERRORLEVEL%
