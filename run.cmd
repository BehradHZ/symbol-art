@echo off
setlocal

set "PYTHON=%~dp0.venv\Scripts\python.exe"
set "PYTHON_ARGS="
if exist "%PYTHON%" goto :run

where py >nul 2>&1
if not errorlevel 1 (
    set "PYTHON=py"
    set "PYTHON_ARGS=-3"
    goto :check
)

where python >nul 2>&1
if not errorlevel 1 (
    set "PYTHON=python"
    goto :check
)

echo Python 3.10+ was not found.
exit /b 1

:check
"%PYTHON%" %PYTHON_ARGS% -c "import PIL, numpy" >nul 2>&1
if errorlevel 1 (
    echo Missing dependencies.
    echo Run: "%PYTHON%" %PYTHON_ARGS% -m pip install -r "%~dp0requirements.txt"
    exit /b 1
)

:run
if "%~1"=="" (
    "%PYTHON%" %PYTHON_ARGS% "%~dp0symbol_art.py" "%~dp0examples\behrad-input.jpg"
) else (
    "%PYTHON%" %PYTHON_ARGS% "%~dp0symbol_art.py" %*
)
exit /b %errorlevel%
