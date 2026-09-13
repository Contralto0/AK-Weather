@echo off
setlocal DisableDelayedExpansion
if defined AK_WEATHER_PYTHON (
    set "python_exe=%AK_WEATHER_PYTHON%"
) else (
    set "python_exe=%~dp0..\..\Software\python-3.14.7\python.exe"
)
if not exist "%python_exe%" (
    echo Fehler: Die portable Python-Laufzeit wurde nicht gefunden. 1>&2
    echo Erwarteter Pfad: "%python_exe%" 1>&2
    echo AK_WEATHER_PYTHON kann auf eine vorhandene portable python.exe zeigen. 1>&2
    set "exit_code=1"
    goto finish
)
"%python_exe%" -I "%~dp0launch.py"
set "exit_code=%ERRORLEVEL%"
:finish
if /I not "%~1"=="--no-pause" pause
exit /b %exit_code%
