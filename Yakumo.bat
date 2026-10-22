@echo off
rem Yakumo launcher for Windows. Arguments are passed to the core:
rem   Yakumo.bat --info
rem   Yakumo.bat --lan --port 9000
rem   Yakumo.bat --hidden        (no console window, control via tray icon)
rem
rem Keep this file ASCII-only: cmd.exe parses .bat files in the console code
rem page, so Cyrillic here breaks commands. Russian messages live in
rem launcher\*.txt (UTF-8) and are printed with "type" after chcp 65001.
setlocal
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

rem 1) Embedded Python next to the program (portable build)
if exist "%~dp0python\python.exe" (
    set "PY="%~dp0python\python.exe""
    set "PYW="%~dp0python\pythonw.exe""
    goto run
)
rem 2) Project virtual environment
if exist "%~dp0.venv\Scripts\python.exe" (
    set "PY="%~dp0.venv\Scripts\python.exe""
    set "PYW="%~dp0.venv\Scripts\pythonw.exe""
    goto run
)
rem 3) Python Launcher
where py >nul 2>nul
if not errorlevel 1 (
    set "PY=py -3"
    set "PYW=pyw -3"
    goto run
)
rem 4) python from PATH
where python >nul 2>nul
if not errorlevel 1 (
    set "PY=python"
    set "PYW=pythonw"
    goto run
)

type "%~dp0launcher\no_python.txt"
pause
exit /b 1

:run
rem -X utf8: UTF-8 mode even for embedded Python, which ignores environment variables.
%PY% -X utf8 -c "import sys; sys.exit(sys.version_info < (3, 10))"
if errorlevel 1 (
    type "%~dp0launcher\old_python.txt"
    pause
    exit /b 1
)

if /i "%~1"=="--hidden" (
    shift
    goto hidden
)

%PY% -X utf8 -m yakumo %*
set "CODE=%errorlevel%"
if not "%CODE%"=="0" (
    echo.
    echo [%CODE%]
    type "%~dp0launcher\failed.txt"
    pause
)
endlocal & exit /b %CODE%

:hidden
rem %* ignores shift, so collect the remaining arguments by hand.
set "ARGS="
:collect
if "%~1"=="" goto launch
set ARGS=%ARGS% %1
shift
goto collect
:launch
start "" %PYW% -X utf8 -m yakumo%ARGS%
endlocal & exit /b 0
