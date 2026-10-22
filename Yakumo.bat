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
set "PY="
set "PYW="
set "PROBE=%TEMP%\yakumo-python-%RANDOM%.txt"

rem Every candidate is actually started and checked: py.exe may point to a
rem removed install, and "python" may be the Microsoft Store stub.
rem 1) Embedded Python next to the program (portable build)
call :probe "%~dp0python\python.exe"
rem 2) Project virtual environment
call :probe "%~dp0.venv\Scripts\python.exe"
rem 3) Python Launcher, then python/python3 from PATH
call :probe py -3
call :probe python
call :probe python3
rem 4) Standard install folders
for /d %%i in ("%LOCALAPPDATA%\Programs\Python\Python3*" "%ProgramFiles%\Python3*" "%ProgramFiles(x86)%\Python3*") do call :probe "%%~fi\python.exe"

rem 5) Nothing works: offer to download embedded Python next to the program
if not defined PY call :offer_python
if not defined PY (
    pause
    exit /b 1
)
echo Python: %PY%

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

rem Asks whether to download embedded Python into python\ (launcher\get_python.ps1).
:offer_python
type "%~dp0launcher\no_python.txt"
type "%~dp0launcher\offer_python.txt"
choice /c 12 /n
echo.
if errorlevel 2 goto :eof
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0launcher\get_python.ps1" -Root "%~dp0."
if errorlevel 1 (
    type "%~dp0launcher\download_failed.txt"
    goto :eof
)
call :probe "%~dp0python\python.exe"
if not defined PY type "%~dp0launcher\download_failed.txt"
goto :eof

rem Runs the given command as Python; if it is 3.10+ and works, remembers
rem the real python.exe (and pythonw.exe next to it) in PY and PYW.
:probe
if defined PY goto :eof
del "%PROBE%" >nul 2>nul
%* -X utf8 -c "import sys; sys.version_info >= (3, 10) or sys.exit(1); open(sys.argv[1], 'w', encoding='utf-8').write(sys.executable)" "%PROBE%" >nul 2>nul
if errorlevel 1 goto :eof
if not exist "%PROBE%" goto :eof
set "EXE="
set /p EXE=<"%PROBE%"
del "%PROBE%" >nul 2>nul
if not defined EXE goto :eof
if not exist "%EXE%" goto :eof
set "PY="%EXE%""
set "PYW=%PY%"
for %%i in ("%EXE%") do if exist "%%~dpipythonw.exe" set "PYW="%%~dpipythonw.exe""
goto :eof
