@echo off
rem Запуск Yakumo на Windows. Аргументы передаются ядру, например:
rem   Yakumo.bat --info
rem   Yakumo.bat --lan --port 9000
setlocal
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

rem 1) Встроенный Python рядом с программой (портативный режим)
if exist "%~dp0python\python.exe" (
    set "PY=%~dp0python\python.exe"
    goto run
)
rem 2) Виртуальное окружение проекта
if exist "%~dp0.venv\Scripts\python.exe" (
    set "PY=%~dp0.venv\Scripts\python.exe"
    goto run
)
rem 3) Python Launcher
where py >nul 2>nul
if not errorlevel 1 (
    set "PY=py -3"
    goto run
)
rem 4) python из PATH
where python >nul 2>nul
if not errorlevel 1 (
    set "PY=python"
    goto run
)

echo Python 3.10+ не найден. Установите его с https://www.python.org/downloads/
echo и отметьте "Add python.exe to PATH".
pause
exit /b 1

:run
%PY% -c "import sys; sys.exit(sys.version_info < (3, 10))"
if errorlevel 1 (
    echo Нужен Python 3.10 или новее.
    pause
    exit /b 1
)
%PY% -m yakumo %*
set "CODE=%errorlevel%"
if not "%CODE%"=="0" (
    echo.
    echo Yakumo завершился с кодом %CODE%.
    pause
)
endlocal & exit /b %CODE%
