@echo off
setlocal DisableDelayedExpansion
if defined AK_WEATHER_PYTHON (
    set "python_exe=%AK_WEATHER_PYTHON%"
    goto check_runtime
)
set "runtime_root=%~dp0..\..\Software"
set "python_exe=%~dp0..\..\Software\python-3.14.7\python.exe"
if exist "%python_exe%" goto run
if not exist "%~dp0bootstrap\Initialize-PythonRuntime.ps1" (
    echo Fehler: Der Repository-Bootstrapper wurde nicht gefunden. 1>&2
    set "exit_code=1"
    goto finish
)
if not exist "%runtime_root%" mkdir "%runtime_root%"
if not exist "%runtime_root%" (
    echo Fehler: Der globale Softwareordner konnte nicht angelegt werden. 1>&2
    set "exit_code=1"
    goto finish
)
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -NonInteractive -ExecutionPolicy RemoteSigned -File "%~dp0bootstrap\Initialize-PythonRuntime.ps1" -RuntimeRootPath "%runtime_root%"
if errorlevel 1 goto bootstrap_failed

:check_runtime
if not exist "%python_exe%" (
    echo Fehler: Die portable Python-Laufzeit wurde nicht gefunden. 1>&2
    echo Erwarteter Pfad: "%python_exe%" 1>&2
    echo AK_WEATHER_PYTHON kann auf eine vorhandene portable python.exe zeigen. 1>&2
    set "exit_code=1"
    goto finish
)
:run
"%python_exe%" -I "%~dp0launch.py"
set "exit_code=%ERRORLEVEL%"
goto finish
:bootstrap_failed
set "exit_code=%ERRORLEVEL%"
echo Fehler: Die portable Python-Laufzeit konnte nicht bereitgestellt werden. 1>&2
:finish
if /I not "%~1"=="--no-pause" pause
exit /b %exit_code%
