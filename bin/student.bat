@echo off
rem PATH-friendly wrapper around student.py. Uses embedded python when present.
setlocal
set "HERE=%~dp0"
set "PY=%HERE%..\python\python.exe"
if not exist "%PY%" set "PY=python"
"%PY%" "%HERE%student.py" %*
endlocal
