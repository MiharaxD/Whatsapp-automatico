@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title Agenda de contatos
set "agenda_python="
set "agenda_python_args="
for /f "delims=" %%P in ('"%SystemRoot%\System32\where.exe" python.exe 2^>nul') do call :try_python "%%P"
if defined agenda_python goto run
for /f "delims=" %%P in ('"%SystemRoot%\System32\where.exe" py.exe 2^>nul') do call :try_py "%%P"
if defined agenda_python goto run
for /d %%D in ("%LOCALAPPDATA%\Python\pythoncore-*") do call :try_python "%%D\python.exe"
for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python*") do call :try_python "%%D\python.exe"
if defined agenda_python goto run
call :try_python "%LOCALAPPDATA%\Microsoft\WindowsApps\python.exe"
if defined agenda_python goto run
call :try_py "%LOCALAPPDATA%\Microsoft\WindowsApps\py.exe"
if defined agenda_python goto run
:missing
echo Não consegui iniciar uma instalação de Python 3.10 ou mais recente.
echo Se você já tem Python, confira se a instalação ainda abre normalmente.
echo Se não tem, instale em https://www.python.org/downloads/
pause
exit /b 1
:run
"%agenda_python%" %agenda_python_args% "%~dp0app.py" %*
set "agenda_exit=%errorlevel%"
if not "%agenda_exit%"=="0" pause
exit /b %agenda_exit%
:try_python
if defined agenda_python exit /b 0
if not exist "%~1" exit /b 0
"%~1" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if errorlevel 1 exit /b 0
set "agenda_python=%~1"
exit /b 0
:try_py
if defined agenda_python exit /b 0
if not exist "%~1" exit /b 0
"%~1" -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if errorlevel 1 exit /b 0
set "agenda_python=%~1"
set "agenda_python_args=-3"
exit /b 0
